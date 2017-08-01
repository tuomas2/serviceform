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

# Celery tasks

import logging

from celery import shared_task
from django.utils import timezone
from datetime import timedelta

from . import models

logger = logging.getLogger('serviceform.tasks')


@shared_task
def cleanup_abandoned_participations():
    logger.info('Deleting abandoned participations')
    models.Participation.objects.filter(last_modified__lt=timezone.now() - timedelta(days=1),
                                        status=models.Participation.STATUS_ONGOING).delete()


@shared_task
def finish_abandoned_updating_participations():
    for p in models.Participation.objects.filter(
            last_modified__lt=timezone.now() - timedelta(days=1),
            status=models.Participation.STATUS_UPDATING):
        logger.info('Finishing abandoned updating participations %s', p)
        p.finish(email_participation=False)


def test_task():
    raise Exception