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
from enum import Enum
from typing import Union, Iterator, Tuple, Optional, List, Sequence, TYPE_CHECKING

from django.conf import settings
from django.contrib import messages
from django.db import models
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import localize
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from .. import utils
from .mixins import PasswordMixin, ContactDetailsMixin, postalcode_regex, phone_regex
from .email import EmailMessage

if TYPE_CHECKING:
    from .participation import ParticipationActivity, QuestionAnswer, ParticipantLog
    from .serviceform import ServiceForm


class Organization(models.Model):
    name = models.CharField(_('Organization name'), max_length=64)


class Member(PasswordMixin, models.Model):

    MEMBER_EXTERNAL = 'external'
    MEMBER_NORMAL = 'normal'
    MEMBER_STAFF = 'staff'
    MEMBERSHIP_CHOICES = (
        (MEMBER_EXTERNAL, _('external')),
        (MEMBER_NORMAL, _('normal')),
        (MEMBER_STAFF, _('staff'))
    )


    forenames = models.CharField(max_length=64, verbose_name=_('Forename(s)'))
    surname = models.CharField(max_length=64, verbose_name=_('Surname'))
    street_address = models.CharField(max_length=128, blank=True,
                                      verbose_name=_('Street address'))
    postal_code = models.CharField(max_length=32, blank=True,
                                   verbose_name=_('Zip/Postal code'),
                                   validators=[postalcode_regex])
    city = models.CharField(max_length=32, blank=True, verbose_name=_('City'))

    year_of_birth = models.SmallIntegerField(_('Year of birth'), null=True, blank=True)

    # TODO: set unique constraint
    email = models.EmailField(blank=True, verbose_name=_('Email'), db_index=True)
    email_verified = models.BooleanField(_('Email verified'), default=False)

    phone_number = models.CharField(max_length=32, validators=[phone_regex], blank=True,
                                    verbose_name=_('Phone number'))

    membership_type = models.CharField(_('Is this person a member of this organization?'),
                                       max_length=8,
                                       choices=MEMBERSHIP_CHOICES,
                                       default=MEMBER_EXTERNAL)

    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)

    # TODO: this might not be appropriate there any more
    AUTH_VIEW = 'authenticate_responsible_new'

    # TODO: rename allow_send_email ?
    send_email_notifications = models.BooleanField(
        default=True,
        verbose_name=_('Send email notifications'),
        help_text=_(
            'Send email notifications whenever new participation to administered activities is '
            'registered. Email contains also has a link that allows accessing raport of '
            'administered activities.'))

    # TODO: rename: allow_showing_contact_details_in_forms
    hide_contact_details = models.BooleanField(_('Hide contact details in form'), default=False)
    show_full_report = models.BooleanField(_('Grant access to full reports'), default=False)

    def __str__(self):
        if self.forenames or self.surname:
            return '%s %s' % (self.forenames.title(), self.surname.title())
        else:
            return self.email

    @property
    def address(self):
        return ('%s\n%s %s' % (
            self.street_address.title(), self.postal_code, self.city.title())).strip()


    @property
    def contact_details(self):
        yield _('Name'), '%s %s' % (self.forenames.title(), self.surname.title())
        if self.email:
            yield _('Email'), self.email
        if self.phone_number:
            yield _('Phone number'), self.phone_number
        if self.address:
            yield _('Address'), '\n' + self.address

    @property
    def contact_display(self):
        return '\n'.join('%s: %s' % (k, v) for k, v in self.contact_details)

    @cached_property
    def item_count(self) -> int:
        return utils.count_for_responsible(self)

    def personal_link(self) -> str:
        return format_html('<a href="{}">{}</a>',
                           reverse('authenticate_responsible_mock', args=(self.pk,)),
                           self.pk) if self.pk else ''

    personal_link.short_description = _('Link to personal report')

    @property
    def secret_id(self) -> str:
        return utils.encode(self.id)

    # TODO: common unsubscribe
    @property
    def list_unsubscribe_link(self) -> str:
        return settings.SERVER_URL + reverse('unsubscribe_responsible', args=(self.secret_id,))

    def resend_auth_link(self) -> 'EmailMessage':
        # TODO
        raise NotImplementedError
        context = {'responsible': str(self),
                   'form': str(self.form),
                   'url': self.make_new_auth_url(),
                   'contact': self.form.responsible.contact_display,
                   'list_unsubscribe': self.list_unsubscribe_link,
                   }
        return EmailMessage.make(self.form.email_to_responsible_auth_link, context, self.email)

    def send_responsibility_email(self, participant: 'Participation') -> None:
        # TODO
        raise NotImplementedError
        if self.send_email_notifications:
            context = {'responsible': str(self),
                       'participant': str(participant),
                       'form': str(self.form),
                       'url': self.make_new_auth_url(),
                       'contact': self.form.responsible.contact_display,
                       'list_unsubscribe': self.list_unsubscribe_link,
                       }

            EmailMessage.make(self.form.email_to_responsibles, context, self.email)

    def send_bulk_mail(self) -> 'Optional[EmailMessage]':
        #TODO
        raise NotImplementedError
        if self.send_email_notifications:
            context = {'responsible': str(self),
                       'form': str(self.form),
                       'url': self.make_new_auth_url(),
                       'contact': self.form.responsible.contact_display,
                       'list_unsubscribe': self.list_unsubscribe_link,
                       }
            return EmailMessage.make(self.form.bulk_email_to_responsibles, context, self.email)



class Participation(PasswordMixin, models.Model):
    class Meta:
        verbose_name = _('Participation')
        verbose_name_plural = _('Participants')

    # Current view is set by view decorator require_authenticated_participant
    _current_view = 'contact_details'
    AUTH_VIEW = 'authenticate_participant_new'

    class EmailIds(Enum):
        ON_FINISH = object()
        ON_UPDATE = object()
        NEW_FORM_REVISION = object()
        RESEND = object()
        INVITE = object()
        EMAIL_VERIFICATION = object()

    SEND_ALWAYS_EMAILS = [EmailIds.RESEND,
                          EmailIds.EMAIL_VERIFICATION,
                          EmailIds.ON_FINISH,
                          EmailIds.ON_UPDATE]

    STATUS_INVITED = 'invited'
    STATUS_ONGOING = 'ongoing'
    STATUS_UPDATING = 'updating'
    STATUS_FINISHED = 'finished'
    READY_STATUSES = (STATUS_UPDATING, STATUS_FINISHED)
    EDIT_STATUSES = (STATUS_UPDATING, STATUS_ONGOING)

    STATUS_CHOICES = (
        (STATUS_INVITED, _('invited')),
        (STATUS_ONGOING, _('ongoing')),
        (STATUS_UPDATING, _('updating')),
        (STATUS_FINISHED, _('finished')))
    STATUS_DICT = dict(STATUS_CHOICES)

    member = models.ForeignKey(Member, on_delete=models.CASCADE)
    #year_of_birth = models.SmallIntegerField(_('Year of birth'), null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ONGOING)
    last_finished_view = models.CharField(max_length=32, default='')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    last_modified = models.DateTimeField(auto_now=True, verbose_name=_('Last modified'))
    last_finished = models.DateTimeField(_('Last finished'), null=True)

    # Last form revision
    form_revision = models.ForeignKey('serviceform.FormRevision', null=True,
                                      on_delete=models.CASCADE)

    #email_verified = models.BooleanField(_('Email verified'), default=False)

    send_email_allowed = models.BooleanField(_('Sending email allowed'), default=True, help_text=_(
        'You will receive email that contains a link that allows later modification of the form. '
        'Also when new version of form is published, you will be notified. '
        'It is highly recommended that you keep this enabled unless you move away '
        'and do not want to participate at all any more. You can also change this setting later '
        'if you wish.'))

    @cached_property
    def age(self) -> Union[int, 'str']:
        return timezone.now().year - self.year_of_birth if self.year_of_birth else '-'

    @property
    def is_updating(self) -> bool:
        return self.status == self.STATUS_UPDATING

    @property
    def contact_details(self) -> Iterator[str]:
        yield from super().contact_details
        yield _('Year of birth'), self.year_of_birth or '-'

    @property
    def additional_data(self) -> Iterator[Tuple[str, str]]:
        yield _('Participation created in system'), self.created_at
        yield _('Last finished'), self.last_finished
        yield _('Last modified'), self.last_modified
        yield _('Email address verified'), (_('No'), _('Yes'))[self.email_verified]
        yield _('Emails allowed'), (_('No'), _('Yes'))[self.send_email_allowed]
        yield _('Form status'), self.STATUS_DICT[self.status]

    @cached_property
    def item_count(self) -> int:
        from .participation import ParticipationActivityChoice
        choices = ParticipationActivityChoice.objects.filter(
            activity__participant=self).values_list('activity_id', flat=True)
        choice_count = len(choices)
        activity_count = self.participationactivity_set.exclude(pk__in=choices).count()
        return activity_count + choice_count

    def make_new_verification_url(self) -> str:
        return settings.SERVER_URL + reverse('verify_email',
                                             args=(self.pk, self.make_new_password()))

    @cached_property
    def activities(self) -> 'Sequence[ParticipationActivity]':
        return self.participationactivity_set.select_related('activity')

    @cached_property
    def questions(self) -> 'Sequence[QuestionAnswer]':
        return self.questionanswer_set.select_related('question')

    def activities_display(self) -> str:
        return ', '.join(a.activity.name for a in self.activities)

    activities_display.short_description = _('Activities')

    @cached_property
    def form(self) -> 'ServiceForm':
        return self.form_revision.form if self.form_revision else None

    def form_display(self) -> str:
        return str(self.form)

    form_display.short_description = _('Form')

    def personal_link(self) -> str:
        return format_html('<a href="{}">{}</a>',
                           reverse('authenticate_participant_mock', args=(self.pk,)),
                           self.pk)

    personal_link.short_description = _('Link to personal report')

    @property
    def secret_id(self) -> str:
        return utils.encode(self.id)

    @property
    def list_unsubscribe_link(self) -> str:
        return settings.SERVER_URL + reverse('unsubscribe_participant', args=(self.secret_id,))

    def send_email_to_responsibles(self) -> None:
        """
        Go through choices, activities, their categories and send email to responsibles.

        :return:
        """
        responsibles = set()

        for pa in self.activities:
            if self.last_finished is None or pa.created_at > self.last_finished:
                responsibles.update(set(pa.activity.responsibles.all()) |
                                    set(pa.activity.category.responsibles.all()) |
                                    set(pa.activity.category.category.responsibles.all()))
            for pc in pa.choices:
                if self.last_finished is None or pc.created_at > self.last_finished:
                    responsibles.update(set(pc.activity_choice.responsibles.all()))

        for q in self.questionanswer_set.all():
            if self.last_finished is None or q.created_at > self.last_finished:
                responsibles.update(set(q.question.responsibles.all()))

        for r in responsibles:
            r.send_responsibility_email(self)

    def finish(self, email_participant: bool=True) -> None:
        updating = self.status == self.STATUS_UPDATING
        self.status = self.STATUS_FINISHED
        if timezone.now() > self.form_revision.send_emails_after:
            self.send_email_to_responsibles()
        if email_participant:
            self.send_participant_email(
                self.EmailIds.ON_UPDATE if updating else self.EmailIds.ON_FINISH)
        self.last_finished = timezone.now()
        self.save(update_fields=['status', 'last_finished'])

    def send_participant_email(self, event: EmailIds,
                               extra_context: dict=None) -> 'Optional[EmailMessage]':
        """
        Send email to participant
        :return: False if email was not sent. Message if it was sent.
        """
        if not self.send_email_allowed and event not in self.SEND_ALWAYS_EMAILS:
            return

        self.form.create_email_templates()

        emailtemplates = {self.EmailIds.ON_FINISH: self.form.email_to_participant,
                          self.EmailIds.ON_UPDATE: self.form.email_to_participant_on_update,
                          self.EmailIds.NEW_FORM_REVISION: self.form.email_to_former_participants,
                          self.EmailIds.RESEND: self.form.resend_email_to_participant,
                          self.EmailIds.INVITE: self.form.email_to_invited_users,
                          self.EmailIds.EMAIL_VERIFICATION:
                              self.form.verification_email_to_participant,
                          }

        emailtemplate = emailtemplates[event]
        url = (self.make_new_verification_url()
               if event == self.EmailIds.EMAIL_VERIFICATION
               else self.make_new_auth_url())
        context = {
            'participant': str(self),
            'contact': self.form.responsible.contact_display,
            'form': str(self.form),
            'url': str(url),
            'last_modified': localize(self.last_modified, use_l10n=True),
            'list_unsubscribe': self.list_unsubscribe_link,
        }
        if extra_context:
            context.update(extra_context)
        return EmailMessage.make(emailtemplate, context, self.email)

    def resend_auth_link(self) -> 'Optional[EmailMessage]':
        return self.send_participant_email(self.EmailIds.RESEND)

    @property
    def flow(self) -> List[str]:
        from ..urls import participant_flow_urls

        rv = [i.name for i in participant_flow_urls]
        if not self.form.questions:
            rv.remove('questions')
        if not self.form.require_email_verification or self.email_verified:
            rv.remove('email_verification')
        if self.form.require_email_verification and not self.email:
            rv.remove('email_verification')
        if not self.form.is_published:
            rv = ['contact_details', 'submitted']
        return rv

    def can_access_view(self, view_name: str, auth: bool=False) -> bool:
        """
            Access is granted to next view after last finished view

            auth: if query is for authentication (if we can already really proceed to view or not).
        """
        if view_name == 'submitted' and not auth:
            return False
        last = self.flow.index(
            self.last_finished_view) if self.last_finished_view in self.flow else -1
        cur = self.flow.index(view_name) if view_name in self.flow else last + 2
        if self.form.flow_by_categories and self.form.allow_skipping_categories:
            # In participation view, allow going straight to questions if skipping categories
            # is allowed
            if self.form.require_email_verification:
                if self.last_finished_view == 'email_verification':
                    last += 1
            elif self.last_finished_view == 'contact_details':
                last += 1

        return cur <= last + 1

    def proceed_to_view(self, next_view: str) -> None:
        if not self.can_access_view(next_view):
            _next = self.flow.index(next_view)
            self.last_finished_view = self.flow[_next - 1]
            self.save(update_fields=['last_finished_view'])

    @property
    def next_view_name(self) -> str:
        return self.flow[self.flow.index(self._current_view) + 1]

    def redirect_next(self, request: HttpRequest, message: bool=True) -> HttpResponse:
        if self.status == self.STATUS_UPDATING and message:
            messages.warning(request, _(
                'Updated information has been stored! Please proceed until the end of the form.'))
        return HttpResponseRedirect(reverse(self.next_view_name))

    def redirect_last(self) -> HttpResponse:
        last = self.flow.index(
            self.last_finished_view) if self.last_finished_view in self.flow else -1
        return HttpResponseRedirect(reverse(self.flow[last + 1]))

    @cached_property
    def log(self) -> 'Sequence[ParticipantLog]':
        return self.participantlog_set.all()