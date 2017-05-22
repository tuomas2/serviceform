from django.utils import timezone

from serviceform.tasks.models import Task
from serviceform.serviceform import models

def test_tasks(serviceform: models.ServiceForm):
    t = Task.make(serviceform.create_initial_data, scheduled_time=timezone.now())
    assert t.status == t.REQUESTED
    t.execute()
    assert t.status == t.DONE
    serviceform.refresh_from_db()
    assert serviceform.current_revision.name == f'{timezone.now().year}'


def test_tasks_canceled(serviceform: models.ServiceForm):
    cur_rev = serviceform.current_revision
    t = Task.make(serviceform.create_initial_data, scheduled_time=timezone.now())
    assert t.status == t.REQUESTED
    t.cancel()
    t.refresh_from_db()
    assert t.status == t.CANCELED
    t.execute()
    t.refresh_from_db()
    assert t.status == t.CANCELED
    serviceform.refresh_from_db()
    assert serviceform.current_revision == cur_rev

