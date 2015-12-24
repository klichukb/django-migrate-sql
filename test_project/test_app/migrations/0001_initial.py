# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import migrate_sql.operations


class Migration(migrations.Migration):

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Book',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('name', models.CharField(max_length=200)),
                ('author', models.CharField(max_length=200)),
                ('rating', models.IntegerField(null=True, blank=True)),
                ('published', models.BooleanField(default=True)),
            ],
        ),
        migrate_sql.operations.MigrateSQL(
            name=b'top_authors',
            sql=[(b'\n            CREATE OR REPLACE FUNCTION top_books()\n                RETURNS SETOF test_app_book AS $$\n            BEGIN\n                RETURN QUERY\n                    SELECT * FROM test_app_book ab\n                    WHERE ab.rating > %s\n                    ORDER BY ab.rating DESC;\n            END;\n            $$ LANGUAGE plpgsql;\n          ', [5])],
            reverse_sql=b'DROP FUNCTION top_books()',
        ),
    ]
