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

import logging
import re
from typing import Optional, TYPE_CHECKING, List

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.core.validators import validate_email
from django.db import transaction
from django.forms import ModelForm, Form, fields, PasswordInput, widgets
from django.http import HttpRequest
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit

from . import utils, models

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.http import QueryDict

logger = logging.getLogger('serviceform.forms')


class MyFormHelper(FormHelper):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.form_class = 'form-horizontal'
        self.label_class = 'col-xs-3'
        self.field_class = 'col-xs-9'
        self.form_method = 'post'
        self.form_action = ''


class ReportSettingsForm(Form):
    revision = fields.ChoiceField(label=_('Revision'), required=False)

    # shuffled_data = fields.BooleanField(label=_('Shuffled data (anonymity mode)'), required=False)

    def __init__(self, service_form: models.ServiceForm,
                 request: HttpRequest, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.request = request
        self.instance = service_form

        helper = self.helper = MyFormHelper(self)
        rev_choices = [(rev.name, rev.name) for rev in service_form.formrevision_set.all()]
        rev_choices.append((utils.RevisionOptions.CURRENT, _('Current')))
        rev_choices.append((utils.RevisionOptions.ALL, _('All')))
        self.fields['revision'].choices = rev_choices

        self.set_initial_data()

        helper.form_id = 'form'
        helper.layout.append(Submit('submit', _('Save settings')))

    def set_initial_data(self) -> None:
        report_settings = utils.get_report_settings(self.request)
        for name, f in self.fields.items():
            val = report_settings.get(name)
            f.initial = val

    def save(self) -> None:
        report_settings = {name: self.cleaned_data[name] for name in self.fields.keys()}
        utils.set_report_settings(self.request, report_settings)


class PasswordForm(Form):
    password = fields.CharField(max_length=32, label=_('Password'), widget=PasswordInput)

    def __init__(self, service_form: models.ServiceForm, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        if not service_form.password:
            del self.fields['password']

        helper = self.helper = MyFormHelper(self)

        helper.form_id = 'contactform'
        helper.layout.append(Submit('submit_password', _('Get in')))
        self.instance = service_form

    def clean_password(self):
        if self.cleaned_data.get('password') != self.instance.password:
            raise ValidationError(_('Incorrect password'))
        return self.cleaned_data


class ParticipantSendEmailForm(Form):
    email = fields.EmailField(max_length=128, label=_('Email'))

    def __init__(self, service_form, request, *args, **kwargs):
        super().__init__(*args, **kwargs)
        helper = self.helper = MyFormHelper(self)
        self.request = request
        helper.form_id = 'emailform'
        helper.layout.append(Submit('submit_email', _('Send the link!')))
        self.instance = service_form

    def clean_email(self):
        email = self.cleaned_data['email']
        if email and 'email' in self.changed_data:
            participant = models.Participant.objects.filter(
                email=email,
                form_revision__form=self.instance).first()
            if not participant:
                raise ValidationError(
                    _('There were no participation with email address {}').format(email))
        return email

    def save(self):
        participant = models.Participant.objects.filter(email=self.cleaned_data['email'],
                                                        form_revision__form=self.instance).first()
        success = participant.send_participant_email(models.Participant.EmailIds.RESEND)
        if success:
            messages.info(self.request,
                          _('Access link sent to email address {}').format(participant.email))
        else:
            messages.error(self.request, _('Email could not be sent to email address {}').format(
                participant.email))
        return success


class ResponsibleSendEmailForm(Form):
    email = fields.EmailField(max_length=128, label=_('Email'))

    def __init__(self, service_form: models.ServiceForm, request: HttpRequest,
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        helper = self.helper = MyFormHelper(self)
        self.request = request
        helper.form_id = 'emailform'
        helper.layout.append(Submit('submit_email', _('Send the link!')))
        self.instance = service_form

    def clean_email(self) -> str:
        email = self.cleaned_data['email']
        if email and 'email' in self.changed_data:
            responsible = models.ResponsibilityPerson.objects.filter(email=email,
                                                                     form=self.instance).first()
            if not responsible:
                raise ValidationError(
                    _('There were no responsible with email address {}').format(email))
        return email

    def save(self) -> Optional[models.EmailMessage]:
        responsible = models.ResponsibilityPerson.objects.filter(email=self.cleaned_data['email'],
                                                                 form=self.instance).first()
        success = responsible.resend_auth_link()
        if success:
            messages.info(self.request,
                          _('Access link sent to email address {}').format(responsible.email))
        else:
            messages.error(self.request, _('Email could not be sent to email address {}').format(
                responsible.email))
        return success


class ContactForm(ModelForm):
    class Meta:
        model = models.Participant
        fields = ('forenames', 'surname', 'year_of_birth', 'street_address',
                  'postal_code', 'city', 'email', 'phone_number', 'send_email_allowed')

    def __init__(self, *args, user: 'AbstractUser'=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.participant = self.instance
        self.service_form = self.participant.form
        self.user = user
        self.helper = helper = MyFormHelper(self)
        self._fix_fields()

        helper.form_id = 'contactform'

        if self.service_form.is_published:
            helper.layout.append(
                Submit('submit', _('Continue'), css_class='btn-participation-continue'))
        else:
            helper.layout.append(
                Submit('submit', _('Save details'), css_class='btn-participation-continue'))

    def _fix_fields(self) -> None:
        req = self.service_form.required_street_address
        self.fields['street_address'].required = req
        self.fields['postal_code'].required = req
        self.fields['city'].required = req

        if not self.service_form.visible_street_address:
            del self.fields['street_address']
            del self.fields['postal_code']
            del self.fields['city']

        req = self.service_form.required_year_of_birth
        if not req:
            self.fields['year_of_birth'].help_text = _('Optional')
        self.fields['year_of_birth'].required = req

        if not self.service_form.visible_year_of_birth:
            del self.fields['year_of_birth']

        self.fields['phone_number'].required = self.service_form.required_phone_number
        if not self.service_form.visible_phone_number:
            del self.fields['phone_number']

        if utils.user_has_serviceform_permission(self.user, self.service_form,
                                                 raise_permissiondenied=False):
            self.fields['email'].required = False

    def clean_year_of_birth(self):
        year_of_birth = self.cleaned_data.get('year_of_birth')
        if year_of_birth is None:
            return year_of_birth
        if year_of_birth < 1900:
            raise ValidationError(_('Invalid year of birth'))
        if year_of_birth > timezone.now().year - 10:
            raise ValidationError(_('You must be at least 10 years old'))
        return year_of_birth

    def clean(self):
        cleaned_data = super().clean()
        if ('email' not in self.errors and not self.fields['email'].required and cleaned_data.get(
                'send_email_allowed')
            and not cleaned_data.get('email')):
            raise ValidationError(_('If sending email is allowed email address need to be given'))
        return cleaned_data

    def clean_email(self):
        email = self.cleaned_data['email']
        if email and 'email' in self.changed_data and \
                models.Participant.objects.filter(email=email,
                                                  form_revision__form=self.service_form) \
                        .exclude(pk=self.participant.pk):
            logger.info('User tried to enter same email address %s again.', email)
            email_link = '<a href="{}">{}</a>'.format(reverse('send_auth_link', args=(email,)),
                                                      _('resend auth link to your email!'))
            raise ValidationError(
                mark_safe(_('There is already participation with this email address. '
                            'To edit earlier participation, {}').format(email_link)))
        return email

    def save(self, commit: bool=True):
        if 'email' in self.changed_data:
            self.instance.email_verified = False
        return super().save(commit=commit)


class ResponsibleForm(ModelForm):
    class Meta:
        model = models.ResponsibilityPerson
        fields = ('forenames', 'surname', 'street_address',
                  'postal_code', 'city', 'email', 'phone_number', 'send_email_notifications')

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.helper = helper = MyFormHelper(self)

        helper.form_id = 'responsibleform'
        helper.layout.append(Submit('submit', _('Save details')))


class LogForm(ModelForm):
    class Meta:
        model = models.ParticipantLog
        fields = ('message',)

    def __init__(self, participant: models.Participant, user: 'AbstractUser',
                 *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.instance.participant = participant
        self.instance.written_by = user


class DeleteParticipationForm(Form):
    yes_please = fields.BooleanField(label=_('Yes I am sure'), required=True)

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.helper = helper = MyFormHelper(self)
        helper.layout.append(
            Submit('submit', _('Delete')))  # , css_class='btn-participation-continue'))


class ParticipationForm:
    """
    Special form class for validating and participation data
    Not any standard Django form.
    """

    def __init__(self, request: HttpRequest, participant: models.Participant,
                 category: models.Level1Category=None, post_data: 'QueryDict'=None,
                 service_form: models.ServiceForm=None) -> None:
        self.instance = participant
        self.request = request
        self.post_data = post_data
        self.all_activities = {}
        self.all_choices = {}
        self.selected_choices = set()
        self.selected_activities = set()
        self.activity_errors = []
        self.form = service_form or self.instance.form
        assert getattr(self.form, '_counters_initialized',
                       None), 'Counters are not yet initialized!'
        self.category = category
        self._fetch_instances()
        if participant and not post_data:
            self.load()

    def load(self) -> None:
        participant = self.instance
        for pact in participant.participationactivity_set.all():
            act = self.all_activities.get(pact.activity_id)
            if not act:
                continue
            act.extra = pact.additional_info
            act.selected = True
            self.selected_activities.add(act)

            for pchoice in pact.choices.all():
                choice = self.all_choices[pchoice.activity_choice_id]
                choice.extra = pchoice.additional_info
                choice.selected = True
                self.selected_choices.add(choice)

    def save(self) -> None:
        participant = self.instance
        with transaction.atomic():
            for choice in self.selected_choices:
                self.selected_activities.add(choice.activity)
            participant.participationactivity_set.filter(
                activity_id__in=self.all_activities.keys()).exclude(
                activity__in=self.selected_activities).delete()
            for act in self.selected_activities:
                pact, created = models.ParticipationActivity.objects.get_or_create(
                    participant=participant, activity=act)
                pact.additional_info = getattr(act, 'extra', None)
                pact.save(update_fields=['additional_info'])
            models.ParticipationActivityChoice.objects.filter(activity__participant=participant) \
                .filter(activity_choice_id__in=self.all_choices.keys()) \
                .exclude(activity_choice__in=self.selected_choices).delete()
            for choice in self.selected_choices:
                pact = participant.participationactivity_set.get(activity_id=choice.activity_id)
                pchoice, created = models.ParticipationActivityChoice.objects.get_or_create(
                    activity=pact,
                    activity_choice=choice)
                pchoice.additional_info = getattr(choice, 'extra', None)
                pchoice.save(update_fields=['additional_info'])

    def _fetch_instances(self) -> None:
        categories = [self.category] if self.category else self.form.sub_items

        for cat1 in categories:
            for cat2 in cat1.sub_items:
                for activity in cat2.sub_items:
                    self.all_activities[activity.pk] = activity
                    for choice in activity.sub_items:
                        self.all_choices[choice.pk] = choice

    def is_valid(self) -> bool:
        try:
            self.clean()
        except ValidationError:
            return False
        return not self.errors

    @property
    def errors(self):
        return self.activity_errors

    def clean(self):
        for key, value in self.post_data.items():
            if key.startswith('SRV_'):
                parts = key.split('_')
                if 'EXTRA' in parts:
                    _srv, _type, _extra, _pk = parts
                else:
                    _srv, _type, _pk = parts
                    _extra = None
                _pk = int(_pk)

                if _type in ['ACTIVITY']:
                    if _pk not in self.all_activities:
                        raise ValidationError(_('Invalid activity input data'))
                    item = self.all_activities[_pk]
                    if not _extra:
                        self.selected_activities.add(item)
                        item.selected = True
                elif _type == 'ACTIVITYCHOICE':
                    if _pk not in self.all_activities:
                        raise ValidationError(_('Invalid activity input data'))
                    activity = self.all_activities[_pk]
                    if activity.multiple_choices_allowed:
                        raise ValidationError(_('Invalid input data in radio button'))
                    assert isinstance(value, str)
                    _choice_pk = int(value)
                    if _choice_pk not in self.all_choices:
                        raise ValidationError(_('Invalid choice input data'))
                    item = self.all_choices[_choice_pk]
                    if not _extra:
                        self.selected_choices.add(item)
                        item.selected = True

                elif _type == 'CHOICE':
                    if _pk not in self.all_choices:
                        raise ValidationError(_('Invalid choice input data'))
                    item = self.all_choices[_pk]
                    if not _extra:
                        self.selected_choices.add(item)
                        item.selected = True
                else:
                    raise ValidationError(_('Invalid input data'))

                if _extra:
                    item.extra = value
        for activity in self.selected_activities:
            all_choices = set(activity.activitychoice_set.all())
            if all_choices and not all_choices & self.selected_choices:
                activity.error = _('No choices selected!')
                self.activity_errors.append(activity)

        self.instance.form.errors = self.errors

    def __str__(self):
        return render_to_string(
            'serviceform/participation/participation_form/participation_form.html',
            {'form': self.form, 'service_form': self.form, 'category': self.category},
            request=self.request)


class QuestionForm:
    """
    Special form class for questions.
    Not any standard Django form.
    """

    def __init__(self, request: HttpRequest, participant: models.Participant,
                 post_data: 'QueryDict'=None) -> None:
        self.instance = participant
        self.request = request
        self.data = post_data
        self.questions = {}
        self.question_errors = []
        self._read_questions()

        if not post_data:
            self.load()

    def _read_questions(self):
        for q in self.instance.form.questions:
            self.questions[q.pk] = q

    def load(self):
        participant = self.instance
        for q in participant.questionanswer_set.all():
            question = self.questions[q.question_id]
            question.answer = q.answer

    def save(self):
        participant = self.instance
        with transaction.atomic():
            with_answer = {q for q in self.questions.values() if getattr(q, 'answer', None)}
            participant.questionanswer_set.exclude(question__in=with_answer).delete()
            for q in with_answer:
                q_a, created = models.QuestionAnswer.objects.get_or_create(participant=participant,
                                                                           question=q)
                answer = getattr(q, 'answer', '')
                if q_a.answer != answer:
                    q_a.answer = answer
                    q_a.created_at = timezone.now()
                    q_a.save()

    def is_valid(self):
        try:
            self.clean()
        except ValidationError:
            return False
        return not self.errors

    @property
    def errors(self):
        return self.question_errors

    def clean(self):
        had_values = set()
        for key, value in self.data.items():
            if key.startswith('SRV_'):
                parts = key.split('_')
                if 'EXTRA' in parts:
                    _srv, _type, _extra, _pk = parts
                else:
                    _srv, _type, _pk = parts
                    _extra = None
                _pk = int(_pk)

                assert not _extra

                if _type in ['QUESTION']:
                    if _pk not in self.questions:
                        raise ValidationError(_('Invalid question input data'))
                    item = self.questions[_pk]
                    item.answer = value
                    had_values.add(_pk)

        for q in self.questions.values():
            if q.pk not in had_values:
                q.answer = ""
            if q.required and not getattr(q, 'answer', ''):
                q.error = _('Answer required')
                self.question_errors.append(q)

    def __str__(self):
        return render_to_string('serviceform/participation/question_form/question_form.html',
                                {'participant': self.instance}, request=self.request)


class InviteForm(Form):
    old_participants = fields.BooleanField(required=False, label=_(
        'Send invitations also to participants that have participated in older form versions '
        'but not yet this form'))
    email_addresses = fields.CharField(widget=widgets.Textarea, required=True, label=_(
        'Email addresses, separated by comma, space or enter'))

    def __init__(self, postdata: 'QueryDict'=None, instance: models.ServiceForm=None,
                 **kwargs) -> None:
        super().__init__(postdata, *kwargs)
        helper = self.helper = MyFormHelper(self)

        helper.form_id = 'inviteform'
        helper.layout.append(Submit('submit', _('Send invites')))
        self.service_form = instance

    @staticmethod
    def address_list(email_str: str) -> List[str]:
        return re.sub('[\n, \r]+', ',', email_str).split(',')

    def clean_email_addresses(self):
        if not self.service_form.is_published:
            raise ValidationError(_("Form is not yet published, emails can't be sent"))
        addresses = self.address_list(self.cleaned_data.get('email_addresses', ''))
        errors = []
        for i in addresses:
            try:
                validate_email(i)
            except ValidationError:
                errors.append(ValidationError(_('Invalid email: {}').format(i)))
        if errors:
            raise ValidationError(errors)
        return self.cleaned_data['email_addresses']

    def save(self, request: HttpRequest=None) -> None:
        addresses = self.address_list(self.cleaned_data.get('email_addresses', ''))
        old_participants = self.cleaned_data.get('old_participants')
        for a in addresses:
            InviteUserResponse = models.ServiceForm.InviteUserResponse
            response = self.service_form.invite_user(a, old_participants=old_participants)
            if response == InviteUserResponse.EMAIL_SENT:
                messages.info(request, _('Invitation sent to {}').format(a))
            elif response == InviteUserResponse.USER_EXISTS:
                messages.warning(request, _(
                    'Invitation was not sent to {} because user already exists').format(a))
            elif response == InviteUserResponse.USER_DENIED_EMAIL:
                messages.warning(request, _(
                    'Invitation was not sent to {} because user denied emailing').format(a))
