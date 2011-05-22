import os
import os.path

DATABASES = {
    'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'},
}

DEFAULT_FILE_STORAGE = 'django_dust.storage.DistributedStorage'

INSTALLED_APPS = ('django_dust',)

MEDIA_ROOT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'tests', 'media')

MEDIA_URL = 'http://media.example.com/'

del os
