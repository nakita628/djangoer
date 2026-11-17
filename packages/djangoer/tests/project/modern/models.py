"""What newer Django has, on the Django that has it: database defaults and generated columns
(5.0), composite primary keys (5.2). On an older Django the app has no models."""

import django
from django.db import models
from django.db.models import F
from django.db.models.functions import Now

if django.VERSION >= (5, 0):

    class Item(models.Model):
        name = models.CharField(
            max_length=50, db_comment="The name shown to customers", help_text="Shown in lists"
        )
        price = models.DecimalField(max_digits=10, decimal_places=2)
        tax = models.DecimalField(max_digits=10, decimal_places=2)
        total = models.GeneratedField(
            expression=F("price") + F("tax"),
            output_field=models.DecimalField(max_digits=11, decimal_places=2),
            db_persist=True,
        )
        created = models.DateTimeField(db_default=Now())
        stock = models.IntegerField(db_default=0)

        class Meta:
            app_label = "modern"
            db_table_comment = "Things we sell"


if django.VERSION >= (5, 2):

    class OrderLine(models.Model):
        pk = models.CompositePrimaryKey("order_id", "item")
        order_id = models.IntegerField()
        item = models.ForeignKey(Item, on_delete=models.CASCADE)
        quantity = models.IntegerField()

        class Meta:
            app_label = "modern"

    class Shipment(models.Model):
        line = models.ForeignObject(
            OrderLine,
            on_delete=models.CASCADE,
            from_fields=("order_id", "item"),
            to_fields=("order_id", "item"),
        )
        order_id = models.IntegerField()
        item = models.ForeignKey(Item, on_delete=models.CASCADE, related_name="+")

        class Meta:
            app_label = "modern"
