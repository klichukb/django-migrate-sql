from collections import namedtuple

from django.db.migrations.graph import Node, NodeNotFoundError
from django.apps import apps

SQLItemNode = namedtuple('SQLItemNode', ('sql', 'reverse_sql'))


class SQLStateGraph(object):
    """
    Represents graph assembled by SQL items as nodes and parent-child relations as arcs.
    """
    def __init__(self):
        self.nodes = {}
        self.node_map = {}
        self.dependencies = []

    def remove_node(self, key):
        # XXX: Workaround for Issue #2
        # Silences state aggregation problem in `migrate` command.
        if key in self.nodes and key in self.node_map:
            del self.nodes[key]
            del self.node_map[key]

    def add_node(self, key, sql_item):
        node = Node(key)
        self.node_map[key] = node
        self.nodes[key] = sql_item

    def add_lazy_dependency(self, app_label, child, parent):
        """
        Add dependency to be resolved and applied later.
        """
        self.dependencies.append((app_label, child, parent))

    def remove_lazy_dependencies(self, app_label, child):
        """
        Remove dependency to be resolved and applied later.
        """
        remove_deps = []
        for dep in self.dependencies:
            if dep[0] == app_label and dep[1] == child:
                remove_deps.append(dep)
        for dep in remove_deps:
            self.dependencies.remove(dep)

    def build_graph(self):
        """
        Read lazy dependency list and build graph.
        """
        for app_label, child, parent in self.dependencies:
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


def build_current_graph():
    """
    Read current state of SQL items from the current project state.

    Returns:
        (SQLStateGraph) Current project state graph.
    """
    graph = SQLStateGraph()
    for config in apps.get_app_configs():
        if not hasattr(config, 'custom_sql'):
            continue

        for sql_item in config.custom_sql:
            graph.add_node(
                (config.label, sql_item.name),
                SQLItemNode(sql_item.sql, sql_item.reverse_sql),
            )
            for dep in sql_item.dependencies:
                graph.add_lazy_dependency(
                    config.label, (config.label, sql_item.name), dep)
    graph.build_graph()
    return graph
