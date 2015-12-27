from collections import namedtuple

from django.db.migrations.graph import Node, NodeNotFoundError
from django.apps import apps

SqlItemNode = namedtuple('SqlItemNode', ('sql', 'reverse_sql'))


class SqlStateGraph(object):
    def __init__(self):
        self.nodes = {}
        self.node_map = {}

    def remove_node(self, key):
        # TODO: Dummy for Issue #2
        # Silences state aggregation problem in `migrate` command.
        if key in self.nodes and key in self.node_map:
            del self.nodes[key]
            del self.node_map[key]

    def add_node(self, key, sql_item):
        node = Node(key)
        self.node_map[key] = node
        self.nodes[key] = sql_item

    def add_dependency(self, app_label, child, parent):
        if child not in self.nodes:
            raise NodeNotFoundError(
                "App %s dependencies reference nonexistent child node %r" % (app_label, child),
                child
            )
        if parent not in self.nodes:
            raise NodeNotFoundError(
                "App %s dependencies reference nonexistent parent node %r" % (app_label, parent),
                parent
            )
        self.node_map[child].add_parent(self.node_map[parent])
        self.node_map[parent].add_child(self.node_map[child])
        self.clear_cache()


def build_current_graph():
    graph = SqlStateGraph()
    for config in apps.get_app_configs():
        if not hasattr(config, 'custom_sql'):
            continue

        for sql_item in config.custom_sql:
            graph.add_node(
                (config.label, sql_item.name),
                SqlItemNode(sql_item.sql, sql_item.reverse_sql),
            )
            for dep in sql_item.dependencies:
                graph.add_dependency(config.label, sql_item.name, dep)
    return graph
