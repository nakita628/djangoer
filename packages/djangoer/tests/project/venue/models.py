"""Models in the shapes real projects have and the shop does not: choices that are no
identifiers, a loop of foreign keys, many-to-many to itself and twice to one model, indexes on
expressions and with conditions, long names."""

import zoneinfo

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
