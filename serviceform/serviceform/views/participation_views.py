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
from typing import Optional

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _

from .decorators import require_authenticated_participation, require_published_form
from .. import forms, models, utils

logger = logging.getLogger(__name__)


def contact_details_creation(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Member and participation creation.

    Contact details form when there is not yet any data in database.
    Redirect to contact_details if (when) member is stored in db.
    """

    serviceform_pk = request.session.get('serviceform_pk')
    serviceform = get_object_or_404(models.ServiceForm.objects, pk=serviceform_pk)
    if not serviceform.is_published:
        raise RuntimeError(f'Contact detail creation even though form {serviceform}'
                           f' is not published')

    form = forms.ContactForm(user=request.user, serviceform=serviceform)

    if request.method == 'POST':
        form = forms.ContactForm(request.POST, serviceform=serviceform, user=request.user)
        if form.is_valid():
            member = form.save()
            # This member is new, so it cannot have earlier participations in the system.
            # thus we can simply create a new one for him.

            participation = models.Participation.objects.create(
                member=member,
                form_revision=serviceform.current_revision)

            utils.mark_as_authenticated_participant(request, participation)

            return participation.redirect_next(request)

    return render(request, 'serviceform/participation/contact_view.html',
                  {'form': form,
                  # TODO: change service_form -> serviceform everywhere
                   'service_form': serviceform,
                   'bootstrap_checkbox_disabled': True})


@require_authenticated_participation
def contact_details_modification(request: HttpRequest,
                                 participation: models.Participation) -> HttpResponse:
    if participation.status == models.Participation.STATUS_FINISHED:
        return HttpResponseRedirect(reverse('submitted'))

    form = forms.ContactForm(instance=participation.member,
                             serviceform=participation.form,
                             user=request.user)

    if request.method == 'POST':
        form = forms.ContactForm(request.POST,
                                 instance=participation.member,
                                 serviceform=participation.form,
                                 user=request.user)
        if form.is_valid():
            form.save()
            if participation.form.is_published:
                return participation.redirect_next(request)
            else:
                participation.status = models.Participation.STATUS_FINISHED
                participation.save(update_fields=['status'])
                return HttpResponseRedirect(reverse('submitted'))

    return render(request, 'serviceform/participation/contact_view.html',
                  {'form': form,
                   'participant': participation,
                   'service_form': participation.form,
                   'bootstrap_checkbox_disabled': True})


@require_authenticated_participation
@require_published_form
def email_verification(request: HttpRequest, participant: models.Participation) -> HttpResponse:
    service_form = participant.form
    member = participant.member
    if request.session.get('verification_sent', '') != member.email:
        participant.send_participant_email(participant.EmailIds.EMAIL_VERIFICATION)
        request.session['verification_sent'] = member.email
    else:
        messages.warning(request,
                         _('Verification email already sent '
                           'to {}, not sending again.').format(member.email))
    return render(request, 'serviceform/participation/email_verification.html',
                  {'service_form': service_form,
                   'participant': participant,
                   'bootstrap_checkbox_disabled': True})


@require_authenticated_participation
@require_published_form
def participation(request: HttpRequest, participant: models.Participation,
                  cat_num: int) -> HttpResponse:
    cat_num = int(cat_num)
    service_form = participant.form
    service_form.init_counters()

    category = service_form.sub_items[cat_num] if service_form.flow_by_categories else None
    num_categories = len(service_form.sub_items) if category else 0

    if participant.can_access_view(
            participant.next_view_name) or service_form.allow_skipping_categories:
        max_cat = num_categories
    else:
        max_cat = int(request.session.get('max_category', 0))

    if cat_num > max_cat:
        return HttpResponseRedirect(reverse('participation', args=(max_cat,)))

    form = forms.ParticipationForm(request, participant, category)
    if request.method == 'POST':
        form = forms.ParticipationForm(request, participant, category, request.POST)
        if form.is_valid():
            form.save()
            cat_num += 1
            request.session['max_category'] = max(cat_num, max_cat)
            if cat_num >= num_categories:
                return participant.redirect_next(request)
            else:
                return HttpResponseRedirect(reverse('participation', args=(cat_num,)))

    return render(request, 'serviceform/participation/participation_view.html',
                  {'form': form,
                   'service_form': service_form,
                   'cat_num': cat_num,
                   'max_cat': max_cat})


@require_authenticated_participation
@require_published_form
def questions(request: HttpRequest, participant: models.Participation) -> HttpResponse:
    if not participant.form.questions:
        return participant.redirect_next(request)

    form = forms.QuestionForm(request, participant)

    if request.method == 'POST':
        form = forms.QuestionForm(request, participant, request.POST)
        if form.is_valid():
            form.save()
            return participant.redirect_next(request)

    return render(request, 'serviceform/participation/question_view.html',
                  {'form': form, 'service_form': participant.form})


@require_authenticated_participation
@require_published_form
def preview(request: HttpRequest, participant: models.Participation) -> HttpResponse:
    if request.method == 'POST' and 'submit' in request.POST:
        return participant.redirect_next(request, message=False)
    else:
        return render(request, 'serviceform/participation/preview_view.html',
                      {'service_form': participant.form, 'participant': participant})


@require_authenticated_participation
def submitted(request: HttpRequest, participant: models.Participation) -> HttpResponse:
    participant.finish()
    utils.clean_session(request)
    return render(request, 'serviceform/participation/submitted_view.html',
                  {'service_form': participant.form, 'participant': participant})


@require_authenticated_participation(check_flow=False)
def send_auth_link(request: HttpRequest, participant: models.Participation,
                   email: str) -> HttpResponse:
    if not email:
        raise Http404
    p = get_object_or_404(models.Participation, email=email, form_revision__form=participant.form)
    p.send_participant_email(p.EmailIds.RESEND)
    messages.add_message(request, messages.INFO,
                         _('Authentication link was sent to email address {}.').format(email))
    return HttpResponseRedirect(reverse('contact_details'))


def auth_participant_common(request: HttpRequest, participant: models.Participation,
                            next_view: str, email_verified: bool=True) -> HttpResponse:
    member = participant.member
    if not member.email_verified and email_verified:
        member.email_verified = True
        messages.info(request,
                      _('Your email {} is now verified successfully!').format(member.email))

    if participant.status == models.Participation.STATUS_FINISHED:
        participant.status = models.Participation.STATUS_UPDATING
    elif participant.status == models.Participation.STATUS_INVITED:
        participant.status = models.Participation.STATUS_ONGOING
    if participant.form_revision != participant.form_revision.form.current_revision:
        participant.last_finished_view = ''
    participant.form_revision = participant.form_revision.form.current_revision
    member.save(update_fields=['email_verified'])
    participant.save(update_fields=['status', 'form_revision', 'last_finished_view'])
    utils.mark_as_authenticated_participant(request, participant)
    return redirect(next_view)


def authenticate_participant_old(request: HttpRequest, uuid: str,
                                 next_view: str='contact_details') -> HttpResponse:
    """
    Old insecure authentication of participant. Just expire link and send new authentication url.
    """
    if not uuid:
        raise Http404
    utils.clean_session(request)
    participant = get_object_or_404(models.Participation.objects.all(), secret_key=uuid)
    return utils.expire_auth_link(request, participant)


def authenticate_participant(request: HttpRequest, participant_id: int, password: str,
                             next_view: str='contact_details') -> HttpResponse:
    utils.clean_session(request)
    participant = get_object_or_404(models.Participation.objects.all(), pk=participant_id)
    member: models.Member = participant.member
    result = member.check_auth_key(password)
    if result == member.PasswordStatus.PASSWORD_NOK:
        messages.error(request, _(
            "Given URL might be expired. Please give your "
            "email address and we'll send you a new link"))
        return redirect('send_participant_email', participant.form.slug)

    elif result == member.PasswordStatus.PASSWORD_EXPIRED:
        return utils.expire_auth_link(request, participant)

    return auth_participant_common(request, participant, next_view)


@login_required(login_url=settings.LOGIN_URL)
def authenticate_participant_mock(request: HttpRequest, participant_id: int,
                                  next_view: str='contact_details') -> HttpResponse:
    utils.clean_session(request)
    participant = get_object_or_404(models.Participation.objects.all(), pk=participant_id)
    utils.user_has_serviceform_permission(request.user, participant.form, raise_permissiondenied=True)
    return auth_participant_common(request, participant, next_view, email_verified=False)


@require_authenticated_participation(check_flow=False)
def delete_participation(request: HttpRequest, participant: models.Participation) -> HttpResponse:
    form = forms.DeleteParticipationForm()
    service_form = participant.form
    if request.method == 'POST':
        form = forms.DeleteParticipationForm(request.POST)
        if form.is_valid():
            logger.info('Deleting participant %s, per request.', participant)
            participant.delete()
            utils.clean_session(request)
            messages.info(request, _('Your participation was deleted'))
            return redirect('password_login', service_form.slug)

    return render(request, 'serviceform/participation/delete_participation.html',
                  {'form': form, 'service_form': service_form,
                   'bootstrap_checkbox_disabled': True})


def verify_email(request: HttpRequest, participant_id: int, password: str) -> HttpResponse:
    return authenticate_participant(request, participant_id, password, 'participation')


def unsubscribe(request: HttpRequest, secret_id: str) -> HttpResponse:
    participant = get_object_or_404(models.Participation.objects, pk=decode(secret_id))
    participant.send_email_allowed = False
    participant.save(update_fields=['send_email_allowed'])
    return render(request, 'serviceform/login/unsubscribe_participant.html',
                  {'participant': participant,
                   'service_form': participant.form})
