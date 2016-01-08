from django.db.migrations.operations import RunSQL
from django.db.migrations.operations.base import Operation

from migrate_sql.graph import SQLStateGraph
from migrate_sql import SQLItem


class MigrateSQLMixin(object):
    def get_sql_state(self, state):
        if not hasattr(state, 'custom_sql'):
            setattr(state, 'custom_sql', SQLStateGraph())
        return state.custom_sql


class AlterSQLState(MigrateSQLMixin, Operation):
    def describe(self):
        return 'Alter SQL state "{name}"'.format(name=self.name)

    def deconstruct(self):
        kwargs = {
            'name': self.name,
        }
        if self.add_dependencies:
            kwargs['add_dependencies'] = self.add_dependencies
        if self.remove_dependencies:
            kwargs['remove_dependencies'] = self.remove_dependencies
        if self.recreate:
            kwargs['recreate'] = self.recreate
        return (self.__class__.__name__, [], kwargs)

    def state_forwards(self, app_label, state):
        custom_sql = self.get_sql_state(state)
        key = (app_label, self.name)

        if key not in custom_sql.nodes:
            # XXX: dummy for `migrate` command, that does not preserve state object.
            # Should fail with error when fixed.
            return

        sql_item = custom_sql.nodes[key]

        for dep in self.add_dependencies:
            # we are also adding relations to aggregated SQLItem, but only to restore
            # original items. Still using graph for advanced node/arc manipulations.

            # XXX: dummy `if` for `migrate` command, that does not preserve state object.
            # Fail with error when fixed
            if dep in sql_item.dependencies:
                sql_item.dependencies.remove(dep)
            custom_sql.add_lazy_dependency(key, dep)

        for dep in self.remove_dependencies:
            sql_item.dependencies.append(dep)
            custom_sql.remove_lazy_dependency(key, dep)

    def database_forwards(self, app_label, schema_editor, from_state, to_state):
        pass

    def database_backwards(self, app_label, schema_editor, from_state, to_state):
        pass

    @property
    def reversible(self):
        return True

    def __init__(self, name, add_dependencies=None, remove_dependencies=None, recreate=False):
        self.name = name
        self.add_dependencies = add_dependencies or ()
        self.remove_dependencies = remove_dependencies or ()
        self.recreate = recreate


class BaseAlterSQL(MigrateSQLMixin, RunSQL):
    def __init__(self, name, sql, reverse_sql=None, state_operations=None, hints=None):
        super(BaseAlterSQL, self).__init__(sql, reverse_sql=reverse_sql,
                                           state_operations=state_operations, hints=hints)
        self.name = name

    def deconstruct(self):
        name, args, kwargs = super(BaseAlterSQL, self).deconstruct()
        kwargs['name'] = self.name
        return (name, args, kwargs)


class ReverseAlterSQL(BaseAlterSQL):
    def describe(self):
        return 'Reverse alter SQL "{name}"'.format(name=self.name)


class AlterSQL(BaseAlterSQL):
    def deconstruct(self):
        name, args, kwargs = super(AlterSQL, self).deconstruct()
        kwargs['name'] = self.name
        return (name, args, kwargs)

    def describe(self):
        return 'Alter SQL "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(AlterSQL, self).state_forwards(app_label, state)
        custom_sql = self.get_sql_state(state)
        key = (app_label, self.name)

        if key not in custom_sql.nodes:
            # XXX: dummy for `migrate` command, that does not preserve state object.
            # Fail with error when fixed
            return

        sql_item = custom_sql.nodes[key]
        sql_item.sql = self.sql
        sql_item.reverse_sql = self.reverse_sql


class CreateSQL(BaseAlterSQL):
    def describe(self):
        return 'Create SQL "{name}"'.format(name=self.name)

    def deconstruct(self):
        name, args, kwargs = super(CreateSQL, self).deconstruct()
        kwargs['name'] = self.name
        if self.dependencies:
            kwargs['dependencies'] = self.dependencies
        if self.recreate:
            kwargs['recreate'] = self.recreate
        return (name, args, kwargs)

    def __init__(self, name, sql, reverse_sql=None, state_operations=None, hints=None,
                 dependencies=None, recreate=False):
        super(CreateSQL, self).__init__(name, sql, reverse_sql=reverse_sql,
                                        state_operations=state_operations, hints=hints)
        self.dependencies = dependencies or ()
        self.recreate = recreate

    def state_forwards(self, app_label, state):
        super(CreateSQL, self).state_forwards(app_label, state)
        custom_sql = self.get_sql_state(state)

        custom_sql.add_node(
            (app_label, self.name),
            SQLItem(self.name, self.sql, self.reverse_sql, list(self.dependencies), self.recreate),
        )

        for dep in self.dependencies:
            custom_sql.add_lazy_dependency((app_label, self.name), dep)


class DeleteSQL(BaseAlterSQL):
    def describe(self):
        return 'Delete SQL "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(DeleteSQL, self).state_forwards(app_label, state)
        custom_sql = self.get_sql_state(state)

        custom_sql.remove_node((app_label, self.name))
        custom_sql.remove_lazy_for_child((app_label, self.name))
