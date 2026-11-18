"""What a model shares with others and what a column declares beside its type: inheritance
(abstract, multi-table, proxy), a many-to-many through a model of its own, a foreign key the
database does not check, grouped choices, a collation, a decimal's precision."""

import django
from django.db import models
from django.db.models.functions import Lower


class Timestamped(models.Model):
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        abstract = True
        app_label = "kinds"


class Site(Timestamped):
    name = models.CharField(max_length=50, db_collation="NOCASE")
    budget = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        app_label = "kinds"


class Shop(Site):
    serves_pizza = models.BooleanField(default=False)

    class Meta:
        app_label = "kinds"


class OpenShop(Shop):
    """The shops open today."""

    class Meta:
        app_label = "kinds"
        proxy = True


class Team(models.Model):
    # A help text of several lines, with a quote: DBML writes it between three quotes.
    name = models.CharField(max_length=50, help_text="The team's name.\n0: no name yet.")

    class Meta:
        app_label = "kinds"


if django.VERSION >= (5, 0):
    models.GeneratedField(
        expression=Lower("name"),
        output_field=models.CharField(max_length=50),
        db_persist=False,
    ).contribute_to_class(Team, "lower_name")


class Person(models.Model):
    teams = models.ManyToManyField(Team, through="Membership", related_name="members")
    # The row may outlive the site: no foreign key in the database.
    lives_near = models.ForeignKey(
        Site, on_delete=models.DO_NOTHING, null=True, db_constraint=False
    )
    media = models.CharField(
        max_length=10,
        choices=[
            ("Audio", [("vinyl", "Vinyl"), ("cd", "CD")]),
            ("Video", [("vhs", "VHS Tape")]),
        ],
    )

    class Meta:
        app_label = "kinds"


class Membership(models.Model):
    person = models.ForeignKey(Person, on_delete=models.CASCADE)
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    joined = models.DateField()

    class Meta:
        app_label = "kinds"
