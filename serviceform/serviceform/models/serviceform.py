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

import datetime
import string
import logging
from enum import Enum
from typing import Tuple, Set, Optional, Sequence, Iterator, Iterable, TYPE_CHECKING, List

from colorful.fields import RGBColorField
from django.conf import settings
from django.contrib.contenttypes.fields import GenericRelation
from django.db import models
from django.db.models import Prefetch
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from guardian.shortcuts import get_users_with_perms
from select2 import fields as select2_fields

from serviceform.tasks.models import Task

from .. import emails, utils
from ..utils import ColorStr, django_cache, invalidate_cache

from .mixins import SubitemMixin, NameDescriptionMixin, CopyMixin
from .people import Member, Organization
from .email import EmailTemplate
from .participation import QuestionAnswer, Participation

if TYPE_CHECKING:
    from .participation import ParticipationActivity, ParticipationActivityChoice

local_tz = timezone.get_default_timezone()
logger = logging.getLogger(__name__)


class ColorField(RGBColorField):
    def get_prep_value(self, value: 'ColorStr') -> 'Optional[ColorStr]':
        rv = super().get_prep_value(value)
        if rv == '#000000':
            rv = None
        return rv

    def from_db_value(self, value: 'Optional[ColorStr]', *args):
        if value is None:
            return '#000000'
        return value



class FormRevision(models.Model):
    class Meta:
        verbose_name = _('Form revision')
        verbose_name_plural = _('Form revisions')
        ordering = ('-valid_from',)
        unique_together = ('form', 'name')

    name = models.SlugField(max_length=32, verbose_name=_('Revision name'), db_index=True)
    form = models.ForeignKey('ServiceForm', verbose_name=_('Service form'))
    valid_from = models.DateTimeField(verbose_name=_('Valid from'),
                                      default=datetime.datetime(3000, 1, 1, tzinfo=local_tz))
    valid_to = models.DateTimeField(verbose_name=_('Valid to'),
                                    default=datetime.datetime(3000, 1, 1, tzinfo=local_tz))
    send_bulk_email_to_participants = models.BooleanField(
        _('Send bulk email to participants'),
        help_text=_('Send email to participants that filled the form when this revision was '
                    'active. Email is sent when new current revision is published.'),
        default=True)
    send_emails_after = models.DateTimeField(
        verbose_name=_('Email sending starts'),
        help_text=_(
            'Sends bulk email to responsibility persons at specified time, after which it will '
            'send email for each new participation'),
        default=datetime.datetime(3000, 1, 1, tzinfo=local_tz))

    def __str__(self):
        return self.name


class ServiceForm(SubitemMixin, models.Model):
    subitem_name = 'level1category'

    class Meta:
        verbose_name = _('Service form')
        verbose_name_plural = _('Service forms')

    def __str__(self):
        return self.name

    # Basic info
    name = models.CharField(max_length=256, verbose_name=_('Name of the serviceform'))
    slug = models.SlugField(unique=True, verbose_name=_('Slug'), db_index=True, help_text=_(
        'This is part of the form url, i.e. form will be located {}/yourslug').format(
        settings.SERVER_URL))

    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    last_updated = models.DateTimeField(auto_now=True, null=True, verbose_name=_('Last updated'))
    last_editor = models.ForeignKey(settings.AUTH_USER_MODEL, verbose_name=_('Last edited by'),
                                    related_name='last_edited_serviceform', null=True,
                                    on_delete=models.SET_NULL)

    # Ownership
    organization = models.ForeignKey(Organization, on_delete=models.CASCADE)
    responsible = models.ForeignKey(Member, null=True, blank=True,
                                    verbose_name=_('Responsible'), on_delete=models.SET_NULL)

    # Email settings
    require_email_verification = models.BooleanField(_('Require email verification'), default=True)

    verification_email_to_participant = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Verification email to participant'),
        help_text=_(
            'Email verification message that is sent to participant when filling form, '
            'if email verification is enabled'),
        on_delete=models.SET_NULL)

    email_to_responsibles = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Email to responsibles'), help_text=_(
            'Email that is sent to responsibles when new participation is registered'),
        on_delete=models.SET_NULL)

    bulk_email_to_responsibles = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        verbose_name=_('Bulk email to responsibles'),
        help_text=_('Email that is sent to responsibles when emailing starts'),
        related_name='+',
        on_delete=models.SET_NULL)

    email_to_responsible_auth_link = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Responsible requests '
                       'auth link'),
        help_text=_('Email that is sent to responsible when he requests auth link'),
        on_delete=models.SET_NULL)

    # Participation emails:

    # on_finish
    email_to_participant = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Email to participant, on finish'),
        help_text=_('Email that is sent to participant after he has fulfilled his participation'),
        on_delete=models.SET_NULL)
    # on update
    email_to_participant_on_update = models.ForeignKey(EmailTemplate, null=True, blank=True,
                                                       related_name='+', verbose_name=_(
            'Email to participant, on update'), help_text=_(
            'Email that is sent to participant after he has updated his participation'),
                                                       on_delete=models.SET_NULL)
    # resend
    resend_email_to_participant = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Resend email to participant'),
        help_text=_('Email that is sent to participant if he requests resending email'),
        on_delete=models.SET_NULL)
    # new_form_revision
    email_to_former_participants = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Bulk email to former participants'),
        help_text=_('Email that is sent to former participants when form is published'),
        on_delete=models.SET_NULL)
    # invite
    email_to_invited_users = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Invite email'),
        help_text=_(
            'Email that is sent when user is invited to the form manually via invite form'),
        on_delete=models.SET_NULL)

    # Form settings
    current_revision = models.ForeignKey(
        FormRevision, null=True, blank=True,
        verbose_name=_('Current revision'),
        help_text=_(
            'You need to first add a revision to form (see below) and save. '
            'Then newly created revision will appear in the list.'),
        on_delete=models.SET_NULL)

    password = models.CharField(
        _('Password'), max_length=32, blank=True,
        help_text=_('Password that is asked from participants'),
        default='')

    hide_contact_details = models.BooleanField(
        _('Hide contact details (other than email) in form'), default=False)
    flow_by_categories = models.BooleanField(_('Split participation form to level 1 categories'),
                                             default=False, help_text=_(
            'Please note that preview shows full form despite this option'))
    allow_skipping_categories = models.BooleanField(
        _('Allow jumping between categories'),
        default=False,
        help_text=_('In effect only if flow by categories option is enabled. If this option is '
                    'enabled, user can jump between categories. If disabled, he must proceed them '
                    'one by one.'))

    level1_color = ColorField(_('Level 1 category default background color'), null=True,
                              blank=True,
                              help_text=_('If left blank (black), default coloring will be used'))
    level2_color = ColorField(_('Level 2 category default background color'), null=True,
                              blank=True, help_text=_(
            'If left blank (black), it will be derived from level 1 background color'))
    activity_color = ColorField(_('Activity default background color'), null=True, blank=True,
                                help_text=_('If left blank (black), it will be derived from '
                                'level 2 background color'))

    description = models.TextField(blank=True, verbose_name=_('Description'), help_text=_(
        'Description box will be shown before instruction box in participation view.'))
    instructions = models.TextField(
        _('Instructions'), help_text=_(
            'Use HTML formatting. Leave this empty to use default. '
            'This is shown in participation view.'),
        blank=True, null=True)
    login_text = models.TextField(_('Login text'), blank=True, null=True,
                                  help_text=_('This will be shown in the login screen'))

    required_year_of_birth = models.BooleanField(_('Year of birth'), default=False)
    required_street_address = models.BooleanField(_('Street address'), default=True)
    required_phone_number = models.BooleanField(_('Phone number'), default=True)

    visible_year_of_birth = models.BooleanField(_('Year of birth'), default=True)
    visible_street_address = models.BooleanField(_('Street address'), default=True)
    visible_phone_number = models.BooleanField(_('Phone number'), default=True)

    tasks = GenericRelation(Task, object_id_field='target_id', content_type_field='target_type')

    class InviteUserResponse(Enum):
        EMAIL_SENT = 0
        USER_DENIED_EMAIL = 1
        USER_EXISTS = 2

    def can_access(self) -> str:
        return ', '.join('%s' % u for u in get_users_with_perms(self))

    can_access.short_description = _('Can access')

    @django_cache('all_responsibles')
    def all_responsibles(self) -> List[Member]:
        rs = {self.responsible}
        for cat1 in self.sub_items:
            rs.update(cat1.responsibles.all())
            for cat2 in cat1.sub_items:
                rs.update(cat2.responsibles.all())
                for act in cat2.sub_items:
                    rs.update(act.responsibles.all())
                    for choice in act.sub_items:
                        rs.update(choice.responsibles.all())
        rs = list(rs)
        rs.sort(key=lambda x: (x.surname, x.forenames))
        return rs

    @cached_property
    def sub_items(self) -> 'Sequence[AbstractServiceFormItem]':
        lvl2s = Prefetch('level2category_set',
                         queryset=Level2Category.objects.prefetch_related('responsibles'))
        acts = Prefetch('level2category_set__activity_set',
                        queryset=Activity.objects.prefetch_related('responsibles'))
        choices = Prefetch('level2category_set__activity_set__activitychoice_set',
                           queryset=ActivityChoice.objects.prefetch_related('responsibles'))

        return self.level1category_set.prefetch_related('responsibles').prefetch_related(
            lvl2s, acts, choices)

    def create_initial_data(self) -> None:
        self.create_email_templates()
        self.current_revision = FormRevision.objects.create(name='%s' % timezone.now().year,
                                                            form=self)
        self.responsible = Member.objects.create(
            forenames=_('Default'),
            surname=_('Responsible'),
            email=_('defaultresponsible@email.com'),
            form=self)
        self.save()

    def create_email_templates(self) -> None:
        if not self.pk:
            logger.error('Cannot create email template if form is not saved')
            return

        commit = False
        # TODO: refactor this
        if not self.bulk_email_to_responsibles:
            commit = True
            self.bulk_email_to_responsibles = EmailTemplate.make(
                _('Default bulk email to responsibles'), self,
                emails.bulk_email_to_responsibles,
                _('Participations can be now viewed for form {{form}}'))
        if not self.email_to_responsibles:
            commit = True
            self.email_to_responsibles = EmailTemplate.make(
                _('Default email to responsibles'),
                self, emails.message_to_responsibles,
                _('New participation arrived for form {{form}}'))
        if not self.email_to_participant:
            commit = True
            self.email_to_participant = EmailTemplate.make(
                _('Default email to participant, on finish'), self,
                emails.participant_on_finish,
                _('Your update to form {{form}}'))
        if not self.email_to_participant_on_update:
            commit = True
            self.email_to_participant_on_update = EmailTemplate.make(
                _('Default email to participant, on update'), self,
                emails.participant_on_update,
                _('Your updated participation to form {{form}}'))
        if not self.email_to_former_participants:
            commit = True
            self.email_to_former_participants = EmailTemplate.make(
                _('Default email to former participants'), self,
                emails.participant_new_form_revision,
                _('New form revision to form {{form}} has been published'))
        if not self.resend_email_to_participant:
            commit = True
            self.resend_email_to_participant = EmailTemplate.make(
                _('Default resend email to participant'), self,
                emails.resend_email_to_participants,
                _('Your participation to form {{form}}'))
        if not self.email_to_invited_users:
            commit = True
            self.email_to_invited_users = EmailTemplate.make(
                _('Default invite email to participants'), self,
                emails.invite,
                _('Invitation to fill participation in {{form}}'))
        if not self.email_to_responsible_auth_link:
            commit = True
            self.email_to_responsible_auth_link = EmailTemplate.make(
                _('Default request responsible auth link email'), self,
                emails.request_responsible_auth_link,
                _('Your report in {{form}}'))
        if not self.verification_email_to_participant:
            commit = True
            self.verification_email_to_participant = EmailTemplate.make(
                _('Default verification email to participant'), self,
                emails.verification_email_to_participant,
                _('Please verify your email in {{form}}'))
        if commit:
            self.save()

    def invite_user(self, email: str, old_participants: bool=False) -> InviteUserResponse:
        """
            Create new participations to current form version and send invites

        :return: int (one of InviteUserResponse constants)
        """
        logger.info('Invite user %s %s', self, email)

        participant = Participation.objects.filter(email=email, form_revision__form=self).first()
        if participant:
            if old_participants and participant.form_revision != self.current_revision:
                rv = participant.send_participant_email(Participation.EmailIds.INVITE)
                return (self.InviteUserResponse.EMAIL_SENT
                        if rv else self.InviteUserResponse.USER_DENIED_EMAIL)
            else:
                return self.InviteUserResponse.USER_EXISTS
        else:
            participant = Participation.objects.create(email=email,
                                                       form_revision=self.current_revision,
                                                       status=Participation.STATUS_INVITED)
            participant.send_participant_email(Participation.EmailIds.INVITE)
            return self.InviteUserResponse.EMAIL_SENT

    @cached_property
    def questions(self) -> 'Sequence[Question]':
        return self.question_set.all()

    def activities(self) -> 'Iterator[Activity]':
        for c1 in self.sub_items:
            for c2 in c1.sub_items:
                for a in c2.sub_items:
                    yield a

    @property
    def is_published(self) -> bool:
        return (self.current_revision and
                self.current_revision.valid_from <= timezone.now()
                                                 <= self.current_revision.valid_to)

    def is_published_display(self) -> bool:
        return self.is_published

    is_published_display.boolean = True
    is_published_display.short_description = _('Is open?')

    def init_counters(self, all_responsibles: bool=True) -> None:
        """
        Initializes counters and collects responsibles from subitems
        """
        if getattr(self, '_counters_initialized', None):
            logger.error('Counters already initialized')
            return
        utils.init_serviceform_counters(self, all_responsibles)
        self._counters_initialized = True

    def _find_new_slug(self) -> str:
        slug = self.slug
        while ServiceForm.objects.filter(slug=slug).exists():
            slug += '-copy'
        return slug

    def links(self) -> Tuple[str]:
        return (format_html('<a href="{}">{}</a>, ', reverse('report', args=(self.slug,)),
                            _('To report')) +
                format_html('<a href="{}">{}</a>, ', reverse('password_login', args=(self.slug,)),
                            _('To form')) +
                format_html('<a href="{}">{}</a>, ', reverse('preview_form', args=(self.slug,)),
                            _('Preview')) +
                format_html('<a href="{}">{}</a>, ',
                            reverse('preview_printable', args=(self.slug,)), _('Printable')) +
                format_html('<a href="{}">{}</a>', reverse('invite', args=(self.slug,)),
                            _('Invite'))
                )

    links.short_description = _('Links')

    def participation_count(self) -> str:
        if self.current_revision:
            old_time = timezone.now() - datetime.timedelta(minutes=20)
            ready = self.current_revision.participation_set.filter(
                status__in=Participation.READY_STATUSES)
            recent_ongoing = self.current_revision.participation_set.filter(
                status__in=[Participation.STATUS_ONGOING],
                last_modified__gt=old_time)

            return '%s + %s' % (ready.count(), recent_ongoing.count())
        else:
            return '0'

    participation_count.short_description = _('Participation count')

    def bulk_email_responsibles(self) -> None:
        logger.info('Bulk email responsibles %s', self)

        for r in self.all_responsibles:
            r.send_bulk_mail()

    def bulk_email_former_participants(self) -> None:
        logger.info('Bulk email former participants %s', self)
        for p in Participation.objects.filter(member__allow_participant_email=True,
                                              form_revision__send_bulk_email_to_participants=True,
                                              form_revision__form=self,
                                              form_revision__valid_to__lt=timezone.now()).distinct():
            p.send_participant_email(Participation.EmailIds.NEW_FORM_REVISION)

    def reschedule_bulk_email(self) -> None:
        now = timezone.now()
        self.tasks.filter(scheduled_time__gt=now, status=Task.REQUESTED).delete()

        if not self.current_revision:
            return

        self.current_revision.refresh_from_db()

        if self.current_revision.send_emails_after > now:
            tr = Task.make(self.bulk_email_responsibles,
                           scheduled_time=self.current_revision.send_emails_after)
        if self.current_revision.valid_from > now:
            tp = Task.make(self.bulk_email_former_participants,
                           scheduled_time=self.current_revision.valid_from)


@receiver(post_save, sender=ServiceForm)
def invalidate_serviceform_caches(sender: ServiceForm, **kwargs):
    invalidate_cache(sender, 'all_participants')


class AbstractServiceFormItem(models.Model):
    _responsibles: Set[Member]
    sub_items: 'Iterable[AbstractServiceFormItem]'

    class Meta:
        abstract = True
        ordering = ('order',)

    order = models.PositiveIntegerField(default=0, blank=False, null=False, db_index=True,
                                        verbose_name=_('Order'))
    responsibles = select2_fields.ManyToManyField(Member, blank=True,
                                                  verbose_name=_('Responsible persons'),
                                                  related_name='%(class)s_responsibles',
                                                  overlay=_('Choose responsibles'),
                                                  )

    def __init__(self, *args, **kwargs) -> None:
        self._responsibles = set()
        super().__init__(*args, **kwargs)

    def has_responsible(self, r: 'Member') -> bool:
        return r in self._responsibles

    subitem_name: str
    _counter: int

    @cached_property
    def sub_items(self):
        return getattr(self, self.subitem_name + '_set').all()

    @cached_property
    def responsibles_display(self) -> str:
        first_resp = ''
        responsibles = self.responsibles.all()
        if responsibles:
            first_resp = str(self.responsibles.first())
        if len(responsibles) > 1:
            return _('{} (and others)').format(first_resp)
        else:
            return first_resp

    def background_color_display(self) -> 'ColorStr':
        raise NotImplementedError


class Level1Category(SubitemMixin, NameDescriptionMixin, AbstractServiceFormItem):
    subitem_name = 'level2category'
    background_color = ColorField(_('Background color'), blank=True, null=True)

    class Meta(AbstractServiceFormItem.Meta):
        verbose_name = _('Level 1 category')
        verbose_name_plural = _('Level 1 categories')

    form = models.ForeignKey(ServiceForm, on_delete=models.CASCADE)

    @cached_property
    def background_color_display(self) -> 'ColorStr':
        return utils.not_black(self.background_color) or utils.not_black(self.form.level1_color)


class Level2Category(SubitemMixin, NameDescriptionMixin, AbstractServiceFormItem):
    subitem_name = 'activity'
    background_color = ColorField(_('Background color'), blank=True, null=True)

    class Meta(AbstractServiceFormItem.Meta):
        verbose_name = _('Level 2 category')
        verbose_name_plural = _('Level 2 categories')

    category = models.ForeignKey(Level1Category, null=True, verbose_name=_('Level 1 category'),
                                 on_delete=models.CASCADE)

    @cached_property
    def background_color_display(self) -> 'ColorStr':
        return (utils.not_black(self.background_color) or
                (self.category.background_color_display and utils.lighter_color(
                    self.category.background_color_display)) or
                utils.not_black(self.category.form.level2_color))


class Activity(SubitemMixin, NameDescriptionMixin, AbstractServiceFormItem):
    subitem_name = 'activitychoice'

    class Meta(AbstractServiceFormItem.Meta):
        verbose_name = _('Activity')
        verbose_name_plural = _('Activities')

    category = models.ForeignKey(Level2Category, verbose_name=_('Category'),
                                 on_delete=models.CASCADE)
    multiple_choices_allowed = models.BooleanField(default=True, verbose_name=_('Multichoice'))
    people_needed = models.PositiveIntegerField(_('Needed'), default=0)
    skip_numbering = models.BooleanField(_('Skip'), default=False)

    @property
    def has_choices(self) -> bool:
        return self.activitychoice_set.exists()

    @property
    def id_display(self) -> str:
        return '%s+' % max(1, self._counter) if self.skip_numbering else self._counter

    def participation_items(self, revision_name: str) -> 'Sequence[ParticipationActivity]':
        current_revision = self.category.category.form.current_revision

        qs = self.participationactivity_set.filter(
            participant__status__in=Participation.READY_STATUSES)

        if revision_name == utils.RevisionOptions.ALL:
            qs = qs.order_by('participant__form_revision')
        elif revision_name == utils.RevisionOptions.CURRENT:
            qs = qs.filter(participant__form_revision=current_revision)
        else:
            qs = qs.filter(participant__form_revision__name=revision_name)
        return qs

    @property
    def show_checkbox(self) -> bool:
        has_choices = self.has_choices
        return not has_choices or (has_choices and not self.multiple_choices_allowed)

    @cached_property
    def background_color_display(self) -> 'ColorStr':
        return self.category.background_color_display and utils.lighter_color(
            self.category.background_color_display)


class ActivityChoice(SubitemMixin, NameDescriptionMixin, AbstractServiceFormItem):
    class Meta(AbstractServiceFormItem.Meta):
        verbose_name = _('Activity choice')
        verbose_name_plural = _('Activity choices')

    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    people_needed = models.PositiveIntegerField(_('Needed'), default=0)
    skip_numbering = models.BooleanField(_('Skip'), default=False)

    @property
    def id_display(self) -> str:
        letter = string.ascii_lowercase[max(0, self._counter - 1)]
        return '%s+' % letter if self.skip_numbering else letter

    @property
    def is_first(self) -> bool:
        return self._counter == 0

    def participation_items(self, revision_name: str) -> 'Sequence[ParticipationActivityChoice]':
        current_revision = self.activity.category.category.form.current_revision

        qs = self.participationactivitychoice_set.filter(
            activity__participant__status__in=Participation.READY_STATUSES)

        if revision_name == utils.RevisionOptions.ALL:
            qs = qs.order_by('activity__participant__form_revision')
        elif revision_name == utils.RevisionOptions.CURRENT:
            qs = qs.filter(activity__participant__form_revision=current_revision)
        else:
            qs = qs.filter(activity__participant__form_revision__name=revision_name)
        return qs

    @cached_property
    def background_color_display(self) -> 'ColorStr':
        return self.activity.category.background_color_display and utils.lighter_color(
            self.activity.category.background_color_display)


class Question(CopyMixin, AbstractServiceFormItem):
    class Meta(AbstractServiceFormItem.Meta):
        verbose_name = _('Question')
        verbose_name_plural = _('Questions')

    ANSWER_INT = 'integer'
    ANSWER_SHORT_TEXT = 'short_text'
    ANSWER_LONG_TEXT = 'long_text'
    ANSWER_BOOL = 'boolean'
    ANSWER_DATE = 'date'

    ANSWER_TYPES = ((ANSWER_INT, _('Integer')),
                    (ANSWER_SHORT_TEXT, _('Short text')),
                    (ANSWER_LONG_TEXT, _('Long text')),
                    (ANSWER_BOOL, _('Boolean')),
                    (ANSWER_DATE, _('Date')),
                    )

    form = models.ForeignKey(ServiceForm, on_delete=models.CASCADE)
    question = models.CharField(max_length=1024, verbose_name=_('Question'))
    answer_type = models.CharField(max_length=16, choices=ANSWER_TYPES, default=ANSWER_SHORT_TEXT,
                                   verbose_name=_('Answer type'))
    required = models.BooleanField(default=False, verbose_name=_('Answer required?'))

    def render(self) -> str:
        return render_to_string(
            'serviceform/participation/question_form/types/question_%s.html' % self.answer_type,
            {'question': self})

    def questionanswers(self, revision_name: str) -> 'Sequence[QuestionAnswer]':
        qs = QuestionAnswer.objects.filter(question=self,
                                           participant__status__in=Participation.READY_STATUSES)

        current_revision = self.form.current_revision

        if revision_name == utils.RevisionOptions.ALL:
            qs = qs.order_by('-participant__form_revision')
        elif revision_name == utils.RevisionOptions.CURRENT:
            qs = qs.filter(participant__form_revision=current_revision)
        else:
            qs = qs.filter(participant__form_revision__name=revision_name)
        return qs

    @property
    def id_display(self):
        # TODO: perhaps we could implement also here some kind of numbering
        return ''

    def __str__(self):
        return self.question


