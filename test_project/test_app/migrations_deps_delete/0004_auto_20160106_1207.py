# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import migrate_sql.operations


class Migration(migrations.Migration):

    dependencies = [
        ('test_app2', '0002_auto_20160106_1207'),
        ('test_app', '0003_auto_20160106_1207'),
    ]

    operations = [
        migrate_sql.operations.AlterSQL(
            name='book',
            sql='CREATE TYPE book AS (sale2 sale, rating2 rating, arg1 int, arg2 int); -- 2',
            reverse_sql='DROP TYPE book',
            dependencies=[(b'test_app', 'rating'), (b'test_app2', 'sale')],
        ),
        migrate_sql.operations.CreateSQL(
            name='author',
            sql='CREATE TYPE author AS (book1 book, arg1 int); -- 1',
            reverse_sql='DROP TYPE author',
            dependencies=[(b'test_app', 'book')],
        ),
        migrate_sql.operations.AlterSQL(
            name='narration',
            sql='CREATE TYPE narration AS (sale1 sale, book1 book, arg1 int); -- 1',
            reverse_sql='DROP TYPE narration',
            dependencies=[(b'test_app', 'book'), (b'test_app2', 'sale')],
        ),
        migrate_sql.operations.CreateSQL(
            name='product',
            sql='CREATE TYPE product AS (book1 book, author1 author, edition1 edition, arg1 int); -- 1',
            reverse_sql='DROP TYPE product',
            dependencies=[(b'test_app', 'edition'), (b'test_app', 'book'), (b'test_app', 'author')],
        ),
    ]
