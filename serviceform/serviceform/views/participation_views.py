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

from .. import forms, models
from ..utils import clean_session, user_has_serviceform_permission, expire_auth_link, decode
from .decorators import require_authenticated_participation, require_published_form

logger = logging.getLogger(__name__)


def contact_details_anonymous(request: HttpRequest) -> HttpResponse:
    """
    Contact details form when there is not yet any data in database.
    """

    # Redirect to contact_details if member is stored in db.

    serviceform_pk = request.session.get('serviceform_pk')
    serviceform = models.ServiceForm.objects.get(pk=serviceform_pk)

    form = forms.ContactForm(user=request.user)

    if request.method == 'POST':
        form = forms.ContactForm(request.POST, user=request.user)
        if form.is_valid():
            member = form.save()
            # Now we can create participation object
            # Try to find existing participation for member on form


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
def contact_details(request: HttpRequest,
                    participation: Optional[models.Participation]) -> HttpResponse:
    if participation and participation.status == models.Participation.STATUS_FINISHED:
        return HttpResponseRedirect(reverse('submitted'))

    if participation:
        member = participation.member
    else:
        member = None

    form = forms.ContactForm(instance=member, user=request.user)

    if request.method == 'POST':
        form = forms.ContactForm(request.POST, instance=member, user=request.user)
        if form.is_valid():
            member = form.save()
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
    if request.session.get('verification_sent', '') != participant.email:
        participant.send_participant_email(models.Participation.EmailIds.EMAIL_VERIFICATION)
        request.session['verification_sent'] = participant.email
    else:
        messages.warning(request,
                         _('Verification email already sent '
                           'to {}, not sending again.').format(participant.email))
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
    clean_session(request)
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


def auth_participant_common(request: HttpRequest, participant: models.Participation, next_view: str,
                            email_verified: bool=True) -> HttpResponse:
    if not participant.email_verified and email_verified:
        participant.email_verified = True
        messages.info(request,
                      _('Your email {} is now verified successfully!').format(participant.email))

    if participant.status == models.Participation.STATUS_FINISHED:
        participant.status = models.Participation.STATUS_UPDATING
    elif participant.status == models.Participation.STATUS_INVITED:
        participant.status = models.Participation.STATUS_ONGOING
    if participant.form_revision != participant.form_revision.form.current_revision:
        participant.last_finished_view = ''
    participant.form_revision = participant.form_revision.form.current_revision
    participant.save(
        update_fields=['status', 'form_revision', 'last_finished_view', 'email_verified'])
    request.session['authenticated_participant'] = participant.pk
    return redirect(next_view)


def authenticate_participant_old(request: HttpRequest, uuid: str,
                                 next_view: str='contact_details') -> HttpResponse:
    """
    Old insecure authentication of participant. Just expire link and send new authentication url.
    """
    if not uuid:
        raise Http404
    clean_session(request)
    participant = get_object_or_404(models.Participation.objects.all(), secret_key=uuid)
    return expire_auth_link(request, participant)


def authenticate_participant(request: HttpRequest, participant_id: int, password: str,
                             next_view: str='contact_details') -> HttpResponse:
    clean_session(request)
    participant = get_object_or_404(models.Participation.objects.all(), pk=participant_id)
    result = participant.check_auth_key(password)
    if result == participant.PasswordStatus.PASSWORD_NOK:
        messages.error(request, _(
            "Given URL might be expired. Please give your "
            "email address and we'll send you a new link"))
        return redirect('send_participant_email', participant.form.slug)

    elif result == participant.PasswordStatus.PASSWORD_EXPIRED:
        return expire_auth_link(request, participant)

    return auth_participant_common(request, participant, next_view)


@login_required(login_url=settings.LOGIN_URL)
def authenticate_participant_mock(request: HttpRequest, participant_id: int,
                                  next_view: str='contact_details') -> HttpResponse:
    clean_session(request)
    participant = get_object_or_404(models.Participation.objects.all(), pk=participant_id)
    user_has_serviceform_permission(request.user, participant.form, raise_permissiondenied=True)
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
            clean_session(request)
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
