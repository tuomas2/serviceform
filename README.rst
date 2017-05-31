.. image:: https://travis-ci.org/tuomas2/serviceform.svg?branch=master
   :target: https://travis-ci.org/tuomas2/serviceform

.. image:: https://coveralls.io/repos/github/tuomas2/serviceform/badge.svg?branch=master
   :target: https://coveralls.io/github/tuomas2/serviceform?branch=master

.. image:: https://img.shields.io/codeclimate/github/tuomas2/serviceform.svg
   :target: https://codeclimate.com/github/tuomas2/serviceform

.. image:: https://www.versioneye.com/user/projects/5922f7e68dcc41003af21f61/badge.svg
   :target: https://www.versioneye.com/user/projects/5922f7e68dcc41003af21f61

.. image:: https://img.shields.io/pypi/v/serviceform.svg
   :target: https://pypi.python.org/pypi/serviceform

.. image:: https://img.shields.io/pypi/pyversions/serviceform.svg
   :target: https://pypi.python.org/pypi/serviceform

.. image:: https://img.shields.io/badge/licence-GPL--3-blue.svg
   :target: https://github.com/tuomas2/serviceform/blob/master/LICENSE.txt


===========
Serviceform
===========

RELEASE IS STILL WORK IN PROGRESS. PLEASE WAIT...

Introduction
============

Web application for collecting data from volunteers of willingness to participate.


=============================
Install as Django application
=============================

Install serviceform and its requirements to your virtualenv::

   pip install serviceform

settings.py modifications
=========================

In your Django application's settings.py perform the following modifications.
Add following applications to INSTALLED_APPS::

    INSTALLED_APPS = [
        'grappelli' # optional but recommended, needs django-grappelli

        ...

        'nested_admin',
        'compressor',
        'crispy_forms',
        'guardian',
        'serviceform.serviceform',
        'serviceform.tasks',
        'select2'
    ]

Settings for Django-compress::

    COMPRESS_PRECOMPILERS = (
        ('text/x-scss', 'django_libsass.SassCompiler'),
    )

    STATICFILES_FINDERS = ("django.contrib.staticfiles.finders.FileSystemFinder",
                           "django.contrib.staticfiles.finders.AppDirectoriesFinder",
                           "compressor.finders.CompressorFinder",
    )

Settings for crispy-forms::

   CRISPY_TEMPLATE_PACK = 'bootstrap3'

Settings for Django guardian::

    AUTHENTICATION_BACKENDS = (
        'django.contrib.auth.backends.ModelBackend', # default
        'guardian.backends.ObjectPermissionBackend',
    )

Database settings, we need postgresql!::

    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql_psycopg2',
            'NAME': 'serviceform',
            'USER': 'serviceform',
            'PASSWORD': 'django',
            'HOST': 'db',
            'PORT': 5433,
        }

We need to set up named caches::

    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'default',
        },
        'persistent': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'persistent',
        },
        'cachalot': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
            'LOCATION': 'cachalot',
        }
    }

In production, use redis or similar instead at least for persistent cache!

Set up static root::

   STATIC_ROOT = os.path.join(BASE_DIR, 'static')

Set up serviceform specific settings::

    SERVER_URL="http://localhost:8000"
    # random capital letters that are used to generate unpredictable
    # links from ids
    CODE_LETTERS='ABCDE'

urls.py modifications
=====================

Add urls that are specific to grappelli (optional), nested_admin, select2 and serviceform::

    urlpatterns = [
        url(r'^admin/', admin.site.urls),

        url(r'^_grappelli/', include('grappelli.urls')), # optional
        url(r'^_nested_admin/', include('nested_admin.urls')),
        url(r'^_select2/', include('select2.urls')),

        url(r'', include('serviceform.serviceform.urls')),
    ]


=============================
Production guide using Docker
=============================

Requirements
============

 - Machine that runs docker
 - Your own web server with SSL sertificates and associated domain name
 - Sendgrid email account for automatic sending emails.
   Your domain DNS settings need to be set up correctly for sendgrid too.
 - (optional) Sentry / sentry account


Docker environment file
=======================

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
    # Available: en, fi
    LANGUAGE_CODE=fi
    TIME_ZONE=Europe/Helsinki

For the following commands set first environment variable

export SERVICEFORM_ENV_FILE=/path_to/serviceform-env.list

.. _external:

External services
=================

Docker commands to start external services needed by Serviceform

PostgreSQL::

   docker run -d --name serviceform-db \
            --env-file $SERVICEFORM_ENV_FILE \
            --volume serviceform-db:/var/lib/postgresql \
            postgres:9.6.2


Redis::

   docker run -d --name serviceform-redis \
            --volume serviceform-redis:/data \
            redis:3.2.8-alpine


Django services
===============

Docker commands to start services bundled within serviceform docker image.

Build serviceform docker image first::

    docker build -t tuomasairaksinen/serviceform:latest .

Or alternatively, pull it from the repository::

    docker pull tuomasairaksinen/serviceform:latest

.. _upgrade:

Initialization / upgrade.
-------------------------

This migrates database::

    docker run --rm -u root \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            --volume serviceform-media:/code/media \
            --volume serviceform-celery-beat-store:/celery-beat-store \
            tuomasairaksinen/serviceform:latest upgrade

Command can be safely run multiple times.

.. _services:

Serviceform services
--------------------

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
            --volume serviceform-celery-beat-store:/store \
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

Main app (HTTP server) x 2::

    docker run -d --name serviceform-app-1 \
            --publish 8038:8080 \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            --volume serviceform-media:/code/media \
            tuomasairaksinen/serviceform:latest app

    docker run -d --name serviceform-app-2 \
            --publish 8039:8080 \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            --volume serviceform-media:/code/media \
            tuomasairaksinen/serviceform:latest app

With this configuration serviceform will listen HTTP connections to ports 8038 and 8039.
Now you need to set up your web server (https) to redirect connections to these ports::

    upstream serviceformapp {
       server 127.0.0.1:8038;
       server 127.0.0.1:8039;
    }

    server{
        listen 80;
        charset utf-8;
        client_max_body_size 2M;
        server_name yourserver.com;
        location / {
            return 302 https://yourserver.com$request_uri;
        }
    }

    server {
        listen      443;
        ssl on;
        ssl_certificate  /path/to/fullchain.pem;
        ssl_certificate_key /path/to/privkey.pem;

        server_name yourserver.com;
        charset     utf-8;

        client_max_body_size 2M;


        location / {
          proxy_pass         http://serviceformapp;
          proxy_redirect     off;

          proxy_set_header   Host              $host;
          proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;
          proxy_set_header   X-Forwarded-Proto $scheme;
        }
    }

With two app instances running simultaneously it is easy to do zero-downtime
upgrades by performing upgrade, restartin first 1 and then second instance, one
at a time.

.. _upgrading:

Upgrading system
================

Simple upgrade procedure::

    docker pull tuomasairaksinen/serviceform:latest
    docker stop serviceform-app-1 serviceform-send-emails serviceform-task-processor \
    serviceform-celery-beat serviceform-celery

Run `upgrade`_ command.
If that is fine, we can remove old containers::

    docker rm serviceform-app-1 serviceform-send-emails serviceform-task-processor \
              serviceform-celery-beat serviceform-celery

Then run all docker run again all `services`_.

Finally stop and remove app-2::

   docker stop serviceform-app-2
   docker rm serviceform-app-2

and then run it again with new image.

.. _restarting:

Shutting down and starting (system reboot procedures)
=====================================================

Shutting down::

    docker stop serviceform-app-1 serviceform-app-2 serviceform-send-emails \
                serviceform-task-processor serviceform-celery-beat serviceform-celery \
                serviceform-redis serviceform-db

Starting again (set this into your system startup). Notice order.::

    docker start serviceform-db serviceform-redis serviceform-celery serviceform-celery-beat \
                 serviceform-task-processor serviceform-send-emails serviceform-app-1 \
                 serviceform-app-2

.. _troubleshooting:

Troubleshooting / shell access
==============================

To investigate problems these shell commands might prove usefull.

Django shell::

    docker run --rm -it \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest shell

Postgresql root shell::

    docker exec -it -u postgres serviceform-db psql

Same with Django's credentials::

    docker run --rm -it \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest dbshell

Bash shell (to investigate/edit volumes etc.)::

    docker run --rm -it -u root \
            --link serviceform-db:db \
            --link serviceform-redis:redis \
            --volume serviceform-media:/code/media:ro \
            --env-file $SERVICEFORM_ENV_FILE \
            tuomasairaksinen/serviceform:latest bash

Dumping/loading production data as/from sql
===========================================

Dump current data
-----------------

Run::

   docker exec -u postgres serviceform-db pg_dump serviceform > backup.sql

Load data from file.
--------------------

First you need to destroy current database from PostgreSQL shell::

   DROP DATABASE serviceform;
   CREATE DATABASE serviceform;

Alternatively, you can stop database, remove volume::

   docker stop serviceform-db
   docker rm serviceform-db
   docker volume rm serviceform-db

and then start database server (see external_).

And then::

   docker exec -i -u postgres serviceform-db psql serviceform < backup.sql

===========
Development
===========

Running tests with docker-compose
=================================

Run::

    docker-compose -f docker-compose-tests.yml run tests

Running staging system with docker-compose
==========================================

Run::

   docker-compose -f docker-compose-staging.yml run upgrade # initialize everything
   docker-compose -f docker-compose-staging.yml run upgrade createsuperuser
   docker-compose -f docker-compose-staging.yml up -d

then go to http://localhost:8080 and log in.

How to set things up and run your local development environment:
================================================================

Install dependencies::

    sudo apt-get install python-dev python-pip virtualenv libpq-dev\
                         postgresql-server-dev-all virtualenvwrapper

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
=======================================================

Database can be dumped with the following command::

    docker-compose exec -u postgres db pg_dump serviceform > init.sql

To load dump, you must first clear the current database. This can be done as follows::

    docker-compose exec -i -u postgres db psql serviceform < init.sql

Dump data in json format for tests::

    ./manage.py dumpdata -o tests/test_data.json -e serviceform.EmailMessage -e admin.LogEntry --indent 2 -e sessions.Session


Translations
============

If changes to translatable strings are made, run::

    cd serviceform
    django-admin.py makemessages

Then update translation (.po) files for example with poedit, and then run::

    django-admin.py compilemessages

Then commit your changes (.po and .mo files) to repository.



=======
LICENSE
=======

Copyright (C) 2017 Tuomas Airaksinen

Serviceform is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

Serviceform is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with Serviceform.  If not, see <http://www.gnu.org/licenses/>.

For more information, see LICENSE.txt