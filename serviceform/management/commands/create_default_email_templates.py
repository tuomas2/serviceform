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

from django.core.management import BaseCommand
from django.utils.translation import activate
from django.conf import settings
from serviceform.models import ServiceForm


class Command(BaseCommand):
    args = '-'
    help = 'Create default email templates'

    def handle(self, *args, **kwargs):
        activate(settings.LANGUAGE_CODE)
        for s in ServiceForm.objects.all():
            s.create_email_templates()
