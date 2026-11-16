from argparse import Namespace
from pathlib import Path

from returns.result import Failure, Success

from djangoer import cli
from djangoer.studio.domain import er, export, svg

ROOT = Path(__file__).parent


def shop():
    """The schema of the test project's own models: the shop app, without django.contrib."""
    return export.schema_for("default", ROOT, everything=False)


def test_an_export_covers_the_projects_own_models_unless_asked_for_all():
    assert [model["name"] for model in shop()["models"]] == ["Customer", "Product", "Order"]
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
    assert "Enum ProductKind {\n  book\n  tool\n}" in text
    assert "  email varchar(254) [unique, not null, note: 'Where receipts go']" in text
    assert "  kind ProductKind [default: 'book', not null]" in text
    assert "  paid bool [default: false, not null]" in text
    assert "Note: '''Someone who orders.'''" in text
    assert (
        "Ref orders_customer_id_fk: orders.customer_id > shop_customer.id [delete: restrict]"
        in text
    )
    assert "Ref: shop_product.id <> orders.id" in text


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
    docs = Namespace(database="default", all=False, output=str(tmp_path / "docs"))
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
