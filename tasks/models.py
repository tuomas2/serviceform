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

import json
import logging
from collections import OrderedDict

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger('tasks')


class Task(models.Model):
    REQUESTED = 'requested'
    DONE = 'done'
    ERROR = 'error'
    CANCELED = 'canceled'
    STATUS_STRS = OrderedDict(((REQUESTED, _('Requested')),
                               (DONE, _('Done')),
                               (ERROR, _('Error')),
                               (CANCELED, _('Canceled')),
                               ))
    STATUS_CHOICES = tuple(STATUS_STRS.items())
    scheduled_time = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)

    target_id = models.PositiveIntegerField()
    target_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    target = GenericForeignKey('target_type', 'target_id')

    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=REQUESTED)
    method_name = models.CharField(max_length=64)  # name of target's member function
    data = models.TextField()  # JSON serialized arguments
    result = models.TextField()  # JSON serialized result of function

    def __str__(self):
        return '%s::%s scheduled at %s (%s)'%(self.target, self.method_name, self.scheduled_time, self.status)

    @classmethod
    def make(cls, method, *args, scheduled_time=None, **kwargs):
        target = method.__self__
        method_name = method.__name__

        if scheduled_time is None:
            scheduled_time = timezone.now()

        data = json.dumps((args, kwargs))
        return cls.objects.create(target=target, method_name=method_name, data=data, scheduled_time=scheduled_time)

    def execute(self):
        args, kwargs = json.loads(self.data)
        try:
            func = getattr(self.target, self.method_name)
            result = func(*args, **kwargs)
        except Exception as e:
            logger.exception('Error in processing task %s', self)
            self.status = self.ERROR
        else:
            self.status = self.DONE
            self.result = json.dumps(result)
        self.save()

    def cancel(self):
        self.status = self.CANCELED
        self.save()