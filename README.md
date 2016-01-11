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
Define SQL items in it (`sql_items`), for example:

```python
# PostgreSQL example.
# Let's define a simple function and let `migrate_sql` manage it's changes.

from migrate_sql.config import SQLItem

sql_items = [
    SQLItem(
        'make_sum',   # name of the item
        'create or replace function make_sum(a int, b int) returns int as $$ '
        'begin return a + b; end; ' 
        '$$ language plpgsql;',  # forward sql
        reverse_sql='drop function make_sum(int, int);',  # sql for removal
    ),
]
```
3) Create migration `./manage.py makemigrations`:
```
Migrations for 'app_name':
  0002_auto_xxxx.py:
    - Create SQL "make_sum"
```

You can take a look at content this generated:

```python
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations, models
import migrate_sql.operations


class Migration(migrations.Migration):
    dependencies = [
        ('app_name', '0001_initial'),
    ]
    operations = [
        migrate_sql.operations.CreateSQL(
            name=b'make_sum',
            sql=b'create or replace function make_sum(a int, b int) returns int as $$ begin return a + b; end; $$ language plpgsql;',
            reverse_sql=b'drop function make_sum(int, int);',
        ),
    ]
```
4) Execute migration `./manage.py migrate`:
```
Operations to perform:
  Apply all migrations: app_name
Running migrations:
  Rendering model states... DONE
  Applying app_name.0004_xxxx... OK
```

Check result in `./manage.py dbshell`:
```
db_name=# select make_sum(12, 15);
 make_sum 
----------
       27
(1 row)
```

Now, say, you want to change the function implementation so that it takes a custom type as argument:

5) Edit your `sql_config.py`:

```python
# PostgreSQL example #2.
# Function and custom type.

from migrate_sql.config import SQLItem

sql_items = [
    SQLItem(
        'make_sum',  # name of the item
        'create or replace function make_sum(a mynum, b mynum) returns mynum as $$ '
        'begin return (a.num + b.num, 'result')::mynum; end; '
        '$$ language plpgsql;',  # forward sql
        reverse_sql='drop function make_sum(mynum, mynum);',  # sql for removal
        # depends on `mynum` since takes it as argument. we won't be able to drop function
        # without dropping `mynum` first.
        dependencies=[('app_name', 'mynum')],
    ),
    SQLItem(
        'mynum'   # name of the item
        'create type mynum as (num int, name varchar(20));',  # forward sql
        reverse_sql='drop type mynum;',  # sql for removal
    ),
]
```

6) Generate migration `./manage.py makemigrations`:

```
Migrations for 'app_name':
  0003_xxxx:
    - Reverse alter SQL "make_sum"
    - Create SQL "mynum"
    - Alter SQL "make_sum"
    - Alter SQL state "make_sum"
``` 

You can take a look at the content this generated:

```
# -*- coding: utf-8 -*-
from __future__ import unicode_literals
from django.db import migrations, models
import migrate_sql.operations


class Migration(migrations.Migration):
    dependencies = [
        ('app_name', '0002_xxxx'),
    ]
    operations = [
        migrate_sql.operations.ReverseAlterSQL(
            name=b'make_sum',
            sql=b'drop function make_sum(int, int);',
            reverse_sql=b'create or replace function make_sum(a int, b int) returns int as $$ begin return a + b; end; $$ language plpgsql;',
        ),
        migrate_sql.operations.CreateSQL(
            name=b'mynum',
            sql=b'create type mynum as (num int, name varchar(20));',
            reverse_sql=b'drop type mynum;',
        ),
        migrate_sql.operations.AlterSQL(
            name=b'make_sum',
            sql=b'create or replace function make_sum(a mynum, b mynum) returns mynum as $$ begin return (a.num + b.num, \'result\')::mynum; end; $$ language plpgsql;',
            reverse_sql=b'drop function make_sum(mynum, mynum);',
        ),
        migrate_sql.operations.AlterSQLState(
            name=b'make_sum',
            add_dependencies=((b'app_name', b'mynum'),),
        ),
    ]
```
_**NOTE:** Previous function is completely dropped before creation
because definition of it changed. `CREATE OR REPLACE` would create another version of it, so `DROP` makes it clean._

**_If you put `replace=True` as kwarg to an `SQLItem` definition, it will NOT drop + create it, but just rerun forward SQL, which is `CREATE OR REPLACE` in this example._**


7) Execute migration `./manage.py migrate`:

```
Operations to perform:
  Apply all migrations: app_name
Running migrations:
  Rendering model states... DONE
  Applying brands.0003_xxxx... OK
```

Check results:
```
db_name=# select make_sum((5, 'a')::mynum, (3, 'b')::mynum);
  make_sum  
------------
 (8,result)
(1 row)

db_name=# select make_sum(12, 15);
ERROR:  function make_sum(integer, integer) does not exist
LINE 1: select make_sum(12, 15);
               ^
HINT:  No function matches the given name and argument types. You might need to add explicit type casts.
```

For more examples see `tests`.



