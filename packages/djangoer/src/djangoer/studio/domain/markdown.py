"""The docs of a schema as Markdown: the diagram, the schema as SQL, and a section per model."""

from __future__ import annotations

import re
from typing import Any

from django.db import DatabaseError, connections

from .er import MERMAID_LIMIT, column_name, columns, mermaid
from .schema import Names

ACTIONS = {"CASCADE": "cascade", "SET_NULL": "set null", "PROTECT": "protect"}


def create_sql(schema: dict[str, Any], known: Names, alias: str) -> str:
    """`CREATE TABLE` and the indexes of every model of the schema, as Django would write them
    for this database. Nothing is run: the statements are collected, not sent.

    The indexes, and on most backends the foreign keys, are deferred: the editor keeps them to
    run as the `with` ends. They are taken from it before that, as Django 4.2 composes each of
    them on PostgreSQL with a cursor, which connects. Not atomic either: on a backend that can
    roll back DDL (PostgreSQL) the transaction would connect too. The docs need no database.

    An add-on may connect all the same: django-pgtrigger opens a transaction for each trigger
    it adds to a table. What Django writes for the model is collected by then, so it is kept,
    and what was not collected is said in a comment at the end, rather than no docs at all.
    """
    connection = connections[alias]
    missing: list[str] = []
    with connection.schema_editor(collect_sql=True, atomic=False) as editor:
        for model in schema["models"]:
            cls = known.get(model["name"])
            if cls is None or not cls._meta.managed:
                continue
            try:
                editor.create_model(cls)
            except DatabaseError as error:
                reason = str(error).strip().splitlines()[0] if str(error).strip() else ""
                missing.append(f"-- {model['name']}: {reason}")
        deferred = [str(statement) for statement in editor.deferred_sql]
        editor.deferred_sql.clear()
    statements = [str(statement) for statement in editor.collected_sql]
    statements += [s if s.rstrip().endswith(";") else f"{s};" for s in deferred]
    sql = "\n\n".join(
        statement for statement in statements if not statement.lstrip().startswith("--")
    )
    if missing:
        note = "-- Not collected: what is added to these tables needs the database, which is down."
        sql += "\n\n" + "\n".join([note, *missing])
    return sql


def _cell(text: str | None) -> str:
    """Text as a table cell: no line breaks, no pipe that would end the cell."""
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _code(text: str | None) -> str:
    return f"`{_cell(text)}`" if text else ""


def _keys(field: dict[str, Any]) -> str:
    marks = []
    if field["isId"]:
        marks.append("PK")
    if field["isForeignKey"]:
        marks.append("FK")
    if field["isUnique"]:
        marks.append("unique")
    return ", ".join(marks)


def slug(text: str, seen: dict[str, int]) -> str:
    """The anchor GitHub gives a heading, as github-slugger makes it: lower case, without what is
    not a letter, a digit, `_`, `-` or a space, spaces as `-`, and `-1`, `-2`… after a slug that
    was made before. `blog.Category` is `#blogcategory`: the dot is dropped."""
    base = re.sub(r"[^\w\- ]", "", text.lower()).replace(" ", "-")
    count = seen.get(base, 0)
    seen[base] = count + 1
    return base if count == 0 else f"{base}-{count}"


def anchors(schema: dict[str, Any]) -> dict[str, str]:
    """The anchor of each model's section, made from every heading in the order of the page."""
    seen: dict[str, int] = {}
    slug("Schema docs", seen)
    return {model["name"]: slug(model["name"], seen) for model in schema["models"]}


def _generic_lines(model: dict[str, Any]) -> list[str]:
    return [
        f"- `{generic['name']}` → any model, by `{generic['contentTypeField']}` + "
        f"`{generic['objectIdField']}` (generic foreign key)"
        for generic in model["genericForeignKeys"]
    ]


def _content_type_of(model: dict[str, Any], object_id: str) -> str | None:
    return next(
        (
            generic["contentTypeField"]
            for generic in model["genericForeignKeys"]
            if generic["objectIdField"] == object_id
        ),
        None,
    )


def _relations(model: dict[str, Any], schema: dict[str, Any], links: dict[str, str]) -> list[str]:
    tables = {entry["name"]: entry for entry in schema["models"]}

    def link(name: str) -> str:
        return f"[{name}](#{links.get(name, name.lower())})"

    lines = _generic_lines(model)
    for relation in schema["relations"]:
        parent, child = relation["from"], relation["to"]
        if model["name"] not in (parent["model"], child["model"]):
            continue
        if relation["origin"] == "implicit-many-to-many":
            other = child["model"] if parent["model"] == model["name"] else parent["model"]
            mine = parent["field"] if parent["model"] == model["name"] else child["field"]
            lines.append(f"- `{mine}` — many to many with {link(other)}")
            continue
        if relation["origin"] == "generic":
            content_type = _content_type_of(tables[child["model"]], child["field"])
            pair = (
                f"`{content_type}` + `{child['field']}`" if content_type else f"`{child['field']}`"
            )
            if parent["model"] == model["name"]:
                lines.append(
                    f"- `{relation['name']}` ← {link(child['model'])}, by {pair} (generic relation)"
                )
            if child["model"] == model["name"]:
                lines.append(
                    f"- `{child['field']}` → {link(parent['model'])}.`{parent['field']}` "
                    f"where `{content_type}` is {parent['model']} "
                    f"(generic, `{parent['model']}.{relation['name']}`)"
                )
            continue
        action = ACTIONS.get(relation["onDelete"] or "", (relation["onDelete"] or "").lower())
        deletes = f", on delete {action}" if action else ""
        if child["model"] == model["name"]:
            target = tables[parent["model"]]
            lines.append(
                f"- `{child['field']}` → {link(parent['model'])}"
                f".`{_key_name(target, parent['field'])}`{deletes}"
            )
        else:
            lines.append(
                f"- {link(child['model'])}.`{child['field']}` → `{parent['field']}`{deletes}"
            )
    return lines


def _key_name(model: dict[str, Any], name: str) -> str:
    return next((column_name(f) for f in model["fields"] if f["name"] == name), name)


def _index(index: dict[str, Any]) -> str:
    """`- unique `name` on `a`, `lower("b")` where `"primary" = 1``."""
    kind = "unique" if index["type"] == "unique" else "index"
    name = f" `{index['name']}`" if index["name"] else ""
    keys = [*index["fields"], *index["expressions"]]
    where = f" where {_code(index['condition'])}" if index["condition"] else ""
    opclasses = ", ".join(_code(opclass) for opclass in index["opclasses"])
    using = f" ({opclasses})" if opclasses else ""
    return f"- {kind}{name} on {', '.join(_code(key) for key in keys)}{using}{where}"


def _model(model: dict[str, Any], schema: dict[str, Any], links: dict[str, str]) -> list[str]:
    lines = [f"## {model['name']}", "", f"Table `{model['dbName']}`, app `{model['app']}`."]
    if model["documentation"]:
        lines += ["", model["documentation"]]
    lines += [
        "",
        "| Column | Field | Type | Null | Key | Default | Description |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for field in columns(model):
        lines.append(
            "| "
            + " | ".join(
                [
                    _code(column_name(field)),
                    _code(field["type"]),
                    _code(field["nativeType"]),
                    "" if field["isRequired"] else "yes",
                    _keys(field),
                    _code(field["default"]),
                    _cell(field["documentation"]),
                ]
            )
            + " |"
        )
    if model["indexes"]:
        lines += ["", "Indexes:", ""]
        lines += [_index(index) for index in model["indexes"]]
    relations = _relations(model, schema, links)
    if relations:
        lines += ["", "Relations:", "", *relations]
    return lines


def _enum(enum: dict[str, Any]) -> list[str]:
    lines = [f"## {enum['name']}", "", "| Name | Stored as |", "| --- | --- |"]
    lines += [f"| `{value['name']}` | {_code(value['dbName'])} |" for value in enum["values"]]
    return lines


def _mermaid_block(text: str) -> list[str]:
    """The diagram as a Mermaid block, or, past what Mermaid draws, why it is not there: an error
    box in its place would say less."""
    if len(text) <= MERMAID_LIMIT:
        return ["```mermaid", text.rstrip("\n"), "```"]
    note = (
        f"> The diagram is {len(text):,} characters of Mermaid, more than the {MERMAID_LIMIT:,} "
        "it draws (GitHub too). Write it as a picture instead: `djangoer er -o er.svg`, or "
        "`djangoer docs`, whose README shows the SVG."
    )
    return [note]


def render(schema: dict[str, Any], *, sql: str, diagram: str | None) -> str:
    """The docs of a schema, as one Markdown document.

    `diagram` is the path of the diagram to show (an SVG written beside the document); without
    one, the diagram is the Mermaid block, which GitHub and most viewers draw themselves.
    """
    lines = ["# Schema docs", ""]
    if diagram is not None:
        lines += [f"![ER diagram]({diagram})", ""]
    else:
        lines += [*_mermaid_block(mermaid(schema)), ""]
    links = anchors(schema)
    lines += [" · ".join(f"[{name}](#{anchor})" for name, anchor in links.items()), ""]
    if sql:
        lines += [
            "<details>",
            "<summary>The whole schema as SQL</summary>",
            "",
            "```sql",
            sql,
            "```",
            "",
            "</details>",
            "",
        ]
    for model in schema["models"]:
        lines += [*_model(model, schema, links), ""]
    if schema["enums"]:
        lines += ["# Enums", ""]
        for enum in schema["enums"]:
            lines += [*_enum(enum), ""]
    return "\n".join(lines).rstrip("\n") + "\n"
