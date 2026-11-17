"""An app whose models share their names with the venue's: `annex.Tag` beside `venue.Tag`."""

from django.db import models


class Tag(models.Model):
    # A field named as `venue.Tag`'s would be, with choices of its own.
    kind = models.CharField(max_length=10, choices=[("x", "X")])

    class Meta:
        app_label = "annex"
