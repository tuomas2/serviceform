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
from typing import Sequence, TYPE_CHECKING, Union, Iterator, Tuple, List, Optional

from django.contrib import messages

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import localize
from django.utils.functional import cached_property
from django.utils.translation import ugettext_lazy as _

from .. import utils

if TYPE_CHECKING:
    from .email import EmailMessage
    from .serviceform import ServiceForm


class Participation(models.Model):
    class Meta:
        verbose_name = _('Participation')
        verbose_name_plural = _('Participations')
        # TODO: unique together: member + form?

    # Current view is set by view decorator require_authenticated_participant
    _current_view = 'contact_details'

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

    member = models.ForeignKey('serviceform.Member', on_delete=models.CASCADE)
    status = models.CharField(max_length=16, choices=STATUS_CHOICES, default=STATUS_ONGOING)
    last_finished_view = models.CharField(max_length=32, default='')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_('Created at'))
    last_modified = models.DateTimeField(auto_now=True, verbose_name=_('Last modified'))
    last_finished = models.DateTimeField(_('Last finished'), null=True)

    # Last form revision
    form_revision = models.ForeignKey('serviceform.FormRevision', null=True,
                                      on_delete=models.CASCADE)

    @property
    def is_updating(self) -> bool:
        return self.status == self.STATUS_UPDATING

    def __str__(self):
        return f'Participation for {self.member} in {self.form}'

    @property
    def additional_data(self) -> Iterator[Tuple[str, str]]:
        yield _('Participation created in system'), self.created_at
        yield _('Last finished'), self.last_finished
        yield _('Last modified'), self.last_modified
        # TODO: these need to be shown in Member view
        #yield _('Email address verified'), (_('No'), _('Yes'))[self.email_verified]
        #yield _('Emails allowed'), (_('No'), _('Yes'))[self.send_email_allowed]
        yield _('Form status'), self.STATUS_DICT[self.status]

    @cached_property
    def item_count(self) -> int:
        choices = ParticipationActivityChoice.objects.filter(
            activity__participant=self).values_list('activity_id', flat=True)
        choice_count = len(choices)
        activity_count = self.participationactivity_set.exclude(pk__in=choices).count()
        return activity_count + choice_count

    @cached_property
    def activities(self) -> 'Sequence[ParticipationActivity]':
        return self.participationactivity_set.select_related('activity')

    @cached_property
    def questions(self) -> 'Sequence[QuestionAnswer]':
        return self.questionanswer_set.select_related('question')

    def activities_display(self) -> str:
        return ', '.join(a.activity.name for a in self.activities)

    activities_display.short_description = _('Activities')

    @cached_property
    def form(self) -> 'Optional[ServiceForm]':
        return self.form_revision.form if self.form_revision else None

    def form_display(self) -> str:
        return str(self.form)

    form_display.short_description = _('Form')

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
                               extra_context: dict=None) -> 'Optional[EmailMessage]':
        """
        Send email to participant
        :return: False if email was not sent. Message if it was sent.
        """
        from .email import EmailMessage
        if not self.member.allow_participant_email and event not in self.SEND_ALWAYS_EMAILS:
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
        url_postfix = (f"?next={reverse('participation', args=(self.form.slug,))}"
                       if event == self.EmailIds.EMAIL_VERIFICATION
                       else f"?next={reverse('update_participation', args=(self.form.slug,))}")
        url = self.member.make_new_auth_url() + url_postfix

        context = {
            'participant': str(self),
            'contact': self.form.responsible.contact_display,
            'form': str(self.form),
            'url': str(url),
            'last_modified': localize(self.last_modified, use_l10n=True),
            'list_unsubscribe': self.member.list_unsubscribe_link,
        }
        if extra_context:
            context.update(extra_context)
        return EmailMessage.make(emailtemplate, context, self.member.email)

    def resend_auth_link(self) -> 'Optional[EmailMessage]':
        return self.send_participant_email(self.EmailIds.RESEND)

    @property
    def flow(self) -> List[str]:
        from ..urls import participant_flow_urls

        rv = [i.name for i in participant_flow_urls]
        if not self.form.questions:
            rv.remove('questions')
        if not self.form.require_email_verification or self.member.email_verified:
            rv.remove('email_verification')
        if self.form.require_email_verification and not self.member.email:
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
        return HttpResponseRedirect(reverse(self.next_view_name, args=(self.form.slug,)))

    def redirect_last(self) -> HttpResponse:
        last = self.flow.index(
            self.last_finished_view) if self.last_finished_view in self.flow else -1
        return HttpResponseRedirect(reverse(self.flow[last + 1], args=(self.form.slug,)))

    @cached_property
    def log(self) -> 'Sequence[ParticipantLog]':
        return self.participantlog_set.all()


class ParticipationActivity(models.Model):
    class Meta:
        unique_together = (('participant', 'activity'),)
        ordering = (
        'activity__category__category__order', 'activity__category__order', 'activity__order',)

    participant = models.ForeignKey(Participation, on_delete=models.CASCADE)
    activity = models.ForeignKey('serviceform.Activity', on_delete=models.CASCADE)
    additional_info = models.CharField(max_length=1024, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    @cached_property
    def cached_participant(self) -> 'Participation':
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
    def cached_participant(self) -> 'Participation':
        return utils.get_participant(self.activity.participant_id)

    def __str__(self):
        return '%s for %s' % (self.activity_choice, self.activity.participant)

    @property
    def additional_info_display(self) -> str:
        return self.additional_info or '-'


class QuestionAnswer(models.Model):
    participant = models.ForeignKey('serviceform.Participation', on_delete=models.CASCADE)
    question = models.ForeignKey('serviceform.Question', on_delete=models.CASCADE)
    answer = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ('question__order',)

    @cached_property
    def cached_participant(self) -> 'Participation':
        return utils.get_participant(self.participant_id)

    def __str__(self):
        return '%s: %s' % (self.question.question, self.answer)


class ParticipantLog(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    participant = models.ForeignKey('serviceform.Participation', on_delete=models.CASCADE)
    writer_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    writer_id = models.PositiveIntegerField()
    # Can be either responsible or django user
    written_by = GenericForeignKey('writer_type', 'writer_id')
    message = models.TextField()
