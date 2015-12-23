from django.db.migrations.operations import RunSQL


class BaseMigrateSQL(RunSQL):
    def deconstruct(self):
        name, args, kwargs = super(BaseMigrateSQL, self).deconstruct()
        kwargs['name'] = self.name
        return (name, args, kwargs)

    def __init__(self, name, sql, reverse_sql=None, state_operations=None, hints=None):
        super(BaseMigrateSQL, self).__init__(sql, reverse_sql=reverse_sql,
                                             state_operations=state_operations, hints=hints)
        self.name = name


class ReverseMigrateSQL(BaseMigrateSQL):
    def describe(self):
        return 'Reverse SQL migration: "{name}"'.format(name=self.name)


class MigrateSQL(BaseMigrateSQL):
    def describe(self):
        return 'Custom SQL migration: "{name}"'.format(name=self.name)

    def state_forwards(self, app_label, state):
        super(MigrateSQL, self).state_forwards(app_label, state)
        if not hasattr(state, 'custom_sql'):
            setattr(state, 'custom_sql', {})
        state.custom_sql.setdefault(app_label, {})
        state.custom_sql[app_label][self.name] = (self.sql, self.reverse_sql)
