from djangoer.studio import inputs
from djangoer.studio.domain.orm import analyze as orm_analyze
from djangoer.studio.domain.orm import complete as orm_complete


# The domain takes one input record; the tests say what they ask in fewer words.
def analyze(query):
    return orm_analyze.analyze(inputs.Query(query=query))


def check(query):
    return orm_analyze.check(inputs.Query(query=query))


def complete(query, offset):
    return orm_complete.complete(inputs.QueryAt(query=query, offset=offset))


def detail(query, offset, name):
    return orm_complete.detail(inputs.CompletionAt(query=query, offset=offset, name=name))


def hover(query, offset):
    return orm_complete.hover(inputs.QueryAt(query=query, offset=offset))


def signature(query, offset):
    return orm_complete.signature(inputs.QueryAt(query=query, offset=offset))


def calls(query):
    return [(c["model"], c["operation"], c["write"]) for c in analyze(query)["calls"]]


def touched(query):
    return {t["model"]: t["fields"] for t in analyze(query)["touched"]}


def messages(query):
    return [d["message"] for d in analyze(query)["diagnostics"]]


def labels(text):
    offset = text.index("|")
    items = complete(text.replace("|", ""), offset)["items"]
    return [item["label"] for item in sorted(items, key=lambda item: item["sortText"])]


def test_a_chain_is_one_call_on_the_model_it_starts_from():
    query = (
        'Order.objects.filter(customer__name__icontains="a", paid=True).order_by("-placed_at")[:5]'
    )
    assert calls(query) == [("Order", "order_by", False)]
    assert touched(query) == {"Order": ["customer", "paid", "placed_at"], "Customer": ["name"]}
    assert messages(query) == []
    assert analyze(query)["calls"][0]["range"] == {"start": 0, "end": len(query)}


def test_variables_carry_what_they_were_assigned():
    query = "c = Customer.objects.get(pk=1)\nc.orders.filter(paid=True).count()"
    assert calls(query) == [("Customer", "get", False), ("Order", "count", False)]
    assert touched(query)["Order"] == ["paid"]
    assert "orders" in touched(query)["Customer"]
    loop = "for o in Order.objects.all():\n    o.products.count()"
    assert calls(loop) == [("Order", "all", False), ("Product", "count", False)]


def test_writes_are_marked():
    assert calls('Customer.objects.create(name="Z", email="z@example.com")') == [
        ("Customer", "create", True)
    ]
    assert calls("Order.objects.filter(paid=False).delete()") == [("Order", "delete", True)]
    assert calls("o = Order.objects.first()\no.paid = True\no.save()") == [
        ("Order", "first", False),
        ("Order", "save", True),
    ]
    two = 'Customer.objects.filter(pk=1).update(name="A")\nOrder.objects.all().delete()'
    assert analyze(two)["transaction"] is True


def test_q_f_and_aggregates_name_fields_of_the_queryset():
    query = (
        'Order.objects.filter(Q(paid=True) | Q(note__startswith="g")).annotate(n=Count("products"))'
    )
    assert touched(query) == {"Order": ["paid", "note", "products"], "Product": []}
    assert messages('Order.objects.annotate(n=Count("products")).filter(n__gt=1)') == []


def test_mistakes():
    assert messages("Order.objects.filter(payed=True)") == [
        'Cannot resolve "payed" into a field of Order'
    ]
    assert messages("Order.objects.filter(paid__foo=1)") == [
        'Unsupported lookup "foo" for field "paid"'
    ]
    assert messages("Nope.objects.all()") == ['Unknown name "Nope"']
    assert messages("Order.objects.filter(")[0].startswith("SyntaxError")
    result = analyze("Order.objects.filter(payed=True)")
    span = result["diagnostics"][0]["range"]
    assert "Order.objects.filter(payed=True)"[span["start"] : span["end"]] == "payed"


def test_what_is_not_available_stops_the_run():
    for query in (
        "import os",
        "Order.__dict__",
        '__import__("os")',
        "while True: pass",
        "Order.objects.all()._query",
    ):
        diagnostics = check(query)["diagnostics"]
        assert diagnostics and diagnostics[0]["severity"] == "error", query
    assert check("Order.objects.filter(payed=True)")["diagnostics"][0]["severity"] == "warning"


def test_completion_follows_the_chain():
    assert "Order" in labels("Or|")
    assert labels("Order.|") == ["objects"]
    assert {"filter", "exclude", "count", "first"} <= set(labels("Order.objects.|"))
    assert {"filter", "count"} <= set(labels("Order.objects.filter(paid=True).|"))
    assert {"customer", "paid", "note"} <= set(labels("Order.objects.filter(|")[:12])
    assert {"name", "email", "orders"} <= set(labels("Order.objects.filter(customer__|"))
    assert {"icontains", "exact", "in"} <= set(labels("Order.objects.filter(customer__name__|"))
    assert {"placed_at", "customer"} <= set(labels('Order.objects.order_by("-|'))
    assert {"name", "email"} <= set(labels('Order.objects.values("customer__|'))
    assert {"paid", "note"} <= set(labels("Order.objects.filter(Q(|")[:12])
    assert {"name", "orders", "save"} <= set(labels("c = Customer.objects.first()\nc.|"))
    assert {"filter", "count"} <= set(labels("c = Customer.objects.first()\nc.orders.|"))
    assert {"filter", "count"} <= set(
        labels("(\n    Order.objects\n    .filter(paid=True)\n    .|")
    )
    assert labels("shop.|") == ["Customer", "Order", "Product"]
    assert labels('Order.objects.filter(note="|') == []


def test_detail_hover_and_signature():
    assert detail("Order.objects.", 14, "filter")["detail"] == "filter(*args, **kwargs)"
    assert detail("Order.objects.filter(", 21, "customer")["detail"].startswith(
        "customer: ForeignKey(Customer"
    )
    query = 'Order.objects.filter(customer__name__icontains="a")'
    assert "class Order(models.Model):" in hover(query, 2)["contents"]
    assert "name: CharField(max_length=100)" in hover(query, query.index("name") + 1)["contents"]
    assert "icontains (lookup)" in hover(query, query.index("icontains") + 1)["contents"]
    assert hover(query, len(query))["contents"] is None
    help_ = signature("Order.objects.filter(paid=True, ", 32)
    assert help_["signatures"][0]["label"] == "filter(*args, **kwargs)"
    assert help_["activeParameter"] == 1
    assert (
        signature("Customer(", 9)["signatures"][0]["label"]
        == "Customer(id=..., name=..., email=...)"
    )
    assert signature("x = 1", 5)["signatures"] == []


def test_run_returns_rows_and_the_sql(api):
    status, body = api(
        "POST", "/api/client/run", {"query": 'Customer.objects.filter(name__startswith="A")'}
    )
    assert status == 200
    assert body["rowCount"] == 1
    assert body["truncated"] is False
    assert body["result"][0]["name"] == "Ann"
    assert len(body["queries"]) == 1
    query = body["queries"][0]
    assert query["sql"].startswith('SELECT "shop_customer"."id"')
    assert query["params"] == ["A%"]
    assert "\nFROM" in query["formatted"]


def test_run_results_of_every_shape(api):
    def result(query):
        status, body = api("POST", "/api/client/run", {"query": query})
        assert status == 200, body
        return body["result"]

    assert result("Customer.objects.count()") == 3
    assert result('Customer.objects.values_list("name", flat=True).order_by("name")') == [
        "Ann",
        "Ben",
        "Chika",
    ]
    assert result('Order.objects.aggregate(n=Count("id"))') == {"n": 2}
    assert result('Customer.objects.get(name="Ben")')["email"] == "ben@example.com"
    assert result('Product.objects.values("kind").annotate(n=Count("id")).order_by("kind")') == [
        {"kind": "book", "n": 1},
        {"kind": "tool", "n": 1},
    ]
    assert result(
        'c = Customer.objects.get(name="Ann")\n[o.paid for o in c.orders.order_by("id")]'
    ) == [True, False]
    assert result("x = 1") is None
    assert result('Product.objects.get(name="Wrench").price') == "12.00"


def test_preview_runs_reads_only(api):
    status, body = api(
        "POST", "/api/client/preview", {"query": "Customer.objects.filter(pk__gt=0).count()"}
    )
    assert status == 200
    assert set(body) == {"queries", "durationMs"}
    assert body["queries"][0]["sql"].startswith("SELECT COUNT(*)")
    # A write, or a method of the project's own, is not run on the way to a preview.
    for query in (
        'Customer.objects.create(name="Zed", email="zed@example.com")',
        "Customer.objects.all().delete()",
        "c = Customer.objects.first()\nc.save()",
        "[c.delete() for c in Customer.objects.all()]",
        'Customer.objects.raw("delete from shop_customer")',
    ):
        status, body = api("POST", "/api/client/preview", {"query": query})
        assert (status, body["queries"]) == (200, []), query
    _status, counts = api("GET", "/api/db/counts")
    assert counts["counts"]["Customer"] == 3


def test_run_commits(api):
    api(
        "POST",
        "/api/client/run",
        {"query": 'Customer.objects.create(name="Zed", email="zed@example.com")'},
    )
    _status, counts = api("GET", "/api/db/counts")
    assert counts["counts"]["Customer"] == 4


def test_run_reports_what_the_query_raised(api):
    status, body = api("POST", "/api/client/run", {"query": "Customer.objects.get(pk=999)"})
    assert status == 422
    assert body["detail"] == "DoesNotExist: Customer matching query does not exist."
    status, body = api("POST", "/api/client/run", {"query": "import os"})
    assert status == 422
    assert body["errors"][0]["field"] == "query"
    # A failed query leaves nothing half-written.
    api(
        "POST",
        "/api/client/run",
        {"query": 'Customer.objects.create(name="Y", email="y@example.com")\n1 / 0'},
    )
    _status, counts = api("GET", "/api/db/counts")
    assert counts["counts"]["Customer"] == 3


def test_client_status_and_the_other_endpoints(api):
    status, body = api("GET", "/api/client")
    assert status == 200 and body["available"] is True and body["source"].startswith("Django ")
    _status, body = api("POST", "/api/client/analyze", {"query": "Order.objects.all()"})
    assert set(body) == {"calls", "transaction", "touched", "diagnostics"}
    _status, body = api("POST", "/api/client/complete", {"query": "Order.", "offset": 6})
    assert body["items"][0]["label"] == "objects"
    _status, body = api("POST", "/api/client/format", {"query": "Order.objects.all()   \n"})
    assert body == {"text": "Order.objects.all()"}
    status, body = api("POST", "/api/client/complete", {"query": "Order.", "offset": -1})
    assert status == 422
