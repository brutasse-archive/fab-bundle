from {{ base_settings }} import *
import django

DEBUG = False
TEMPLATE_DEBUG = DEBUG

ADMINS = ({% for admin in admins %}
    ('{{ admin.name }}', '{{ admin.email }}'),{% endfor %}
)
MANAGERS = ADMINS
SEND_BROKEN_LINK_EMAILS = True

SECRET_KEY = '{{ secret_key }}'

TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

BASE_URL = 'https://{{ http_host }}'
MEDIA_ROOT = '{{ media_root }}'
MEDIA_URL = BASE_URL + '/media/'

{% if staticfiles %}
# Staticfiles with cached storage if available
if 'django.contrib.staticfiles' in INSTALLED_APPS:
    STATICFILES_FINDERS = (
        'django.contrib.staticfiles.finders.FileSystemFinder',
        'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    )
    if django.VERSION >= (1, 4):
        STATICFILES_STORAGE = 'django.contrib.staticfiles.storage.CachedStaticFilesStorage'
elif 'staticfiles' in INSTALLED_APPS:
    STATICFILES_FINDERS = (
        'staticfiles.finders.FileSystemFinder',
        'staticfiles.finders.AppDirectoriesFinder',
    )

    import staticfiles
    if staticfiles.__version__ >= (1, 1):
        STATICFILES_STORAGE = 'staticfiles.storage.CachedStaticFilesStorage'

STATIC_ROOT = '{{ static_root }}'
STATIC_URL = BASE_URL + '/static/'
ADMIN_MEDIA_PREFIX = STATIC_URL + 'admin/'
{% endif %}

{% if cache >= 0 %}
CACHES = {
    'default': {
        'BACKEND': 'redis_cache.RedisCache',
        'LOCATION': 'localhost:6379',
        'OPTIONS': {
            'DB': {{ cache }},
        },
    },
}
MESSAGE_STORAGE = 'django.contrib.messages.storage.fallback.FallbackStorage'
SESSION_ENGINE = 'django.contrib.sessions.backends.cached_db'
{% endif %}

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': '{{ http_host }}',
        'USER': 'postgres',
    }
}

{% if sentry %}
SENTRY_KEY = '{{ sentry.key }}'
SENTRY_SERVERS = [
    '{{ sentry.url }}',
]
SENTRY_ADMINS = ({% for admin in admins %}
    '{{ admin }}',{% endfor %}
)
{% endif %}

{% if email %}
EMAIL_SUBJECT_PREFIX = '[{{ http_host }}] '
SERVER_EMAIL = '{{ email.from }}'
EMAIL_HOST = '{{ email.host }}'
{% if email.user %}EMAIL_HOST_USER = '{{ email.user }}'{% endif %}
{% if email.password %}EMAIL_HOST_PASSWORD = '{{ email.password }}'{% endif %}
{% if email.port %}EMAIL_PORT = '{{ email.port }}'{% endif %}
{% if email.backend %}EMAIL_BACKEND = '{{ email.user }}'{% endif %}
{% if email.tls %}EMAIL_USE_TLS = True{% endif %}
{% endif %}

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True
