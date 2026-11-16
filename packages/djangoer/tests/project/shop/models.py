from django.db import models


class Customer(models.Model):
    """Someone who orders."""

    name = models.CharField(max_length=100)
    email = models.EmailField(unique=True, help_text="Where receipts go")

    class Meta:
        app_label = "shop"


class Product(models.Model):
    class Kind(models.TextChoices):
        BOOK = "book", "Book"
        TOOL = "tool", "Tool"

    name = models.CharField(max_length=100)
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.BOOK)
    price = models.DecimalField(max_digits=8, decimal_places=2)
    attributes = models.JSONField(default=dict)

    class Meta:
        app_label = "shop"


class Order(models.Model):
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT, related_name="orders")
    products = models.ManyToManyField(Product, related_name="orders")
    note = models.TextField(blank=True)
    paid = models.BooleanField(default=False)
    placed_at = models.DateTimeField(auto_now_add=True)
    shipped_at = models.DateTimeField(null=True)

    class Meta:
        app_label = "shop"
        db_table = "orders"
        ordering = ["-placed_at"]
