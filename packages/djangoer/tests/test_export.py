# Django gives every model class `_meta` as it is created, which no annotation says:
# pyright: reportAttributeAccessIssue=false
import os
import subprocess
import sys
from argparse import Namespace
from itertools import pairwise
from pathlib import Path

import django
import pytest
from django.conf import settings
from django.db import connections
from returns.result import Failure, Success

from djangoer import cli
from djangoer.studio.domain import er, export, markdown, svg
from djangoer.studio.domain.schema import names

ROOT = Path(__file__).parent


def since(major: int, minor: int) -> bool:
    """Whether the Django under test is this version or a later one."""
    return django.VERSION[:2] >= (major, minor)


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
    scope = export.schema_for("default", ROOT, everything=False)
    own = {**scope, "models": [model for model in scope["models"] if not er.external(model)]}
    assert [model["name"] for model in own["models"]] == [
        "Customer",
        "Product",
        "Order",
        "Organizer",
        "Event",
        "PageViewRestriction",
        "venue.Tag",
        "Place",
        "Restaurant",
        "Connection",
        "Gallery",
        "Rating",
        "Article",
        "HistoricalArticle",
        "Price",
        "annex.Tag",
        # The models of the modern app, on the Django that has them.
        *(["Item"] if since(5, 0) else []),
        *(["OrderLine", "Shipment"] if since(5, 2) else []),
        *(["Category"] if since(5, 0) else []),
        "Worker",
        "Job",
        "Document",
        "Reservation",
        # A proxy has no table: it is a note of its model's (`Shop.proxies`), not a model.
        "Site",
        "Shop",
        "Team",
        "Person",
        "Membership",
    ]
    everything = export.schema_for("default", ROOT, everything=True)
    assert "Group" in [model["name"] for model in everything["models"]]
    # The installed packages' models the project's refer to stay, as stubs (#31).
    assert [model["name"] for model in scope["models"] if er.external(model)] == [
        "ContentType",
        "User",
    ]


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
    # Every model of the shop has a relation, so each has a diagram of its own.
    assert set(files) == {
        "README.md",
        "er.svg",
        "tables/Customer.svg",
        "tables/Product.svg",
        "tables/Order.svg",
    }
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
        enums=True,
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
    docs = Namespace(
        database="default", all=False, enum_values=12, enums=True, output=str(tmp_path / "docs")
    )
    assert cli.write_docs(docs) == 0
    assert (tmp_path / "docs" / "README.md").is_file()
    assert (tmp_path / "docs" / "er.svg").is_file()
    assert (tmp_path / "docs" / "tables" / "Order.svg").is_file()


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


def where(alias: str = "default") -> str:
    """The condition of `one_primary_event` as this Django writes it for the database: on
    SQLite `"primary"` before 6.1, `"primary" = 1` from it."""
    from project.venue.models import Event

    constraint = next(c for c in Event._meta.constraints if c.name == "one_primary_event")
    return constraint._get_condition_sql(Event, connections[alias].schema_editor())


def test_indexes_are_the_ones_the_database_has():
    event = next(model for model in venue()["models"] if model["name"] == "Event")
    by_name = {index["name"]: index for index in event["indexes"]}
    # A foreign key and a db_index=True column are indexed on their own, by Django's names.
    assert by_name["venue_event_organizer_id_17d987d6"]["fields"] == ["organizer_id"]
    assert by_name["venue_event_code_7025c133"]["attribute"] == "code: db_index=True"
    assert by_name["one_primary_event"]["condition"] == where()
    assert by_name["event_code_lower_unique"]["expressions"] == ['LOWER("code")']
    assert by_name["event_email_lower"] == {
        "type": "normal",
        "name": "event_email_lower",
        "dbName": "event_email_lower",
        "fields": [],
        "expressions": ['LOWER("email")'],
        "condition": None,
        "opclasses": [],
        "method": None,
        "include": [],
        "parameters": [],
        "descending": [],
        "deferrable": None,
        "nullsDistinct": None,
        "attribute": "Index(Lower(F(email)), name='event_email_lower')",
    }
    restriction = next(m for m in venue()["models"] if m["name"] == "PageViewRestriction")
    # A foreign key with db_index=False has none.
    assert restriction["indexes"] == []
    text = table(er.dbml(venue()), "venue_event")
    assert "    (code) [name: 'venue_event_code_7025c133']" in text
    assert (
        f"    (owner_id, primary) [unique, name: 'one_primary_event', note: 'where {where()}']"
    ) in text
    assert "    (`LOWER(\"email\")`) [name: 'event_email_lower']" in text


def test_docs_list_every_index_and_the_sql_creates_them():
    text = export.render_docs("default", venue())["README.md"].decode()
    assert "- index `venue_event_code_7025c133` on `code`" in text
    assert f"- unique `one_primary_event` on `owner_id`, `primary` where `{where()}`" in text
    assert '- index `event_email_lower` on `LOWER("email")`' in text
    # The indexes are collected as the schema editor closes, after the tables.
    assert 'CREATE INDEX "venue_event_code_7025c133" ON "venue_event" ("code");' in text
    assert (
        'CREATE UNIQUE INDEX "one_primary_event" ON "venue_event" ("owner_id", "primary") '
        f"WHERE {where()};"
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
    assert by_name["one_primary_event"]["condition"] == where(postgresql)
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


def test_a_child_of_multi_table_inheritance_has_its_own_columns_only():
    restaurant = next(m for m in venue()["models"] if m["name"] == "Restaurant")
    assert [f["name"] for f in restaurant["fields"]] == [
        "place_ptr_id",
        "place_ptr",
        "serves_pizza",
    ]
    assert restaurant["fields"][0]["isId"] is True
    text = er.dbml(venue())
    assert table(text, "venue_restaurant").splitlines()[1:3] == [
        (
            "  place_ptr_id bigint [pk, note: 'parent link: a Restaurant is a Place (multi-table "
            "inheritance)']"
        ),
        "  serves_pizza bool [default: false, not null]",
    ]
    # The parent's many-to-many is the parent's, written once.
    assert text.count("Table venue_place_tags {") == 1
    assert "venue_restaurant }o--o{" not in er.mermaid(venue())
    assert (
        "Ref venue_restaurant_place_ptr_id_fk: venue_restaurant.place_ptr_id - venue_place.id "
        "[delete: cascade]"
    ) in text


def test_dbml_writes_a_stored_value_once_with_its_labels():
    text = er.dbml(venue())
    assert (
        "Enum ConnectionEngine {\n"
        '  "django.db.backends.postgresql"\n'
        "  \"django.db.backends.mysql\" [note: 'MySQL / MariaDB']\n"
        "}"
    ) in text
    # The docs list every choice with its label.
    docs = markdown.render(venue(), sql="", diagram=None)
    assert "| `MySQL` | `django.db.backends.mysql` |" in docs
    assert "| `MariaDB` | `django.db.backends.mysql` |" in docs


def test_docs_on_postgresql_need_no_database(postgresql):
    schema = export.schema_for(postgresql, ROOT, everything=False)
    text = export.render_docs(postgresql, schema)["README.md"].decode()
    assert 'CREATE TABLE "venue_event"' in text
    assert 'CREATE INDEX "venue_event_code_7025c133_like" ON "venue_event"' in text
    assert connections[postgresql].connection is None


def enum_heavy() -> dict:
    """Three models in a chain, each with four `choices` fields: twelve enums, and no column of
    models taller than one short card."""
    schema = shop()
    customer = next(m for m in schema["models"] if m["name"] == "Customer")
    kind = next(f for f in schema["models"][1]["fields"] if f["name"] == "kind")
    enums = []
    for model in schema["models"]:
        for number in range(4):
            name = f"{model['name']}Choice{number}"
            model["fields"].append({**kind, "name": f"choice_{number}", "type": name})
            enums.append({**schema["enums"][0], "name": name})
    assert customer["fields"][-1]["type"] == "CustomerChoice3"
    return {**schema, "enums": enums}


def test_svg_wraps_the_enums_into_columns_no_taller_than_the_models():
    cards = svg.layout(enum_heavy())
    models = [card for card in cards.values() if not card.enum]
    enums = [card for card in cards.values() if card.enum]
    bottom = max(card.y + card.height for card in models)
    assert all(card.y + card.height <= bottom for card in enums)
    assert len({card.column for card in enums}) > 1
    assert min(card.column for card in enums) > max(card.column for card in models)


def test_svg_without_enums(tmp_path, monkeypatch):
    assert not any(card.enum for card in svg.layout(venue(), enums=False).values())
    document = svg.render(venue(), enums=False)
    assert 'class="enum-node"' not in document
    assert 'class="enum-edge"' not in document
    monkeypatch.chdir(ROOT)
    assert cli.main(["er", "-o", str(tmp_path / "er.svg"), "--no-enums"]) == 0
    assert 'class="enum-node"' not in (tmp_path / "er.svg").read_text()


def test_docs_link_to_the_anchors_github_gives_the_headings():
    own = export.schema_for("default", ROOT, everything=False)
    text = markdown.render(own, sql="", diagram=None)
    # GitHub drops the dot of `venue.Tag` from the heading's anchor.
    assert "## venue.Tag\n" in text
    assert "[venue.Tag](#venuetag)" in text
    assert "[annex.Tag](#annextag)" in text
    assert "(#venue.tag)" not in text
    assert "- `photos` — many to many with [venue.Tag](#venuetag)" in text


def test_slugs_are_githubs():
    seen: dict[str, int] = {}
    names = ["Schema docs", "blog.Category", "cas_server.User", "Post", "Post"]
    assert [markdown.slug(name, seen) for name in names] == [
        "schema-docs",
        "blogcategory",
        "cas_serveruser",
        "post",
        "post-1",
    ]


def test_two_models_of_one_name_have_an_enum_each():
    own = export.schema_for("default", ROOT, everything=False)
    enums = {enum["name"]: enum for enum in own["enums"]}
    assert [value["dbName"] for value in enums["VenueTagKind"]["values"]] == ["a", "b"]
    assert [value["dbName"] for value in enums["AnnexTagKind"]["values"]] == ["x"]
    kinds = {
        model["name"]: next(f["type"] for f in model["fields"] if f["name"] == "kind")
        for model in own["models"]
        if model["name"].endswith(".Tag")
    }
    assert kinds == {"venue.Tag": "VenueTagKind", "annex.Tag": "AnnexTagKind"}


def test_dbml_writes_the_columns_a_through_model_adds():
    text = table(er.dbml(venue()), "venue_gallery_photos")
    assert text.splitlines()[1:5] == [
        "  id integer [pk, increment]",
        "  gallery_id bigint [not null]",
        "  tag_id bigint [not null]",
        "  sort_value integer [default: 0, not null]",
    ]


def test_a_generic_foreign_key_and_the_generic_relations_to_it():
    schema = venue()
    rating = next(m for m in schema["models"] if m["name"] == "Rating")
    assert rating["genericForeignKeys"] == [
        {
            "name": "content_object",
            "contentTypeField": "content_type_id",
            "objectIdField": "object_id",
        }
    ]
    generic = next(r for r in schema["relations"] if r["origin"] == "generic")
    assert generic["from"] == {"model": "Article", "field": "id", "cardinality": "one"}
    assert generic["to"] == {"model": "Rating", "field": "object_id", "cardinality": "zero-many"}
    assert generic["name"] == "ratings"
    text = markdown.render(schema, sql="", diagram=None)
    assert (
        "- `content_object` → any model, by `content_type_id` + `object_id` (generic foreign key)"
    ) in text
    assert (
        "- `object_id` → [Article](#article).`id` where `content_type_id` is Article "
        "(generic, `Article.ratings`)"
    ) in text
    assert (
        "- `ratings` ← [Rating](#rating), by `content_type_id` + `object_id` (generic relation)"
    ) in text
    assert '    venue_article ||..o{ venue_rating : "(id) - (object_id)"' in er.mermaid(schema)
    dbml = er.dbml(schema)
    # No reference, which would read as a foreign key: a note on the key column.
    assert "Ref venue_rating_object_id_fk" not in dbml
    assert (
        "note: 'content_object: with content_type_id, a generic foreign key to a row of any "
        "model (from Article.ratings)']"
    ) in table(dbml, "venue_rating")
    assert 'stroke-dasharray="2 3"' in svg.render(schema)


def test_docs_keep_what_was_collected_when_an_add_on_connects(postgresql, monkeypatch):
    # django-pgtrigger opens a transaction for each trigger it adds, which connects.
    editor = type(connections[postgresql].schema_editor())
    create_model = editor.create_model

    def with_a_trigger(self, model):
        create_model(self, model)
        self.connection.ensure_connection()

    monkeypatch.setattr(editor, "create_model", with_a_trigger)
    schema = export.schema_for(postgresql, ROOT, everything=False)
    sql = markdown.create_sql(schema, names(), postgresql)
    assert 'CREATE TABLE "venue_event"' in sql
    assert 'CREATE INDEX "venue_event_code_7025c133" ON "venue_event"' in sql
    assert "-- Not collected: what is added to these tables needs the database" in sql
    assert "\n-- Event: " in sql


def test_a_model_a_package_makes_for_the_project_is_the_projects():
    own = export.schema_for("default", ROOT, everything=False)
    history = next(m for m in own["models"] if m["name"] == "HistoricalArticle")
    # Its class has no `class` statement to open the source at, but it is the project's.
    assert history["own"] is True
    assert history["location"] is None
    assert any(
        r["from"]["model"] == "Article" and r["to"]["model"] == "HistoricalArticle"
        for r in own["relations"]
    )
    assert "Table venue_historicalarticle {" in er.dbml(own)


def modern():
    return app("modern")


@pytest.mark.skipif(not since(5, 2), reason="CompositePrimaryKey is Django 5.2's")
def test_a_composite_primary_key_and_a_foreign_object_to_it():
    schema = modern()
    line = next(m for m in schema["models"] if m["name"] == "OrderLine")
    assert line["primaryKey"] == ["order_id", "item_id"]
    text = er.dbml(schema)
    orderline = table(text, "modern_orderline")
    assert "    (order_id, item_id) [pk]" in orderline
    # The key is the index, not `pk` on each column, which would be a key each.
    assert "  order_id integer [not null]" in orderline
    # A ForeignObject has no foreign key in the database: no Ref, a note on its columns.
    assert "Ref modern_shipment_line_fk" not in text
    assert (
        "  order_id integer [not null, note: 'line: refers to modern_orderline.(order_id, "
        "item_id), with no foreign key in the database']"
    ) in table(text, "modern_shipment")
    mermaid = er.mermaid(schema)
    assert "        IntegerField order_id PK\n" in mermaid
    assert "        ForeignKey item_id PK\n" in mermaid
    assert (
        'modern_orderline ||..o{ modern_shipment : "(order_id, item_id) - (order_id, item_id), '
        'no constraint"'
    ) in mermaid
    docs = markdown.render(schema, sql="", diagram=None)
    assert "| `order_id` | `IntegerField` | `integer` |  | PK |  |  |" in docs
    assert "| `item_id` | `ForeignKey` | `bigint` |  | PK, FK |  |  |" in docs
    assert (
        "- `line` (`order_id`, `item_id`) → [OrderLine](#orderline).(`order_id`, `item_id`), "
        "on delete cascade, no database constraint"
    ) in docs
    # Shipment's `order_id` is read by the ForeignObject only; `item_id` is a foreign key too.
    assert "| `order_id` | `IntegerField` | `integer` |  | FK (no constraint) |  |  |" in docs
    assert "| `item_id` | `ForeignKey` | `bigint` |  | FK |  |  |" in docs
    assert ("order_id", "IntegerField", "PK") in svg.layout(schema)["OrderLine"].rows


@pytest.mark.skipif(not since(5, 0), reason="GeneratedField and db_default are 5.0's")
def test_generated_columns_database_defaults_and_comments():
    schema = modern()
    item = next(m for m in schema["models"] if m["name"] == "Item")
    fields = {field["name"]: field for field in item["fields"]}
    assert '"price" + "tax"' in fields["total"]["generated"]
    # Created without NOT NULL, as Django creates a generated column.
    assert fields["total"]["isRequired"] is False
    assert fields["stock"]["dbDefault"] == "0"
    assert fields["stock"]["default"] is None
    assert fields["name"]["documentation"] == "The name shown to customers — Shown in lists"
    assert item["documentation"] == "Things we sell"
    text = table(er.dbml(schema), "modern_item")
    assert "  total decimal [note: 'generated (stored): " in text
    assert "  stock integer [default: 0, not null]" in text
    assert "  created datetime [default: `(" in text
    assert (
        "  name varchar(50) [not null, note: 'The name shown to customers — Shown in lists']"
    ) in text
    assert "Note: '''Things we sell'''" in text
    docs = markdown.render(schema, sql="", diagram=None)
    assert (
        "| `total` | `GeneratedField(11, 2)` | `decimal` | yes |  | generated (stored): `" in docs
    )
    assert "| `stock` | `IntegerField` | `integer` |  |  | `0` (database) |  |" in docs
    assert "\nThings we sell\n" in docs


def test_a_python_default_and_a_database_default_are_apart():
    product = next(m for m in shop()["models"] if m["name"] == "Product")
    kind = next(f for f in product["fields"] if f["name"] == "kind")
    assert (kind["default"], kind["dbDefault"], kind["generated"]) == ("'book'", None, None)


def test_a_model_with_a_relation_has_a_diagram_of_its_own():
    files = export.render_docs("default", venue())
    text = files["README.md"].decode()
    # In its section, under the table name and the docstring.
    assert (
        "## Rating\n\nTable `venue_rating`, app `venue`.\n\nA row of any model: the pair of "
        "columns names it.\n\n![Rating and the models it relates to](tables/Rating.svg)\n"
    ) in text
    # A model with no relation has none: its card would say what its table of columns says.
    assert "Connection" not in er.related(venue())
    assert "tables/Connection.svg" not in files
    assert "![Connection and" not in text


def test_the_diagram_of_a_model_is_the_model_and_the_models_it_joins():
    part = er.neighborhood(shop(), "Customer")
    # Customer is referred to by Order only; Product, which Order joins, is not Customer's.
    assert [model["name"] for model in part["models"]] == ["Customer", "Order"]
    assert all("Customer" in (r["from"]["model"], r["to"]["model"]) for r in part["relations"])
    assert part["enums"] == []
    order = er.neighborhood(shop(), "Order")
    assert [model["name"] for model in order["models"]] == ["Customer", "Product", "Order"]
    # Product's enum is on Product's own diagram: Order's card names it as the type only.
    assert order["enums"] == []
    product = er.neighborhood(shop(), "Product")
    assert [enum["name"] for enum in product["enums"]] == ["ProductKind"]
    document = export.render_docs("default", shop())["tables/Customer.svg"].decode()
    assert document.count('class="model-node"') == 2
    assert ">Product</text>" not in document


def test_writing_the_docs_again_removes_the_diagram_of_a_model_that_is_gone(tmp_path):
    docs = Namespace(
        database="default", all=False, enum_values=12, enums=True, output=str(tmp_path)
    )
    gone = tmp_path / "tables" / "Gone.svg"
    gone.parent.mkdir()
    gone.write_text("<svg/>")
    kept = tmp_path / "tables" / "notes.txt"
    kept.write_text("mine")
    assert cli.write_docs(docs) == 0
    assert not gone.exists()
    assert (tmp_path / "tables" / "Order.svg").is_file()
    # Only the diagrams are the command's to remove.
    assert kept.read_text() == "mine"


def chain(count: int, reach: int) -> dict:
    """Models in a chain, each referring to the one before it (a column each), and to the one
    `reach` before it too: those lines cross columns."""
    base = shop()
    key = next(f for f in base["models"][0]["fields"] if f["name"] == "id")

    def column(name: str, foreign: bool) -> dict:
        return {
            **key,
            "name": name,
            "isId": not foreign,
            "isForeignKey": foreign,
            "type": "ForeignKey" if foreign else "BigAutoField",
        }

    names = [f"M{index}" for index in range(count)]
    models = [
        {
            **base["models"][0],
            "name": name,
            "dbName": name.lower(),
            "fields": [column("id", False), column("near_id", True), column("far_id", True)],
        }
        for name in names
    ]

    def relation(parent: str, child: str, field: str) -> dict:
        return {
            "id": f"{parent}->{child}.{field}",
            "name": None,
            "origin": "inferred",
            "from": {"model": parent, "field": "id", "cardinality": "one"},
            "to": {"model": child, "field": field, "cardinality": "zero-many"},
            "onDelete": None,
            "onUpdate": None,
            "through": None,
        }

    relations = [relation(names[i - 1], names[i], "near_id") for i in range(1, count)]
    relations += [relation(names[i - reach], names[i], "far_id") for i in range(reach, count)]
    return {**base, "models": models, "enums": [], "relations": relations}


def test_svg_lines_across_the_cards_share_a_lane_when_they_do_not_overlap():
    schema = chain(20, 3)
    cards = svg.layout(schema)
    router = svg.Router(cards)
    svg._edges(schema, cards, router)
    long_lines = len([r for r in schema["relations"] if r["to"]["field"] == "far_id"])
    assert long_lines == 17
    # A lane each for the lines that run side by side, not one for every line: a line over
    # three columns meets only the two before it and the two after it.
    assert len(router.across) <= 4
    assert sum(len(spans) for spans in router.across.values()) == long_lines


def test_svg_lines_on_one_lane_do_not_meet():
    schema = chain(20, 3)
    cards = svg.layout(schema)
    router = svg.Router(cards)
    svg._edges(schema, cards, router)
    for lanes in [router.tracks, *router.gaps.values()]:
        for spans in lanes.taken:
            ordered = sorted(spans)
            assert all(a[1] + svg.LANE <= b[0] for a, b in pairwise(ordered))
    for spans in router.across.values():
        ordered = sorted(spans)
        assert all(a[1] + svg.LANE <= b[0] for a, b in pairwise(ordered))


def test_svg_lines_to_a_far_column_run_through_the_gaps_between_cards():
    schema = chain(20, 3)
    cards = svg.layout(schema)
    router = svg.Router(cards)
    svg._edges(schema, cards, router)
    # Every card of the chain is as tall as the others: the lines run under them, not over.
    assert len(router.tracks) == 0
    # A column of two cards between the two ends of a line: it runs between them.
    first, second, third = (cards[name] for name in ("M0", "M1", "M2"))
    filler = svg.Card("filler", "filler", "", [("a", "", "")] * 3, column=second.column)
    filler.x, filler.y, filler.width = second.x, second.y + second.height + 2 * svg.ROW_GAP, 340
    router = svg.Router({**cards, "filler": filler})
    points = router.between(first, first.y + 60, third, third.y + 60)
    assert points is not None
    across = points[2][1]
    assert second.y + second.height < across < filler.y
    assert len(router.tracks) == 0


def legacy():
    return app("legacy")


def test_dbml_quotes_a_sized_array_and_escapes_a_note():
    text = table(er.dbml(legacy()), "legacy_jobs")
    assert '  authors "varchar(64)[]" [' in text
    # A plain array of a plain type parses bare, as it did.
    assert "  tags text[] [" in text
    assert "Removed later by \\'python manage.py cleanup\\''''" in text


def test_a_python_default_is_a_note_not_a_database_default():
    text = er.dbml(shop())
    # `default=dict` is called by Python for a new row; the database has no default for it.
    assert "  attributes text [not null, note: 'default in Python: dict()']" in text
    assert "`dict()`" not in text
    # A literal default stays a default.
    assert "  paid bool [default: false, not null]" in text


def test_a_model_django_does_not_manage_is_marked_and_has_only_declared_indexes():
    schema = legacy()
    job = next(m for m in schema["models"] if m["name"] == "Job")
    assert job["managed"] is False
    # No index Django would name for a foreign key or a db_index: it creates none here.
    assert job["indexes"] == []
    document = next(m for m in schema["models"] if m["name"] == "Document")
    assert [index["name"] for index in document["indexes"]] == [
        "document_labels",
        "document_seen",
        "document_digest",
        "document_base_path",
    ]
    docs = markdown.render(schema, sql="", diagram=None)
    assert "## Job\n\nTable `legacy_jobs`, app `legacy`.\n\nNot managed by Django" in docs
    assert "Indexes, as declared:" in docs
    assert "Note: '''Not managed by Django (managed = False)." in er.dbml(schema)
    assert 'class="unmanaged"' in svg.render(schema)
    assert 'class="unmanaged"' not in svg.render(shop())


def test_an_index_says_its_method_include_and_parameters():
    document = next(m for m in legacy()["models"] if m["name"] == "Document")
    by_name = {index["name"]: index for index in document["indexes"]}
    assert by_name["document_labels"]["method"] == "gin"
    assert by_name["document_seen"]["parameters"] == ["pages_per_range = 16"]
    # An OpClass around a field is the field with its operator class, not an expression.
    base_path = by_name["document_base_path"]
    assert (base_path["fields"], base_path["expressions"]) == (["base_path"], [])
    assert (base_path["opclasses"], base_path["include"]) == (["text_ops"], ["domain"])
    docs = markdown.render(legacy(), sql="", diagram=None)
    assert "- gin index `document_labels` on `labels`" in docs
    assert "- brin index `document_seen` on `seen` with `pages_per_range = 16`" in docs
    assert "- index `document_base_path` on `base_path` (`text_ops`) include `domain`" in docs
    text = table(er.dbml(legacy()), "legacy_document")
    assert "    (labels) [name: 'document_labels', note: 'using gin']" in text
    assert "    (digest) [type: hash, name: 'document_digest']" in text
    assert (
        "    (seen) [name: 'document_seen', note: 'using brin; with (pages_per_range = 16)']"
    ) in text


def test_on_delete_set_and_every_action_read_as_written():
    relations = [r for r in venue()["relations"] if r["to"]["model"] == "Price"]
    assert {r["to"]["field"]: r["onDelete"] for r in relations} == {
        "replaced_by_id": "SET(None)",
        "place_id": "SET_DEFAULT",
    }
    docs = markdown.render(venue(), sql="", diagram=None)
    assert "- `replaced_by_id` → [Price](#price).`id`, on delete set (None)" in docs
    assert "- `place_id` → [Place](#place).`id`, on delete set default" in docs
    text = er.dbml(venue())
    # SET(None) is what the database's `set null` does.
    assert "venue_price.replaced_by_id > venue_price.id [delete: set null]" in text
    assert "venue_price.place_id > venue_place.id [delete: set default]" in text
    # default=None is a literal default, null.
    assert "  place_id bigint [default: null]" in table(text, "venue_price")


def test_a_relation_to_an_installed_packages_model_is_kept_with_a_stub():
    scope = export.schema_for("default", ROOT, everything=False)
    user = next(m for m in scope["models"] if m["name"] == "User")
    # Its key, as much as the project's models refer to; not every column of auth_user.
    assert [field["name"] for field in user["fields"]] == ["id"]
    assert any(
        r["from"]["model"] == "User" and r["to"]["model"] == "Event" for r in scope["relations"]
    )
    files = export.render_docs("default", scope)
    docs = files["README.md"].decode()
    assert "- `owner_id` → `User`.`id` (auth, not in these docs), on delete cascade" in docs
    # No section, no diagram of its own, and no CREATE TABLE.
    assert "## User\n" not in docs
    assert "tables/User.svg" not in files
    assert 'CREATE TABLE "auth_user"' not in docs
    text = er.dbml(scope)
    assert table(text, "auth_user").startswith("Table auth_user {\n  id integer [pk, increment]\n")
    assert "Not in these docs: a model of the auth app" in table(text, "auth_user")
    assert "Ref venue_event_owner_id_fk: venue_event.owner_id > auth_user.id" in text
    assert "    auth_user ||--o{ venue_event" in er.mermaid(scope)
    assert 'class="external"' in files["tables/Event.svg"].decode()


def test_checks_exclusions_descending_columns_and_deferrable():
    price = next(m for m in venue()["models"] if m["name"] == "Price")
    assert price["checks"] == [{"name": "price_not_negative", "expression": "\"amount\" >= '0'"}]
    by_name = {index["name"]: index for index in price["indexes"]}
    assert by_name["category_amount"]["descending"] == ["amount"]
    assert by_name["code_unique_deferred"]["deferrable"] == "deferred"
    docs = markdown.render(venue(), sql="", diagram=None)
    assert "Checks:\n\n- `price_not_negative`: `\"amount\" >= '0'`" in docs
    assert "- index `category_amount` on `category`, `amount` desc" in docs
    assert "- unique `code_unique_deferred` on `code`, deferrable (initially deferred)" in docs
    text = table(er.dbml(venue()), "venue_price")
    assert "  checks {\n    `\"amount\" >= '0'` [name: 'price_not_negative']\n  }" in text
    assert "    (category, amount) [name: 'category_amount', note: 'descending: amount']" in text
    reservation = next(m for m in legacy()["models"] if m["name"] == "Reservation")
    exclusion = reservation["indexes"][0]
    assert (exclusion["type"], exclusion["method"]) == ("exclusion", "gist")
    assert exclusion["expressions"] == ["during WITH &&", "room WITH ="]
    docs = markdown.render(legacy(), sql="", diagram=None)
    assert "- gist exclusion `exclude_overlapping` on `during WITH &&`, `room WITH =` where" in docs


@pytest.mark.skipif(not since(5, 0), reason="nulls_distinct is Django 5.0's")
def test_nulls_distinct_is_said():
    category = next(m for m in modern()["models"] if m["name"] == "Category")
    assert category["indexes"][-1]["nullsDistinct"] is False
    docs = markdown.render(modern(), sql="", diagram=None)
    assert (
        "- unique `category_slug_unique` on `project`, `parent_id`, `slug`, nulls not distinct"
    ) in docs


@pytest.mark.skipif(
    not since(5, 0) or since(6, 1), reason="on 6.1, nulls distinct asks no version of the server"
)
def test_docs_on_postgresql_assume_a_version_when_the_server_cannot_be_asked(postgresql):
    schema = export.schema_for(postgresql, ROOT, everything=False)
    sql = markdown.create_sql(schema, names(), postgresql)
    assert sql.startswith("-- Written for PostgreSQL 17, assumed: the database could not be asked.")
    assert 'CREATE TABLE "modern_category"' in sql
    assert "UNIQUE NULLS NOT DISTINCT" in sql
    connection = connections[postgresql]
    # Forgotten afterwards: a connection that reaches its server later asks it.
    assert "pg_version" not in vars(connection)
    assert not any("postgresql_1" in key for key in vars(connection.features))
    assert connection.connection is None


def test_docs_on_postgresql_write_a_database_default_without_a_database(postgresql):
    schema = export.schema_for(postgresql, ROOT, everything=False)
    sql = markdown.create_sql(schema, names(), postgresql)
    assert "-- Not collected" not in sql
    if since(5, 0):
        assert '"stock" integer DEFAULT 0 NOT NULL' in sql


def hub(count: int) -> dict:
    """One model and `count` models that refer to it."""
    base = shop()
    customer, order = base["models"][0], base["models"][2]
    relation = next(r for r in base["relations"] if r["to"]["model"] == "Order")
    return {
        **base,
        "models": [
            customer,
            *({**order, "name": f"Thing{i}", "dbName": f"thing{i}"} for i in range(count)),
        ],
        "relations": [
            {**relation, "id": f"r{i}", "to": {**relation["to"], "model": f"Thing{i}"}}
            for i in range(count)
        ],
        "enums": [],
    }


def test_a_models_own_diagram_wraps_the_models_around_it_and_names_the_rest():
    schema = er.neighborhood(hub(60), "Customer")
    cards = svg.layout_around(schema, "Customer")
    customer = cards["Customer"]
    others = [card for card in cards.values() if card.name != "Customer"]
    # The models that refer to it are on its right, in columns no taller than the limit.
    assert all(card.column > customer.column for card in others)
    limit = max(customer.height * svg.AROUND_HEIGHT, svg.AROUND_FLOOR)
    assert all(card.y + card.height <= svg.MARGIN + limit for card in others)
    assert len({card.column for card in others}) > 1
    # 29 cards and one naming the 31 others.
    assert len(others) == svg.AROUND_CARDS
    more = next(card for card in others if card.title.startswith("…"))
    assert more.title == "… 31 more"
    assert more.rows[0][0] == "Thing29"
    order = svg.layout_around(er.neighborhood(shop(), "Order"), "Order")
    # Order refers to Customer (on its left) and declares the many-to-many to Product (right).
    assert order["Customer"].column < order["Order"].column < order["Product"].column


def kinds():
    return app("kinds")


def test_inheritance_is_described_as_inheritance():
    schema = kinds()
    models = {model["name"]: model for model in schema["models"]}
    # The proxy is no model of its own, but its model names it.
    assert "OpenShop" not in models
    assert models["Shop"]["proxies"] == [
        {"name": "OpenShop", "app": "kinds", "documentation": "The shops open today."}
    ]
    assert models["Site"]["abstractBases"] == [{"name": "Timestamped", "fields": ["created"]}]
    # The child's columns are its own: the abstract base's are its parent's.
    assert models["Shop"]["abstractBases"] == []
    link = next(r for r in schema["relations"] if r["to"]["model"] == "Shop")
    assert link["parentLink"] is True
    docs = markdown.render(schema, sql="", diagram=None)
    assert (
        "Inherits from [Site](#site) (multi-table): its rows are joined on `site_ptr_id`." in docs
    )
    assert "Subclasses (multi-table): [Shop](#shop)." in docs
    assert "Proxy models, on this table: `OpenShop`." in docs
    assert "Columns from `Timestamped` (abstract): `created`." in docs
    assert "- `site_ptr_id` → [Site](#site).`id`, parent link, on delete cascade" in docs
    assert 'kinds_site ||--o| kinds_shop : "is a, by site_ptr_id"' in er.mermaid(schema)
    text = er.dbml(schema)
    assert "Note: '''Proxy models: OpenShop.'''" in table(text, "kinds_shop")
    assert "Note: '''Columns from Timestamped (abstract): created.'''" in table(text, "kinds_site")
    # A hollow triangle at the parent, as UML draws it.
    assert svg.render(schema).count('class="inheritance"') == 1


def test_a_foreign_key_the_database_does_not_check_says_so():
    schema = kinds()
    loose = next(r for r in schema["relations"] if r["to"]["field"] == "lives_near_id")
    assert loose["constrained"] is False
    docs = markdown.render(schema, sql="", diagram=None)
    assert "| `lives_near_id` | `ForeignKey` | `bigint` | yes | FK (no constraint) |" in docs
    assert (
        "- `lives_near_id` → [Site](#site).`id`, on delete do nothing, no database constraint"
    ) in docs
    text = er.dbml(schema)
    # No Ref, which would read as a foreign key: the column's note says what it refers to.
    assert "Ref kinds_person_lives_near_id_fk" not in text
    assert (
        "  lives_near_id bigint [note: 'refers to kinds_site.id, with no foreign key in the "
        "database']"
    ) in text
    assert 'kinds_site |o..o{ kinds_person : "(id) - (lives_near_id), no constraint"' in (
        er.mermaid(schema)
    )
    assert 'stroke-dasharray="8 4"' in svg.render(schema)


def test_a_many_to_many_through_a_model_is_in_both_models_relations():
    docs = markdown.render(kinds(), sql="", diagram=None)
    assert "- `teams` — many to many with [Team](#team), through [Membership](#membership)" in docs
    assert (
        "- `members` — many to many with [Person](#person), through [Membership](#membership)"
    ) in docs


def test_what_a_column_declares_beside_its_type():
    schema = kinds()
    fields = {
        (model["name"], field["name"]): field
        for model in schema["models"]
        for field in model["fields"]
    }
    assert fields[("Site", "name")]["collation"] == "NOCASE"
    budget = fields[("Site", "budget")]
    assert (budget["maxDigits"], budget["decimalPlaces"]) == (10, 2)
    docs = markdown.render(schema, sql="", diagram=None)
    assert "| `name` | `CharField` | `varchar(50)` collation `NOCASE` |" in docs
    assert "| `budget` | `DecimalField(10, 2)` | `decimal` |" in docs
    text = er.dbml(schema)
    assert "  name varchar(50) [not null, note: 'collation NOCASE']" in text
    assert (
        "  budget decimal [not null, note: 'declared max_digits=10, decimal_places=2, which the "
        "database does not enforce']"
    ) in text
    if since(5, 0):
        assert fields[("Team", "lower_name")]["stored"] is False
        assert '| generated (virtual): `LOWER("name")` |' in docs
        assert """  lower_name varchar(50) [note: 'generated (virtual): LOWER("name")']""" in text


def test_grouped_choices_keep_their_groups():
    schema = kinds()
    media = next(enum for enum in schema["enums"] if enum["name"] == "PersonMedia")
    assert [(value["dbName"], value["group"]) for value in media["values"]] == [
        ("vinyl", "Audio"),
        ("cd", "Audio"),
        ("vhs", "Video"),
    ]
    docs = markdown.render(schema, sql="", diagram=None)
    assert "| Group | Name | Stored as |" in docs
    assert "| Video | `VHS Tape` | `vhs` |" in docs
    assert "  \"vhs\" [note: 'group: Video']" in er.dbml(schema)
    assert ("VHS Tape", "vhs · Video", "") in svg.layout(schema)["enum:PersonMedia"].rows


def test_a_note_of_several_lines_is_between_three_quotes():
    text = table(er.dbml(kinds()), "kinds_team")
    # DBML takes no line break between single quotes.
    assert "  name varchar(50) [not null, note: '''The team\\'s name.\n0: no name yet.''']" in text


def test_a_models_own_diagram_draws_its_own_enums_only():
    schema = kinds()
    assert [e["name"] for e in er.neighborhood(schema, "Person")["enums"]] == ["PersonMedia"]
    # Site is Person's neighbour: Person's enum is on Person's diagram, not on Site's.
    assert er.neighborhood(schema, "Site")["enums"] == []


@pytest.fixture
def mysql():
    """A MySQL alias whose server is not running: PyMySQL stands in for mysqlclient."""
    pymysql = pytest.importorskip("pymysql")
    pymysql.version_info = (2, 2, 1, "final", 0)
    pymysql.install_as_MySQLdb()
    from django.db.backends.mysql.base import DatabaseWrapper

    alias = "mysql"
    config = connections.configure_settings(
        {
            "default": settings.DATABASES["default"],
            # A port nothing listens on: refused at once.
            alias: {"ENGINE": "django.db.backends.mysql", "NAME": "x", "PORT": "1"},
        }
    )[alias]
    connections[alias] = DatabaseWrapper(config, alias)
    yield alias
    del connections[alias]


def test_docs_on_mysql_assume_a_server_when_it_cannot_be_asked(mysql):
    schema = export.schema_for(mysql, ROOT, everything=False)
    customer = next(model for model in schema["models"] if model["name"] == "Customer")
    types = {field["name"]: field["nativeType"] for field in customer["fields"]}
    assert types["name"] == "varchar(100)"
    # The way a key is filled is its default's to say, as on every other backend.
    assert types["id"] == "bigint"
    sql = markdown.create_sql(schema, names(), mysql)
    assert sql.startswith("-- Written for MySQL 8.4, assumed: the database could not be asked.")
    assert "CREATE TABLE `shop_customer`" in sql
    assert "-- Not collected" not in sql
    assert "  name varchar(100) [not null" in er.dbml(schema)
    connection = connections[mysql]
    # Forgotten afterwards: a connection that reaches its server later asks it.
    assert "mysql_server_data" not in vars(connection)
    assert "data_types" not in vars(connection)
    assert connection.connection is None
