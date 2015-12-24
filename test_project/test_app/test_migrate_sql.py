from django.test import TestCase

from test_app.models import Book


class MigrateSQLTestCase(TestCase):
    def setUp(self):
        books = (
            Book(name="Clone Wars", author="John Ben", rating=9, published=True),
            Book(name="The mysterious dog", author="John Ben", rating=6, published=True),
            Book(name="HTML 5", author="John Ben", rating=9, published=True),
            Book(name="Management", author="John Ben", rating=9, published=False),
            Book(name="Python 3", author="John Ben", rating=9, published=False),
        )
        Book.objects.bulk_create(books)

    def test_all(self):
        self.assertTrue(True)
