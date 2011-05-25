from distutils.core import setup
import os.path

with open(os.path.join(os.path.dirname(__file__), 'README.md')) as f:
    long_description = '\n\n'.join(f.read().split('\n\n')[2:5])

setup(
    name='django_dust',
    version='0.1',
    description='Distributed Upload STorage for Django, a file backend '
                'that mirrors all incoming media files to several servers',
    long_description=long_description,
    packages=[
        'django_dust',
        'django_dust.backends',
        'django_dust.management',
        'django_dust.management.commands',
    ],
    classifiers = [
        "Development Status :: 3 - Alpha",
        "Environment :: Web Environment",
        "Framework :: Django",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: BSD License",
        "Operating System :: OS Independent",
        "Programming Language :: Python",
        "Topic :: Internet :: WWW/HTTP :: Site Management",
    ],
)
