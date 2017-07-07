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
from typing import Optional, TYPE_CHECKING, Union, Iterator, List
import logging

import time

import datetime
from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.postgres.fields import JSONField
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _
from django.utils import timezone

from .email import EmailMessage, EmailTemplate
from .mixins import postalcode_regex, phone_regex
from .. import utils, emails


if TYPE_CHECKING:
    from .participation import Participation
    from .serviceform import ServiceForm

logger = logging.getLogger(__name__)


class Organization(models.Model):
    name = models.CharField(_('Organization name'), max_length=64)

    email_to_member_auth_link = models.ForeignKey(
        EmailTemplate, null=True, blank=True,
        related_name='+',
        verbose_name=_('Auth link email to member'), help_text=_(
            'Email that is sent to member when auth link is requested'),
        on_delete=models.SET_NULL)

    def create_initial_data(self) -> None:
        self.create_email_templates()
        self.save()

    def create_email_templates(self) -> None:
        if not self.pk:
            logger.error('Cannot create email template if form is not saved')
            return

        commit = False
        if not self.email_to_member_auth_link:
            commit = True
            self.email_to_member_auth_link = EmailTemplate.make(
                _('Default auth link to member email'), self,
                emails.email_to_member_auth_link,
                _('Your authentication link to access your data in {{organization}}'))

        if commit:
            self.save()


class Member(models.Model):
    class PasswordStatus(Enum):
        PASSWORD_EXPIRED = object()
        PASSWORD_OK = True
        PASSWORD_NOK = False

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

    # New style auth link hash
    auth_keys_hash_storage = JSONField(default=[])  # List of (hash, expire) tuples

    # TODO: remove this field (as well as views using it) when all users are having new auth_key_hash set up.
    secret_key = models.CharField(max_length=36, default=utils.generate_uuid, db_index=True,
                                  unique=True,
                                  verbose_name=_('Secret key'))


    allow_responsible_email = models.BooleanField(
        default=True,
        verbose_name=_('Send email notifications'),
        help_text=_(
            'Send email notifications whenever new participation to administered activities is '
            'registered. Email contains also has a link that allows accessing raport of '
            'administered activities.'))

    allow_participation_email = models.BooleanField(
        default=True,
        verbose_name=_('Send email notifications'),
        help_text=_(
        'You will receive email that contains a link that allows later modification of the form. '
        'Also when new version of form is published, you will be notified. '
        'It is highly recommended that you keep this enabled unless you move away '
        'and do not want to participate at all any more. You can also change this setting later '
        'if you wish.'))

    # TODO: rename: allow_showing_contact_details_in_forms etc.
    hide_contact_details = models.BooleanField(_('Hide contact details in form'), default=False)
    # TODO: this should be per-form (grant access to 1 form only). Or could it be per-organization?
    show_full_report = models.BooleanField(_('Grant access to full reports'), default=False)

    # TODO change view name
    def personal_link(self) -> str:
        return format_html('<a href="{}">{}</a>',
                           reverse('authenticate_participation_mock', args=(self.pk,)),
                           self.pk)

    personal_link.short_description = _('Link to personal report')

    @property
    def secret_id(self) -> str:
        return utils.encode(self.id)

    # TODO: change view name
    @property
    def list_unsubscribe_link(self) -> str:
        return settings.SERVER_URL + reverse('unsubscribe_participation', args=(self.secret_id,))


    @cached_property
    def age(self) -> Union[int, str]:
        return timezone.now().year - self.year_of_birth if self.year_of_birth else '-'

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
        # TODO: rename view as generic authenticate_member
        return settings.SERVER_URL + reverse('authenticate_member',
                                             args=(self.pk, self.make_new_password(),))

    def check_auth_key(self, password: str) -> PasswordStatus:
        for key, expire_timestamp in reversed(self.auth_keys_hash_storage):
            if check_password(password, key):
                if expire_timestamp < time.time():
                    return self.PasswordStatus.PASSWORD_EXPIRED
                return self.PasswordStatus.PASSWORD_OK

        return self.PasswordStatus.PASSWORD_NOK

    def __str__(self):
        if self.forenames or self.surname:
            return '%s %s' % (self.forenames.title(), self.surname.title())
        else:
            return self.email

    @property
    def member(self) -> 'Member':
        """Convenience property, to make Participation and Member interfaces
        similar for templates"""
        return self

    @property
    def address(self):
        return ('%s\n%s %s' % (
            self.street_address.title(), self.postal_code, self.city.title())).strip()


    @property
    def contact_details(self) -> Iterator[str]:
        yield _('Name'), '%s %s' % (self.forenames.title(), self.surname.title())
        if self.email:
            yield _('Email'), self.email
        if self.phone_number:
            yield _('Phone number'), self.phone_number
        if self.address:
            yield _('Address'), '\n' + self.address
        yield _('Year of birth'), self.year_of_birth or '-'

    @property
    def contact_display(self):
        return '\n'.join('%s: %s' % (k, v) for k, v in self.contact_details)

    @cached_property
    def item_count(self) -> int:
        return utils.count_for_responsible(self)

    def personal_link(self) -> str:
        return format_html('<a href="{}">{}</a>',
                           reverse('authenticate_mock', args=(self.pk,)),
                           self.pk) if self.pk else ''

    personal_link.short_description = _('Link to personal report')

    @property
    def secret_id(self) -> str:
        return utils.encode(self.id)

    # TODO: common unsubscribe -- rename view
    @property
    def list_unsubscribe_link(self) -> str:
        return settings.SERVER_URL + reverse('unsubscribe_responsible', args=(self.secret_id,))

    # TODO: rename to 'send_auth_link'
    def resend_auth_link(self) -> 'EmailMessage':
        context = {'member': str(self), # TODO: check context (responsible -> member)
                   'url': self.make_new_auth_url(),
                   #  TODO we might need organization contact details here?
                   #'contact': self.form.responsible.contact_display,
                   'list_unsubscribe': self.list_unsubscribe_link,
                   }
        # TODO: more generic auth link email to organization member (not responsible nor participation)
        # TODO auth link email should be per-organization, not per-form. Members will be shared between forms.
        return EmailMessage.make(self.organization.email_to_member_auth_link, context, self.email)

    def send_responsibility_email(self, participation: 'Participation') -> None:
        if self.allow_responsible_email:
            next = reverse('responsible_report', args=(participation.form.slug,))
            context = {'responsible': str(self),
                       'participation': str(participation),
                       'form': str(participation.form),
                       'url': self.make_new_auth_url() + f'?next={next}',
                       'contact': participation.form.responsible.contact_display,
                       'list_unsubscribe': self.list_unsubscribe_link,
                       }

            EmailMessage.make(participation.form.email_to_responsibles, context, self.email)

    def send_bulk_mail(self) -> 'Optional[EmailMessage]':
        # FIXME
        if self.allow_responsible_email:
            context = {'responsible': str(self),
                       'form': str(self.form),
                       'url': self.make_new_auth_url(),
                       'contact': self.form.responsible.contact_display,
                       'list_unsubscribe': self.list_unsubscribe_link,
                       }
            return EmailMessage.make(self.form.bulk_email_to_responsibles, context, self.email)

    @property
    def forms_responsible(self) -> 'List[ServiceForm]':
        """
        Return list of serviceform where this member is assigned as responsible to a activity etc.
        """
        # TODO: implement this.
        return []