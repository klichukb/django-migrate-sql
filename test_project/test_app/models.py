from django.db import models

class Author(models.Model):
    name = models.CharField(max_length=200)
    registered = models.BooleanField(default=False)

class Book(models.Model):
    name = models.CharField(max_length=200)
    author = models.ForeignKey(Author)
    rating = models.IntegerField(null=True, blank=True)
    published = models.BooleanField(default=True)
