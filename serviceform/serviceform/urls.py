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

"""
The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.9/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.conf.urls import url, include
    2. Add a URL to urlpatterns:  url(r'^blog/', include('blog.urls'))
"""
from itertools import chain

from django.conf.urls import url
from django.utils.translation import ugettext_lazy as _
from django.http import HttpResponseRedirect

from django.conf import settings

from .views import login_views
from .views import participation_views
from .views import reports_views


def error(request):
    raise Exception('Test error')


def main_page(request):
    return HttpResponseRedirect(settings.LOGIN_URL)


class DummyUrl:
    """
    URL that is shown in menu but ignored in django config.
    """

    def __init__(self, name, kwargs):
        self.name = name
        self.default_args = kwargs


class Requires:
    ACCESS_FULL_REPORT = object()
    RESPONSIBLE_LOGGED_IN = object()
    EMAIL_VERIFICATION = object()


participant_flow_urls = [
    url(r'^participant/contact/new/$', participation_views.contact_details_creation,
        name='contact_details_creation', kwargs={'title': _('Contact details')}),
    url(r'^participant/contact/$', participation_views.contact_details_modification,
        name='contact_details', kwargs={'title': _('Contact details')}),
    url(r'^participant/email_verification/$', participation_views.email_verification,
        name='email_verification', kwargs={'title': _('Email verification')}),
    url(r'^participant/participation/(\d+)/$', participation_views.participation,
        name='participation', kwargs={'title': _('Participation details')}),
    url(r'^participant/questions/$', participation_views.questions, name='questions',
        kwargs={'title': _('Questions')}),
    url(r'^participant/preview/$', participation_views.preview, name='preview',
        kwargs={'title': _('Preview')}),
    url(r'^participant/submitted/$', participation_views.submitted, name='submitted',
        kwargs={'title': _('Ready!')}),
]

report_urls = [
    url(r'^report/([\w-]+)/$', reports_views.all_responsibles, name='report',
        kwargs={'title': _('Responsibles')}),
    url(r'^report/([\w-]+)/all_participants/$', reports_views.all_participants,
        name='all_participants', kwargs={'title': _('Participants')}),
    url(r'^report/([\w-]+)/all_activities/$', reports_views.all_activities, name='all_activities',
        kwargs={'title': _('Participations')}),
    url(r'^report/([\w-]+)/all_questions/$', reports_views.all_questions, name='all_questions',
        kwargs={'title': _('Answers')}),
    DummyUrl(name='responsible_report',
             kwargs={'title': _('My report'), 'arglist': (), 'icon': 'bullseye',
                     'require': (Requires.RESPONSIBLE_LOGGED_IN,)}),

    # Invite users
    url(r'^report/([\w-]+)/settings/$', reports_views.settings_view, name='settings',
        kwargs={'title': _('Report settings'), 'right': True, 'icon': 'cog'}),
    url(r'^invite/([\w-]+)/$', reports_views.invite, name='invite',
        kwargs={'title': _('Invite'), 'right': True, 'icon': 'user-plus'}),
    DummyUrl(name="admin:serviceform_serviceform_change",
             kwargs={'title': _('Edit form'), 'icon': 'pencil-square-o', 'right': True,
                     'arglist': ('id',)}),
    DummyUrl(name="admin:serviceform_serviceform_changelist",
             kwargs={'title': _('Admin'), 'icon': 'wrench', 'right': True, 'arglist': ()}),
    url(r'^logout/$', reports_views.logout_view, name='logout',
        kwargs={'title': _('Log out'), 'icon': 'sign-out', 'right': True, 'arglist': ()}),
]

anonymous_report_urls = [
    url(r'^for_responsible/$', reports_views.responsible_report, name='responsible_report',
        kwargs={'title': _('Your report'), 'arglist': ()}),
    url(r'^for_responsible/edit_details/$', reports_views.edit_responsible,
        name='edit_responsible',
        kwargs={'title': _('Edit your contact details'), 'icon': 'pencil-square-o',
                'arglist': ()}),
    url(r'^for_responsible/to_full_report/$', reports_views.to_full_report, name='to_full_report',
        kwargs={'title': _('To full report'), 'icon': 'bullseye', 'arglist': (),
                'require': (Requires.ACCESS_FULL_REPORT,)}),
    # DummyUrl(name='report', kwargs={'title': _('To full report'), 'arglist': ()}),
    url(r'^logout/$', reports_views.logout_view, name='logout',
        kwargs={'title': _('Log out'), 'icon': 'sign-out', 'right': True, 'arglist': ()}),
]

login_urls = [
    DummyUrl(name='password_login', kwargs={'title': _('Password login'), 'icon': 'sign-in'}),
    url(r'^([\w-]+)/send_participant_link/', login_views.send_participant_email,
        name='send_participant_email', kwargs={'title': _('Former users'), 'icon': 'key'}),
    url(r'^([\w-]+)/send_responsible_link/', login_views.send_responsible_email,
        name='send_responsible_email', kwargs={'title': _('Responsibles'), 'icon': 'user'}),
    DummyUrl(name='report',
             kwargs={'title': _('Admin login'), 'icon': 'user-secret', 'right': True}),
]

menu_urls = {'report': report_urls, 'anonymous_report': anonymous_report_urls,
             'participant_flow': participant_flow_urls, 'login': login_urls}

urlpatterns = [u for u in
               chain(participant_flow_urls, report_urls, anonymous_report_urls, login_urls) if
               not isinstance(u, DummyUrl)] + \
              [
                  # Test erorr email
                  url(r'^test_error/$', error, name='test_error'),
                  # Later actions for participant
                  url(r'^anonymous/authenticate_participant/([\w-]+)/$',
                      participation_views.authenticate_participant_old,
                      name='authenticate_participant'),
                  url(r'^anonymous/authenticate_participant/(\d+)/([\w-]+)/$',
                      participation_views.authenticate_participant,
                      name='authenticate_participant_new'),
                  url(r'^anonymous/authenticate_participant_mock/(\d+)/$',
                      participation_views.authenticate_participant_mock,
                      name='authenticate_participant_mock'),

                  # Anonymous report viewing pages for responsible persons
                  url(r'^anonymous/authenticate_responsible/([\w-]+)/$',
                      reports_views.authenticate_responsible_old, name='authenticate_responsible'),
                  url(r'^anonymous/authenticate_responsible/(\d+)/([\w-]+)/$',
                      reports_views.authenticate_responsible, name='authenticate_responsible_new'),
                  url(r'^anonymous/authenticate_responsible_mock/(\d+)/$',
                      reports_views.authenticate_responsible_mock,
                      name='authenticate_responsible_mock'),

                  url(r'^email/unsubscribe_participant/(\w+)/$', participation_views.unsubscribe,
                      name='unsubscribe_participant'),
                  url(r'^email/unsubscribe_responsible/(\w+)/$', reports_views.unsubscribe,
                      name='unsubscribe_responsible'),

                  url(r'^participant/verify_email/(\d+)/([\w-]+)/$',
                      participation_views.verify_email, name='verify_email'),

                  # Report views
                  url(r'^report/participant/(\d+)/$', reports_views.view_participant,
                      name='view_user'),
                  url(r'^report/responsible/(\d+)/([\w-]+)/$', reports_views.view_responsible,
                      name='view_responsible'),

                  # Form previews
                  url(r'^preview/([\w-]+)/$', reports_views.preview_form, name='preview_form'),
                  url(r'^preview_printable/([\w-]+)/$', reports_views.preview_printable,
                      name='preview_printable'),

                  url(r'^logout/$', reports_views.logout_view, name='logout'),
                  url(r'^send_auth_link/(.*)$', participation_views.send_auth_link,
                      name='send_auth_link'),
                  url(r'^participant/delete/$', participation_views.delete_participation,
                      name='delete_participation'),
                  url(r'^([\w-]+)/$', login_views.password_login, name='password_login'),
                  url(r'^participant/participation/$', participation_views.participation,
                      name='participation', kwargs={'cat_num': 0}),
                  url(r'^$', main_page, name='main_page'),
              ]
