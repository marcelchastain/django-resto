import os

DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'},
}

DEFAULT_FILE_STORAGE = 'django_resto.storage.HybridStorage'

INSTALLED_APPS = ('django_resto',)

MEDIA_ROOT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tests', 'media')

MEDIA_URL = 'http://media.example.com/'

SECRET_KEY = 'Secret key for django-resto tests.'

del os
