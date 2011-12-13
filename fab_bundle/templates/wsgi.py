import os

from django.core.handlers.wsgi import WSGIHandler


os.environ['DJANGO_SETTINGS_MODULE'] = 'settings'
application = WSGIHandler()
