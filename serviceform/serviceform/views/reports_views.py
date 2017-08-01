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

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import reverse
from django.http import HttpResponseRedirect, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.utils.translation import gettext_lazy as _

from .. import models, forms
from ..utils import user_has_serviceform_permission, fetch_participations, expire_auth_link, decode, \
    RevisionOptions, get_authenticated_member
from .decorators import require_serviceform, require_authenticated_member


#def authenticate_responsible_old(request: HttpRequest, uuid: str) -> HttpResponse:
#    """
#    Just expire old and insecure authrorization link if such is being used and send a new one.
#    """
#    if not uuid:
#        raise Http404
#    responsible = get_object_or_404(models.Member.objects.all(), secret_key=uuid)
#    return expire_auth_link(request, responsible)
#
#
#def authenticate_responsible(request: HttpRequest, responsible_id: int,
#                             password: str) -> HttpResponse:
#    responsible = get_object_or_404(models.Member.objects.all(), pk=responsible_id)
#    result = responsible.check_auth_key(password)
#    if result == responsible.PasswordStatus.PASSWORD_NOK:
#        messages.error(request, _(
#            "Given URL might be expired. Please give your email address and we'll send "
#            "you a new link"))
#        return redirect('send_responsible_email', responsible.form.slug)
#    elif result == responsible.PasswordStatus.PASSWORD_EXPIRED:
#        return expire_auth_link(request, responsible)
#
#    request.session['authenticated_responsibility'] = responsible.pk
#    return HttpResponseRedirect(reverse('responsible_report'))


#@login_required(login_url=settings.LOGIN_URL)
#def authenticate_responsible_mock(request: HttpRequest, responsible_id: int) -> HttpResponse:
#    """
#    Mocked authentication to responsible view from admin panel
#    """
#    responsible = get_object_or_404(models.Member.objects.all(), pk=responsible_id)
#    user_has_serviceform_permission(request.user, responsible.form, raise_permissiondenied=True)
#
#    request.session['authenticated_responsibility'] = responsible.pk
#    return HttpResponseRedirect(reverse('responsible_report'))


@require_serviceform(check_form_permission=True)
def settings_view(request: HttpRequest, service_form: models.ServiceForm) -> HttpResponse:
    form = forms.ReportSettingsForm(service_form, request)
    if request.method == 'POST':
        form = forms.ReportSettingsForm(service_form, request, request.POST)
        if form.is_valid():
            form.save()
            messages.info(request, _('Settings saved'))
        else:
            messages.error(request, _('Settings could not be saved'))
            # return HttpResponseRedirect('') # TODO: why does this not work?
    return render(request, 'serviceform/reports/settings.html',
                  {'service_form': service_form, 'form': form})


@require_serviceform(check_form_permission=True, init_counters=True)
def all_responsibles(request: HttpRequest, service_form: models.ServiceForm) -> HttpResponse:
    return render(request, 'serviceform/reports/all_responsibles.html',
                  {'service_form': service_form})


@require_serviceform(check_form_permission=True, fetch_participations=True)
def all_participations(request: HttpRequest, service_form: models.ServiceForm) -> HttpResponse:
    return render(request, 'serviceform/reports/all_participations.html',
                  {'service_form': service_form})


@require_serviceform(check_form_permission=True, init_counters=True, fetch_participations=True)
def all_activities(request: HttpRequest, service_form: models.ServiceForm) -> HttpResponse:
    return render(request, 'serviceform/reports/all_activities.html',
                  {'service_form': service_form})


@require_serviceform(check_form_permission=True, init_counters=True, fetch_participations=True)
def all_questions(request: HttpRequest, service_form: models.ServiceForm) -> HttpResponse:
    return render(request, 'serviceform/reports/all_questions.html',
                  {'service_form': service_form})


@require_authenticated_member
def view_participation(request: HttpRequest, responsible: models.Member,
                     participation_id: int) -> HttpResponse:
    participation = get_object_or_404(models.Participation.objects, pk=participation_id)
    anonymous = False

    if request.user.pk:
        user_has_serviceform_permission(request.user, participation.form)
        user = request.user
    else:
        if responsible.form != participation.form:
            raise PermissionDenied
        user = responsible
        anonymous = True

    if request.method == 'POST':
        form = forms.LogForm(participation, user, request.POST)
        if form.is_valid():
            form.save()
        return HttpResponseRedirect(reverse('view_user', args=(participation_id,)))

    form = forms.LogForm(participation, user)
    service_form = participation.form
    return render(request, 'serviceform/reports/view_participation.html',
                  {'service_form': service_form, 'participation': participation, 'log_form': form,
                   'anonymous': anonymous})


@require_authenticated_member
def view_responsible(request: HttpRequest, auth_responsible: models.Member,
                     responsible_pk: int, form_slug: str) -> HttpResponse:
    responsible = models.Member.objects.get(pk=responsible_pk)
    service_form = models.ServiceForm.objects.get(slug=form_slug)
    if not user_has_serviceform_permission(request.user, service_form,
                                           raise_permissiondenied=False):
            # TODO: show_full_report must be changed to be per-form m2m list
#            or (auth_responsible and auth_responsible.show_full_report
#                and responsible.form == auth_responsible.form)):
        raise PermissionDenied
    # TODO why do we do this?
    request.service_form = service_form
    service_form.init_counters()
    fetch_participations(service_form, revision_name=RevisionOptions.ALL)
    return render(request, 'serviceform/reports/responsible.html',
                  {'service_form': service_form, 'responsible': responsible,
                   'show_report_btn': True})


@require_authenticated_member
def preview_form(request: HttpRequest, responsible: models.Member,
                 slug: str) -> HttpResponse:
    service_form = get_object_or_404(models.ServiceForm.objects, slug=slug)
    user_has_serviceform_permission(request.user, service_form)
    service_form.init_counters()
    form = forms.ParticipationForm(request, None, None, service_form=service_form)
    return render(request, 'serviceform/participation/participation_view.html',
                  {'form': form, 'service_form': service_form, 'readonly': True})


@require_authenticated_member
def preview_printable(request: HttpRequest, responsible: models.Member,
                      slug: str) -> HttpResponse:
    service_form = get_object_or_404(models.ServiceForm.objects, slug=slug)
    user_has_serviceform_permission(request.user, service_form)
    service_form.init_counters()
    return render(request, 'serviceform/preview_printable.html',
                  {'form': service_form, 'preview': True, 'printable': True})


# TODO: rename view and variables
@require_authenticated_member
def edit_responsible(request: HttpRequest,
                     responsible: models.Member) -> HttpResponse:
    if responsible is None:
        raise PermissionDenied
    form = forms.ResponsibleForm(instance=responsible)
    if request.method == 'POST':
        form = forms.ResponsibleForm(request.POST, instance=responsible)
        if form.is_valid():
            form.save()
            messages.info(request, _('Saved contact details'))
    return render(request, 'serviceform/reports/edit_responsible.html',
                  {'form': form, 'responsible': responsible})


@require_authenticated_member
def responsible_report(request: HttpRequest,
                       responsible: models.Member,
                       serviceform_slug: str) -> HttpResponse:
    if responsible is None:
        raise PermissionDenied
    service_form = get_object_or_404(models.ServiceForm.objects, slug=serviceform_slug)
    service_form.init_counters(all_responsibles=True)
    fetch_participations(service_form, revision_name=RevisionOptions.ALL)
    return render(request, 'serviceform/reports/responsible_anonymous.html',
                  {'service_form': service_form, 'responsible': responsible})


def logout_view(request: HttpRequest, **kwargs) -> HttpResponse:
    logout(request)
    messages.info(request, _('You have been logged out'))
    return HttpResponseRedirect(reverse('main_page'))


@login_required(login_url=settings.LOGIN_URL)
def invite(request: HttpRequest, serviceform_slug: str, **kwargs) -> HttpResponse:
    service_form = get_object_or_404(models.ServiceForm.objects, slug=serviceform_slug)
    user_has_serviceform_permission(request.user, service_form)

    if request.method == 'POST':
        form = forms.InviteForm(request.POST, instance=service_form)
        if form.is_valid():
            form.save(request=request)
            return HttpResponseRedirect(reverse('invite', args=(service_form.slug,)))
        else:
            return render(request, 'serviceform/reports/invite.html',
                          {'form': form, 'service_form': service_form})
    else:
        form = forms.InviteForm(instance=service_form)
        return render(request, 'serviceform/reports/invite.html',
                      {'form': form, 'service_form': service_form})


#TODO: make authentication per-form
@require_authenticated_member
def to_full_report(request: HttpRequest, member: models.Member,
                   serviceform_slug: str) -> HttpResponse:
    if not member.show_full_report:
        raise PermissionDenied

    #serviceform = models.ServiceForm.objects.get(slug=serviceform_slug)

    return redirect('report', serviceform_slug)


def unsubscribe(request: HttpRequest, secret_id: str) -> HttpResponse:
    responsible: models.Member = get_object_or_404(models.Member.objects, pk=decode(secret_id))
    responsible.allow_responsible_email = False
    responsible.allow_participation_email = False
    responsible.save(update_fields=['allow_responsible_email', 'allow_participation_email'])
    return render(request, 'serviceform/login/unsubscribe_member.html',
                  {'responsible': responsible})


@require_authenticated_member
def member_main(request: HttpRequest, member: models.Member):
    return render(request, 'serviceform/member/main.html', {'member': member})