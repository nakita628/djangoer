# Django adds `objects` to every model class as it is created, which no annotation says:
# pyright: reportAttributeAccessIssue=false
import os
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

import django
import pytest

sys.path.insert(0, str(Path(__file__).parent))
os.environ["DJANGO_SETTINGS_MODULE"] = "project.settings"
os.environ["DJANGOER_TEST_DB"] = str(
    Path(tempfile.mkdtemp(prefix="djangoer-tests-")) / "db.sqlite3"
)
django.setup()

from django.core.management import call_command  # noqa: E402
from django.db import connection  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def tables():
    """One database for the session, with the tables of every model."""
    call_command("migrate", run_syncdb=True, verbosity=0)
    yield


@pytest.fixture(autouse=True)
def data(tables):
    """Three customers, two products, two orders — and nothing a test left behind."""
    from project.shop.models import Customer, Order, Product

    Order.objects.all().delete()
    Product.objects.all().delete()
    Customer.objects.all().delete()
    ann = Customer.objects.create(name="Ann", email="ann@example.com")
    Customer.objects.create(name="Ben", email="ben@example.com")
    Customer.objects.create(name="Chika", email="chika@example.com")
    book = Product.objects.create(name="Two Scoops", kind="book", price=Decimal("39.50"))
    tool = Product.objects.create(name="Wrench", kind="tool", price=Decimal("12.00"))
    first = Order.objects.create(customer=ann, note="gift", paid=True)
    first.products.set([book, tool])
    Order.objects.create(customer=ann).products.set([book])
    yield
    connection.close()


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from djangoer.studio.app import create_app
    from djangoer.studio.brands import Alias
    from djangoer.studio.state import State

    app = create_app(State(Alias("default"), Path(__file__).parent))
    return TestClient(app, base_url="http://127.0.0.1", raise_server_exceptions=False)


@pytest.fixture
def api(client):
    """Call the API as the browser would: (status, parsed JSON)."""

    def call(method: str, path: str, body=None):
        response = client.request(method, path, json=body)
        return response.status_code, response.json()

    return call
