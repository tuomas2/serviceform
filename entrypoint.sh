#!/usr/bin/env bash

function wait_for {
    while ! $(nc -z $1 $2); do
        echo 'Waiting for $1:$2';
        sleep 2;
    done
}

function wait_db { wait_for db 5432; }
function wait_redis { wait_for redis 6379; }

echo "Launching $@"

wait_db

case "$1" in
  'upgrade')
    # Set media volume permissions
    chown -R web /code/media
    chown -R web /celery-beat-store
    ./manage.py migrate
  ;;
  'app')
    wait_redis
    IS_WEB=1 uwsgi /code/serviceform_project/uwsgi.ini
  ;;
  'send-emails')
    ./manage.py send_emails
  ;;
  'task-processor')
    ./manage.py task_processor
  ;;
  'celery')
    wait_redis
    celery -A serviceform_project worker -l info
  ;;
  'celery-beat')
    wait_redis
    celery -A serviceform_project beat -l info -S django --pidfile /store/beat.pid --schedule /store/beat.db
  ;;
  'tests')
    wait_redis
    export TESTS_RUNNING=1
    py.test -v tests/
  ;;
  'travis-tests')
    wait_redis
    cd $2
    ./manage.py collectstatic --noinput
    ./manage.py compress
    export TESTS_RUNNING=1
    py.test -v --cov serviceform/ --cov tasks/ tests/
  ;;
  'bash')
    bash
  ;;
  *)
    wait_redis
    ./manage.py $@
  ;;
esac