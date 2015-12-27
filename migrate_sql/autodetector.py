from django.db.migrations.autodetector import MigrationAutodetector as DjangoMigrationAutodetector

from migrate_sql.operations import AlterSQL, ReverseAlterSQL, CreateSQL, DeleteSQL
from migrate_sql.graph import SqlStateGraph


class MigrationAutodetector(DjangoMigrationAutodetector):
    def __init__(self, from_state, to_state, questioner=None, to_sql_graph=None):
        super(MigrationAutodetector, self).__init__(from_state, to_state, questioner)
        self.to_sql_graph = to_sql_graph
        self.from_sql_graph = getattr(self.from_state, 'custom_sql', None) or SqlStateGraph()

    def generate_changed_sql(self):
        from_keys = set(self.from_sql_graph.nodes.keys())
        to_keys = set(self.to_sql_graph.nodes.keys())
        new_keys = to_keys - from_keys
        deleted_keys = from_keys - to_keys
        changed_keys = set()

        for key in new_keys:
            app_label, sql_name = key
            new_node = self.to_sql_graph.nodes[key]
            self.add_operation(
                app_label,
                CreateSQL(sql_name, new_node.sql, reverse_sql=new_node.reverse_sql),
            )

        for key in deleted_keys:
            app_label, sql_name = key
            old_node = self.from_sql_graph.nodes[key]
            self.add_operation(
                app_label,
                DeleteSQL(sql_name, old_node.reverse_sql, reverse_sql=old_node.sql),
            )

        for key in from_keys & to_keys:
            # Compare SQL of `from` and `to` states. If they match -- no changes have been
            # made. Sides can be both strings and lists of 2-tuples,
            # natively supported by Django's RunSQL:
            #
            # https://docs.djangoproject.com/en/1.8/ref/migration-operations/#runsql
            #
            # NOTE: if iterables inside a list provide params, they should strictly be
            # tuples, not list, in order comparison to work.
            if self.from_sql_graph.nodes[key] == self.to_sql_graph.nodes[key].sql:
                continue
            changed_keys.add(key)

        for key in changed_keys:
            app_label, sql_name = key
            old_node = self.from_sql_graph.nodes[key]
            new_node = self.to_sql_graph.nodes[key]
            # migrate backwards
            if old_node.reverse_sql:
                self.add_operation(
                    app_label,
                    ReverseAlterSQL(sql_name, old_node.reverse_sql, reverse_sql=old_node.sql),
                )

            self.add_operation(
                app_label,
                AlterSQL(sql_name, new_node.sql, reverse_sql=new_node.reverse_sql),
            )

    def generate_altered_fields(self):
        result = super(MigrationAutodetector, self).generate_altered_fields()
        self.generate_changed_sql()
        return result
