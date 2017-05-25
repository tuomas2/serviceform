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
import time
from enum import Enum
from typing import TYPE_CHECKING

from django.conf import settings
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.postgres.fields import JSONField
from django.core.validators import RegexValidator
from django.db import models
from django.db.models.options import Options
from django.urls import reverse
from django.utils import timezone
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

if TYPE_CHECKING:
    from .people import Member

from .. import utils

phone_regex = RegexValidator(regex=r'^\+?1?\d{9,15}$',
                             message=_("Phone number must be entered in the format: "
                                       "'050123123' or '+35850123123'. "
                                       "Up to 15 digits allowed."))
postalcode_regex = RegexValidator(
    regex=r'^\d{5}$',
    message=_('Enter a valid postal code.'),
    code='invalid',
)


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

    def has_responsible(self, r: 'Member') -> bool:
        return r in self._responsibles


#TODO: remove this
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


