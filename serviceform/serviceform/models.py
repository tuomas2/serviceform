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
import json
import logging
import string
import time
from enum import Enum
from typing import Set, Optional, Iterable, Iterator, Tuple, Union, List, Sequence, TYPE_CHECKING

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.contrib.postgres.fields import JSONField
from django.core.mail import EmailMultiAlternatives
from django.core.urlresolvers import reverse
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Prefetch
from django.db.models.options import Options
from django.http import HttpResponseRedirect, HttpRequest, HttpResponse
from django.template.loader import render_to_string, get_template
from django.utils import timezone
from django.template import Template, Context
from django.utils.formats import localize
from guardian.shortcuts import get_users_with_perms

from select2 import fields as select2_fields
# Create your models here.
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from colorful.fields import RGBColorField
from serviceform.tasks.models import Task

from . import utils, emails

if TYPE_CHECKING:
    from .utils import ColorStr


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


phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$',
                             message=_("Phone number must be entered in the format: "
                                       "'050123123' or '+35850123123'. "
                                       "Up to 15 digits allowed."))
local_tz = timezone.get_default_timezone()
logger = logging.getLogger('serviceform')

postalcode_regex = RegexValidator(
    regex=r'^\d{5}$',
    message=_('Enter a valid postal code.'),
    code='invalid',
)


class ContactDetailsMixin(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        if self.forenames or self.surname:
            return '%s %s' % (self.forenames.title(), self.surname.title())
        else:
            return self.email

    @property
    def address(self):
        return ('%s\n%s %s' % (
            self.street_address.title(), self.postal_code, self.city.title())).strip()

    forenames = models.CharField(max_length=64, verbose_name=_('Forename(s)'))
    surname = models.CharField(max_length=64, verbose_name=_('Surname'))
    street_address = models.CharField(max_length=128, blank=False,
                                      verbose_name=_('Street address'))
    postal_code = models.CharField(max_length=32, blank=False,
                                   verbose_name=_('Zip/Postal code'),
                                   validators=[postalcode_regex])
    city = models.CharField(max_length=32, blank=False, verbose_name=_('City'))
    email = models.EmailField(blank=False, verbose_name=_('Email'), db_index=True)
    phone_number = models.CharField(max_length=32, validators=[phone_regex], blank=False,
                                    verbose_name=_('Phone number'))

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


class ContactDetailsMixinEmail(ContactDetailsMixin):
    class Meta:
        abstract = True

ContactDetailsMixinEmail._meta.get_field('street_address').blank = True
ContactDetailsMixinEmail._meta.get_field('postal_code').blank = True
ContactDetailsMixinEmail._meta.get_field('city').blank = True
ContactDetailsMixinEmail._meta.get_field('phone_number').blank = True


class NameDescriptionMixin(models.Model):
    class Meta:
        abstract = True

    def __str__(self):
        return self.name

    name = models.CharField(max_length=256, verbose_name=_('Name'))
    description = models.TextField(blank=True, verbose_name=_('Description'))


class CopyMixin:
    _meta: Options
    def create_copy(self):
        fr = self.__class__()
        for field in self._meta.fields:
            setattr(fr, field.name, getattr(self, field.name))
        fr.pk = None
        return fr


class SubitemMixin(CopyMixin):
    subitem_name: str
    _counter: int

    def __init__(self, *args, **kwargs):
        self._responsibles = set()
        super().__init__(*args, **kwargs)

    @cached_property
    def sub_items(self):
        return getattr(self, self.subitem_name + '_set').all()

    def has_responsible(self, r: 'ResponsibilityPerson') -> bool:
        return r in self._responsibles


class PasswordMixin(models.Model):
    """
    New 'password' is generated every time user requests a auth email to be sent
    to him. Password will expire after AUTH_KEY_EXPIRE_DAYS. We will store
    AUTH_STORE_KEYS number of most recent keys in a json storage.
    """

    AUTH_VIEW: str

    class Meta:
        abstract = True

    class PasswordStatus(Enum):
        PASSWORD_EXPIRED = object()
        PASSWORD_OK = True
        PASSWORD_NOK = False

    # New style auth link hash
    auth_keys_hash_storage = JSONField(default=[])  # List of (hash, expire) tuples

    # TODO: remove this field (as well as views using it) when all users are having new auth_key_hash set up.
    secret_key = models.CharField(max_length=36, default=utils.generate_uuid, db_index=True,
                                  unique=True,
                                  verbose_name=_('Secret key'))

    def make_new_password(self) -> str:
        valid_hashes = []
        for key, expire in self.auth_keys_hash_storage:
            if expire > time.time():
                valid_hashes.append((key, expire))

        password = utils.generate_uuid()

        auth_key_hash = make_password(password)
        auth_key_expire: datetime.datetime = (timezone.now() +
                           datetime.timedelta(days=getattr(settings, 'AUTH_KEY_EXPIRE_DAYS', 90)))

        valid_hashes.append((auth_key_hash, auth_key_expire.timestamp()))
        self.auth_keys_hash_storage = valid_hashes[-getattr(settings, 'AUTH_STORE_KEYS', 10):]
        self.save(update_fields=['auth_keys_hash_storage'])
        return password

    def make_new_auth_url(self) -> str:
        url = settings.SERVER_URL + reverse(self.AUTH_VIEW, args=(self.pk,
                                                                  self.make_new_password(),))
        return url

    def check_auth_key(self, password: str) -> PasswordStatus:
        for key, expire_timestamp in reversed(self.auth_keys_hash_storage):
            if check_password(password, key):
                if expire_timestamp < time.time():
                    return self.PasswordStatus.PASSWORD_EXPIRED
                return self.PasswordStatus.PASSWORD_OK

        return self.PasswordStatus.PASSWORD_NOK


class ResponsibilityPerson(CopyMixin, PasswordMixin, ContactDetailsMixinEmail, models.Model):
    class Meta:
        verbose_name = _('Responsibility person')
        verbose_name_plural = _('Responsibility persons')
        ordering = ('surname',)

    AUTH_VIEW = 'authenticate_responsible_new'

    form = models.ForeignKey('ServiceForm', null=True)
    send_email_notifications = models.BooleanField(
        default=True,
        verbose_name=_('Send email notifications'),
        help_text=_(
            'Send email notifications whenever new participation to administered activities is '
            'registered. Email contains also has a link that allows accessing raport of '
            'administered activities.'))

    hide_contact_details = models.BooleanField(_('Hide contact details in form'), default=False)
    show_full_report = models.BooleanField(_('Grant access to full reports'), default=False)

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

    @property
    def list_unsubscribe_link(self) -> str:
        return settings.SERVER_URL + reverse('unsubscribe_responsible', args=(self.secret_id,))

    def resend_auth_link(self) -> 'EmailMessage':

        context = {'responsible': str(self),
                   'form': str(self.form),
                   'url': self.make_new_auth_url(),
                   'contact': self.form.responsible.contact_display,
                   'list_unsubscribe': self.list_unsubscribe_link,
                   }
        return EmailMessage.make(self.form.email_to_responsible_auth_link, context, self.email)

    def send_responsibility_email(self, participant: 'Participant') -> None:
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
        if self.send_email_notifications:
            context = {'responsible': str(self),
                       'form': str(self.form),
                       'url': self.make_new_auth_url(),
                       'contact': self.form.responsible.contact_display,
                       'list_unsubscribe': self.list_unsubscribe_link,
                       }
            return EmailMessage.make(self.form.bulk_email_to_responsibles, context, self.email)


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


class EmailMessage(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    template = models.ForeignKey('EmailTemplate', null=True, on_delete=models.SET_NULL)
    from_address = models.CharField(max_length=256)
    to_address = models.CharField(max_length=256)
    subject = models.CharField(max_length=256)
    content = models.TextField()
    sent_at = models.DateTimeField(null=True)
    context = models.TextField(default="{}")  # JSONified context variables

    def __str__(self):
        return '<EmailMessage %s to %s>' % (self.pk, self.to_address)

    @cached_property
    def context_dict(self) -> Context:
        return Context(json.loads(self.context))

    def content_display(self) -> str:
        return Template(self.content).render(self.context_dict)

    content_display.short_description = _('Content')

    def subject_display(self) -> str:
        return Template(self.subject).render(self.context_dict)

    subject_display.short_description = _('Subject')

    def _cleanup_context(self) -> None:
        context = json.loads(self.context)
        if 'url' in context:
            # Remove URL from email message, as it contains password
            context['url'] = 'http://***password*removed***'
            self.context = json.dumps(context)
            self.save(update_fields=['context'])

    def send(self) -> None:
        logger.info('Sending email to %s', self.to_address)
        body = self.content_display()
        html_body = render_to_string('serviceform/email.html', context={'body': body})
        headers = {'List-Unsubscribe': '<%s>' % self.context_dict['list_unsubscribe']}
        mail = EmailMultiAlternatives(subject=self.subject_display(),
                                      body=body,
                                      from_email=settings.SERVER_EMAIL,
                                      headers=headers,
                                      to=[self.to_address])
        mail.attach_alternative(html_body, 'text/html')
        emails = mail.send()
        if emails == 1:
            self.sent_at = timezone.now()
            self.save(update_fields=['sent_at'])
            self._cleanup_context()
        else:
            logger.error('Email message to %s could not be sent', self)

    @classmethod
    def make(cls, template: 'EmailTemplate', context_dict: dict, address: str,
             send: bool=False) -> 'EmailMessage':
        logger.info('Creating email to %s', address)
        msg = cls.objects.create(template=template, to_address=address,
                                 from_address=settings.SERVER_EMAIL,
                                 subject=template.subject, content=template.content,
                                 context=json.dumps(context_dict))
        if send:
            msg.send()
        return msg


class EmailTemplate(CopyMixin, models.Model):
    class Meta:
        verbose_name = _('Email template')
        verbose_name_plural = _('Email templates')

    def __str__(self):
        return self.name

    name = models.CharField(_('Template name'), max_length=256)
    subject = models.CharField(_('Subject'), max_length=256)
    content = models.TextField(_('Content'), help_text=_(
        'Following context may (depending on topic) be available for both subject and content: '
        '{{responsible}}, {{participant}}, {{last_modified}}, {{form}}, {{url}}, {{contact}}'))
    form = models.ForeignKey('ServiceForm', on_delete=models.CASCADE)

    @classmethod
    def make(cls, name: str, form: 'ServiceForm', content: str, subject: str):
        return cls.objects.create(name=name, form=form, subject=subject, content=content)


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
    responsible = models.ForeignKey(ResponsibilityPerson, null=True, blank=True,
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

    # Participant emails:

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
        self.responsible = ResponsibilityPerson.objects.create(
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

        participant = Participant.objects.filter(email=email, form_revision__form=self).first()
        if participant:
            if old_participants and participant.form_revision != self.current_revision:
                rv = participant.send_participant_email(Participant.EmailIds.INVITE)
                return (self.InviteUserResponse.EMAIL_SENT
                        if rv else self.InviteUserResponse.USER_DENIED_EMAIL)
            else:
                return self.InviteUserResponse.USER_EXISTS
        else:
            participant = Participant.objects.create(email=email,
                                                     form_revision=self.current_revision,
                                                     status=Participant.STATUS_INVITED)
            participant.send_participant_email(Participant.EmailIds.INVITE)
            return self.InviteUserResponse.EMAIL_SENT

    @cached_property
    def questions(self) -> 'Iterable[Question]':
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
            ready = self.current_revision.participant_set.filter(
                status__in=Participant.READY_STATUSES)
            recent_ongoing = self.current_revision.participant_set.filter(
                status__in=[Participant.STATUS_ONGOING],
                last_modified__gt=old_time)

            return '%s + %s' % (ready.count(), recent_ongoing.count())
        else:
            return '0'

    participation_count.short_description = _('Participation count')

    def bulk_email_responsibles(self) -> None:
        logger.info('Bulk email responsibles %s', self)

        for r in self.responsibilityperson_set.all():
            r.send_bulk_mail()

    def bulk_email_former_participants(self) -> None:
        logger.info('Bulk email former participants %s', self)
        for p in Participant.objects.filter(send_email_allowed=True,
                                            form_revision__send_bulk_email_to_participants=True,
                                            form_revision__form=self,
                                            form_revision__valid_to__lt=timezone.now()).distinct():
            p.send_participant_email(Participant.EmailIds.NEW_FORM_REVISION)

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


class AbstractServiceFormItem(models.Model):
    _responsibles: Set[ResponsibilityPerson]
    sub_items: 'Iterable[AbstractServiceFormItem]'

    class Meta:
        abstract = True
        ordering = ('order',)

    order = models.PositiveIntegerField(default=0, blank=False, null=False, db_index=True,
                                        verbose_name=_('Order'))
    responsibles = select2_fields.ManyToManyField(ResponsibilityPerson, blank=True,
                                                  verbose_name=_('Responsible persons'),
                                                  related_name='%(class)s_related',
                                                  overlay=_('Choose responsibles'),
                                                  )

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

    def participation_items(self, revision_name: str=None) -> 'Iterable[ParticipationActivity]':
        if revision_name is None:
            revision_name = self.category.category.form.current_revision.name
        return self.participationactivity_set.filter(
            participant__form_revision__name=revision_name,
            participant__status__in=Participant.READY_STATUSES)

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

    def participation_items(self, revision_name: str=None) \
            -> 'Iterable[ParticipationActivityChoice]':
        if revision_name is None:
            revision_name = self.activity.category.category.form.current_revision.name
        return ParticipationActivityChoice.objects.filter(
            activity_choice=self,
            activity__participant__form_revision__name=revision_name,
            activity__participant__status__in=Participant.READY_STATUSES
        )

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

    @property
    def questionanswers(self) -> 'Iterable[QuestionAnswer]':
        revision = self.form.current_revision
        return QuestionAnswer.objects.filter(question=self, participant__form_revision=revision,
                                             participant__status__in=Participant.READY_STATUSES)

    def __str__(self):
        return self.question


### PARTICIPANT MODELS

class Participant(ContactDetailsMixin, PasswordMixin, models.Model):
    email: str

    class Meta:
        verbose_name = _('Participant')
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

    year_of_birth = models.SmallIntegerField(_('Year of birth'), null=True, blank=True)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ONGOING)
    last_finished_view = models.CharField(max_length=32, default='')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    last_modified = models.DateTimeField(auto_now=True, verbose_name=_('Last modified'))
    last_finished = models.DateTimeField(_('Last finished'), null=True)

    # Last form revision
    form_revision = models.ForeignKey(FormRevision, null=True, on_delete=models.CASCADE)

    email_verified = models.BooleanField(_('Email verified'), default=False)

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
        yield _('Participant created in system'), self.created_at
        yield _('Last finished'), self.last_finished
        yield _('Last modified'), self.last_modified
        yield _('Email address verified'), (_('No'), _('Yes'))[self.email_verified]
        yield _('Emails allowed'), (_('No'), _('Yes'))[self.send_email_allowed]
        yield _('Form status'), self.STATUS_DICT[self.status]

    @cached_property
    def item_count(self) -> int:
        choices = ParticipationActivityChoice.objects.filter(
            activity__participant=self).values_list('activity_id', flat=True)
        choice_count = len(choices)
        activity_count = self.participationactivity_set.exclude(pk__in=choices).count()
        return activity_count + choice_count

    def make_new_verification_url(self) -> str:
        return settings.SERVER_URL + reverse('verify_email',
                                             args=(self.pk, self.make_new_password()))

    @cached_property
    def activities(self) -> 'Iterable[ParticipationActivity]':
        return self.participationactivity_set.select_related('activity')

    @cached_property
    def questions(self) -> 'Iterable[QuestionAnswer]':
        return self.questionanswer_set.select_related('question')

    def activities_display(self) -> str:
        return ', '.join(a.activity.name for a in self.activities)

    activities_display.short_description = _('Activities')

    @cached_property
    def form(self) -> ServiceForm:
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
                               extra_context: dict=None) -> Optional[EmailMessage]:
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

    def resend_auth_link(self) -> Optional[EmailMessage]:
        return self.send_participant_email(self.EmailIds.RESEND)

    @property
    def flow(self) -> List[str]:
        from .urls import participant_flow_urls

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
    def log(self) -> 'Iterable[ParticipantLog]':
        return self.participantlog_set.all()


class ParticipantLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    writer_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    writer_id = models.PositiveIntegerField()
    # Can be either responsible or django user
    written_by = GenericForeignKey('writer_type', 'writer_id')
    message = models.TextField()


class ParticipationActivity(models.Model):
    class Meta:
        unique_together = (('participant', 'activity'),)
        ordering = (
        'activity__category__category__order', 'activity__category__order', 'activity__order',)

    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    activity = models.ForeignKey(Activity, on_delete=models.CASCADE)
    additional_info = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    @cached_property
    def cached_participant(self) -> Participant:
        return utils.get_participant(self.participant_id)

    def __str__(self):
        return '%s for %s' % (self.activity, self.participant)

    @property
    def choices(self) -> 'Iterable[ParticipationActivityChoice]':
        return self.choices_set.select_related('activity_choice')

    @property
    def additional_info_display(self) -> str:
        return self.additional_info or '-'


class ParticipationActivityChoice(models.Model):
    class Meta:
        unique_together = (('activity', 'activity_choice'),)
        ordering = ('activity_choice__order',)

    activity = models.ForeignKey(ParticipationActivity, related_name='choices_set',
                                 on_delete=models.CASCADE)
    activity_choice = models.ForeignKey(ActivityChoice, on_delete=models.CASCADE)
    additional_info = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    @cached_property
    def cached_participant(self) -> Participant:
        return utils.get_participant(self.activity.participant_id)

    def __str__(self):
        return '%s for %s' % (self.activity_choice, self.activity.participant)

    @property
    def additional_info_display(self) -> str:
        return self.additional_info or '-'


class QuestionAnswer(models.Model):
    participant = models.ForeignKey(Participant, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ('question__order',)

    @cached_property
    def cached_participant(self) -> Participant:
        return utils.get_participant(self.participant_id)

    def __str__(self):
        return '%s: %s' % (self.question.question, self.answer)
