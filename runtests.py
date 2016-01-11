#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import os
import sys

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.test_project.settings")
sys.path.insert(0, 'tests')

import django
from django.core.management import call_command

django.setup()

call_command('test')

sys.exit(0)
