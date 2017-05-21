import os
import socket
from logging.config import dictConfig
from django.utils.translation import ugettext_lazy as _

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IS_WEB = bool(os.environ.get('IS_WEB', False))

PRODUCTION = bool(os.environ.get('PRODUCTION', False))
STAGING = bool(os.environ.get('STAGING', False))
DEBUG = bool(os.environ.get('DEBUG', False))

EMAIL_BACKEND = "sgbackend.SendGridBackend"
# SMTP based backend
#EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"


# Get these from environment variables:
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY', '')
RAVEN_DSN = os.getenv('RAVEN_DSN', '')
SECRET_KEY = os.getenv('SECRET_KEY', 'LOCAL NOT SO SECRET KEY')
POSTGRES_USER = os.getenv('POSTGRES_USER', 'serviceform')
POSTGRES_DB = os.getenv('POSTGRES_DB', 'serviceform')
POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'django')
SERVICEFORM_HOST = os.getenv('SERVICEFORM_HOST', 'localhost')
ADMIN_NAME = os.getenv('ADMIN_NAME', 'Unknown Admin')
ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'no@email.set')
SERVER_EMAIL = os.getenv('SERVER_EMAIL', f'noreply@{SERVICEFORM_HOST}')
CODE_LETTERS = os.getenv('CODE_LETTERS', 'ABCDE')
LANGUAGE_CODE = os.getenv('LANGUAGE_CODE', 'fi')
TIME_ZONE = os.getenv('TIME_ZONE', 'Europe/Helsinki')


ALLOWED_HOSTS = [SERVICEFORM_HOST]

# Application definition

INSTALLED_APPS = [
    'raven.contrib.django.raven_compat',
    'grappelli',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'compressor',
    'crispy_forms',
    'nested_admin',
    'djcelery',
    'colorful',
    'cachalot',
    'guardian',

    'serviceform',
    'tasks',

    'select2',
]

CACHALOT_ENABLED = IS_WEB and not DEBUG

if DEBUG:
    INSTALLED_APPS += [
        'debug_toolbar',
        ]

AUTHENTICATION_BACKENDS = (
    'django.contrib.auth.backends.ModelBackend', # default
    'guardian.backends.ObjectPermissionBackend',
)

DEBUG_TOOLBAR_PANELS = [
    'debug_toolbar.panels.versions.VersionsPanel',
    'debug_toolbar.panels.timer.TimerPanel',
    'debug_toolbar.panels.settings.SettingsPanel',
    'debug_toolbar.panels.headers.HeadersPanel',
    'debug_toolbar.panels.request.RequestPanel',
    'debug_toolbar.panels.sql.SQLPanel',
    'debug_toolbar.panels.staticfiles.StaticFilesPanel',
    'debug_toolbar.panels.templates.TemplatesPanel',
    'debug_toolbar.panels.cache.CachePanel',
    'debug_toolbar.panels.signals.SignalsPanel',
    'debug_toolbar.panels.logging.LoggingPanel',
    'debug_toolbar.panels.redirects.RedirectsPanel',
    'cachalot.panels.CachalotPanel'
]

GRAPPELLI_CLEAN_INPUT_TYPES = False
CRISPY_TEMPLATE_PACK = 'bootstrap3'
MIDDLEWARE_CLASSES = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.auth.middleware.SessionAuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'serviceform.utils.ClearParticipantCacheMiddleware',
    'serviceform.utils.InvalidateCachalotAfterEachRequestMiddleware'
]

if DEBUG:
    MIDDLEWARE_CLASSES += ['debug_toolbar.middleware.DebugToolbarMiddleware']

ROOT_URLCONF = 'serviceform_project.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [os.path.join(BASE_DIR, 'templates')]
        ,
        'APP_DIRS': DEBUG,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

if not DEBUG:
    TEMPLATES[0]['OPTIONS'].update(
        {
            'loaders': [
                ('django.template.loaders.cached.Loader', [
                    'django.template.loaders.filesystem.Loader',
                    'django.template.loaders.app_directories.Loader',
                ])]})

WSGI_APPLICATION = 'serviceform_project.wsgi.application'


# Database
# https://docs.djangoproject.com/en/1.9/ref/settings/#databases


DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': POSTGRES_DB,
        'USER': POSTGRES_USER,
        'PASSWORD': POSTGRES_PASSWORD,
        'HOST': 'db',
        'PORT': 5432,
    }
}


LOGGING_CONFIG = None

if PRODUCTION:
    SESSION_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    CSRF_COOKIE_SECURE = True
    CSRF_COOKIE_HTTPONLY = True
    X_FRAME_OPTIONS = 'DENY'
    SECURE_BROWSER_XSS_FILTER = True


if not PRODUCTION:
    EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s %(name)s %(message)s'
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            },
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
            },
        },
        'loggers': {
            '': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': True,
            },
            'celery': {
                'handlers': ['console'],
                'level': 'INFO',
                'propagate': False,
            },
        },
    }
    dictConfig(LOGGING)

else:
    LOGGING = {
        'version': 1,
        'disable_existing_loggers': True,
        'formatters': {
            'verbose': {
                'format': '%(levelname)s %(asctime)s %(module)s %(name)s %(message)s'
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            },
        },
        'handlers': {
            'mail_admins': {
                'level': 'ERROR',
                'class': 'django.utils.log.AdminEmailHandler',
                'include_html': True,
            },
            'console': {
                'class': 'logging.StreamHandler',
            },
            'sentry': {
                'level': 'WARNING',  # To capture more than ERROR, change to WARNING, INFO, etc.
                'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
                #'tags': {'custom-tag': 'x'},
            },
        },
        'loggers': {
            '': {
                'handlers': ['console', 'sentry'],
                'level': 'DEBUG',
                'propagate': True,
            },
            'django.template': {
                'handlers': ['console', 'sentry'],
                'level': 'WARNING',
                'propagate': False,
            },
            'django': {
                'handlers': ['console', 'sentry'],
                'level': 'DEBUG',
                'propagate': False,
            },
            'celery': {
                'handlers': ['console', 'sentry'],
                'level': 'DEBUG',
                'propagate': False,
            },
        },
    }
    dictConfig(LOGGING)


# Password validation
# https://docs.djangoproject.com/en/1.9/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

COMPRESS_PRECOMPILERS = (
    ('text/x-scss', 'django_libsass.SassCompiler'),
)

COMPRESS_OFFLINE = True

# Internationalization
# https://docs.djangoproject.com/en/1.9/topics/i18n/


USE_I18N = True

USE_L10N = True

USE_TZ = True

OTHER_CAN_SEE_DATA = False

# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/1.9/howto/static-files/

STATICFILES_FINDERS = ("django.contrib.staticfiles.finders.FileSystemFinder",
                       "django.contrib.staticfiles.finders.AppDirectoriesFinder",
                       "compressor.finders.CompressorFinder",
)

STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'static')
GRAPPELLI_ADMIN_TITLE = _('Serviceform admin')

LOCALE_PATHS = [os.path.join(BASE_DIR, 'serviceform_project', 'locale')]

ADMINS = [(ADMIN_NAME, ADMIN_EMAIL)]
SERVER_URL = 'http://localhost:8000' if not PRODUCTION else f'https://{SERVICEFORM_HOST}'

BROKER_URL = 'redis://redis:6379/15'

LOGIN_URL = '/admin/login/'
CELERY_RESULT_BACKEND='djcelery.backends.database:DatabaseBackend'
CELERYBEAT_SCHEDULER='djcelery.schedulers.DatabaseScheduler'
CELERYD_HIJACK_ROOT_LOGGER = False
CELERY_TASK_SERIALIZER='json'
CELERY_ACCEPT_CONTENT = ['json']

CACHES = {
    'default': {
        'BACKEND': 'redis_cache.RedisCache',
        'LOCATION': [
            'redis:6379',
        ],
        'OPTIONS': {
            'DB': 2, # local 2, production 1.
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'SERIALIZER_CLASS': 'redis_cache.serializers.JSONSerializer',
        },
    },
    'persistent': {
        'BACKEND': 'redis_cache.RedisCache',
        'LOCATION': [
            'redis:6379',
        ],
        'OPTIONS': {
            'DB': 1, # local 2, production 1.
            'PARSER_CLASS': 'redis.connection.HiredisParser',
            'SERIALIZER_CLASS': 'redis_cache.serializers.JSONSerializer',
        },
        'TIMEOUT': None,
    },
    'cachalot': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'cachalot',
    }
}

if os.getenv('DOCKER_BUILD'):  # Disable redis while running docker build command
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        }
    }

CACHALOT_CACHE = 'cachalot'

from django.conf.locale.fi import formats as fi_formats
fi_formats.DATETIME_FORMAT = "d.m.Y H:i"

if PRODUCTION:
    import raven
    RAVEN_CONFIG = {
        'dsn': RAVEN_DSN,
        # If you are using git, you can also automatically configure the
        # release based on the git info.
        #'release': raven.fetch_git_sha(os.path.dirname(__file__) + '/..'),
    }

DATA_UPLOAD_MAX_NUMBER_FIELDS = 20000

SILENCED_SYSTEM_CHECKS = [
    'cachalot.E001'
]

AUTH_KEY_EXPIRE_DAYS = 3*30  # 3 months
AUTH_STORE_KEYS = 10

