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

from typing import TYPE_CHECKING

from django.core.validators import RegexValidator
from django.db import models
from django.db.models.options import Options
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

if TYPE_CHECKING:
    from .people import Member

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

