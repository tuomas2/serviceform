#from django.test import TestCase
import os
from datetime import timedelta
from itertools import chain
from urllib.parse import urlparse
from typing import List
import pytest

# Hit admin pages (create new, update existing) but do not try to create any real content
from django.db.models import QuerySet
from django.test import Client
from django.utils import timezone

from serviceform import models

SLUG = 'jklvapis'

def test_hit_admin_pages(settings, db, admin_client: Client):
    res = admin_client.get('/admin/')
    assert res.status_code == Http.OK
    res = admin_client.get('/admin/serviceform/serviceform/')
    assert res.status_code == Http.OK
    res = admin_client.get('/admin/serviceform/serviceform/11/change/') # TODO hard-coded id.
    assert res.status_code == Http.OK
    assert b'Tutustu palvelulomakkeeseen' in res.content


def test_hit_admin_reports(db, settings, admin_client: Client):
    p = models.Participant.objects.filter(form_revision__form__slug=SLUG).first()
    r = models.ResponsibilityPerson.objects.filter(form__slug=SLUG).first()
    pages = [
                f"/report/{SLUG}/",
                f"/report/{SLUG}/all_participants/",
                f"/report/{SLUG}/all_activities/",
                f"/report/{SLUG}/settings/",
                f"/report/{SLUG}/all_questions/",
                f"/report/participant/{p.pk}/",
                f"/report/responsible/{r.pk}/",
                f"/invite/{SLUG}/",
                f"/preview/{SLUG}/",
                f"/preview_printable/{SLUG}/",
    ]
    for p in pages:
        res = admin_client.get(p)
        assert res.status_code == 200

# Test utils.py

# Test serviceform flow pages and make sure they create appropriate content

class Http:
    OK = 200
    REDIR = 302
    FORBIDDEN = 403
    NOT_FOUND = 404
    
def test_flow_login_frontpage(db, client: Client):
    res = client.get(f'/{SLUG}/')
    assert res.status_code == Http.OK


def test_flow_login_wrong_password(db, client: Client):
    res = client.post(f'/{SLUG}/', {'password': 'WrongPassword'})
    assert res.status_code == Http.OK
    assert b'Virheellinen salasana' in res.content


def test_flow_login_send_participant_email(db, client: Client):
    page = Pages.LOGIN_SEND_PARTICIPANT_LINK
    res = client.get(page)
    assert res.status_code == Http.OK
    res = client.post(page, {'email': 'some@email.com'})
    assert res.status_code == Http.OK
    assert 'Lomakkeelle ei löytynyt aikaisempaa osallistumistietoa' in res.context['email_form'].errors['email'][0]

    email = models.Participant.objects.first().email
    timestamp = timezone.now()
    res = client.post(page, {'email': email})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.LOGIN_SEND_PARTICIPANT_LINK
    emailmsg = models.EmailMessage.objects.filter(created_at__gt=timestamp).get()
    assert emailmsg.to_address == email


def test_flow_login_send_responsible_email(db, client: Client):
    page = Pages.LOGIN_SEND_RESPONSIBLE_LINK
    res = client.get(page)
    assert res.status_code == Http.OK
    res = client.post(page, {'email': 'some@email.com'})
    assert res.status_code == Http.OK
    assert 'Lomakkeelle ei löytynyt vastuuhenkilöä' in res.context['email_form'].errors['email'][0]

    email = models.ResponsibilityPerson.objects.first().email
    timestamp = timezone.now()
    res = client.post(page, {'email': email})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.LOGIN_SEND_RESPONSIBLE_LINK
    emailmsg = models.EmailMessage.objects.filter(created_at__gt=timestamp).get()
    assert emailmsg.to_address == email


class Pages:
    ADMIN_LOGIN = '/admin/login/'
    LOGIN = f'/{SLUG}/'
    MAIN_PAGE = '/'
    LOGIN_SEND_PARTICIPANT_LINK = f'/{SLUG}/send_participant_link/'
    LOGIN_SEND_RESPONSIBLE_LINK = f'/{SLUG}/send_responsible_link/'


    CONTACT = '/participant/contact/'
    EMAIL_VERIFICATION = '/participant/email_verification/'
    PARTICIPATION = '/participant/participation/'
    PARTICIPATIONX = '/participant/participation/%d/'

    PARTICIPATION0 = '/participant/participation/0/'
    PARTICIPATION1 = '/participant/participation/1/'
    PARTICIPATION2 = '/participant/participation/2/'
    PARTICIPATION3 = '/participant/participation/3/'
    PARTICIPATION4 = '/participant/participation/4/'
    PARTICIPATION5 = '/participant/participation/4/'
    PARTICIPATION6 = '/participant/participation/4/'

    QUESTIONS = '/participant/questions/'
    PREVIEW = '/participant/preview/'
    SUBMITTED = '/participant/submitted/'

    PARTICIPATION_PAGES = [CONTACT, EMAIL_VERIFICATION] + \
                          [f'/participant/participation/{d}/' for d in range(7)] + \
                          [QUESTIONS, PREVIEW, SUBMITTED]

    REPORT_RESPONSIBLE = "/for_responsible/"

    DELETE_PARTICIPATION = '/participant/delete/'

    RESPONSIBLE_MOCK_AUTH = '/anonymous/authenticate_responsible_mock/%d/'
    #RESPONSIBLE_MOCK_AUTH = '/authenticate_responsible_mock/%d/'
    RESPONSIBLE_REPORT = '/for_responsible/'
    RESPONSIBLE_EDIT = '/for_responsible/edit_details/'

    RESPONSIBLE_RESEND_LINK = f'/{SLUG}/send_responsible_link/'
    RESPONSIBLE_TO_FULL_RAPORT = '/for_responsible/to_full_report/'
    FULL_REPORT_RESPONSIBLES = f'/report/{SLUG}/'
    FULL_REPORT_PARTICIPANTS = f"/report/{SLUG}/all_participants/"
    FULL_REPORT_ACTIVITIES = f"/report/{SLUG}/all_activities/"
    FULL_REPORT_QUESTIONS = f"/report/{SLUG}/all_questions/"
    FULL_REPORT_SETTINGS = f"/report/{SLUG}/settings/"
    LOGOUT = f'/logout/'

    INVITE = f"/invite/{SLUG}/"
    UNSUBSCRIBE_PARTICIPANT = '/email/unsubscribe_participant/%s/'
    UNSUBSCRIBE_RESPONSIBLE = '/email/unsubscribe_responsible/%s/'

    REPORT_PAGES = [
                FULL_REPORT_RESPONSIBLES,
                FULL_REPORT_ACTIVITIES,
                FULL_REPORT_PARTICIPANTS,
                FULL_REPORT_QUESTIONS,
                FULL_REPORT_SETTINGS,
                ]

@pytest.mark.skipif(os.getenv('SKIP_SLOW_TESTS', False), reason='Very slow test')
@pytest.mark.parametrize('email_verification', [False, True])
@pytest.mark.parametrize('flow_by_categories', [False, True])
@pytest.mark.parametrize('allow_skip_categories', [False, True])
# Check if email is sent to responsibility persons
@pytest.mark.parametrize('emailing_time_now', [False, True])
# Check if email needs to be given in contact info
@pytest.mark.parametrize('use_admin_user', [False, True])
@pytest.mark.parametrize('send_email_allowed', [True, False])
def test_participation_flow(db, client: Client, client1: Client, client2: Client, admin_client: Client,
                            email_verification, flow_by_categories,
                            allow_skip_categories, emailing_time_now,
                            use_admin_user, send_email_allowed):
    """
    Go through participation flow step by step.
    
    TODO:
    
    We chould create and parametrize the chosen activities in categories.
    We should add there parametrized responsibility persons etc and check
    that correct emails are being sent. But this might be enough for now.
    """

    if use_admin_user:
        client = admin_client

    EMAIL_ADDRESS = 'forename.surname@domain.fi'

    if not flow_by_categories and allow_skip_categories:
        # allow_skip_categories takes effect only if flow_by_caterogies is enabled.
        return

    def assert_forbidden():
        for p in Pages.PARTICIPATION_PAGES:
            res = client.get(p)
            assert res.status_code == Http.FORBIDDEN

    def can_access_other_pages(position, updating=False):
        """ 
        Check if other participation pages can be already accessed 
        """
        for page_num in range(7):
            res = client.get(Pages.PARTICIPATIONX % page_num)
            if allow_skip_categories or page_num <= position or updating:
                assert res.status_code == Http.OK
            else:
                assert res.status_code == Http.REDIR
                assert res.url == Pages.PARTICIPATIONX % position

    def skip_other_pages(updating=False):
        for page_num in range(1, 6):
            res = client.post(Pages.PARTICIPATIONX % page_num)
            assert res.status_code == Http.REDIR
            assert res.url == Pages.PARTICIPATIONX % (page_num + 1)
            can_access_other_pages(page_num + 1, updating)

        return client.post(Pages.PARTICIPATIONX % 6)

    def check_responsible_reports(emails: QuerySet, resps: List[models.ResponsibilityPerson], num_responsibles: int):
        assert len(resps) == num_responsibles
        assert len(emails) == num_responsibles + 1 - 1 # +1 to participant. -1 because 1 does not want email notifications.
        _full_report_hit = False
        _no_full_report_hit = False
        _no_email_hit = False

        for r in resps:
            if not r.send_email_notifications:
                _no_email_hit = True
                continue

            email = emails.get(to_address=r.email)
            url = urlparse(email.context_dict['url']).path
            client1.session.clear()

            res = client1.get(url)
            assert res.status_code == Http.REDIR
            assert res.url == Pages.REPORT_RESPONSIBLE
            res = client1.get(res.url)
            assert res.status_code == Http.OK
            if r.show_full_report:
                _full_report_hit = True
                for p in REPORT_PAGES:
                    res = client1.get(p)
                    assert res.status_code == Http.OK
            else:
                _no_full_report_hit = True
                for p in REPORT_PAGES:
                    res = client1.get(p)
                    assert res.status_code == Http.REDIR
                    assert res.url.startswith(Pages.ADMIN_LOGIN)
        assert _no_full_report_hit and _full_report_hit and _no_email_hit  #  check that test data is comprehensive enough

    s = models.ServiceForm.objects.get(slug=SLUG)
    s.require_email_verification = email_verification
    s.flow_by_categories = flow_by_categories
    s.allow_skipping_categories = allow_skip_categories
    rev = s.current_revision
    rev.valid_from = timezone.now() - timedelta(days=10)
    rev.valid_to = timezone.now() + timedelta(days=10)
    if emailing_time_now:
        rev.send_emails_after = timezone.now() - timedelta(days=1)
    else:
        rev.send_emails_after = timezone.now() + timedelta(days=1)
    rev.save()
    s.save()

    FULL_REPORT = f"/report/{s.slug}/"
    ALL_PARTICIPANTS = f"/report/{s.slug}/all_participants/"
    ALL_ACTIVITIES = f"/report/{s.slug}/all_activities/"
    ALL_QUESTIONS = f"/report/{s.slug}/all_questions/"
    REPORT_PAGES = [FULL_REPORT, ALL_ACTIVITIES, ALL_PARTICIPANTS, ALL_QUESTIONS]

    first_cat1:models.Level1Category = s.sub_items[0]
    first_cat2:models.Level2Category = first_cat1.sub_items[0]
    first_activity: models.Activity = first_cat2.sub_items[0]
    first_choice: models.ActivityChoice = first_activity.sub_items[0]
    second_activity: models.Activity = first_cat2.sub_items[1]
    earlier_p = models.Participant.objects.filter(
        status=models.Participant.STATUS_FINISHED, form_revision=s.current_revision).first()

    assert_forbidden()
    res = client.post(f'/{SLUG}/', {'password': s.password})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.CONTACT
    res = client.get(Pages.CONTACT)
    assert res.status_code == Http.OK
    participant_id = client.session['authenticated_participant']
    p = models.Participant.objects.get(pk=participant_id)

    user_data_without_email = dict(forenames='Forenames',
                                   surname='Surname',
                                   street_address='Addr',
                                   postal_code='10101',
                                   city='City',
                                   email='',
                                   phone_number='041434434434',
                                   send_email_allowed='on')
    if not send_email_allowed:
        del user_data_without_email['send_email_allowed']

    user_data_earlier_email = user_data_without_email.copy()
    user_data = user_data_without_email.copy()

    user_data_earlier_email['email'] = earlier_p.email

    user_data_without_email.pop('send_email_allowed', None)
    user_data['email'] = EMAIL_ADDRESS

    # Email missing
    res = client.post(Pages.CONTACT, user_data_without_email)
    if use_admin_user:
        assert res.status_code == Http.REDIR
        assert res.url == Pages.PARTICIPATION
        return # Nothing important to test for admin user after this

    assert res.status_code == Http.OK
    assert 'email' in res.context['form'].errors

    # Earlier user already in system
    res = client.post(Pages.CONTACT, user_data_earlier_email)
    assert res.status_code == Http.OK
    assert 'email' in res.context['form'].errors
    timestamp = timezone.now()
    res = client.get(f'/send_auth_link/{earlier_p.email}')
    assert res.status_code == Http.REDIR
    assert res.url == Pages.CONTACT
    assert earlier_p.send_email_allowed

    email = models.EmailMessage.objects.get(created_at__gt=timestamp)
    assert email.to_address == earlier_p.email

    res = client.post(Pages.CONTACT, user_data)

    assert res.status_code == Http.REDIR

    p.refresh_from_db()
    assert p.email == EMAIL_ADDRESS
    assert p.forenames == 'Forenames'


    if email_verification:
        assert res.url == Pages.EMAIL_VERIFICATION
        # let's check that we can't pass to participation without verification!
        res = client.get(Pages.PARTICIPATION)
        assert res.status_code == Http.REDIR
        assert res.url == Pages.EMAIL_VERIFICATION


        timestamp = timezone.now()
        res = client.get(Pages.EMAIL_VERIFICATION)
        assert res.status_code == 200

        res = client.get(Pages.PARTICIPATION)
        assert res.status_code == Http.REDIR
        assert res.url == Pages.EMAIL_VERIFICATION

        # Then let's click verification link from email
        email = models.EmailMessage.objects.last()
        assert email.created_at > timestamp
        assert email.to_address == EMAIL_ADDRESS

        url = urlparse(email.context_dict['url']).path
        res = client.get(url)
        assert res.status_code == Http.REDIR

    assert res.url == Pages.PARTICIPATION
    res = client.get(Pages.PARTICIPATION)
    assert res.status_code == Http.OK
    if flow_by_categories:
        can_access_other_pages(0)

    participation_data = {f'SRV_CHOICE_{first_choice.pk}': '1',
                          f'SRV_CHOICE_EXTRA_{first_choice.pk}': 'Testing testing'}

    res = client.post(Pages.PARTICIPATION, participation_data)

    p.refresh_from_db()
    assert len(p.participationactivity_set.all()) == 1
    pacs = models.ParticipationActivityChoice.objects.filter(activity__participant=p)
    assert len(pacs) == 1
    assert pacs[0].additional_info == 'Testing testing'

    assert res.status_code == Http.REDIR
    if flow_by_categories:
        assert res.url == Pages.PARTICIPATION1
        res = skip_other_pages()

    assert res.status_code == Http.REDIR
    assert res.url == Pages.QUESTIONS
    res = client.get(Pages.QUESTIONS)
    assert res.status_code == Http.OK
    q1, q2, q3, q4 = models.Question.objects.filter(form=s).all()
    res = client.post(Pages.QUESTIONS, {f'SRV_QUESTION_{q1.pk}': 'on'})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.PREVIEW
    p.refresh_from_db()
    qa1 = p.questionanswer_set.get()
    assert qa1.question == q1
    assert qa1.answer == 'on' # on and off (from web side, checkbox status)

    res = client.get(Pages.PREVIEW)
    assert res.status_code == Http.OK
    if flow_by_categories:
        can_access_other_pages(7)
    res = client.post(Pages.PREVIEW, {'submit': '1'})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.SUBMITTED
    assert p.status == models.Participant.STATUS_ONGOING
    timestamp = timezone.now()
    res = client.get(Pages.SUBMITTED)
    assert res.status_code == Http.OK
    emails = models.EmailMessage.objects.filter(created_at__gt=timestamp)
    # Check responsible report for this person
    if emailing_time_now:
        resps = list(chain(first_cat1.responsibles.all(),
                           first_cat2.responsibles.all(),
                           first_activity.responsibles.all(),
                           first_choice.responsibles.all(),
                           q1.responsibles.all(),
                           ))
        check_responsible_reports(emails, resps, 4) # 1 from q1, 2 from cat2, 1 from choice1
    else:
        assert len(emails) == 1 #just participant

    p.refresh_from_db()
    assert p.status == models.Participant.STATUS_FINISHED
    assert_forbidden()


    # Check updating flow.
    email = emails.get(to_address=EMAIL_ADDRESS)
    update_url = urlparse(email.context_dict['url']).path

    res = client.get(update_url)
    assert res.status_code == Http.REDIR
    assert res.url == Pages.CONTACT
    res = client.get(Pages.CONTACT)
    assert res.status_code == Http.OK
    if flow_by_categories and allow_skip_categories:
        can_access_other_pages(7)
    user_data_mod = user_data.copy()
    user_data_mod['city'] = 'Modified city'
    res = client.post(Pages.CONTACT, user_data_mod)
    assert res.status_code == Http.REDIR
    assert res.url == Pages.PARTICIPATION
    p.refresh_from_db()
    assert p.city == 'Modified city'
    res = client.get(Pages.PARTICIPATION)
    assert res.status_code == Http.OK
    participation_data.update(
        {f'SRV_ACTIVITY_{second_activity.pk}': '1',
         f'SRV_ACTIVITY_EXTRA_{second_activity.pk}': 'Testing testing 2'})

    res = client.post(Pages.PARTICIPATION, participation_data)
    assert res.status_code == Http.REDIR
    if flow_by_categories:
        assert res.url == Pages.PARTICIPATION1
        res = skip_other_pages(updating=True)
    else:
        assert res.url == Pages.QUESTIONS

    p.refresh_from_db()
    pas = p.participationactivity_set.all()
    assert len(pas) == 2
    pa1 = pas.get(activity=first_activity)
    pa2 = pas.get(activity=second_activity)
    assert pa2.additional_info == 'Testing testing 2'

    pac = models.ParticipationActivityChoice.objects.filter(activity__participant=p).get()
    assert pac.additional_info == 'Testing testing'

    res = client.post(Pages.QUESTIONS, {
        f'SRV_QUESTION_{q1.pk}': '',
        f'SRV_QUESTION_{q2.pk}': 'Answer to q2'})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.PREVIEW
    p.refresh_from_db()
    qa2 = p.questionanswer_set.get()
    assert qa2.question == q2
    assert qa2.answer == 'Answer to q2'
    res = client.get(Pages.PREVIEW)
    assert res.status_code == Http.OK
    if flow_by_categories:
        can_access_other_pages(7, updating=True)
    res = client.post(Pages.PREVIEW, {'submit': '1'})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.SUBMITTED
    p.refresh_from_db()
    assert p.status == p.STATUS_UPDATING
    timestamp = timezone.now()
    res = client.get(Pages.SUBMITTED)
    assert res.status_code == Http.OK
    p.refresh_from_db()
    assert p.status == p.STATUS_FINISHED
    assert_forbidden()
    emails = models.EmailMessage.objects.filter(created_at__gt=timestamp)

    # Check responsible report for this person after update
    if emailing_time_now:
        resps = list(chain(first_cat1.responsibles.all(),
                           first_cat2.responsibles.all(),
                           first_activity.responsibles.all(),
                           second_activity.responsibles.all(),
                           first_choice.responsibles.all(),
                           q2.responsibles.all(),
                           ))
        check_responsible_reports(emails, resps, 6) # 2 from cat2, 1 from choice1, 1 from act2, 2 from q2
    else:
        assert len(emails) == 1


    # Let's get in once more and delete participation
    res = client.get(update_url)
    assert res.status_code == Http.REDIR
    res = client.get(res.url)
    assert res.status_code == Http.OK
    res = client.get(Pages.DELETE_PARTICIPATION)
    assert res.status_code == Http.OK
    res = client.post(Pages.DELETE_PARTICIPATION, {'yes_please': 'on'})
    assert res.status_code == Http.REDIR
    assert res.url == Pages.LOGIN
    with pytest.raises(p.DoesNotExist):
        models.Participant.objects.get(pk=p.pk)


@pytest.mark.parametrize('full_raport', [False, True])
@pytest.mark.parametrize('mock_login', [False, True])
def test_responsible_personal_report(client1: Client, admin_client:Client, mock_login, full_raport):
    forenames = 'Anne-Maija Sven'
    s = models.ServiceForm.objects.get(slug=SLUG)
    resp = s.responsibilityperson_set.get(pk=89)
    resp.show_full_report = full_raport
    resp.save()

    assert resp.forenames == forenames

    if mock_login:
        client = admin_client
        res = client.get(Pages.RESPONSIBLE_MOCK_AUTH % resp.pk)
    else:
        client = client1
        res = client.get(Pages.RESPONSIBLE_RESEND_LINK)
        assert res.status_code == Http.OK
        assert not resp.auth_keys_hash_storage
        timestamp = timezone.now()
        res = client.post(Pages.RESPONSIBLE_RESEND_LINK, {'email': resp.email})
        assert res.status_code == Http.REDIR
        assert res.url == Pages.RESPONSIBLE_RESEND_LINK
        email = models.EmailMessage.objects.get(created_at__gt=timestamp)
        assert email.to_address == resp.email
        auth_url = urlparse(email.context_dict['url']).path
        res = client.get(auth_url)

    assert res.status_code == Http.REDIR
    assert res.url == Pages.RESPONSIBLE_REPORT
    res = client.get(Pages.RESPONSIBLE_REPORT)
    assert res.status_code == Http.OK
    res = client.get(Pages.RESPONSIBLE_EDIT)
    assert res.status_code == Http.OK
    assert res.context['form'].initial['forenames'] == forenames
    post_data = {'forenames': resp.forenames + ' DAA',
                 'surname': resp.surname,
                 'email': resp.email,
                 'phone_number': resp.phone_number,
                 'send_email_notifications': 'on'}
    res = client.post(Pages.RESPONSIBLE_EDIT, post_data)
    assert res.status_code == Http.OK
    resp.refresh_from_db()
    assert resp.forenames == forenames + ' DAA'
    # test full raport link
    if full_raport:
        res = client.get(Pages.RESPONSIBLE_TO_FULL_RAPORT)
        assert res.status_code == Http.REDIR
        assert res.url == Pages.FULL_REPORT_RESPONSIBLES
        for p in Pages.REPORT_PAGES:
            res = client.get(p)
            assert res.status_code == Http.OK
        res = client.get(Pages.RESPONSIBLE_REPORT)
        assert res.status_code == Http.OK
    else:
        res = client.get(Pages.RESPONSIBLE_TO_FULL_RAPORT)
        assert res.status_code == Http.FORBIDDEN
        for p in Pages.REPORT_PAGES:
            res = client.get(p)
            if mock_login:
                assert res.status_code == Http.OK
            else:
                assert res.status_code == Http.REDIR
                assert res.url.startswith(Pages.ADMIN_LOGIN)
        res = client.get(Pages.RESPONSIBLE_REPORT)
        assert res.status_code == Http.OK

    res = client.get(Pages.LOGOUT)
    assert res.status_code == Http.REDIR
    assert res.url == Pages.LOGIN

    res = client.get(Pages.FULL_REPORT_PARTICIPANTS)
    assert res.status_code == Http.REDIR
    assert res.url.startswith(Pages.ADMIN_LOGIN)



def test_report_settings_and_logout(admin_client: Client):
    from serviceform.templatetags.serviceform_tags import all_revisions
    res = admin_client.get(Pages.FULL_REPORT_PARTICIPANTS)
    assert res.status_code == Http.OK
    assert not all_revisions(res.context) # default settings

    res = admin_client.get(Pages.FULL_REPORT_SETTINGS)
    assert res.status_code == Http.OK
    res = admin_client.post(Pages.FULL_REPORT_SETTINGS, {'revision': '__all'})
    assert res.status_code == Http.OK

    assert all_revisions(res.context)
    res = admin_client.get(Pages.LOGOUT)
    assert res.status_code == Http.REDIR
    assert res.url == Pages.MAIN_PAGE

    res = admin_client.get(Pages.FULL_REPORT_PARTICIPANTS)
    assert res.status_code == Http.REDIR
    assert res.url.startswith(Pages.ADMIN_LOGIN)


@pytest.mark.parametrize('send_existing', [False, True])
@pytest.mark.parametrize('emails', ['test@test.fi, test2@test.fi', 'test@test.fi\ntest2@test.fi',
                                    'test@test.fi test2@test.fi', 'test@test.fi test2@test.fi'])
def test_invite_success(serviceform, admin_client: Client, emails, send_existing):
    res = admin_client.get(Pages.INVITE)
    assert res.status_code == Http.OK
    part_email = 'timo.ahlroth@email.com'
    participant = models.Participant.objects.get(email=part_email)
    revision = models.FormRevision.objects.create(name='old', form=serviceform)

    participant.form_revision = revision
    participant.save()

    post_data = {'email_addresses': emails + f' {part_email}'}
    if send_existing:
        post_data.update({'old_participants': 'on'})
    timestamp = timezone.now()
    res = admin_client.post(Pages.INVITE, post_data)
    assert res.status_code == Http.REDIR
    assert res.url == Pages.INVITE
    assert len(models.EmailMessage.objects.filter(created_at__gt=timestamp)) == (3 if send_existing else 2)


def test_unsubscribe_participant(client: Client, participant: models.Participant):
    from serviceform.utils import encode
    assert participant.send_email_allowed
    res = client.get(Pages.UNSUBSCRIBE_PARTICIPANT % encode(participant.pk))
    assert res.status_code == 200
    participant.refresh_from_db()
    assert not participant.send_email_allowed


def test_unsubscribe_responsible(client: Client, responsible: models.ResponsibilityPerson):
    from serviceform.utils import encode
    assert responsible.send_email_notifications
    res = client.get(Pages.UNSUBSCRIBE_RESPONSIBLE % encode(responsible.pk))
    assert res.status_code == 200
    responsible.refresh_from_db()
    assert not responsible.send_email_notifications


# TODO:
# Test emailing
# Test task processor
# Test login views more carefully (email sending etc)

