from urllib.parse import quote


def test_status_and_counts(api):
    status, body = api("GET", "/api/db")
    assert status == 200
    assert body["connected"] is True
    assert body["dialect"] == "sqlite"
    assert body["source"] == "settings"
    _status, counts = api("GET", "/api/db/counts")
    assert counts["counts"]["Customer"] == 3
    assert counts["counts"]["Order"] == 2


def test_rows_page_and_search(api):
    status, body = api("GET", "/api/db/rows/Customer?take=2")
    assert status == 200
    assert body["total"] == 3
    assert body["key"] == ["id"]
    assert body["columns"] == ["id", "name", "email"]
    assert [row["name"] for row in body["rows"]] == ["Ann", "Ben"]
    _status, found = api("GET", "/api/db/rows/Customer?search=chika")
    assert [row["name"] for row in found["rows"]] == ["Chika"]


def test_rows_serialize_decimals_json_and_dates_as_text(api):
    _status, body = api("GET", "/api/db/rows/Product")
    book = body["rows"][0]
    assert book["price"] == "39.50"
    assert book["attributes"] == "{}"
    _status, orders = api("GET", "/api/db/rows/Order")
    assert orders["rows"][0]["paid"] is True
    assert orders["rows"][0]["placed_at"].endswith("+00:00")


def test_rows_validation_and_unknown_model(api):
    status, body = api("GET", "/api/db/rows/Customer?take=5000")
    assert status == 422
    assert body["errors"] == [
        {"field": "take", "message": "Input should be less than or equal to 1000"}
    ]
    status, body = api("GET", "/api/db/rows/Nope")
    assert status == 404
    assert body["type"] == "/problems/not-found"
    assert body["detail"] == 'Unknown model "Nope".'


def test_insert_update_delete(api):
    status, body = api(
        "POST", "/api/db/rows/Product", {"values": {"name": "Saw", "price": "9.99", "kind": "tool"}}
    )
    assert (status, body) == (200, {"affected": 1})
    _status, found = api("GET", "/api/db/rows/Product?search=Saw")
    saw = found["rows"][0]
    assert saw["price"] == "9.99"
    status, body = api(
        "PATCH",
        "/api/db/rows/Product",
        {"where": {"id": saw["id"]}, "values": {"price": "11", "attributes": '{"teeth": 20}'}},
    )
    assert (status, body) == (200, {"affected": 1})
    _status, found = api("GET", "/api/db/rows/Product?search=Saw")
    assert found["rows"][0]["price"] == "11.00"
    assert found["rows"][0]["attributes"] == '{"teeth": 20}'
    status, body = api("DELETE", "/api/db/rows/Product", {"where": {"id": saw["id"]}})
    assert (status, body) == (200, {"affected": 1})


def test_writes_the_database_or_the_fields_refuse(api):
    status, body = api(
        "POST", "/api/db/rows/Customer", {"values": {"name": "Dup", "email": "ann@example.com"}}
    )
    assert status == 422
    assert "UNIQUE" in body["detail"]
    status, body = api("POST", "/api/db/rows/Product", {"values": {"name": "X", "price": "abc"}})
    assert status == 422
    assert body["errors"][0]["field"] == "price"
    status, body = api("PATCH", "/api/db/rows/Product", {"where": {}, "values": {"name": "X"}})
    assert status == 422
    # PROTECT: a customer with orders stays.
    _status, found = api("GET", "/api/db/rows/Customer?search=Ann")
    status, body = api("DELETE", "/api/db/rows/Customer", {"where": {"id": found["rows"][0]["id"]}})
    assert status == 422
    assert "protected" in body["detail"]


def test_sql_runs_with_and_without_parameters(api):
    status, body = api(
        "POST", "/api/db/sql", {"sql": "select name from shop_customer order by name;"}
    )
    assert status == 200
    assert body["columns"] == ["name"]
    assert body["rows"] == [{"name": "Ann"}, {"name": "Ben"}, {"name": "Chika"}]
    assert body["rowCount"] == 3
    _status, body = api(
        "POST",
        "/api/db/sql",
        {"sql": "select name from shop_customer where name like ?", "params": ["A%"]},
    )
    assert body["rows"] == [{"name": "Ann"}]
    # Without parameters a percent sign is only a percent sign.
    _status, body = api(
        "POST", "/api/db/sql", {"sql": "select name from shop_customer where name like 'B%'"}
    )
    assert body["rows"] == [{"name": "Ben"}]
    _status, body = api("POST", "/api/db/sql", {"sql": "select 1 as a, 2 as a"})
    assert body["columns"] == ["a", "a_2"]
    status, body = api("POST", "/api/db/sql", {"sql": "select * from nope"})
    assert status == 422
    assert "no such table" in body["detail"]
    _status, body = api(
        "POST", "/api/db/sql", {"sql": "update shop_customer set name = 'Benn' where name = 'Ben'"}
    )
    assert body["rowCount"] == 1


def test_explain(api):
    status, body = api(
        "POST",
        "/api/db/explain",
        {"sql": "select * from shop_customer where id = ?", "params": [1]},
    )
    assert status == 200
    assert body["dialect"] == "sqlite"
    assert "shop_customer" in body["nodes"][0]["label"]


def test_model_name_is_url_decoded(api):
    status, _body = api("GET", f"/api/db/rows/{quote('Customer')}")
    assert status == 200
