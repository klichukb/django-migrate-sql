# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import tempfile
import shutil
import os
from StringIO import StringIO
from contextlib import contextmanager, nested
from importlib import import_module
from psycopg2.extras import register_composite, CompositeCaster

from django.test import TestCase
from django.db import connection
from django.db.migrations.loader import MigrationLoader
from django.apps import apps
from django.core.management import call_command
from django.conf import settings
from django.test.utils import extend_sys_path

from test_app.models import Book
from migrate_sql import SQLItem


class TupleComposite(CompositeCaster):
    def make(self, values):
        return tuple(values)


def module_dir(module):
    """
    Find the name of the directory that contains a module, if possible.
    RMigrateaise ValueError otherwise, e.g. for namespace packages that are split
    over several directories.
    """
    # Convert to list because _NamespacePath does not support indexing on 3.3.
    paths = list(getattr(module, '__path__', []))
    if len(paths) == 1:
        return paths[0]
    else:
        filename = getattr(module, '__file__', None)
        if filename is not None:
            return os.path.dirname(filename)
    raise ValueError("Cannot determine directory containing %s" % module)


def item(name, version, dependencies=None):
    dependencies = dependencies or ()
    args = ', '.join(['{name}{ver} {name}'.format(name=dep[1], ver=version)
                      for dep in dependencies] + ['arg{i} int'.format(i=i + 1)
                                                  for i in range(version)])
    sql, reverse_sql = ('CREATE TYPE {name} AS ({args}); -- {ver}'.format(
        name=name, args=args, ver=version),
                        'DROP TYPE {}'.format(name))
    return SQLItem(name, sql, reverse_sql, dependencies=dependencies)


def mig_name(name):
    return name[0], name[1][:4]


def run_query(sql, params=None):
    cursor = connection.cursor()
    cursor.execute(sql, params=params)
    return cursor.fetchall()


class BaseMigrateSQLTestCase(TestCase):
    def setUp(self):
        super(BaseMigrateSQLTestCase, self).setUp()
        self.config = apps.get_app_config('test_app')
        self.config2 = apps.get_app_config('test_app2')
        self.out = StringIO()

    def tearDown(self):
        super(BaseMigrateSQLTestCase, self).tearDown()
        if hasattr(self.config, 'custom_sql'):
            del self.config.custom_sql
        if hasattr(self.config2, 'custom_sql'):
            del self.config2.custom_sql

    def check_migrations_content(self, expected):
        loader = MigrationLoader(None, load=True)
        available = loader.disk_migrations.keys()
        for expc_mig, (check_exists, dependencies, operations) in expected.items():
            key = next((mig for mig in available if mig_name(mig) == mig_name(expc_mig)), None)
            if check_exists:
                self.assertIsNotNone(key, 'Expected migration {} not found.'.format(expc_mig))
            else:
                self.assertIsNone(key, 'Unexpected migration {} was found.'.format(expc_mig))
                continue
            migration = loader.disk_migrations[key]
            self.assertEqual([mig_name(dep) for dep in migration.dependencies], dependencies)
            self.assertEqual([(op.__class__.__name__, op.name) for op in migration.operations],
                             operations)

    @contextmanager
    def temporary_migration_module(self, app_label='test_app', module=None):
        """
        Allows testing management commands in a temporary migrations module.
        The migrations module is used as a template for creating the temporary
        migrations module. If it isn't provided, the application's migrations
        module is used, if it exists.
        Returns the filesystem path to the temporary migrations module.
        """
        temp_dir = tempfile.mkdtemp()
        try:
            target_dir = tempfile.mkdtemp(dir=temp_dir)
            with open(os.path.join(target_dir, '__init__.py'), 'w'):
                pass
            target_migrations_dir = os.path.join(target_dir, 'migrations')

            if module is None:
                module = apps.get_app_config(app_label).name + '.migrations'

            try:
                source_migrations_dir = module_dir(import_module(module))
            except (ImportError, ValueError):
                pass
            else:
                shutil.copytree(source_migrations_dir, target_migrations_dir)

            with extend_sys_path(temp_dir):
                new_module = os.path.basename(target_dir) + '.migrations'
                new_setting = settings.MIGRATION_MODULES.copy()
                new_setting[app_label] = new_module
                with self.settings(MIGRATION_MODULES=new_setting):
                    yield target_migrations_dir
        finally:
            shutil.rmtree(temp_dir)


class MigrateSQLTestCase(BaseMigrateSQLTestCase):
    SQL_V1 = (
        # sql
        [("""
            CREATE OR REPLACE FUNCTION top_books()
                RETURNS SETOF test_app_book AS $$
            BEGIN
                RETURN QUERY
                    SELECT * FROM test_app_book ab
                    WHERE ab.rating > %s
                    ORDER BY ab.rating DESC;
            END;
            $$ LANGUAGE plpgsql;
          """, [5])],
        # reverse sql
        'DROP FUNCTION top_books()',
    )

    SQL_V2 = (
        # sql
        [("""
            CREATE OR REPLACE FUNCTION top_books(min_rating int = %s)
                RETURNS SETOF test_app_book AS $$
            BEGIN
                RETURN QUERY EXECUTE
                   'SELECT * FROM test_app_book ab
                    WHERE ab.rating > $1
                    AND ab.published
                    ORDER BY ab.rating DESC'
                USING min_rating;
            END;
            $$ LANGUAGE plpgsql;
          """, [5])],
        # reverse sql
        'DROP FUNCTION top_books(int)',
    )

    def setUp(self):
        super(MigrateSQLTestCase, self).setUp()
        books = (
            Book(name="Clone Wars", author="John Ben", rating=4, published=True),
            Book(name="The mysterious dog", author="John Ben", rating=6, published=True),
            Book(name="HTML 5", author="John Ben", rating=9, published=True),
            Book(name="Management", author="John Ben", rating=8, published=False),
            Book(name="Python 3", author="John Ben", rating=3, published=False),
        )
        Book.objects.bulk_create(books)

    def check_run_migrations(self, migrations):
        for migration, expected in migrations:
            call_command('migrate', 'test_app', migration, stdout=self.out)
            if expected:
                result = run_query('SELECT name FROM top_books()')
                self.assertEqual(result, expected)
            else:
                result = run_query("SELECT COUNT(*) FROM pg_proc WHERE proname = 'top_books'")
                self.assertEqual(result, [(0,)])

    def check_migrations(self, content, results, migration_module=None, app_label='test_app'):
        with self.temporary_migration_module(module=migration_module):
            call_command('makemigrations', app_label, stdout=self.out)
            self.check_migrations_content(content)

            call_command('migrate', app_label, stdout=self.out)
            self.check_run_migrations(results)

    def test_migration_add(self):
        sql, reverse_sql = self.SQL_V1
        self.config.custom_sql = [SQLItem('top_books', sql, reverse_sql)]
        expected_content = {
            ('test_app', '0002'): (
                True,
                [('test_app', '0001')],
                [('CreateSQL', 'top_books')],
            ),
        }
        expected_results = (
            ('0002', [('HTML 5',), ('Management',), ('The mysterious dog',)]),
        )
        self.check_migrations(expected_content, expected_results)

    def test_migration_change(self):
        sql, reverse_sql = self.SQL_V2
        self.config.custom_sql = [SQLItem('top_books', sql, reverse_sql)]

        expected_content = {
            ('test_app', '0003'): (
                True,
                [('test_app', '0002')],
                [('ReverseAlterSQL', 'top_books'), ('AlterSQL', 'top_books')],
            ),
        }
        expected_results = (
            ('0003', [('HTML 5',), ('The mysterious dog',)]),
            ('0002', [('HTML 5',), ('Management',), ('The mysterious dog',)]),
            ('0001', None),
        )
        self.check_migrations(expected_content, expected_results, 'test_app.migrations_change')

    def test_migration_delete(self):
        self.config.custom_sql = []

        expected_content = {
            ('test_app', '0003'): (
                True,
                [('test_app', '0002')],
                [('DeleteSQL', 'top_books')],
            ),
        }
        expected_results = (
            ('0003', None),
        )
        self.check_migrations(expected_content, expected_results, 'test_app.migrations_change')

    def test_migration_recreate(self):
        sql, reverse_sql = self.SQL_V2
        self.config.custom_sql = [SQLItem('top_books', sql, reverse_sql)]

        expected_content = {
            ('test_app', '0004'): (
                True,
                [('test_app', '0003')],
                [('CreateSQL', 'top_books')],
            ),
        }
        expected_results = (
            ('0003', None),
            ('0002', [('HTML 5',), ('Management',), ('The mysterious dog',)]),
        )
        self.check_migrations(expected_content, expected_results, 'test_app.migrations_recreate')


class SQLDependenciesTestCase(BaseMigrateSQLTestCase):
    RESULTS_EXPECTED = {
        ('test_app', '0004'): [
            # product check
            ("(('(1, 2)', '(3)', 4, 5), (('(6, 7)', '(8)', 9, 10), 11), '(12)', 13)",
             'product',
             ['product', 'book', 'author',
              'rating', 'sale', 'edition'],
             (((1, 2), (3,), 4, 5), (((6, 7), (8,), 9, 10), 11), (12,), 13)),

            # narration check
            ("('(1, 2)', ('(3, 4)', '(5)', 6, 7), 8)",
             'narration',
             ['narration', 'book', 'sale', 'rating'],
             ((1, 2), ((3, 4), (5,), 6, 7), 8)),
        ],
        ('test_app', '0002'): [
            # narration check
            ("('(1)', '(2)', 3)",
             'narration',
             ['rating', 'book', 'sale', 'narration'],
             ((1,), (2,), 3)),
        ],
        ('test_app2', 'zero'): [
            # edition check
            (None, 'edition', [], None),
            # ratings check
            (None, 'ratings', [], None),
        ],
        ('test_app', '0005'): [
            # narration check
            ("(1)", 'edition', ['edition'], (1,)),

            # product check
            (None, 'product', [], None),
        ],
        ('test_app2', '0003'): [
            # sale check
            (None, 'sale', [], None),
        ],
    }

    def check_type(self, repr_sql, fetch_type, known_types, expect):
        cursor = connection.cursor()
        if repr_sql:
            for _type in known_types:
                register_composite(str(_type), cursor.cursor, factory=TupleComposite)

            sql = 'SELECT ROW{repr_sql}::{ftype}'.format(repr_sql=repr_sql, ftype=fetch_type)
            cursor.execute(sql)
            result = cursor.fetchone()[0]
            self.assertEqual(result, expect)
        else:
            result = run_query("SELECT COUNT(*) FROM pg_type WHERE typname = %s",
                               [fetch_type])
            self.assertEqual(result, [(0,)])

    def check_migrations(self, content, migrations, module=None, module2=None):
        with nested(self.temporary_migration_module(app_label='test_app', module=module),
                    self.temporary_migration_module(app_label='test_app2', module=module2)):
            call_command('makemigrations', stdout=self.out)
            self.check_migrations_content(content)

            for app_label, migration in migrations:
                call_command('migrate', app_label, migration, stdout=self.out)
                check_cases = self.RESULTS_EXPECTED[(app_label, migration)]
                for check_case in check_cases:
                    self.check_type(*check_case)

    def test_deps_create(self):
        self.config.custom_sql = [
            item('rating', 1),
            item('book', 1),
            item('narration', 1, [('test_app2', 'sale'), ('test_app', 'book')]),
        ]
        self.config2.custom_sql = [item('sale', 1)]
        expected_content = {
            ('test_app2', '0001'): (
                True,
                [],
                [('CreateSQL', 'sale')],
            ),
            ('test_app', '0002'): (
                True,
                [('test_app2', '0001'), ('test_app', '0001')],
                [('CreateSQL', 'book'), ('CreateSQL', 'rating'),
                 ('CreateSQL', 'narration')],
            ),
        }
        migrations = (
            ('test_app', '0002'),
        )
        self.check_migrations(expected_content, migrations)

    def test_deps_update(self):
        self.config.custom_sql = [
            item('rating', 1),
            item('edition', 1),
            item('author', 1, [('test_app', 'book')]),
            item('narration', 1,  [('test_app2', 'sale'), ('test_app', 'book')]),
            item('book', 2, [('test_app2', 'sale'), ('test_app', 'rating')]),
            item('product', 1,
                 [('test_app', 'book'), ('test_app', 'author'), ('test_app', 'edition')]),
        ]
        self.config2.custom_sql = [item('sale', 2)]

        expected_content = {
            ('test_app', '0003'): (
                True,
                [('test_app', '0002')],
                [('ReverseAlterSQL', 'narration'), ('CreateSQL', 'edition'),
                 ('ReverseAlterSQL', 'book')],
            ),
            ('test_app2', '0002'): (
                True,
                [('test_app', '0003'), ('test_app2', '0001')],
                [('ReverseAlterSQL', 'sale'), ('AlterSQL', 'sale')],
            ),
            ('test_app', '0004'): (
                True,
                [('test_app2', '0002'), ('test_app', '0003')],
                [('AlterSQL', 'book'), ('CreateSQL', 'author'),
                 ('AlterSQL', 'narration'), ('CreateSQL', 'product')],
            ),
        }
        migrations = (
            ('test_app', '0004'),
            ('test_app', '0002'),
            ('test_app', '0004'),
        )
        self.check_migrations(
            expected_content, migrations,
            module='test_app.migrations_deps_update', module2='test_app2.migrations_deps_update',
        )

    def test_deps_no_changes(self):
        self.config.custom_sql = [
            item('rating', 1),
            item('book', 1),
            item('narration', 1, [('test_app2', 'sale'), ('test_app', 'book')]),
        ]
        self.config2.custom_sql = [item('sale', 1)]

        expected_content = {
            ('test_app', '0003'): (False, [], []),
            ('test_app2', '0002'): (False, [], []),
        }
        migrations = ()
        self.check_migrations(
            expected_content, migrations,
            module='test_app.migrations_deps_update', module2='test_app2.migrations_deps_update',
        )

    def test_deps_delete(self):
        self.config.custom_sql = [
            item('rating', 1),
            item('edition', 1),
        ]
        self.config2.custom_sql = []

        expected_content = {
            ('test_app', '0005'): (
                True,
                [('test_app', '0004')],
                [('DeleteSQL', 'narration'), ('DeleteSQL', 'product'),
                 ('DeleteSQL', 'author'), ('DeleteSQL', 'book')],
            ),
            ('test_app2', '0003'): (
                True,
                [('test_app', '0005'), ('test_app2', '0002')],
                [('DeleteSQL', 'sale')],
            ),
        }
        migrations = (
            ('test_app', '0005'),
            ('test_app', '0002'),
            ('test_app2', 'zero'),
            ('test_app', '0005'),
            ('test_app2', '0003'),
            ('test_app', '0004'),
        )
        self.check_migrations(
            expected_content, migrations,
            module='test_app.migrations_deps_delete', module2='test_app2.migrations_deps_delete',
        )
