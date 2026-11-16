"""The ER model as text: a Mermaid diagram and a DBML document.

Both are written from the schema Studio draws (schema.py), so a file and the diagram on screen
say the same thing. Tables go by their database names, as the two formats expect.
"""

from __future__ import annotations

import re
from typing import Any

# The crow's-foot ends of a Mermaid relation, parent side and child side.
PARENT_END = {"one": "||", "zero-one": "|o", "zero-many": "}o", "many": "}|"}
CHILD_END = {"one": "||", "zero-one": "o|", "zero-many": "o{", "many": "|{"}
# on_delete as DBML names a referential action.
DBML_ACTIONS = {
    "CASCADE": "cascade",
    "SET_NULL": "set null",
    "SET_DEFAULT": "set default",
    "PROTECT": "restrict",
    "RESTRICT": "restrict",
    "DO_NOTHING": "no action",
}


def scoped(schema: dict[str, Any], *, everything: bool) -> dict[str, Any]:
    """The schema an export covers: the project's own models, or every model with `everything`.

    A model of an installed package (django.contrib.auth) has no source in the project, which
    is how it is told apart. A relation to a model left out is left out with it, and so is an
    enum no remaining field uses.
    """
    if everything:
        return schema
    models = [model for model in schema["models"] if model["location"] is not None]
    kept = {model["name"] for model in models}
    used = {
        field["type"] for model in models for field in model["fields"] if field["kind"] == "enum"
    }
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


def columns(model: dict[str, Any]) -> list[dict[str, Any]]:
    """The fields of a model that are columns of its table."""
    return [field for field in model["fields"] if field["kind"] != "object"]


def column_name(field: dict[str, Any]) -> str:
    return field["dbName"] or field["name"]


def _tables(schema: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {model["name"]: model for model in schema["models"]}


def _column_of(model: dict[str, Any], name: str) -> str:
    """The column a field name stands for; a relation field (`tags`) stands for itself."""
    for field in model["fields"]:
        if field["name"] == name:
            return column_name(field)
    return name


def _identifier(text: str) -> str:
    """A name Mermaid takes as one word."""
    return re.sub(r"\W", "_", text)


def _quoted(text: str) -> str:
    return text.replace('"', "'").replace("\n", " ")


def mermaid(schema: dict[str, Any]) -> str:
    """An `erDiagram`: the relations first, then each table with its columns."""
    tables = _tables(schema)
    lines = ["erDiagram"]
    for relation in schema["relations"]:
        parent = tables[relation["from"]["model"]]
        child = tables[relation["to"]["model"]]
        many_to_many = relation["origin"] == "implicit-many-to-many"
        left = "}o" if many_to_many else PARENT_END[relation["from"]["cardinality"]]
        right = "o{" if many_to_many else CHILD_END[relation["to"]["cardinality"]]
        label = (
            f"({_column_of(parent, relation['from']['field'])}) - "
            f"({_column_of(child, relation['to']['field'])})"
        )
        lines.append(
            f"    {_identifier(parent['dbName'])} {left}--{right} "
            f'{_identifier(child["dbName"])} : "{label}"'
        )
    for model in schema["models"]:
        lines.append(f"    {_identifier(model['dbName'])} {{")
        for field in columns(model):
            key = "PK" if field["isId"] else "FK" if field["isForeignKey"] else ""
            key = f"{key}, UK".strip(", ") if field["isUnique"] else key
            note = f' "{_quoted(field["documentation"])}"' if field["documentation"] else ""
            parts = [_identifier(field["type"]), _identifier(column_name(field)), key]
            lines.append("        " + " ".join(part for part in parts if part) + note)
        lines.append("    }")
    return "\n".join(lines) + "\n"


def _dbml_type(field: dict[str, Any]) -> str:
    """The column's type in the database; a type of several words is quoted."""
    if field["kind"] == "enum":
        return field["type"]
    text = field["nativeType"] or field["type"]
    return f'"{text}"' if re.search(r"\s", text) else text


def _dbml_string(text: str) -> str:
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _dbml_default(field: dict[str, Any]) -> str | None:
    default = field["default"]
    if default is None or default == "autoincrement()":
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?", default) or default in ("True", "False"):
        return default.lower()
    if (default.startswith("'") and default.endswith("'")) or (
        default.startswith('"') and default.endswith('"')
    ):
        return _dbml_string(default[1:-1])
    # A callable or an expression: `now()`, `dict()`.
    return f"`{default}`"


def _dbml_settings(field: dict[str, Any]) -> str:
    settings = []
    if field["isId"]:
        settings.append("pk")
    if field["default"] == "autoincrement()":
        settings.append("increment")
    if field["isUnique"]:
        settings.append("unique")
    default = _dbml_default(field)
    if default is not None:
        settings.append(f"default: {default}")
    if field["isRequired"] and not field["isId"]:
        settings.append("not null")
    if field["documentation"]:
        settings.append(f"note: {_dbml_string(field['documentation'])}")
    return f" [{', '.join(settings)}]" if settings else ""


def dbml(schema: dict[str, Any]) -> str:
    """A DBML document: enums, tables with their indexes and notes, then the references."""
    tables = _tables(schema)
    blocks: list[str] = []
    for enum in schema["enums"]:
        values = "\n".join(f"  {value['dbName'] or value['name']}" for value in enum["values"])
        blocks.append(f"Enum {enum['name']} {{\n{values}\n}}")
    for model in schema["models"]:
        lines = [f"Table {model['dbName']} {{"]
        lines += [
            f"  {column_name(field)} {_dbml_type(field)}{_dbml_settings(field)}"
            for field in columns(model)
        ]
        if model["indexes"]:
            lines += ["", "  indexes {"]
            for index in model["indexes"]:
                names = ", ".join(_column_of(model, name) for name in index["fields"])
                settings = ["unique"] if index["type"] == "unique" else []
                if index["name"]:
                    settings.append(f"name: {_dbml_string(index['name'])}")
                suffix = f" [{', '.join(settings)}]" if settings else ""
                lines.append(f"    ({names}){suffix}")
            lines.append("  }")
        if model["documentation"]:
            lines += ["", f"  Note: '''{model['documentation']}'''"]
        lines.append("}")
        blocks.append("\n".join(lines))
    for relation in schema["relations"]:
        parent = tables[relation["from"]["model"]]
        child = tables[relation["to"]["model"]]
        if relation["origin"] == "implicit-many-to-many":
            # A many-to-many has no column of its own on either table: it joins their keys.
            blocks.append(
                f"Ref: {child['dbName']}.{_key(child)} <> {parent['dbName']}.{_key(parent)}"
            )
            continue
        column = _column_of(child, relation["to"]["field"])
        arrow = "-" if relation["to"]["cardinality"] == "zero-one" else ">"
        action = DBML_ACTIONS.get(relation["onDelete"] or "")
        settings = f" [delete: {action}]" if action else ""
        blocks.append(
            f"Ref {child['dbName']}_{column}_fk: {child['dbName']}.{column} {arrow} "
            f"{parent['dbName']}.{_column_of(parent, relation['from']['field'])}{settings}"
        )
    return "\n\n".join(blocks) + "\n"


def _key(model: dict[str, Any]) -> str:
    return next((column_name(field) for field in columns(model) if field["isId"]), "id")
