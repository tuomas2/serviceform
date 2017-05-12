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

import time
from django.core.management import BaseCommand
from django.utils import timezone

from tasks.models import Task
from serviceform.utils import DelayedKeyboardInterrupt


class Command(BaseCommand):
    args = '-'
    help = 'Process tasks'

    def handle(self, *args, **kwargs):
        while True:
            tasks = Task.objects.filter(status=Task.REQUESTED, scheduled_time__gte=timezone.now())
            for t in tasks:
                with DelayedKeyboardInterrupt():
                    t.execute()
            time.sleep(60)
