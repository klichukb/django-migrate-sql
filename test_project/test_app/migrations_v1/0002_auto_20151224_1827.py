# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
import migrate_sql.operations


class Migration(migrations.Migration):

    dependencies = [
        ('test_app', '0001_initial'),
    ]

    operations = [
        migrate_sql.operations.MigrateSQL(
            name=b'top_books',
            sql=[(b'\n            CREATE OR REPLACE FUNCTION top_books()\n                RETURNS SETOF test_app_book AS $$\n            BEGIN\n                RETURN QUERY\n                    SELECT * FROM test_app_book ab\n                    WHERE ab.rating > %s\n                    ORDER BY ab.rating DESC;\n            END;\n            $$ LANGUAGE plpgsql;\n          ', [5])],
            reverse_sql=b'DROP FUNCTION top_books()',
        ),
    ]
