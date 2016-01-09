
class SQLItem(object):
    def __init__(self, name, sql, reverse_sql=None, dependencies=None, replace=False):
        self.name = name
        self.sql = sql
        self.reverse_sql = reverse_sql
        self.dependencies = dependencies or []
        self.replace = replace
