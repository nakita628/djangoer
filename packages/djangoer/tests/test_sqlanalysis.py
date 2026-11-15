from djangoer.studio import inputs
from djangoer.studio.domain import sqlanalysis
from djangoer.studio.domain.sqlanalysis import to_format_placeholders


def analyze(sql):
    return sqlanalysis.analyze(inputs.AnalyzeSql(alias="default", sql=sql))


def one(sql):
    statements = analyze(sql)["statements"]
    assert len(statements) == 1
    return statements[0]


def kinds(statement):
    return [node["kind"] for node in statement["nodes"]]


def test_a_select_is_a_flow_from_tables_to_limit():
    statement = one(
        "select c.name, count(o.id) n from shop_customer c join orders o on o.customer_id = c.id "
        "where o.paid = ? group by c.id having n > 1 order by n desc limit 5"
    )
    assert statement["kind"] == "select"
    assert kinds(statement) == [
        "table",
        "table",
        "join",
        "filter",
        "aggregate",
        "having",
        "project",
        "sort",
        "limit",
    ]
    assert statement["diagnostics"] == []
    tables = {t["name"]: t for t in statement["tables"]}
    assert tables["shop_customer"]["alias"] == "c"
    assert tables["shop_customer"]["known"] is True
    assert set(tables["orders"]["columnsUsed"]) == {"id", "customer_id", "paid"}
    assert [(c["name"], c["tsType"]) for c in statement["columns"]] == [
        ("name", "str"),
        ("n", "int"),
    ]
    assert statement["columns"][0]["sources"] == [{"table": "shop_customer", "column": "name"}]
    assert statement["parameters"][0]["tsType"] == "bool"
    assert statement["parameters"][0]["context"] == "o.paid = ?"
    assert statement["rowType"] == "class Row(TypedDict):\n    name: str\n    n: int"
    assert statement["paramsType"] == "Params = tuple[bool]"


def test_star_spreads_over_the_table_and_marks_nullable_columns():
    statement = one("select * from orders")
    assert [c["name"] for c in statement["columns"]] == [
        "id",
        "customer_id",
        "note",
        "paid",
        "placed_at",
        "shipped_at",
    ]
    assert "    shipped_at: datetime | None" in statement["rowType"]


def test_unknown_table_and_column_are_warnings():
    statement = one("select nmae from shop_customer join nope on 1 = 1")
    messages = [d["message"] for d in statement["diagnostics"]]
    assert 'Unknown table "nope"' in messages
    statement = one("select nmae from shop_customer")
    assert [d["message"] for d in statement["diagnostics"]] == ['Unknown column "nmae"']
    assert statement["diagnostics"][0]["range"] == {"start": 7, "end": 11}


def test_cte_and_subquery():
    statement = one(
        "with paid as (select customer_id from orders where paid) "
        "select name from shop_customer where id in (select customer_id from paid)"
    )
    assert statement["kind"] == "select"
    assert "cte" in kinds(statement) and "subquery" in kinds(statement)
    assert any(edge["kind"] == "lookup" for edge in statement["edges"])
    assert statement["diagnostics"] == []


def test_writes():
    insert = one("insert into shop_customer (name, email) values (?, ?) returning id")
    assert insert["kind"] == "insert"
    assert insert["paramsType"] == "Params = tuple[str, str]"
    assert insert["rowType"] == "class Row(TypedDict):\n    id: int"
    update = one("update orders set paid = ? where id = ?")
    assert update["kind"] == "update"
    assert update["paramsType"] == "Params = tuple[bool, int]"
    assert update["rowType"] == "Row = None"
    delete = one("delete from orders where paid = 0")
    assert kinds(delete) == ["table", "filter", "delete"]


def test_several_statements_and_broken_ones():
    statements = analyze("select 1; select 'abc")["statements"]
    assert [s["kind"] for s in statements] == ["select", "invalid"]
    assert statements[1]["diagnostics"][0]["message"] == "Unterminated string"
    assert analyze("")["statements"] == []
    assert one("select (1")["kind"] == "invalid"
    assert one("pragma table_info(orders)")["kind"] == "other"


def test_statements_cut_short_do_not_raise():
    for text in (
        "select",
        "select * from",
        "select * from orders where",
        "insert into",
        "update",
        "with x as (",
        "select a.",
        "select * from orders o join",
        "delete from orders where id in (",
    ):
        analyze(text)


def test_placeholders_for_the_cursor():
    assert to_format_placeholders("select '?' , 50 % 3, a from t where a = ? and b = $2") == (
        "select '?' , 50 %% 3, a from t where a = %s and b = %s"
    )
