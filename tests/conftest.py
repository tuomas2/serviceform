import pytest
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.db import connection
import os

sql = """DELETE from auth_group_permissions CASCADE;
DELETE from auth_permission CASCADE;
DELETE from django_content_type CASCADE;"""

@pytest.fixture(scope='session')
def django_db_setup(django_db_setup, django_db_blocker):
    #ContentType.objects.all().delete()
    with django_db_blocker.unblock():
        with connection.cursor() as c:
            c.execute(sql)
        call_command('loaddata', os.path.join(os.path.dirname(__file__), 'test_data.json'))


@pytest.fixture
def client1(client):
    return client

@pytest.fixture
def client2(client):
    return client
