
class SQLItem(object):
    def __init__(self, name, sql, reverse_sql=None, dependencies=None, recreate=False):
        self.name = name
        self.sql = sql
        self.reverse_sql = reverse_sql
        self.dependencies = dependencies or []
        self.recreate = recreate
