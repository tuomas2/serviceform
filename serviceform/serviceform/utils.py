# -*- coding: utf-8 -*-
# (c) 2017 Tuomas Airaksinen
#
# This file is part of Serviceform.
#
# Serviceform is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Serviceform is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Serviceform.  If not, see <http://www.gnu.org/licenses/>.


import re
import signal
import uuid
import random
import string
import logging
from functools import wraps
from itertools import chain
from typing import Optional, TYPE_CHECKING, Iterable, Union

from django.core.serializers import serialize, deserialize
from django.db.models import Model

if TYPE_CHECKING:
    from .models import ServiceForm, Participation, Member
    from .models.serviceform import AbstractServiceFormItem

from django.contrib import messages
from django.core.cache import caches, BaseCache
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.utils.safestring import mark_safe

from collections import defaultdict

from colour import Color
from django.core.exceptions import PermissionDenied
from django.utils.translation import ugettext_lazy as _
from django.utils import translation
from django.conf import settings


logger = logging.getLogger(__name__)


class DelayedKeyboardInterrupt(object):
    def __init__(self):
        self.will_interrupt = False
        signal.signal(signal.SIGINT, self.handler)

    def __enter__(self):
        return self

    def handler(self, signum, frame):
        self.will_interrupt = True

    def __exit__(self, type, value, traceback):
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        if self.will_interrupt:
            raise KeyboardInterrupt()


def _get_ident(request: HttpRequest) -> str:
    service_form = getattr(request, 'service_form', '')
    if not service_form:
        logger.error('No serviceform in _get_ident!?')

    if request.user.pk:
        ident = 'user_%s' % request.user.pk
    else:
        resp = get_authenticated_member(request)
        ident = 'responsible_%s' % resp.pk if resp else 'anonymous'
        service_form = resp.form if resp else None

    return f"{ident}_serviceform_{getattr(service_form, 'pk', '')}"


class RevisionOptions:
    CURRENT = '__current'
    ALL = '__all'


settings_defaults = {'revision': RevisionOptions.CURRENT}


def get_report_settings(request: HttpRequest, parameter: str=None) -> Union[dict, str]:
    cache = caches['persistent']
    report_settings = cache.get('settings_for_%s' % _get_ident(request), settings_defaults.copy())
    if parameter:
        return report_settings.get(parameter)
    return report_settings


def set_report_settings(request: HttpRequest, report_settings: dict) -> None:
    cache = caches['persistent']
    cache.set('settings_for_%s' % _get_ident(request), report_settings)


def user_has_serviceform_permission(user: settings.AUTH_USER_MODEL, service_form: 'ServiceForm',
                                    raise_permissiondenied: bool=True):
    if user.has_perm('serviceform.can_access_serviceform', service_form):
        return True
    else:
        if raise_permissiondenied:
            raise PermissionDenied(_('User is not allowed to access document'))
        else:
            return False


_participants = {}


def get_participant(_id: int) -> 'Participation':
    p = _participants.get(_id)
    if p is None:
        logger.error('Participation %d was not in cache!', _id)
    return p


def fetch_participants(service_form: 'ServiceForm', revision_name: str) -> None:
    global _participants
    from .models import Participation
    is_all_revisions = revision_name == RevisionOptions.ALL
    is_current_revision = revision_name == RevisionOptions.CURRENT

    qs = Participation.objects.prefetch_related('participantlog_set__written_by')
    if is_all_revisions:
        qs = qs.select_related('form_revision')
        participants = qs.filter(form_revision__form=service_form).distinct()
    elif is_current_revision:
        participants = qs.filter(form_revision=service_form.current_revision)
    else:
        participants = qs.filter(form_revision__name=revision_name)

    _participants = {itm.pk: itm for itm in participants}
    return


class ClearParticipantCacheMiddleware:
    def process_request(self, request: HttpRequest):
        _participants.clear()
        _responsible_counts.clear()


class InvalidateCachalotAfterEachRequestMiddleware(object):
    """
    This middleware clears the cachalot cache at the end of every request.
    """

    def process_exception(self, request: HttpRequest, exception: Exception):
        if 'cachalot' in settings.INSTALLED_APPS:
            cachalot_cache = settings.CACHALOT_CACHE
            caches[cachalot_cache].clear()

    def process_response(self, request: HttpRequest, response: HttpResponse):
        if 'cachalot' in settings.INSTALLED_APPS:
            cachalot_cache = settings.CACHALOT_CACHE
            caches[cachalot_cache].clear()
        return response

_responsible_counts = defaultdict(int)


def init_serviceform_counters(service_form: 'ServiceForm', all_responsibles: bool=True) -> None:
    """
    Initializes counters and collects responsibles from subitems

    :return:
    """
    activity_count = 0
    cat1_counter = 0
    _responsible_counts.clear()

    def _add_responsible(responsibles: 'Iterable[Member]',
                         *targets: 'AbstractServiceFormItem',
                         resp_count: bool=False) -> None:
        if resp_count:
            for r in {resp for target in targets for resp in target.responsibles.all() if resp}:
                _responsible_counts[r.pk] += 1
        for resp in responsibles:
            for t in targets:
                t._responsibles.add(resp)

    for cat1 in service_form.sub_items:
        cat2_counter = 0
        cat1._counter = cat1_counter
        cat1_counter += 1
        cat1._responsibles = set(cat1.responsibles.all())
        for cat2 in cat1.sub_items:
            cat2._counter = cat2_counter
            cat2_counter += 1
            _add_responsible(cat2.responsibles.all(), cat1, cat2)
            if all_responsibles:
                cat2._responsibles.update(set(cat1.responsibles.all()))
            for activity in cat2.sub_items:
                if not activity.skip_numbering:
                    activity_count += 1
                activity._counter = activity_count

                choice_counter = 0
                _add_responsible(activity.responsibles.all(), cat1, cat2, activity,
                                 resp_count=True)
                if all_responsibles:
                    activity._responsibles.update(
                        set(cat1.responsibles.all()) | set(cat2.responsibles.all()))
                for choice in activity.sub_items:
                    if not choice.skip_numbering:
                        choice_counter += 1
                    choice._counter = choice_counter
                    _add_responsible(choice.responsibles.all(), cat1, cat2, activity, choice,
                                     resp_count=True)
                    if all_responsibles:
                        choice._responsibles.update(set(activity.responsibles.all()) |
                                                    set(cat1.responsibles.all()) |
                                                    set(cat2.responsibles.all()))


def shuffle_person_data(service_form: 'ServiceForm') -> None:
    from .models import Participation, Member, Question
    letters = len(string.ascii_letters)
    forenames = set()
    surnames = set()
    participants = Participation.objects.filter(form_revision__form=service_form)
    responsibles = Member.objects.filter(form=service_form)
    for p in chain(participants, responsibles):
        for n in p.forenames.split(' '):
            if n:
                forenames.add(n.title())
        for n in p.surname.split('-'):
            if n:
                surnames.add(n.title())

    def shuffle(m, *attrs):
        for a in attrs:
            old = getattr(m, a)
            if old:
                new = [string.ascii_letters[random.randrange(0, letters)] for i in range(len(old))]
                for i in range(len(old)):
                    if old[i] in '@ .,':
                        new[i] = old[i]
                setattr(m, a, ''.join(new))
        m.save()

    def shuffle_question(q):
        if q.question.answer_type in [Question.ANSWER_LONG_TEXT,
                                      Question.ANSWER_SHORT_TEXT]:
            shuffle(q, 'answer')

    forenames = tuple(forenames)
    surnames = tuple(surnames)

    def valid_email(s):
        return re.sub('[^a-zA-Z@\.-]', '', s)

    def shuffle_contact_details(p):
        p.forenames = ' '.join(
            forenames[random.randrange(0, len(forenames))] for i in range(random.randint(1, 2)))
        p.surname = '-'.join(
            surnames[random.randrange(0, len(surnames))] for i in range(random.randint(1, 2)))
        if p.email:
            p.email = valid_email(
                '%s.%s@email.com' % (p.forenames.replace(' ', '.').lower(), p.surname.lower()))
        if p.street_address:
            p.street_address = 'Kontaktikatu %d' % random.randint(0, 99)
        if p.postal_code:
            p.postal_code = ''.join('%s' % random.randint(0, 9) for i in range(5))
        if p.phone_number:
            p.phone_number = ''.join('%s' % random.randint(0, 9) for i in range(9))
        if p.city:
            p.city = 'Hemilä'
        p.save()

    for p in chain(participants, responsibles):
        shuffle_contact_details(p)

    for p in participants:
        for a in p.activities:
            shuffle(a, 'additional_info')
            for c in a.choices:
                shuffle(c, 'additional_info')
        for q in p.questions:
            shuffle_question(q)


def count_for_responsible(resp: 'Member') -> int:
    return _responsible_counts[resp.pk]


def generate_uuid() -> str:
    return str(uuid.uuid4())


# TODO: move to color_utils

ColorStr = str  # TODO: Type validation against RGB_REGEX.pattern?


def darker_color(color: ColorStr) -> ColorStr:
    c = Color(color)
    h, s, l = c.get_hsl()
    l_new = l * 0.75  # l - (1.0-l)*0.5
    c.set_hsl((h, s, l_new))
    return c.get_hex()


def lighter_color(color: ColorStr) -> ColorStr:
    c = Color(color)
    h, s, l = c.get_hsl()
    l_new = l + (1.0 - l) * 0.5
    c.set_hsl((h, s, l_new))
    return c.get_hex()


def not_black(color: ColorStr) -> Optional[ColorStr]:
    return color if color != '#000000' else None


def color_for_count(count: int) -> ColorStr:
    if not count:
        return Color('white').get_hex()
    c = Color('green')
    max = 10
    count_real = min(max, count)
    c.hue = (max - count_real) / max * 0.33
    c.saturation = 1.0
    c.luminance = 0.7
    return c.get_hex()


def update_serviceform_default_emails() -> None:
    from .models import ServiceForm
    translation.activate('fi')
    for s in ServiceForm.objects.all():
        s.create_email_templates()


def safe_join(sep: str, args_generator: Iterable[str]):
    sep = mark_safe(sep)
    result = mark_safe('')
    args = list(args_generator)
    for a in args[:-1]:
        result += a
        result += sep
    result += args[-1]
    return result


def expire_auth_link(request: HttpRequest, obj: 'Member') -> HttpResponse:
    obj.resend_auth_link()
    messages.info(request,
                  _('Your authentication URL was expired. New link has been sent to {}').format(
                      obj.email))
    # TODO: organization_main page
    return redirect('organization_main', obj.organization_id)


def encode(number: int) -> str:
    letters = settings.CODE_LETTERS
    result = ''.join(reversed('%o' % (100000 + number)))
    for ii in range(0, 9, 2):
        result = result.replace(str(ii), letters[ii // 2], 1)
    return result


def decode(number: str) -> Optional[int]:
    letters = settings.CODE_LETTERS
    if number is None:
        return None
    for ii in range(0, 9, 2):
        number = number.replace(letters[ii // 2], str(ii))
    try:
        result = int(''.join(reversed(number)), 8)
    except ValueError:
        return None
    result -= 100000
    if result < 0:
        result = None
    return result


def django_cache(key, cache_name='default'):
    """
    Decorator that caches list of django models into Django cache.
    
    Decorated function must return an iterable of django models.
    
    """
    cache: BaseCache = caches[cache_name]

    def decorator(fn):
        @wraps(fn)
        def wrapper(obj: Model, *args, **kwargs) -> Iterable[Model]:
            cache_key = f'{obj.__class__.__name__}_{obj.pk}_{key}'
            result_json = cache.get(cache_key)

            if result_json:
                result = (i.object for i in deserialize('json', result_json))
            else:
                result = fn(obj, *args, **kwargs)
                cache.set(cache_key, serialize('json', result))

            return result
        return wrapper

    return decorator


def invalidate_cache(obj, key, cache_name='default'):
    cache: BaseCache = caches[cache_name]
    cache_key = f'{obj.__class__.__name__}_{obj.pk}_{key}'
    cache.delete(cache_key)

def clean_session(request: HttpRequest):
    keys = ['max_category', 'serviceform_pk', 'authenticated_member', 'verification_sent']
    for key in keys:
        request.session.pop(key, None)
        # request.session.clear()


## TODO: create authentication module and move these there.
#def mark_as_authenticated_participant(request: HttpRequest,
#                                      participation: 'Participation') -> None:
#    request.session['authenticated_participant'] = participation.pk


#def get_authenticated_participant(request: HttpRequest) -> 'Optional[Participation]':
#    # TODO: remove participant-only authentication, or rename to active participation etc.
#    from .models import Participation
#    participant_pk = request.session.get('authenticated_participant')
#    return participant_pk and Participation.objects.get(pk=participant_pk)


def get_authenticated_member(request: HttpRequest) -> 'Optional[Member]':
    # TODO check that this is being used everywhere
    from .models import Member
    member_pk = request.session.get('authenticated_member')
    return member_pk and Member.objects.get(pk=member_pk)


def mark_as_authenticated_member(request: HttpRequest, member: 'Member') -> None:
    request.session['authenticated_member'] = member.pk


def authenticate_to_serviceform(request: HttpRequest, serviceform: 'ServiceForm') -> None:
    request.session['serviceform_pk'] = serviceform.pk


def get_authenticated_serviceform(request: HttpRequest):
    from .models import ServiceForm
    serviceform_pk = request.session.get('serviceform_pk')
    # TODO: if None -> crash? Should it be 404 then or something?
    return ServiceForm.objects.get(pk=serviceform_pk)


def is_serviceform_password_authenticated(request: HttpRequest, serviceform: 'ServiceForm') -> bool:
    serviceform_pk = request.session.get('serviceform_pk')
    return serviceform_pk == serviceform.pk