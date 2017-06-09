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

from functools import wraps

from django.conf import settings
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.urlresolvers import resolve
from django.http import Http404, HttpResponseRedirect, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404

from .. import models, utils

# TODO: perhaps still bad name
def require_serviceform(function=None, check_form_permission=False, init_counters=False,
                        all_responsibles=True, fetch_participants=False):
    def actual_decorator(func):
        @wraps(func)
        def wrapper(request: HttpRequest, slug: str,
                    *args, **kwargs) -> HttpResponse:
            service_form = get_object_or_404(models.ServiceForm.objects, slug=slug)
            request.service_form = service_form
            # TODO: serviceform document loading form cache (-> no more init_counters etc.)
            if init_counters:
                service_form.init_counters(all_responsibles)
            if fetch_participants:
                revision_name = utils.get_report_settings(request, 'revision')
                utils.fetch_participants(service_form, revision_name=revision_name)
            func_ = require_form_permissions(func) if check_form_permission else func
            return func_(request, service_form, *args)

        return wrapper

    if function:
        return actual_decorator(function)
    return actual_decorator


def require_authenticated_responsible(func):
    @wraps(func)
    def wrapper(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        responsible = utils.get_authenticated_member(request)
        if responsible:
            request.service_form = responsible.form
        if request.user.pk or responsible:
            return func(request, responsible, *args)
        else:
            raise PermissionDenied

    return wrapper


def require_authenticated_participation(function=None, check_flow=True, accept_anonymous=False):
    """
    These urls in contain serviceform_slug as first argument.
    They require that member is authenticated, and because a member can have
    only 1 participation in a serviceform, we can identify participation from that.
    View itself takes participation as first argument.
    """
    def actual_decorator(func):
        @wraps(func)
        def wrapper(request: HttpRequest, serviceform_slug, *args, title: str='',
                    **kwargs) -> HttpResponse:
            current_view = request.resolver_match.view_name

            member = utils.get_authenticated_member(request)
            participation = get_object_or_404(member.participation_set,
                                              form_revision__form__slug=serviceform_slug)

            # TODO: rename request.participant
            request.participant = participation
            # TODO: should we check if this is in EDITING_STATUS or not?
            if check_flow:
                # Check flow status
                participation._current_view = current_view
                if not participation.can_access_view(current_view, auth=True):
                    return participation.redirect_last()
                rv = func(request, participation, *args, **kwargs)
                if isinstance(rv, HttpResponseRedirect):
                    url = resolve(rv.url)
                    next_view = url.view_name
                    participation.proceed_to_view(next_view)
                return rv
            else:
                return func(request, participation, *args, **kwargs)

        return wrapper

    if function:
        return actual_decorator(function)
    return actual_decorator


def require_published_form(func):
    @wraps(func)
    def wrapper(request: HttpRequest, participant: models.Participation,
                *args, **kwargs) -> HttpResponse:
        if not participant.form.is_published:
            raise PermissionDenied
        return func(request, participant, *args, **kwargs)

    return wrapper


def require_form_permissions(func):
    @wraps(func)
    def wrapper(request: HttpRequest, service_form: models.ServiceForm,
                *args, **kwargs) -> HttpResponse:
        try:
            utils.user_has_serviceform_permission(request.user, service_form)
        except PermissionDenied:
            responsible = utils.get_authenticated_member(request)
            if not responsible or not responsible.show_full_report:
                return redirect_to_login(request.path, login_url=settings.LOGIN_URL)

        return func(request, service_form, *args, **kwargs)

    return wrapper  #
