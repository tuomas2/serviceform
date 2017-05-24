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

from typing import Sequence, TYPE_CHECKING

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.functional import cached_property
from .. import utils

if TYPE_CHECKING:
    from .people import Participant

class ParticipantLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    participant = models.ForeignKey('serviceform.Participant', on_delete=models.CASCADE)
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

    participant = models.ForeignKey('serviceform.Participant', on_delete=models.CASCADE)
    activity = models.ForeignKey('serviceform.Activity', on_delete=models.CASCADE)
    additional_info = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    @cached_property
    def cached_participant(self) -> 'Participant':
        return utils.get_participant(self.participant_id)

    def __str__(self):
        return '%s for %s' % (self.activity, self.participant)

    @property
    def choices(self) -> 'Sequence[ParticipationActivityChoice]':
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
    activity_choice = models.ForeignKey('serviceform.ActivityChoice', on_delete=models.CASCADE)
    additional_info = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    @cached_property
    def cached_participant(self) -> 'Participant':
        return utils.get_participant(self.activity.participant_id)

    def __str__(self):
        return '%s for %s' % (self.activity_choice, self.activity.participant)

    @property
    def additional_info_display(self) -> str:
        return self.additional_info or '-'


class QuestionAnswer(models.Model):
    participant = models.ForeignKey('serviceform.Participant', on_delete=models.CASCADE)
    question = models.ForeignKey('serviceform.Question', on_delete=models.CASCADE)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ('question__order',)

    @cached_property
    def cached_participant(self) -> 'Participant':
        return utils.get_participant(self.participant_id)

    def __str__(self):
        return '%s: %s' % (self.question.question, self.answer)