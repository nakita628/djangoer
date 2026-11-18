"""The docs of a schema as Markdown: the diagram, the schema as SQL, and a section per model."""

from __future__ import annotations

import re
from contextlib import ExitStack
from typing import Any

from django.db import DatabaseError, connections

from .assumed import assumed as server_assumed
from .assumed import offline, without_server
from .er import (
    MERMAID_LIMIT,
    column_name,
    columns,
    digits,
    external,
    generated,
    is_key,
    loose,
    mermaid,
    referring_fields,
    relation_columns,
)
from .schema import Names

# What the docs and DBML say of a model with `managed = False`.
UNMANAGED = (
    "Not managed by Django (`managed = False`): it neither creates nor changes the table, whose "
    "indexes are the ones its own SQL gives it."
)
ACTIONS = {
    "CASCADE": "cascade",
    "SET_NULL": "set null",
    "SET_DEFAULT": "set default",
    "PROTECT": "protect",
    "RESTRICT": "restrict",
    "DO_NOTHING": "do nothing",
}


def create_sql(schema: dict[str, Any], known: Names, alias: str) -> str:
    """`CREATE TABLE` and the indexes of every model of the schema, as Django would write them
    for this database. Nothing is run: the statements are collected, not sent.

    The indexes, and on most backends the foreign keys, are deferred: the editor keeps them to
    run as the `with` ends. They are taken from it before that, as Django 4.2 composes each of
    them on PostgreSQL with a cursor, which connects. Not atomic either: on a backend that can
    roll back DDL (PostgreSQL) the transaction would connect too. The docs need no database.

    Some of what Django writes depends on the server's version (a `UniqueConstraint` with
    `nulls_distinct` asks whether it is PostgreSQL 15), which takes a connection. When the
    database cannot be reached, the model is written again for a server assumed
    (`assumed.ASSUMED`), and the SQL says so in its first line. On MySQL even a column's type
    needs the server, which is assumed before anything is written.

    An add-on may connect all the same: django-pgtrigger opens a transaction for each trigger
    it adds to a table. What Django writes for the model is collected by then, so it is kept,
    and what was not collected is said in a comment at the end, rather than no docs at all.
    """
    connection = connections[alias]
    missing: list[str] = []
    assumed: set[str] = set()
    with ExitStack() as stack:
        # MySQL's column types need the server: assumed at once when it cannot be asked.
        version = stack.enter_context(offline(connection))
        if version is not None:
            assumed.add(version)
        editor = stack.enter_context(connection.schema_editor(collect_sql=True, atomic=False))
        without_server(editor)
        _merge_client_side(editor)
        for model in schema["models"]:
            cls = known.get(model["name"])
            if cls is None or not cls._meta.managed or external(model):
                continue
            mark = (len(editor.collected_sql), len(editor.deferred_sql))
            try:
                editor.create_model(cls)
                continue
            except DatabaseError as error:
                failure = error
            version = stack.enter_context(server_assumed(connection)) if not assumed else None
            if version is not None:
                without_server(editor)
                # Kept for the models after it: one try to connect is enough to know.
                assumed.add(version)
                # What the failed try collected is the start of the same statements.
                del editor.collected_sql[mark[0] :]
                del editor.deferred_sql[mark[1] :]
                try:
                    editor.create_model(cls)
                    continue
                except DatabaseError as error:
                    failure = error
            reason = str(failure).strip().splitlines()[0] if str(failure).strip() else ""
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
    if assumed:
        versions = ", ".join(sorted(assumed))
        sql = f"-- Written for {versions}, assumed: the database could not be asked.\n\n{sql}"
    return sql


def _merge_client_side(editor: Any) -> None:
    """Have the editor merge a statement's parameters itself, as Django's own editor does when
    it collects (`quote_value`): PostgreSQL's merges them with a cursor, which connects, for a
    `CREATE TABLE` with a `db_default` and for every deferred statement on Django 4.2."""
    execute = editor.execute

    def collect(sql: Any, params: Any = ()) -> Any:
        if params is not None:
            sql = str(sql) % tuple(editor.quote_value(param) for param in params)
        return execute(sql, None)

    editor.execute = collect


def _cell(text: str | None) -> str:
    """Text as a table cell: no line breaks, no pipe that would end the cell."""
    return (text or "").replace("|", "\\|").replace("\n", " ")


def _code(text: str | None) -> str:
    return f"`{_cell(text)}`" if text else ""


def _keys(model: dict[str, Any], field: dict[str, Any], unconstrained: set[str]) -> str:
    """The Key cell. A column that refers to another model with no constraint in the database
    (`db_constraint=False`, the columns of a ForeignObject) says so: the database does not
    check it. `unconstrained` holds the columns no relation the database checks reads."""
    marks = []
    if is_key(model, field):
        marks.append("PK")
    if field["name"] in unconstrained:
        marks.append("FK (no constraint)")
    elif field["isForeignKey"]:
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
    return {
        model["name"]: slug(model["name"], seen)
        for model in schema["models"]
        if not external(model)
    }


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
        # A stub of a model outside the docs is named, with nothing to link to.
        return f"[{name}](#{links[name]})" if name in links else f"`{name}`"

    def outside(name: str) -> str:
        """What follows a model outside the docs: its app, and that it is not here."""
        return "" if name in links else f" ({tables[name]['app']}, not in these docs)"

    lines = _generic_lines(model) + _through_lines(model, link)
    for relation in schema["relations"]:
        parent, child = relation["from"], relation["to"]
        if model["name"] not in (parent["model"], child["model"]):
            continue
        if relation["origin"] == "implicit-many-to-many":
            other = child["model"] if parent["model"] == model["name"] else parent["model"]
            mine = parent["field"] if parent["model"] == model["name"] else child["field"]
            lines.append(f"- `{mine}` — many to many with {link(other)}{outside(other)}")
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
        action = _action(relation["onDelete"])
        deletes = f", on delete {action}" if action else ""
        if relation.get("parentLink"):
            deletes = f", parent link{deletes}"
        if loose(relation):
            deletes += ", no database constraint"
        referred, referring = relation_columns(tables, relation)
        if len(referring) > 1:
            # A ForeignObject to a composite key: the columns it reads, and theirs.
            mine, theirs = _columns(referring), _columns(referred)
            if child["model"] == model["name"]:
                lines.append(
                    f"- `{child['field']}` {mine} → {link(parent['model'])}.{theirs}{deletes}"
                )
            if parent["model"] == model["name"]:
                lines.append(
                    f"- {link(child['model'])}.`{child['field']}` {mine} → {theirs}{deletes}"
                )
            continue
        if child["model"] == model["name"]:
            target = tables[parent["model"]]
            lines.append(
                f"- `{child['field']}` → {link(parent['model'])}"
                f".`{_key_name(target, parent['field'])}`{outside(parent['model'])}{deletes}"
            )
        else:
            lines.append(
                f"- {link(child['model'])}.`{child['field']}` → `{parent['field']}`{deletes}"
            )
    return lines


def _through_lines(model: dict[str, Any], link) -> list[str]:
    """The many-to-many of a model that go through a model of the project's (`through=`), on
    each side: the diagrams draw the through model's two foreign keys, and the docs name the
    field the code reaches the other side by."""
    lines = []
    for field in model["fields"]:
        relation = field["relation"]
        if field["kind"] != "object" or relation is None or not relation.get("through"):
            continue
        lines.append(
            f"- `{field['name']}` — many to many with {link(field['type'])}, "
            f"through {link(relation['through'])}"
        )
    return lines


def _columns(names: list[str]) -> str:
    return "(" + ", ".join(f"`{name}`" for name in names) + ")"


def _action(on_delete: str | None) -> str:
    """`on_delete` as the docs say it: `cascade`, `set null`, `set (None)`…"""
    if not on_delete:
        return ""
    if on_delete.startswith("SET(") and on_delete.endswith(")"):
        return f"set ({on_delete[4:-1]})"
    return ACTIONS.get(on_delete, on_delete.lower().replace("_", " "))


def _key_name(model: dict[str, Any], name: str) -> str:
    return next((column_name(f) for f in model["fields"] if f["name"] == name), name)


def _index(index: dict[str, Any]) -> str:
    """`- gin index `name` on `a`, `b` desc (`opclass`) include `c` with `m = 16`
    where `"primary" = 1`, nulls not distinct, deferrable (initially deferred)`: the method only
    when it is not a B-tree."""
    kind = {"unique": "unique", "exclusion": "exclusion"}.get(index["type"], "index")
    method = f"{index['method']} " if index["method"] else ""
    name = f" `{index['name']}`" if index["name"] else ""
    keys = [*index["fields"], *index["expressions"]]
    opclasses = ", ".join(_code(opclass) for opclass in index["opclasses"])
    using = f" ({opclasses})" if opclasses else ""
    include = ", ".join(_code(column) for column in index["include"])
    including = f" include {include}" if include else ""
    parameters = f" with {_code(', '.join(index['parameters']))}" if index["parameters"] else ""
    where = f" where {_code(index['condition'])}" if index["condition"] else ""
    on = ", ".join(_code(key) + (" desc" if key in index["descending"] else "") for key in keys)
    rules = []
    if index["nullsDistinct"] is not None:
        rules.append("nulls distinct" if index["nullsDistinct"] else "nulls not distinct")
    if index["deferrable"]:
        rules.append(f"deferrable (initially {index['deferrable']})")
    after = "".join(f", {rule}" for rule in rules)
    return f"- {method}{kind}{name} on {on}{using}{including}{parameters}{where}{after}"


def _native(field: dict[str, Any]) -> str:
    """The Type cell: the column's type in the database, and its collation when it has one."""
    collation = f" collation {_code(field['collation'])}" if field.get("collation") else ""
    return _code(field["nativeType"]) + collation


def _unconstrained(model: dict[str, Any], schema: dict[str, Any]) -> set[str]:
    """The columns of a model that refer to another with no foreign key in the database, and
    are not the column of a foreign key it has besides (a ForeignObject reads those too)."""
    tables = {entry["name"]: entry for entry in schema["models"]}
    mine = [
        relation
        for relation in schema["relations"]
        if relation["origin"] == "inferred" and relation["to"]["model"] == model["name"]
    ]
    checked = {name for r in mine if not loose(r) for name in referring_fields(tables, r)}
    return {name for r in mine if loose(r) for name in referring_fields(tables, r)} - checked


def _inheritance(model: dict[str, Any], schema: dict[str, Any], links: dict[str, str]) -> list[str]:
    """What a model shares with others: the parent whose rows its rows are (multi-table), the
    models whose rows are its own, its proxy models, the abstract models its columns are from."""

    def link(name: str) -> str:
        return f"[{name}](#{links[name]})" if name in links else f"`{name}`"

    lines = []
    for relation in schema["relations"]:
        if not relation.get("parentLink"):
            continue
        if relation["to"]["model"] == model["name"]:
            lines.append(
                f"Inherits from {link(relation['from']['model'])} (multi-table): its rows are "
                f"joined on `{relation['to']['field']}`."
            )
    children = [
        link(relation["to"]["model"])
        for relation in schema["relations"]
        if relation.get("parentLink") and relation["from"]["model"] == model["name"]
    ]
    if children:
        lines.append(f"Subclasses (multi-table): {', '.join(children)}.")
    if model.get("proxies"):
        proxies = ", ".join(f"`{proxy['name']}`" for proxy in model["proxies"])
        lines.append(f"Proxy models, on this table: {proxies}.")
    for base in model.get("abstractBases") or []:
        fields = ", ".join(f"`{name}`" for name in base["fields"])
        lines.append(f"Columns from `{base['name']}` (abstract): {fields}.")
    # One paragraph each.
    return [part for line in lines for part in (line, "")][:-1]


def _default(field: dict[str, Any]) -> str:
    """The Default cell: what Python gives a new row, the database's own default (as the SQL
    the column is created with), or the expression a generated column is computed from, and
    whether it is stored or computed on read."""
    if field["generated"]:
        kind, _colon, _expression = (generated(field) or "generated:").partition(":")
        return f"{kind}: {_code(field['generated'])}"
    if field["dbDefault"]:
        return f"{_code(field['dbDefault'])} (database)"
    return _code(field["default"])


def _model(
    model: dict[str, Any], schema: dict[str, Any], links: dict[str, str], diagram: str | None
) -> list[str]:
    lines = [f"## {model['name']}", "", f"Table `{model['dbName']}`, app `{model['app']}`."]
    if not model["managed"]:
        lines += ["", UNMANAGED]
    inheritance = _inheritance(model, schema, links)
    if inheritance:
        lines += ["", *inheritance]
    if model["documentation"]:
        lines += ["", model["documentation"]]
    if diagram is not None:
        lines += ["", f"![{model['name']} and the models it relates to]({diagram})"]
    lines += [
        "",
        "| Column | Field | Type | Null | Key | Default | Description |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    unconstrained = _unconstrained(model, schema)
    for field in columns(model):
        lines.append(
            "| "
            + " | ".join(
                [
                    _code(column_name(field)),
                    _code(field["type"] + (digits(field) or "")),
                    _native(field),
                    "" if field["isRequired"] else "yes",
                    _keys(model, field, unconstrained),
                    _default(field),
                    _cell(field["documentation"]),
                ]
            )
            + " |"
        )
    if model["indexes"]:
        heading = "Indexes:" if model["managed"] else "Indexes, as declared:"
        lines += ["", heading, ""]
        lines += [_index(index) for index in model["indexes"]]
    if model["checks"]:
        lines += ["", "Checks:", ""]
        lines += [f"- `{c['name']}`: {_code(c['expression'])}" for c in model["checks"]]
    relations = _relations(model, schema, links)
    if relations:
        lines += ["", "Relations:", "", *relations]
    return lines


def _enum(enum: dict[str, Any]) -> list[str]:
    """An enum's table; with a Group column when its choices are grouped."""
    if any(value.get("group") for value in enum["values"]):
        lines = [f"## {enum['name']}", "", "| Group | Name | Stored as |", "| --- | --- | --- |"]
        lines += [
            f"| {_cell(value.get('group'))} | `{value['name']}` | {_code(value['dbName'])} |"
            for value in enum["values"]
        ]
        return lines
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


def render(
    schema: dict[str, Any],
    *,
    sql: str,
    diagram: str | None,
    tables: dict[str, str] | None = None,
) -> str:
    """The docs of a schema, as one Markdown document.

    `diagram` is the path of the diagram to show (an SVG written beside the document); without
    one, the diagram is the Mermaid block, which GitHub and most viewers draw themselves.
    `tables` is the path of each model's own diagram, shown in its section, by model.
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
        if external(model):
            continue
        own = (tables or {}).get(model["name"])
        lines += [*_model(model, schema, links, own), ""]
    if schema["enums"]:
        lines += ["# Enums", ""]
        for enum in schema["enums"]:
            lines += [*_enum(enum), ""]
    return "\n".join(lines).rstrip("\n") + "\n"
