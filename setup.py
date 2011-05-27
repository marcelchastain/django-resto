import distutils.core
import os
import os.path

# Avoid polluting the .tar.gz with ._* files under Mac OS X
os.putenv('COPYFILE_DISABLE', 'true')

with open(os.path.join(os.path.dirname(__file__), 'README.txt')) as f:
    long_description = '\n\n'.join(f.read().split('\n\n')[2:5])

distutils.core.setup(
    name='django-dust',
    version='0.2',
    author='Aymeric Augustin',
    author_email='aymeric.augustin@m4x.org',
    url='https://github.com/aaugustin/django-dust',
    description='Distributed Upload STorage for Django, a file backend '
                'that mirrors all incoming media files to several servers',
    long_description=long_description,
    packages=[
        'django_dust',
        'django_dust.tests',
    ],
    classifiers = [
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
    ],
)
