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

from typing import Optional, TYPE_CHECKING

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property
from django.utils.html import format_html
from django.utils.translation import ugettext_lazy as _

from .email import EmailMessage
from .mixins import PasswordMixin, postalcode_regex, phone_regex
from .. import utils


if TYPE_CHECKING
    from .participation import Participation

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
        context = {'responsible': str(self),
                   'form': str(self.form),
                   'url': self.make_new_auth_url(),
                   'contact': self.form.responsible.contact_display,
                   'list_unsubscribe': self.list_unsubscribe_link,
                   }
        return EmailMessage.make(self.form.email_to_responsible_auth_link, context, self.email)

    def send_responsibility_email(self, participant: 'Participation') -> None:
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

