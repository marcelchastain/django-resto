import distutils.core
import os

# Avoid polluting the .tar.gz with ._* files under Mac OS X
os.putenv('COPYFILE_DISABLE', 'true')

description = ('REplicated STOrage for Django, file backends '
               'that mirror media files to several servers over HTTP')

with open(os.path.join(os.path.dirname(__file__), 'README')) as f:
    long_description = '\n\n'.join(f.read().split('\n\n')[2:8])

distutils.core.setup(
    name='django-resto',
    version='1.1',
    author='Aymeric Augustin',
    author_email='aymeric.augustin@m4x.org',
    url='https://github.com/aaugustin/django-resto',
    description=description,
    long_description=long_description,
    download_url='http://pypi.python.org/pypi/django-resto',
    packages=[
        'django_resto',
        'django_resto.tests',
    ],
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2",
        "Programming Language :: Python :: 2.6",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.2",
        "Programming Language :: Python :: 3.3",
    ],
    platforms='all',
    license='BSD'
)
