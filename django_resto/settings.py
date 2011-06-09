"""Default settings. Override them in the settings file of your project.

See the README for more information.
"""

from django.conf import settings


def get_setting(name):
    name = 'RESTO_%s' % name
    # raise a KeyError if we have no such setting
    default = globals()[name]
    return getattr(settings, name, default)


RESTO_TIMEOUT = 2

RESTO_MEDIA_HOSTS = ()

RESTO_FATAL_EXCEPTIONS = True

RESTO_SHOW_TRACEBACK = False
