"""Models Django does not manage (`managed = False`): tables made by something else. Their
indexes are declared, not created, so PostgreSQL's kinds of index can be declared here on a
SQLite test database."""

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import ArrayField, DateTimeRangeField, RangeOperators
from django.contrib.postgres.indexes import BrinIndex, GinIndex, HashIndex, OpClass
from django.db import models
from django.db.models import F, Q


class Worker(models.Model):
    name = models.CharField(max_length=50)

    class Meta:
        app_label = "legacy"
        managed = False
        db_table = "legacy_workers"


class Job(models.Model):
    """Removed later by 'python manage.py cleanup'"""

    lock = models.TextField(unique=True, null=True)
    worker = models.ForeignKey(Worker, on_delete=models.SET_NULL, null=True)
    authors = ArrayField(models.CharField(max_length=64), default=list)
    tags = ArrayField(models.TextField(), default=list)

    class Meta:
        app_label = "legacy"
        managed = False
        db_table = "legacy_jobs"


class Document(models.Model):
    labels = models.JSONField(default=dict)
    base_path = models.TextField()
    seen = models.DateTimeField()
    domain = models.IntegerField()
    digest = models.CharField(max_length=64)

    class Meta:
        app_label = "legacy"
        managed = False
        indexes = [
            GinIndex(fields=["labels"], name="document_labels"),
            BrinIndex(fields=["seen"], name="document_seen", pages_per_range=16),
            HashIndex(fields=["digest"], name="document_digest"),
            models.Index(
                OpClass(F("base_path"), name="text_ops"),
                name="document_base_path",
                include=["domain"],
            ),
        ]


class Reservation(models.Model):
    room = models.IntegerField()
    during = DateTimeRangeField()
    cancelled = models.BooleanField(default=False)

    class Meta:
        app_label = "legacy"
        managed = False
        constraints = [
            ExclusionConstraint(
                name="exclude_overlapping",
                expressions=[("during", RangeOperators.OVERLAPS), ("room", RangeOperators.EQUAL)],
                condition=Q(cancelled=False),
            ),
        ]
