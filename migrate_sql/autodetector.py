from django.db.migrations.autodetector import MigrationAutodetector as DjangoMigrationAutodetector
from django.apps import apps

from migrate_sql.operations import MigrateSQL, ReverseMigrateSQL


class MigrationAutodetector(DjangoMigrationAutodetector):

    def generate_altered_fields(self):
        result = super(MigrationAutodetector, self).generate_altered_fields()
        for config in apps.get_app_configs():
            if hasattr(config, 'custom_sql'):
                custom_sql = getattr(self.from_state, 'custom_sql', {})
                old_state = custom_sql.get(config.label, {})
                for sql_name, (sql, reverse_sql) in config.custom_sql:
                    old_sql, old_reverse_sql = old_state.get(sql_name, (None, None))

                    # Compare SQL of `from` and `to` states. If they match -- no changes have been
                    # made. Sides can be both strings and lists of 2-tuples,
                    # natively supported by Django's RunSQL:
                    #
                    # https://docs.djangoproject.com/en/1.8/ref/migration-operations/#runsql
                    #
                    # NOTE: if iterables inside a list provide params, they should strictly be
                    # tuples, not list, in order comparison to work.
                    if sql == old_sql:
                        continue

                    # migrate backwards
                    if old_reverse_sql:
                        self.add_operation(
                            config.label,
                            ReverseMigrateSQL(sql_name, old_reverse_sql, reverse_sql=old_sql),
                        )
                    self.add_operation(
                        config.label,
                        MigrateSQL(sql_name, sql, reverse_sql=reverse_sql),
                    )
        return result
