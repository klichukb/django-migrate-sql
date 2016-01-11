# django-migrate-sql

[![Build Status](https://travis-ci.org/klichukb/django-migrate-sql.svg?branch=master)](https://travis-ci.org/klichukb/django-migrate-sql)
[![codecov.io](https://img.shields.io/codecov/c/github/klichukb/django-migrate-sql/master.svg)](https://codecov.io/github/klichukb/django-migrate-sql?branch=master)

Django Migrations support for raw SQL.

## About
This tool implements mechanism for managing changes to custom SQL entities (functions, types, indices, triggers) using built-in migration mechanism. Technically creates a sophistication layer on top of the `RunSQL` Django operation.

## What it does
* Makes maintaining your SQL functions, custom composite types, indices and triggers easier.
* Structures SQL into configuration of **SQL items**, that are identified by names and divided among apps, just like models.
* Automatically gathers and persists changes of your custom SQL into migrations using `makemigrations`.
* Properly executes backwards/forwards keeping integrity of database.
* Create -> Drop -> Recreate approach for changes to items that do not support altering and require dropping and recreating.
* Dependencies system for SQL items, which solves the problem of updating items, that rely on others (for example custom types/functions that use other custom types), and require dropping all dependency tree previously with further recreation.

## What it does not
* Does not parse SQL nor validate queries during `makemigrations` or `migrate` because is database-agnostic. For this same reason setting up proper dependencies is user's responsibility.
* Does not create `ALTER` queries for items that support this, for example `ALTER TYPE` in Postgre SQL, because is database-agnostic. In case your tools allow rolling all the changes through `ALTER` queries, you can consider not using this app **or** restructure migrations manually after creation by nesting generated operations into [`state_operations` of `RunSQL`](https://docs.djangoproject.com/en/1.8/ref/migration-operations/#runsql) that does `ALTER`.
* (**TODO**)During `migrate` does not restore full state of items for analysis, thus does not notify about existing changes to schema that are not migrated **nor** does not recognize circular dependencies during migration execution.

## Installation

Download source code
```
$ pip install -e git+http://github.com/klichukb/django-migrate-sql.git#egg=django-migrate-sql
```

Add `migrate_sql` to `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    `migrate_sql`,
]
```
App defines a custom `makemigrations` command, that inherits from Django's core one, so in order `migrate_sql` app to kick in put it after any other apps that redefine `makemigrations` command too.

## Usage
1) Create `sql_config.py` module to root of a target app you want to manage custom SQL for.
2) Define SQL items in it as follows:

```python
# PostgreSQL example.
# Let's define a simple function and let `migrate_sql` manage it's changes.

from migrate_sql.config import SQLItem

sql_items = [
    SQLItem(
        # name of the item
        'make_sum',
        # forward sql
        'create or replace function make_sum(a int, b int) returns int as $$ '
        'begin return a + b; end; '
        '$$ language plpgsql;',
        # sql for removal
        reverse_sql='drop function make_sum;',
        # this item should not drop itself before creating new version -- 'create or replace' will replace it.
        replace=True,
    ),
]
```
3) Create migration `./manage.py makemigrations`:
```
Migrations for 'app_name':
  0004_auto_xxxx.py:
    - Create SQL "make_sum"
```
4) Execute migration `./manage.py migrate`:
```
Operations to perform:
  Apply all migrations: app_name
Running migrations:
  Rendering model states... DONE
  Applying app_name.0004_xxxx... OK
```

5) Check result in `./manage.py dbshell`:
```
db_name=# select make_sum(12, 15);
 make_sum 
----------
       27
(1 row)
```








