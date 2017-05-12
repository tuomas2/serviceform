Serviceform
===========

RELEASE IS STILL WORK IN PROGRESS. PLEASE WAIT...


Web application for collecting data from volunteers of willingness to participate.

Docker
======

To run whole serviceform in docker (development environment)::

    cd serviceform-docker
    docker-compose -f docker-compose-dev.yml up

Optionally, to run within docker in an environment more closely imitating production::

    docker-compose up

Then go to http://localhost:8080
Admin login: admin, password: asdf


Running tests with docker
-------------------------

Run::

    docker-compose -f docker-compose-tests.yml run tests

Production guide
================

Requirements
------------

 - Machine that runs docker
 - Your own web server with SSL sertificates and associated domain name
 - Sendgrid email account for automatic sending emails.
   Your domain DNS settings need to be set up correctly for sendgrid too.
 - (optional) Sentry / sentry account


Docker environment file
-----------------------

Put environment variables in file serviceform-env.list::

    PRODUCTION=1
    # You can choose your credentials here. Initial database will be made according to these
    # settings
    POSTGRES_USER=serviceform
    POSTGRES_DB=serviceform
    POSTGRES_PASSWORD=django
    # Django's secret key. Use generator such as this:
    # http://www.miniwebtool.com/django-secret-key-generator/
    SECRET_KEY=asdf
    # API key to Sendgrid email sending service.
    SENDGRID_API_KEY=asdf
    # Sentry authentication. Leave this out if you don't have Sentry account.
    RAVEN_DSN=https://asdf
    # Your service will be at https://SERVICEFORM_HOST
    SERVICEFORM_HOST=yourhost.com
    ADMIN_NAME=Your Name
    ADMIN_EMAIL=your.name@yourhost.com
    SERVER_EMAIL=noreply@yourhost.com
    # This code is used to generate unpredictable id, choose 5 random letters here
    CODE_LETTERS=ABCDE

For the following commands set first environment variable

export SERVICEFORM_ENV_FILE=/path_to/serviceform-env.list


External services
-----------------

Docker commands to start external services needed by Serviceform

Postgresql::

   docker run -d --name serviceform-db \
            --env-file $SERVICEFORM_ENV_FILE \
            --volume $(pwd)/init.sql:/docker-entrypoint-initdb.d/10-init.sql:ro \
            --volume serviceform-db:/var/lib/postgresql \
            postgres:9.6.2


Redis::

   docker run -d --name serviceform-redis \
            --volume serviceform-redis:/data \
            redis:3.2.8-alpine


Django services
---------------

Docker commands to start services bundled within serviceform docker image.

Build serviceform docker image first::

    docker build -t tuomasairaksinen/serviceform:latest .

Or alternatively, pull it from the repository::

    docker pull tuomasairaksinen/serviceform:latest


Initialization / upgrade. This migrates database
and (re-)creates static files in shared volume (for nginx)::

    docker run --rm -u root \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            --volume serviceform-media:/code/media:ro \
            --volume serviceform-static:/code/static \
            --volume serviceform-nginx-config:/nginx-config \
            tuomasairaksinen/serviceform:latest upgrade

Celery::

   docker run -d --name serviceform-celery \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest celery


Celery-beat::

    docker run -d --name serviceform-celery-beat \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest celery-beat

Task-processor::

   docker run -d --name serviceform-task-processor \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest task-processor

Send-emails::

    docker run -d --name serviceform-send-emails \
            --link serviceform-db:db \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest send-emails

App::

    docker run -d --name serviceform-app \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            --volume serviceform-static:/code/static \
            --volume serviceform-media:/code/media \
            tuomasairaksinen/serviceform:lates app


Web server::

    docker run -d --name serviceform-nginx \
            --publish 8038:80 \
            --link serviceform-app:app \
            --volume serviceform-static:/serviceform-static:ro \
            --volume serviceform-media:/serviceform-media:ro \
            --volume serviceform-nginx-config:/etc/nginx/conf.d:ro \
            nginx:1.13-alpine

With this configuration serviceform will listen HTTP connections to port 8038.
Now you need to set up your web server (https) to redirect connections to this port.

Shells
------

To investigate problems these shell commands might prove usefull.

Django shell::

    docker run --rm -it \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:lates shell

Postgresql root shell::

    docker exec -it -u postgres serviceform-db psql

Same with Django's credentials::

    docker run --rm -it \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:lates dbshell

Bash shell (to investigate/edit volumes etc.)::

    docker run --rm -it -u root \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --volume serviceform-media:/code/media:ro \
            --volume serviceform-static:/code/static \
            --volume serviceform-nginx-config:/nginx-config \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest bash

Upgrading system
----------------

 - Pull (or build) new docker image(s)
 - Stop affected service(s), not all necessary
    - docker stop serviceform-nginx
    - docker stop serviceform-app
    - docker stop serviceform-send-emails
    - docker stop serviceform-task-processor
    - docker stop serviceform-celery
    - docker stop serviceform-celery-beat
    - docker stop serviceform-redis (if redis upgrade)
    - docker stop serviceform-db (if db upgrade)

 - If upgrading redis or postgres, start them again
 - Run upgrade command
 - Start applications again
 - Start services

No-downtime upgrade is planned in the future.

Development
===========

How to set things up and run your local development environment:
----------------------------------------------------------------

Install dependencies::

    sudo apt-get install docker.io git python-dev python-pip virtualenv libpq-dev postgresql-server-dev-all virtualenvwrapper

Note: Python 3.6 or newer is required.

Create virtualenv::

    mkvirtualenv -p /usr/bin/python3.6 serviceform_env


To start using it type::

    workon serviceform_env


Install requirements to your virtualenv::

    pip install -r requirements.txt


Run external services (redis and postgresql) inside docker::

    docker-compose up


When DB is set up, you can run initial migrations with command::

    ./manage.py migrate


Then you must create your initial account::

    ./manage.py createsuperuser


Then run can run development server::

    ./manage.py runserver


Then open browser in http://localhost:8000 and use your initial superuser account to log in.


Dumping and loading database in development environment
-------------------------------------------------------

Database can be dumped with the following command::

        docker-compose exec db su - postgres -c "pg_dump serviceform" > init.sql

To load dump, you must first clear the current database. This can be done as follows::

    cat init.sql | docker exec -i serviceform-db su - postgres -c "psql serviceform"

Dump data in json format for tests::

    ./manage.py dumpdata -o tests/test_data.json -e serviceform.EmailMessage -e admin.LogEntry --indent 2 -e sessions.Session -e djcelery




Translations
------------

If changes to translatable strings are made, run::

    django-admin.py makemessages

Then update translation (*.po) files for example with poedit, and then run::

    django-admin.py compilemessages

Then commit your changes (.po and .mo files) to repository.




LICENCE
=======

GPL version 3, see LICENCE.txt