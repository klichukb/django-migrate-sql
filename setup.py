#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import os

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup


def get_version(package):
    """
    Get migrate_sql version as listed in `__version__` in `__init__.py`.
    """
    init_py = open(os.path.join(package, '__init__.py')).read()
    return re.search("__version__ = ['\"]([^'\"]+)['\"]", init_py).group(1)

VERSION = get_version('migrate_sql')


setup(
    name='django-migrate-sql',
    version=VERSION,
    description='Raw SQL Migration layer for Django',
    author='Bogdan Klichuk',
    author_email='klichukb@gmail.com',
    packages=[
        'migrate_sql',
    ],
    package_dir={'migrate_sql': 'migrate_sql'},
    license='BSD',
    zip_safe=False,
    url='https://github.com/klichukb/django-migrate-sql',
    classifiers=[
     'Development Status :: 2 - Pre-Alpha',
        'Framework :: Django',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: BSD License',
        'Natural Language :: English',
        "Programming Language :: Python :: 2",
        'Programming Language :: Python :: 2.7',
    ],
    test_suite='runtests',
    install_requires=[],
)
