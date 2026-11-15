from django.apps import AppConfig


class DjangoerConfig(AppConfig):
    """In INSTALLED_APPS, djangoer adds `python manage.py studio`. It has no models."""

    name = "djangoer"
    verbose_name = "Djangoer"
