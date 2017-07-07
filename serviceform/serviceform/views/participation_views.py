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

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpRequest, HttpResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.utils.translation import ugettext_lazy as _

from .decorators import require_authenticated_participation, require_published_form, \
    serviceform_from_session, require_authenticated_member
from .. import forms, models, utils

logger = logging.getLogger(__name__)


def contact_details_creation(request: HttpRequest, serviceform_slug: str,
                             **kwargs) -> HttpResponse:
    """
    Member and participation creation.

    Contact details form when there is not yet any data in database.
    Redirect to contact_details if (when) member is stored in db.
    """
    serviceform = get_object_or_404(models.ServiceForm.objects, slug=serviceform_slug)

    if not utils.is_serviceform_password_authenticated(request, serviceform):
        raise PermissionDenied

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
                last_finished_view='contact_details',
                form_revision=serviceform.current_revision)

            utils.mark_as_authenticated_member(request, member)
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
        return HttpResponseRedirect(reverse('submitted', args=(participation.form.slug,)))

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
                return HttpResponseRedirect(reverse('submitted', args=(participation.form.slug,)))

    return render(request, 'serviceform/participation/contact_view.html',
                  {'form': form,
                   'participation': participation,
                   'service_form': participation.form,
                   'bootstrap_checkbox_disabled': True})


def contact_details(request: HttpRequest, service_form_slug: str, **kwargs) -> HttpResponse:
    member = utils.get_authenticated_member(request)
    if member:
        return contact_details_modification(request, service_form_slug, **kwargs)
    else:
        return contact_details_creation(request, service_form_slug, **kwargs)


@require_authenticated_participation
@require_published_form
def email_verification(request: HttpRequest, participation: models.Participation) -> HttpResponse:
    service_form = participation.form
    member = participation.member
    if request.session.get('verification_sent', '') != member.email:
        participation.send_participation_email(participation.EmailIds.EMAIL_VERIFICATION)
        request.session['verification_sent'] = member.email
    else:
        messages.warning(request,
                         _('Verification email already sent '
                           'to {}, not sending again.').format(member.email))
    return render(request, 'serviceform/participation/email_verification.html',
                  {'service_form': service_form,
                   'participation': participation,
                   'bootstrap_checkbox_disabled': True})


@require_authenticated_participation
@require_published_form
def participation(request: HttpRequest, participation: models.Participation,
                  cat_num: int) -> HttpResponse:
    cat_num = int(cat_num)
    service_form = participation.form
    service_form.init_counters()

    category = service_form.sub_items[cat_num] if service_form.flow_by_categories else None
    num_categories = len(service_form.sub_items) if category else 0

    if participation.can_access_view(
            participation.next_view_name) or service_form.allow_skipping_categories:
        max_cat = num_categories
    else:
        max_cat = int(request.session.get('max_category', 0))

    if cat_num > max_cat:
        return HttpResponseRedirect(reverse('participation', args=(service_form.slug, max_cat,)))

    form = forms.ParticipationForm(request, participation, category)
    if request.method == 'POST':
        form = forms.ParticipationForm(request, participation, category, request.POST)
        if form.is_valid():
            form.save()
            cat_num += 1
            request.session['max_category'] = max(cat_num, max_cat)
            if cat_num >= num_categories:
                return participation.redirect_next(request)
            else:
                return HttpResponseRedirect(reverse('participation',
                                                    args=(service_form.slug, cat_num,)))

    return render(request, 'serviceform/participation/participation_view.html',
                  {'form': form,
                   'service_form': service_form,
                   'cat_num': cat_num,
                   'max_cat': max_cat})


@require_authenticated_participation
@require_published_form
def questions(request: HttpRequest, participation: models.Participation) -> HttpResponse:
    if not participation.form.questions:
        return participation.redirect_next(request)

    form = forms.QuestionForm(request, participation)

    if request.method == 'POST':
        form = forms.QuestionForm(request, participation, request.POST)
        if form.is_valid():
            form.save()
            return participation.redirect_next(request)

    return render(request, 'serviceform/participation/question_view.html',
                  {'form': form, 'service_form': participation.form})


@require_authenticated_participation
@require_published_form
def preview(request: HttpRequest, participation: models.Participation) -> HttpResponse:
    if request.method == 'POST' and 'submit' in request.POST:
        return participation.redirect_next(request, message=False)
    else:
        return render(request, 'serviceform/participation/preview_view.html',
                      {'service_form': participation.form, 'participation': participation})


@require_authenticated_participation
def submitted(request: HttpRequest, participation: models.Participation) -> HttpResponse:
    participation.finish()
    utils.clean_session(request)
    return render(request, 'serviceform/participation/submitted_view.html',
                  {'service_form': participation.form, 'participation': participation})


@serviceform_from_session
def send_auth_link(request: HttpRequest,
                   serviceform: models.ServiceForm, email: str) -> HttpResponse:
    if not email:
        raise Http404

    authenticated = (utils.get_authenticated_serviceform(request)
                     or utils.get_authenticated_member(request))
    if not authenticated:
        raise PermissionDenied

    m = get_object_or_404(models.Member, email=email, organization=authenticated.organization)
    m.resend_auth_link()
    messages.add_message(request, messages.INFO,
                         _('Authentication link was sent to email address {}.').format(email))
    return HttpResponseRedirect(reverse('contact_details', args=(serviceform.slug,)))


@require_authenticated_participation(check_flow=False)
def update_participation(request: HttpRequest,
                         participation: models.Participation) -> HttpResponse:
    if participation.status == models.Participation.STATUS_FINISHED:
        participation.status = models.Participation.STATUS_UPDATING
    elif participation.status == models.Participation.STATUS_INVITED:
        participation.status = models.Participation.STATUS_ONGOING
    if participation.form_revision != participation.form_revision.form.current_revision:
        participation.last_finished_view = ''
    participation.form_revision = participation.form_revision.form.current_revision
    participation.save(update_fields=['status', 'form_revision', 'last_finished_view'])
    return redirect(reverse('contact_details', args=(participation.form.slug,)))


def authenticate_participation_old(request: HttpRequest, uuid: str,
                                 next_view: str='contact_details') -> HttpResponse:
    """
    Old insecure authentication of participation. Just expire link and send new authentication url.
    """
    if not uuid:
        raise Http404
    utils.clean_session(request)
    participation = get_object_or_404(models.Participation.objects.all(), secret_key=uuid)
    return utils.expire_auth_link(request, participation)


def authenticate_member(request: HttpRequest, member_id: int, password: str) -> HttpResponse:
    # TODO: create main entrypoint for members, which is default
    next_url = request.GET.get('next', reverse('member_main'))

    utils.clean_session(request)
    member: models.Member = get_object_or_404(models.Member.objects, pk=member_id)
    result = member.check_auth_key(password)
    if result == member.PasswordStatus.PASSWORD_NOK:
        messages.error(request, _(
            "Given URL might be expired. Please give your "
            "email address and we'll send you a new link"))
        # TODO: create generic send_member_auth_link view (similar to send_participation_link view)
        return redirect('send_member_auth_link')

    elif result == member.PasswordStatus.PASSWORD_EXPIRED:
        return utils.expire_auth_link(request, member)
    if not member.email_verified:
        member.email_verified = True
        member.save(update_fields=['email_verified'])
        messages.info(request,
                      _('Your email {} is now verified successfully!').format(member.email))

    utils.mark_as_authenticated_member(request, member)
    return redirect(next_url)


@login_required(login_url=settings.LOGIN_URL)
def authenticate_member_mock(request: HttpRequest, member_id: int) -> HttpResponse:
    next_url = request.GET.get('next', reverse('member_main'))
    utils.clean_session(request)
    member: models.Member = get_object_or_404(models.Member.objects, pk=member_id)
    utils.mark_as_authenticated_member(request, member)
    return redirect(next_url)


@require_authenticated_participation(check_flow=False)
def delete_participation(request: HttpRequest, participation: models.Participation) -> HttpResponse:
    form = forms.DeleteParticipationForm()
    service_form = participation.form
    if request.method == 'POST':
        form = forms.DeleteParticipationForm(request.POST)
        if form.is_valid():
            logger.info('Deleting participation %s, per request.', participation)
            participation.delete()
            utils.clean_session(request)
            messages.info(request, _('Your participation was deleted'))
            return redirect('password_login', service_form.slug)

    return render(request, 'serviceform/participation/delete_participation.html',
                  {'form': form, 'service_form': service_form,
                   'bootstrap_checkbox_disabled': True})


def unsubscribe(request: HttpRequest, secret_id: str) -> HttpResponse:
    participation = get_object_or_404(models.Participation.objects, pk=utils.decode(secret_id))
    participation.member.allow_participation_email = False
    participation.member.save(update_fields=['allow_participation_email'])
    return render(request, 'serviceform/login/unsubscribe_participation.html',
                  {'participation': participation,
                   'service_form': participation.form})


# see update_participation...
#@require_authenticated_member
#def member_update_form(request: HttpRequest, member: models.Member,
#                       serviceform_slug: str) -> HttpResponse:
#    participation = member.participation_set.get(form_revision__form__slug=serviceform_slug)
#    # TODO: should create better entry point for updating form.
#    return render(request, 'serviceform/participation/preview_view.html',
#                  {'service_form': participation.form, 'participation': participation})
