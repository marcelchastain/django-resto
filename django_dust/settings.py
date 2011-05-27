"""Default settings. Override them in the settings file of your project.

See the README for more information.
"""

from django.conf import settings


def get_setting(name):
    # raise a KeyError if we have no such setting
    default = globals()['DUST_%s' % name]
    return getattr(settings, name, default)


DUST_TIMEOUT = 2

DUST_MEDIA_HOSTS = ()

DUST_FATAL_EXCEPTIONS = True

DUST_SHOW_TRACEBACK = False
