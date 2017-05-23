import os
import logging

from django.core.cache import caches
from django.core.management import call_command
from django.db import connection
import pytest
from serviceform.serviceform import models

SLUG = 'jklvapis'

sql = """DELETE from auth_group_permissions CASCADE;
DELETE from auth_permission CASCADE;
DELETE from django_content_type CASCADE;"""

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    cache = caches['persistent']
    cache.clear()
    with django_db_blocker.unblock():
        with connection.cursor() as c:
            c.execute(sql)
        call_command('loaddata', os.path.join(os.path.dirname(__file__), 'test_data.json'))

@pytest.fixture
def serviceform(db):
    yield models.ServiceForm.objects.get(slug=SLUG)

@pytest.fixture
def participant(serviceform: models.ServiceForm):
    yield serviceform.current_revision.participant_set.get(pk=89)

@pytest.fixture
def responsible(serviceform: models.ServiceForm):
    yield serviceform.responsibilityperson_set.get(pk=89)

@pytest.fixture
def client1(client):
    return client

@pytest.fixture
def client2(client):
    return client

@pytest.fixture(autouse=True)
def check_log(request, caplog):
    yield None
    if not getattr(caplog, 'error_ok', False):
        for i in caplog.records():
            if i.levelno >= logging.ERROR:
                pytest.fail('Error: %s' % i.getMessage())