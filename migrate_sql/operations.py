from django.db.migrations.operations import RunSQL

from migrate_sql.graph import SqlStateGraph, SqlItemNode


class BaseMigrateSQL(RunSQL):
    def deconstruct(self):
        name, args, kwargs = super(BaseMigrateSQL, self).deconstruct()
        kwargs['name'] = self.name
        return (name, args, kwargs)

    def __init__(self, name, sql, reverse_sql=None, state_operations=None, hints=None):
        super(BaseMigrateSQL, self).__init__(sql, reverse_sql=reverse_sql,
                                             state_operations=state_operations, hints=hints)
        self.name = name


class ReverseAlterSQL(BaseMigrateSQL):
    def describe(self):
        return 'Reverse alter SQL "{name}"'.format(name=self.name)


class AlterSQL(BaseMigrateSQL):
    def describe(self):
        return 'Alter SQL "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(AlterSQL, self).state_forwards(app_label, state)
        if not hasattr(state, 'custom_sql'):
            setattr(state, 'custom_sql', SqlStateGraph())

        state.custom_sql.add_node(
            (app_label, self.name),
            SqlItemNode(self.sql, self.reverse_sql),
        )


class CreateSQL(AlterSQL):
    def describe(self):
        return 'Create SQL "{name}"'.format(name=self.name)
