from django.apps import AppConfig

from test_app.sql import top_authors_sql

class TestAppConfig(AppConfig):
    name = 'test_app'
    verbose_name = 'Test App'
    custom_sql = (
        ('top_authors', top_authors_sql()),
    )
