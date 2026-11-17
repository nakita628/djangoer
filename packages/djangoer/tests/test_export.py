import os
import subprocess
import sys
from argparse import Namespace
from pathlib import Path

import pytest
from django.conf import settings
from django.db import connections
from returns.result import Failure, Success

from djangoer import cli
from djangoer.studio.domain import er, export, markdown, svg

ROOT = Path(__file__).parent


def app(label: str):
    """The schema of one app of the test project, with the enums its fields use."""
    schema = export.schema_for("default", ROOT, everything=False)
    models = [model for model in schema["models"] if model["app"] == label]
    kept = {model["name"] for model in models}
    used = {field["type"] for model in models for field in model["fields"]}
    return {
        **schema,
        "models": models,
        "enums": [enum for enum in schema["enums"] if enum["name"] in used],
        "relations": [
            relation
            for relation in schema["relations"]
            if relation["from"]["model"] in kept and relation["to"]["model"] in kept
        ],
    }


def shop():
    """The shop app: customers, products and orders."""
    return app("shop")


def venue():
    """The venue app: the shapes of real projects the shop does not have."""
    return app("venue")


def table(text: str, name: str) -> str:
    """The `Table` block of a DBML document."""
    start = text.index(f"Table {name} {{")
    return text[start : text.index("\n}", start) + 2]


def test_an_export_covers_the_projects_own_models_unless_asked_for_all():
    own = export.schema_for("default", ROOT, everything=False)
    assert [model["name"] for model in own["models"]] == [
        "Customer",
        "Product",
        "Order",
        "Organizer",
        "Event",
        "PageViewRestriction",
    ]
    everything = export.schema_for("default", ROOT, everything=True)
    assert "User" in [model["name"] for model in everything["models"]]
    # A relation to a model that is left out is left out with it.
    assert all(
        relation["from"]["model"] != "User" and relation["to"]["model"] != "User"
        for relation in shop()["relations"]
    )


def test_mermaid():
    text = er.mermaid(shop())
    assert text.startswith("erDiagram\n")
    assert '    shop_customer ||--o{ orders : "(id) - (customer_id)"' in text
    assert '    orders }o--o{ shop_product : "(products) - (orders)"' in text
    assert '        EmailField email UK "Where receipts go"' in text
    assert "        ForeignKey customer_id FK" in text


def test_dbml():
    text = er.dbml(shop())
    assert 'Enum ProductKind {\n  "book"\n  "tool"\n}' in text
    assert "  email varchar(254) [unique, not null, note: 'Where receipts go']" in text
    assert "  kind ProductKind [default: 'book', not null]" in text
    assert "  paid bool [default: false, not null]" in text
    assert "Note: '''Someone who orders.'''" in text
    assert (
        "Ref orders_customer_id_fk: orders.customer_id > shop_customer.id [delete: restrict]"
        in text
    )
    assert (
        "Ref orders_products_product_id_fk: orders_products.product_id > shop_product.id "
        "[delete: cascade]"
    ) in text


def test_svg_places_every_model_and_draws_no_line_through_a_card():
    cards = svg.layout(shop())
    assert set(cards) == {"Customer", "Product", "Order", "enum:ProductKind"}
    # Order refers to Customer, so it is one column to its right.
    assert cards["Order"].x > cards["Customer"].x
    document = svg.render(shop())
    assert document.startswith("<svg ")
    assert document.count('class="model-node"') == 3
    assert document.count('class="relation-edge"') == 2
    assert ">customer_id</text>" in document


def test_er_by_extension():
    schema = shop()
    assert isinstance(export.render_er(schema, ".md"), Success)
    assert export.render_er(schema, ".dbml").unwrap().startswith(b"Enum ProductKind")
    assert export.render_er(schema, ".svg").unwrap().startswith(b"<svg ")
    unknown = export.render_er(schema, ".txt")
    assert isinstance(unknown, Failure)
    assert 'No ER format for ".txt"' in str(unknown.failure())


def test_docs_are_markdown_with_the_schema_as_sql():
    files = export.render_docs("default", shop())
    assert set(files) == {"README.md", "er.svg"}
    text = files["README.md"].decode()
    assert text.startswith("# Schema docs\n\n![ER diagram](er.svg)\n")
    assert 'CREATE TABLE "orders"' in text
    assert "## Order\n\nTable `orders`, app `shop`." in text
    assert "| `customer_id` | `ForeignKey` | `bigint` |  | FK |  |  |" in text
    assert "- `customer_id` → [Customer](#customer).`id`, on delete protect" in text
    assert "| `BOOK` | `book` |" in text


def test_the_commands_write_the_files(tmp_path, capsys):
    options = Namespace(
        database="default",
        all=False,
        enum_values=12,
        output=[
            str(tmp_path / "er.md"),
            str(tmp_path / "out" / "schema.dbml"),
            str(tmp_path / "er.gif"),
        ],
    )
    # One file has no format: the others are written, and the command says it failed.
    assert cli.write_er(options) == 1
    assert (tmp_path / "er.md").read_text().startswith("```mermaid\nerDiagram\n")
    assert (tmp_path / "out" / "schema.dbml").is_file()
    assert not (tmp_path / "er.gif").exists()
    assert 'No ER format for ".gif"' in capsys.readouterr().err
    docs = Namespace(database="default", all=False, enum_values=12, output=str(tmp_path / "docs"))
    assert cli.write_docs(docs) == 0
    assert (tmp_path / "docs" / "README.md").is_file()
    assert (tmp_path / "docs" / "er.svg").is_file()


def test_studio_hands_the_files_over(client):
    response = client.get("/api/export/schema.dbml")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == 'attachment; filename="schema.dbml"'
    assert response.text.startswith("Enum ProductKind")
    docs = client.get("/api/export/docs.md")
    # One file, so its diagram is the Mermaid block inside it.
    assert "```mermaid\nerDiagram" in docs.text
    assert client.get("/api/export/er.svg").headers["content-type"] == "image/svg+xml"
    unknown = client.get("/api/export/nope.txt")
    assert unknown.status_code == 404
    assert unknown.json()["detail"].startswith('No export named "nope.txt"')


def test_dbml_quotes_every_enum_value():
    text = er.dbml(venue())
    assert '  "Africa/Abidjan"\n' in text
    assert 'Enum EventVote {\n  "1"\n  "-1"\n}' in text
    # The empty string is stored, not its label; DBML has no name for it, so it is a comment.
    assert (
        'Enum EventStatus {\n  // "" (---): the empty string, which DBML cannot name\n'
        '  "IN PROGRESS"\n  "done"\n}'
    ) in text


def test_dbml_writes_a_many_to_many_as_its_table():
    text = er.dbml(venue())
    assert "<>" not in text
    assert table(text, "venue_organizer_partners") == (
        "Table venue_organizer_partners {\n"
        "  id integer [pk, increment]\n"
        "  from_organizer_id bigint [not null]\n"
        "  to_organizer_id bigint [not null]\n"
        "\n"
        "  indexes {\n"
        "    (from_organizer_id) [name: 'venue_organizer_partners_from_organizer_id_c59f1e22']\n"
        "    (to_organizer_id) [name: 'venue_organizer_partners_to_organizer_id_6278e6fc']\n"
        "    (from_organizer_id, to_organizer_id) [unique, name: "
        "'venue_organizer_partners_from_organizer_id_to_organizer_id_4d4275c5_uniq']\n"
        "  }\n"
        "}"
    )
    # A many-to-many to itself refers to the same table twice, from two columns.
    assert (
        "Ref venue_organizer_partners_to_organizer_id_fk: "
        "venue_organizer_partners.to_organizer_id > venue_organizer.id [delete: cascade]"
    ) in text
    # Two many-to-many between one pair of models are two tables.
    assert "Table venue_event_included {" in text
    assert "Table venue_event_excluded {" in text


def test_indexes_are_the_ones_the_database_has():
    event = next(model for model in venue()["models"] if model["name"] == "Event")
    by_name = {index["name"]: index for index in event["indexes"]}
    # A foreign key and a db_index=True column are indexed on their own, by Django's names.
    assert by_name["venue_event_organizer_id_17d987d6"]["fields"] == ["organizer_id"]
    assert by_name["venue_event_code_7025c133"]["attribute"] == "code: db_index=True"
    assert by_name["one_primary_event"]["condition"] == '"primary" = 1'
    assert by_name["event_code_lower_unique"]["expressions"] == ['LOWER("code")']
    assert by_name["event_email_lower"] == {
        "type": "normal",
        "name": "event_email_lower",
        "dbName": "event_email_lower",
        "fields": [],
        "expressions": ['LOWER("email")'],
        "condition": None,
        "opclasses": [],
        "attribute": "Index(Lower(F(email)), name='event_email_lower')",
    }
    restriction = next(m for m in venue()["models"] if m["name"] == "PageViewRestriction")
    # A foreign key with db_index=False has none.
    assert restriction["indexes"] == []
    text = table(er.dbml(venue()), "venue_event")
    assert "    (code) [name: 'venue_event_code_7025c133']" in text
    assert (
        "    (owner_id, primary) [unique, name: 'one_primary_event', note: 'where \"primary\" = 1']"
    ) in text
    assert "    (`LOWER(\"email\")`) [name: 'event_email_lower']" in text


def test_docs_list_every_index_and_the_sql_creates_them():
    text = export.render_docs("default", venue())["README.md"].decode()
    assert "- index `venue_event_code_7025c133` on `code`" in text
    assert '- unique `one_primary_event` on `owner_id`, `primary` where `"primary" = 1`' in text
    assert '- index `event_email_lower` on `LOWER("email")`' in text
    # The indexes are collected as the schema editor closes, after the tables.
    assert 'CREATE INDEX "venue_event_code_7025c133" ON "venue_event" ("code");' in text
    assert (
        'CREATE UNIQUE INDEX "one_primary_event" ON "venue_event" ("owner_id", "primary") '
        'WHERE "primary" = 1;'
    ) in text


def test_svg_is_the_same_on_every_run():
    # Organizer → Event → Organizer is a loop: which side is cut must not depend on the hash seed.
    script = (
        "import hashlib, sys, django; sys.path.insert(0, sys.argv[1]); django.setup()\n"
        "from pathlib import Path\n"
        "from djangoer.studio.domain import export, svg\n"
        "schema = export.schema_for('default', Path(sys.argv[1]), everything=False)\n"
        "print(hashlib.sha256(svg.render(schema).encode()).hexdigest())\n"
    )
    digests = {
        subprocess.run(  # noqa: S603 - this interpreter, on a script of the test's own
            [sys.executable, "-c", script, str(ROOT)],
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in ("1", "2", "3", "5")
    }
    assert len(digests) == 1


def test_svg_cards_fit_their_text():
    cards = svg.layout(venue())
    restriction = cards["PageViewRestriction"]
    # Wide enough for `restriction_type` and `PageViewRestrictionRestrictionType` side by side.
    longest = svg.NAME_X + svg.PAD + svg.TEXT_GAP
    longest += svg.text_width("restriction_type", svg.NAME_SIZE)
    longest += svg.text_width("PageViewRestrictionRestrictionType", svg.TYPE_SIZE)
    assert restriction.width >= longest
    # The cards of a column are one width, so the next column starts past the widest.
    columns: dict[int, set[tuple[float, float]]] = {}
    for card in cards.values():
        columns.setdefault(card.column, set()).add((card.x, card.width))
    assert all(len(places) == 1 for places in columns.values())
    for column in range(1, len(columns)):
        ((x, width),) = columns[column - 1]
        assert columns[column] == {(x + width + svg.COLUMN_GAP, next(iter(columns[column]))[1])}
    document = svg.render(venue())
    assert "<title>" not in document


def test_svg_cuts_what_is_wider_than_the_widest_card():
    schema = venue()
    model = next(model for model in schema["models"] if model["name"] == "Organizer")
    long = "a_field_whose_name_goes_on_and_on_" * 3
    model["fields"] = [{**model["fields"][1], "name": long, "dbName": None}]
    document = svg.render(schema)
    assert svg.layout(schema)["Organizer"].width == svg.MAX_NODE_WIDTH
    assert f"<title>{long}</title>" in document
    assert "…</text>" in document


def test_svg_shows_the_first_values_of_a_long_enum():
    card = svg.layout(venue())["enum:EventTimezone"]
    assert len(card.rows) == svg.ENUM_ROWS
    assert card.rows[0][1] == "Africa/Abidjan"
    hidden = len(next(e for e in venue()["enums"] if e["name"] == "EventTimezone")["values"])
    assert card.rows[-1][0] == f"… {hidden - svg.ENUM_ROWS + 1} more"


@pytest.fixture
def postgresql():
    """A PostgreSQL alias, never connected to: what its schema editor would create is enough."""
    from django.db.backends.postgresql.base import DatabaseWrapper

    alias = "postgresql"
    config = connections.configure_settings(
        {
            "default": settings.DATABASES["default"],
            alias: {"ENGINE": "django.db.backends.postgresql", "NAME": "djangoer"},
        }
    )[alias]
    connections[alias] = DatabaseWrapper(config, alias)
    yield alias
    del connections[alias]


def test_indexes_on_postgresql_have_the_like_index_of_a_text_column(postgresql):
    schema = export.schema_for(postgresql, ROOT, everything=False)
    event = next(model for model in schema["models"] if model["name"] == "Event")
    like = next(i for i in event["indexes"] if i["name"] == "venue_event_code_7025c133_like")
    assert like["fields"] == ["code"]
    assert like["opclasses"] == ["varchar_pattern_ops"]
    assert like["attribute"] == "code: varchar_pattern_ops for LIKE"
    by_name = {index["name"]: index for index in event["indexes"]}
    assert by_name["one_primary_event"]["condition"] == '"primary"'
    assert "    (code) [name: 'venue_event_code_7025c133_like', note: 'varchar_pattern_ops']" in (
        er.dbml(schema)
    )
    text = markdown.render(schema, sql="", diagram=None)
    assert "- index `venue_event_code_7025c133_like` on `code` (`varchar_pattern_ops`)" in text


def test_the_number_of_enum_values_the_diagram_shows_is_an_option(tmp_path, monkeypatch):
    monkeypatch.chdir(ROOT)
    every = svg.layout(venue(), enum_rows=None)["enum:EventTimezone"]
    timezones = next(e for e in venue()["enums"] if e["name"] == "EventTimezone")["values"]
    assert len(every.rows) == len(timezones)
    assert len(svg.layout(venue(), enum_rows=3)["enum:EventTimezone"].rows) == 3
    small = cli.main(["er", "-o", str(tmp_path / "small.svg"), "--enum-values", "3"])
    full = cli.main(["er", "-o", str(tmp_path / "full.svg"), "--enum-values", "0"])
    assert small == full == 0
    assert "… 588 more" not in (tmp_path / "full.svg").read_text()
    assert (tmp_path / "full.svg").stat().st_size > (tmp_path / "small.svg").stat().st_size


def test_a_mermaid_diagram_too_long_to_draw_says_so(tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(ROOT)
    monkeypatch.setattr(er, "MERMAID_LIMIT", 100)
    monkeypatch.setattr(markdown, "MERMAID_LIMIT", 100)
    text = markdown.render(shop(), sql="", diagram=None)
    assert "```mermaid" not in text
    assert "more than the 100 it draws" in text
    assert cli.main(["er", "-o", str(tmp_path / "er.md")]) == 0
    assert "more than the 100 Mermaid draws" in capsys.readouterr().err
