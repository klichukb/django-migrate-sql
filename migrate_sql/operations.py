from django.db.migrations.operations import RunSQL

from migrate_sql.graph import SqlStateGraph, SqlItemNode


class BaseMigrateSQL(RunSQL):
    def deconstruct(self):
        name, args, kwargs = super(BaseMigrateSQL, self).deconstruct()
        kwargs['name'] = self.name
        return (name, args, kwargs)

    def __init__(self, name, sql, reverse_sql=None, state_operations=None, hints=None,
                 dependencies=None):
        super(BaseMigrateSQL, self).__init__(sql, reverse_sql=reverse_sql,
                                             state_operations=state_operations, hints=hints)
        self.name = name
        self.dependencies = dependencies or ()


class ReverseAlterSQL(BaseMigrateSQL):
    def describe(self):
        return 'Reverse alter SQL "{name}"'.format(name=self.name)


class BaseAlterSQL(BaseMigrateSQL):
    def get_sql_state(self, state):
        if not hasattr(state, 'custom_sql'):
            setattr(state, 'custom_sql', SqlStateGraph())
        return state.custom_sql


class AlterSQL(BaseAlterSQL):
    def describe(self):
        return 'Alter SQL "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(AlterSQL, self).state_forwards(app_label, state)
        custom_sql = self.get_sql_state(state)

        custom_sql.add_node(
            (app_label, self.name),
            SqlItemNode(self.sql, self.reverse_sql),
        )
        for dep in self.dependencies:
            custom_sql.add_dependency(app_label, self.name, dep)


class CreateSQL(AlterSQL):
    def describe(self):
        return 'Create SQL "{name}"'.format(name=self.name)


class DeleteSQL(BaseAlterSQL):
    def describe(self):
        return 'Delete SQL "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(DeleteSQL, self).state_forwards(app_label, state)
        custom_sql = self.get_sql_state(state)

        custom_sql.remove_node((app_label, self.name))
