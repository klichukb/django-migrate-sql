# -*- coding: utf-8 -*-
from __future__ import unicode_literals

import tempfile
import shutil
import os
from StringIO import StringIO
from contextlib import contextmanager
from importlib import import_module

from django.test import TestCase
from django.db import connection
from django.apps import apps
from django.core.management import call_command
from django.test.utils import extend_sys_path

from test_app.models import Book
from migrate_sql import SqlItem


def top_books_sql_v1():
    min_rating = 5
    return (
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
          """, [min_rating])],

        # reverse sql
        'DROP FUNCTION top_books()',
    )


def top_books_sql_v2():
    min_rating = 5
    return (
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
          """, [min_rating])],

        # reverse sql
        'DROP FUNCTION top_books(int)',
    )


def run_query(sql, params=None):
    cursor = connection.cursor()
    cursor.execute(sql, params=params)
    return cursor.fetchall()


def module_dir(module):
    """
    Find the name of the directory that contains a module, if possible.
    Raise ValueError otherwise, e.g. for namespace packages that are split
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


class MigrateSQLTestCase(TestCase):
    def setUp(self):
        books = (
            Book(name="Clone Wars", author="John Ben", rating=4, published=True),
            Book(name="The mysterious dog", author="John Ben", rating=6, published=True),
            Book(name="HTML 5", author="John Ben", rating=9, published=True),
            Book(name="Management", author="John Ben", rating=8, published=False),
            Book(name="Python 3", author="John Ben", rating=3, published=False),
        )
        Book.objects.bulk_create(books)
        self.config = apps.get_app_config('test_app')
        self.counter = 0

    def tearDown(self):
        if hasattr(self.config, 'custom_sql'):
            del self.config.custom_sql

    def sample_sql(self):
        self.counter += 1
        return 'SELECT {}'.format(self.counter)

    def _test_output(self, string_io, expected_lines):
        lines = [ln.strip() for ln in string_io.getvalue().splitlines()]
        assert len(expected_lines) > 0
        self.assertIn(expected_lines[0], lines)
        pos = lines.index(expected_lines[0])
        for ln in lines: print ln
        self.assertEqual(lines[pos:pos + len(expected_lines)], expected_lines)

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
                with self.settings(MIGRATION_MODULES={app_label: new_module}):
                    yield target_migrations_dir

        finally:
            shutil.rmtree(temp_dir)

    def test_migration_add(self):
        sql, reverse_sql = top_books_sql_v1()
        self.config.custom_sql = [SqlItem('top_books', sql, reverse_sql)]
        cmd_output = StringIO()
        with self.temporary_migration_module():
            call_command('makemigrations', 'test_app', stdout=cmd_output)
            lines = [ln.strip() for ln in cmd_output.getvalue().splitlines()]
            expected_log = '- Create SQL "top_books"'
            self.assertIn(expected_log, lines)

            call_command('migrate', 'test_app', stdout=cmd_output)
            result = run_query('SELECT name FROM top_books()')
            self.assertEqual(result, [('HTML 5',), ('Management',), ('The mysterious dog',)])

    def test_migration_change(self):
        progress_expected = (
            ('0003', [('HTML 5',), ('The mysterious dog',)]),
            ('0002', [('HTML 5',), ('Management',), ('The mysterious dog',)]),
            ('0001', None),
        )
        sql, reverse_sql = top_books_sql_v2()
        self.config.custom_sql = [SqlItem('top_books', sql, reverse_sql)]

        cmd_output = StringIO()
        with self.temporary_migration_module(module='test_app.migrations_v1'):
            call_command('makemigrations', 'test_app', stdout=cmd_output)
            lines = [ln.strip() for ln in cmd_output.getvalue().splitlines()]
            self.assertIn('- Reverse alter SQL "top_books"', lines)
            self.assertIn('- Alter SQL "top_books"', lines)

            for migration, expected in progress_expected:
                call_command('migrate', 'test_app', migration, stdout=cmd_output)
                if expected:
                    result = run_query('SELECT name FROM top_books()')
                    self.assertEqual(result, expected)
                else:
                    result = run_query("SELECT COUNT(*) FROM pg_proc WHERE proname = 'top_books'")
                    self.assertEqual(result, [(0,)])

    def item(self, name, version, dependencies=None):
        dependencies = dependencies or ()
        deps = ', '.join(['_{name}{ver} {name}'.format(name=dep[1], ver=version)
                          for dep in dependencies])
        sql, reverse_sql = ('CREATE TYPE {name} AS ({deps}); -- {ver}'.format(
            name=name, deps=deps, ver=version),
                            'DROP TYPE {}'.format(name))
        return SqlItem(name, sql, reverse_sql, dependencies=dependencies)

    def test_migration_deps(self):
        sql, reverse_sql = top_books_sql_v1()
        sql2, reverse_sql2 = top_books_sql_v2()

        with self.temporary_migration_module():
            self.config.custom_sql = [
                self.item('top_ratings', 1),
                self.item('top_books', 1),
                self.item('top_narrations', 1, dependencies=[
                    ('test_app', 'top_sales'), ('test_app', 'top_books')]),
                self.item('top_sales', 1),
            ]
            cmd_output = StringIO()
            call_command('makemigrations', 'test_app', stdout=cmd_output)
            expected = [
                '- Create SQL "top_sales"',
                '- Create SQL "top_books"',
                '- Create SQL "top_narrations"',
                '- Create SQL "top_ratings"',
            ]
            self._test_output(cmd_output, expected)

            self.config.custom_sql = [
                self.item('top_sales', 2),
                self.item('top_ratings', 1),
                self.item('top_editions', 1),
                self.item('top_authors', 1,
                          dependencies=[('test_app', 'top_books')]),
                self.item('top_narrations', 1,  dependencies=[
                    ('test_app', 'top_sales'), ('test_app', 'top_books')]),
                self.item('top_books', 2, dependencies=[
                    ('test_app', 'top_sales'), ('test_app', 'top_ratings')]),
                self.item('top_products', 1, dependencies=[
                    ('test_app', 'top_books'), ('test_app', 'top_authors'),
                    ('test_app', 'top_editions')]),
            ]
            cmd_output = StringIO()
            call_command('makemigrations', 'test_app', stdout=cmd_output)
            expected = [
                '- Reverse alter SQL "top_narrations"',
                '- Reverse alter SQL "top_books"',
                '- Reverse alter SQL "top_sales"',
                '- Alter SQL "top_sales"',
                '- Alter SQL "top_books"',
                '- Create SQL "top_authors"',
                '- Alter SQL "top_narrations"',
                '- Create SQL "top_editions"',
                '- Create SQL "top_products"',
            ]
            self._test_output(cmd_output, expected)
            call_command('migrate', 'test_app')
            call_command('migrate', 'test_app', 'zero')

    def test_migration_delete(self):
        progress_expected = (
            ('0003', None),
            ('0002', [('HTML 5',), ('Management',), ('The mysterious dog',)]),
        )

        cmd_output = StringIO()
        with self.temporary_migration_module(module='test_app.migrations_v1'):
            self.config.custom_sql = []
            call_command('makemigrations', 'test_app', stdout=cmd_output)
            lines = [ln.strip() for ln in cmd_output.getvalue().splitlines()]
            self.assertIn('- Delete SQL "top_books"', lines)

            sql, reverse_sql = top_books_sql_v2()
            self.config.custom_sql = [SqlItem('top_books', sql, reverse_sql)]
            call_command('makemigrations', 'test_app', stdout=cmd_output)
            lines = [ln.strip() for ln in cmd_output.getvalue().splitlines()]
            self.assertIn('- Create SQL "top_books"', lines)

            for migration, expected in progress_expected:
                call_command('migrate', 'test_app', migration, stdout=cmd_output)
                if expected:
                    result = run_query('SELECT name FROM top_books()')
                    self.assertEqual(result, expected)
                else:
                    result = run_query("SELECT COUNT(*) FROM pg_proc WHERE proname = 'top_books'")
                    self.assertEqual(result, [(0,)])
