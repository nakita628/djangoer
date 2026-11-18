def model(api, name):
    _status, snapshot = api("GET", "/api/schema")
    return next(m for m in snapshot["schema"]["models"] if m["name"] == name)


def field(api, model_name, name):
    return next(f for f in model(api, model_name)["fields"] if f["name"] == name)


def test_snapshot_lists_models_with_their_app_and_table(api):
    status, snapshot = api("GET", "/api/schema")
    assert status == 200
    assert snapshot["error"] is None
    schema = snapshot["schema"]
    assert schema["provider"] == "sqlite"
    names = [m["name"] for m in schema["models"]]
    assert {"Customer", "Product", "Order", "User"} <= set(names)
    order = model(api, "Order")
    assert order["app"] == "shop"
    assert order["dbName"] == "orders"
    assert "db_table = 'orders'" in order["attributes"]
    assert order["location"]["file"] == "project/shop/models.py"
    assert "project/shop/models.py" in [f["path"] for f in snapshot["files"]]


def test_a_foreign_key_is_a_column_and_a_relation(api):
    column = field(api, "Order", "customer_id")
    assert column["kind"] == "scalar"
    assert column["type"] == "ForeignKey"
    assert column["isForeignKey"] is True
    assert column["relation"] is None
    relation = field(api, "Order", "customer")
    assert relation["kind"] == "object"
    assert relation["type"] == "Customer"
    assert relation["relation"] == {
        "name": "orders",
        "fromFields": ["customer_id"],
        "toFields": ["id"],
        "onDelete": "PROTECT",
        "onUpdate": None,
        "through": None,
    }
    reverse = field(api, "Customer", "orders")
    assert reverse["kind"] == "object"
    assert reverse["isList"] is True


def test_choices_become_an_enum(api):
    kind = field(api, "Product", "kind")
    assert kind["kind"] == "enum"
    assert kind["type"] == "ProductKind"
    assert kind["default"] == "'book'"
    _status, snapshot = api("GET", "/api/schema")
    enum = next(e for e in snapshot["schema"]["enums"] if e["name"] == "ProductKind")
    assert enum["values"] == [
        {"name": "BOOK", "dbName": "book", "group": None},
        {"name": "TOOL", "dbName": "tool", "group": None},
    ]


def test_field_details(api):
    email = field(api, "Customer", "email")
    assert email["isUnique"] is True
    assert email["documentation"] == "Where receipts go"
    assert "unique=True" in email["attributes"]
    assert field(api, "Customer", "id")["isId"] is True
    assert field(api, "Order", "shipped_at")["isRequired"] is False
    assert field(api, "Order", "placed_at")["default"] == "now()"
    assert model(api, "Customer")["documentation"] == "Someone who orders."
    assert model(api, "Order")["documentation"] is None


def test_relations_for_the_diagram(api):
    _status, snapshot = api("GET", "/api/schema")
    relations = {r["id"]: r for r in snapshot["schema"]["relations"]}
    fk = relations["Customer.id->Order.customer_id"]
    assert fk["origin"] == "inferred"
    assert fk["from"] == {"model": "Customer", "field": "id", "cardinality": "one"}
    assert fk["to"] == {"model": "Order", "field": "customer_id", "cardinality": "zero-many"}
    m2m = relations["Order.products<->Product.orders"]
    assert m2m["origin"] == "implicit-many-to-many"
    assert (fk["constrained"], fk["parentLink"]) == (True, False)


def test_docs_describe_every_model(api):
    status, docs = api("GET", "/api/docs")
    assert status == 200
    order = next(m for m in docs["models"] if m["name"] == "Order")
    operations = {o["name"]: o for o in order["operations"]}
    assert "Order.objects.create(customer_id=1)" in operations["create"]["usage"]
    assert {"name": "ProductKind", "values": ["BOOK", "TOOL"]} in docs["enumTypes"]
    assert any(t["name"] == "OrderLookups" for t in docs["inputTypes"])
