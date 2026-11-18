"""Models in the shapes real projects have and the shop does not: choices that are no
identifiers, a loop of foreign keys, many-to-many to itself and twice to one model, indexes on
expressions and with conditions, long names."""

import zoneinfo

import django
from django.contrib.contenttypes.fields import GenericForeignKey, GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.db.models.functions import Lower


class Organizer(models.Model):
    name = models.CharField(max_length=100)
    # Organizer → Event → Organizer: a loop.
    default_event = models.ForeignKey(
        "Event", null=True, on_delete=models.SET_NULL, related_name="+"
    )
    partners = models.ManyToManyField("self", blank=True)

    class Meta:
        app_label = "venue"


class Event(models.Model):
    organizer = models.ForeignKey(Organizer, on_delete=models.CASCADE)
    owner = models.ForeignKey("auth.User", on_delete=models.CASCADE)
    code = models.CharField(max_length=20, db_index=True)
    email = models.EmailField()
    primary = models.BooleanField(default=False)
    timezone = models.CharField(
        max_length=63, choices=[(tz, tz) for tz in sorted(zoneinfo.available_timezones())]
    )
    status = models.CharField(
        max_length=20, choices=[("", "---"), ("IN PROGRESS", "In progress"), ("done", "Done")]
    )
    vote = models.SmallIntegerField(choices=[(1, "Up"), (-1, "Down")], default=1)
    included = models.ManyToManyField(Organizer, related_name="included_in")
    excluded = models.ManyToManyField(Organizer, related_name="excluded_from")

    class Meta:
        app_label = "venue"
        indexes = [models.Index(Lower("email"), name="event_email_lower")]
        constraints = [
            models.UniqueConstraint(
                fields=["owner", "primary"], condition=Q(primary=True), name="one_primary_event"
            ),
            models.UniqueConstraint(Lower("code"), name="event_code_lower_unique"),
        ]


class PageViewRestriction(models.Model):
    restriction_type = models.CharField(
        max_length=20,
        choices=[
            ("none", "Public"),
            ("password", "Private, accessible with a shared password"),
            ("login", "Private, accessible to any logged-in users"),
            ("groups", "Private, accessible to users in specific groups"),
        ],
    )
    event = models.ForeignKey(Event, on_delete=models.CASCADE, db_index=False)

    class Meta:
        app_label = "venue"
        db_table = "venue_pageviewrestriction_with_a_long_table_name"


class Tag(models.Model):
    name = models.CharField(max_length=50)
    # `annex.Tag.kind` has choices of its own: the two enums must not be one.
    kind = models.CharField(max_length=10, choices=[("a", "A"), ("b", "B")], default="a")

    class Meta:
        app_label = "venue"


class Place(models.Model):
    name = models.CharField(max_length=100)
    tags = models.ManyToManyField(Tag)

    class Meta:
        app_label = "venue"


class Restaurant(Place):
    """Multi-table inheritance: its table has the link to its parent and its own columns."""

    serves_pizza = models.BooleanField(default=False)

    class Meta:
        app_label = "venue"


class Connection(models.Model):
    # One stored value under two labels, as django-sql-explorer has it.
    engine = models.CharField(
        max_length=255,
        choices=[
            ("django.db.backends.postgresql", "PostgreSQL"),
            ("django.db.backends.mysql", "MySQL"),
            ("django.db.backends.mysql", "MariaDB"),
        ],
    )

    class Meta:
        app_label = "venue"


class SortedManyToManyField(models.ManyToManyField):
    """As django-sortedm2m's: the through model Django creates has a column of its own."""

    def contribute_to_class(self, cls, name, **kwargs):
        super().contribute_to_class(cls, name, **kwargs)
        through = self.remote_field.through
        if not isinstance(through, str) and through._meta.auto_created:
            models.IntegerField(default=0).contribute_to_class(through, "sort_value")


class Gallery(models.Model):
    photos = SortedManyToManyField(Tag)

    class Meta:
        app_label = "venue"


class Rating(models.Model):
    """A row of any model: the pair of columns names it."""

    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey()
    score = models.PositiveSmallIntegerField()

    class Meta:
        app_label = "venue"


class Article(models.Model):
    ratings = GenericRelation(Rating)

    class Meta:
        app_label = "venue"


# As django-simple-history makes `HistoricalArticle`: a model built with type(), whose source
# no `class` statement holds.
HistoricalArticle = type(
    "HistoricalArticle",
    (models.Model,),
    {
        "__module__": __name__,
        "history_id": models.AutoField(primary_key=True),
        "article": models.ForeignKey(
            Article, on_delete=models.DO_NOTHING, db_constraint=False, related_name="+"
        ),
        "history_date": models.DateTimeField(),
        "Meta": type("Meta", (), {"app_label": "venue"}),
    },
)


# `condition` since Django 5.1, `check` before it.
_CHECK = "condition" if django.VERSION[:2] >= (5, 1) else "check"


class Price(models.Model):
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    discounted = models.DecimalField(max_digits=10, decimal_places=2, null=True)
    category = models.CharField(max_length=30)
    code = models.CharField(max_length=10)
    # SET(None) and SET_DEFAULT, as Django's docs show them.
    replaced_by = models.ForeignKey("self", on_delete=models.SET(None), null=True)
    place = models.ForeignKey(Place, on_delete=models.SET_DEFAULT, default=None, null=True)

    class Meta:
        app_label = "venue"
        constraints = [
            models.CheckConstraint(**{_CHECK: Q(amount__gte=0)}, name="price_not_negative"),
            models.UniqueConstraint(
                fields=["code"], name="code_unique_deferred", deferrable=models.Deferrable.DEFERRED
            ),
        ]
        indexes = [models.Index(fields=["category", "-amount"], name="category_amount")]
