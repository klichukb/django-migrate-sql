from django.db.migrations.autodetector import MigrationAutodetector as DjangoMigrationAutodetector

from migrate_sql.operations import AlterSQL, ReverseAlterSQL, CreateSQL, DeleteSQL
from migrate_sql.graph import SqlStateGraph


class SQLBlob(object):
    pass

SQL_BLOB = SQLBlob()


def _sql_params(sql):
    params = None
    if isinstance(sql, (list, tuple)):
        elements = len(sql)
        if elements == 2:
            sql, params = sql
        else:
            raise ValueError("Expected a 2-tuple but got %d" % elements)
    return sql, params


def is_sql_equal(sqls1, sqls2):
    is_seq1 = isinstance(sqls1, (list, tuple))
    is_seq2 = isinstance(sqls2, (list, tuple))

    if not is_seq1:
        sqls1 = (sqls1,)
    if not is_seq2:
        sqls2 = (sqls2,)

    if len(sqls1) != len(sqls2):
        return False

    for sql1, sql2 in zip(sqls1, sqls2):
        sql1, params1 = _sql_params(sql1)
        sql2, params2 = _sql_params(sql2)
        if sql1 != sql2 or params1 != params2:
            return False
    return True


class MigrationAutodetector(DjangoMigrationAutodetector):
    def __init__(self, from_state, to_state, questioner=None, to_sql_graph=None):
        super(MigrationAutodetector, self).__init__(from_state, to_state, questioner)
        self.to_sql_graph = to_sql_graph
        self.from_sql_graph = getattr(self.from_state, 'custom_sql', None) or SqlStateGraph()
        self.from_sql_graph.resolve_dependencies()

    def sort_sql_changes(self, new_keys, changed_keys):
        result_keys = []
        all_keys = new_keys | changed_keys
        for key in all_keys:
            node = self.to_sql_graph.node_map[key]
            ancs = node.ancestors()[:-1]
            ancs.reverse()
            pos = next((i for i, k in enumerate(result_keys) if k in ancs), len(result_keys))
            result_keys.insert(pos, key)

            if key in changed_keys:
                descs = reversed(node.descendants()[:-1])
                for desc in descs:
                    if desc not in all_keys and desc not in result_keys:
                        result_keys.insert(pos, desc)
                        changed_keys.add(desc)
        return result_keys

    def _generate_reversed_sql(self, keys, changed_keys, latest_operations):
        for key in keys:
            if key not in changed_keys:
                continue
            app_label, sql_name = key
            old_node = self.from_sql_graph.nodes[key]
            if not old_node.reverse_sql:
                continue

            # migrate backwards
            operation = ReverseAlterSQL(sql_name, old_node.reverse_sql, reverse_sql=old_node.sql)
            sql_deps = self.from_sql_graph.node_map[key].children
            sql_deps.add(key)
            deps = []
            for sql_dep in sql_deps:
                info = latest_operations.get(sql_dep)
                dep = (sql_dep[0], SQL_BLOB, sql_dep[1], info)
                deps.append(dep)

            self.add_operation(app_label, operation, dependencies=deps)
            latest_operations[key] = operation

    def _generate_sql(self, keys, changed_keys, latest_operations):
        for key in reversed(keys):
            app_label, sql_name = key
            new_node = self.to_sql_graph.nodes[key]
            operation_cls = AlterSQL if key in changed_keys else CreateSQL
            sql_deps = self.to_sql_graph.node_map[key].parents
            operation = operation_cls(sql_name, new_node.sql, reverse_sql=new_node.reverse_sql,
                                      dependencies=set(sql_deps))
            sql_deps.add(key)
            deps = []
            for sql_dep in sql_deps:
                info = latest_operations.get(sql_dep)
                dep = (sql_dep[0], SQL_BLOB, sql_dep[1], info)
                deps.append(dep)
            self.add_operation(app_label, operation, dependencies=deps)
            latest_operations[key] = operation

    def _generate_delete_sql(self, deleted_keys, latest_operations):
        for key in deleted_keys:
            app_label, sql_name = key
            old_node = self.from_sql_graph.nodes[key]
            self.add_operation(
                app_label,
                DeleteSQL(sql_name, old_node.reverse_sql, reverse_sql=old_node.sql),
            )

    def generate_changed_sql(self):
        from_keys = set(self.from_sql_graph.nodes.keys())
        to_keys = set(self.to_sql_graph.nodes.keys())
        new_keys = to_keys - from_keys
        deleted_keys = from_keys - to_keys
        changed_keys = set()

        for key in from_keys & to_keys:
            # Compare SQL of `from` and `to` states. If they match -- no changes have been
            # made. Sides can be both strings and lists of 2-tuples,
            # natively supported by Django's RunSQL:
            #
            # https://docs.djangoproject.com/en/1.8/ref/migration-operations/#runsql
            if is_sql_equal(self.from_sql_graph.nodes[key].sql, self.to_sql_graph.nodes[key].sql):
                continue
            changed_keys.add(key)

        keys = self.sort_sql_changes(new_keys, changed_keys)
        latest_operations = {}

        self._generate_reversed_sql(keys, changed_keys, latest_operations)
        self._generate_sql(keys, changed_keys, latest_operations)
        self._generate_delete_sql(deleted_keys, latest_operations)

    def check_dependency(self, operation, dependency):
        if isinstance(dependency[1], SQLBlob):
            return dependency[3] == operation
        return super(MigrationAutodetector, self).check_dependency(operation, dependency)

    def generate_altered_fields(self):
        result = super(MigrationAutodetector, self).generate_altered_fields()
        self.generate_changed_sql()
        return result
