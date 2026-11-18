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
# The longest text Mermaid draws: its default `maxTextSize`, which GitHub keeps. A longer
# diagram is an error box where the picture would be.
MERMAID_LIMIT = 50_000
# on_delete as DBML names a referential action.
DBML_ACTIONS = {
    "CASCADE": "cascade",
    "SET_NULL": "set null",
    "SET_DEFAULT": "set default",
    "PROTECT": "restrict",
    "RESTRICT": "restrict",
    "DO_NOTHING": "no action",
}


def referring(relation: dict[str, Any]) -> str:
    """The model whose rows say what they refer to: the one with the foreign key (or with the
    generic one), or the one that declares the many-to-many."""
    end = "from" if relation["origin"] == "implicit-many-to-many" else "to"
    return relation[end]["model"]


def scoped(schema: dict[str, Any], *, everything: bool) -> dict[str, Any]:
    """The schema an export covers: the project's own models, or every model with `everything`.

    A model of an installed package (django.contrib.auth) is not in the project's directory,
    which is how it is told apart (`own`). It is left out, but not that the project's models
    refer to it: "who wrote this post" is the first question a schema answers. A model a
    project's model refers to stays as a stub, `external`: its key and the columns referred
    to, no section of its own in the docs. A relation between models left out is left out, and
    so is an enum no remaining field uses.
    """
    if everything:
        return schema
    own = {model["name"] for model in schema["models"] if model["own"]}
    relations = [relation for relation in schema["relations"] if referring(relation) in own]
    referred: dict[str, set[str]] = {}
    for relation in relations:
        for end in ("from", "to"):
            if relation[end]["model"] not in own:
                referred.setdefault(relation[end]["model"], set()).add(relation[end]["field"])
    models = [
        model if model["own"] else _stub(model, referred[model["name"]])
        for model in schema["models"]
        if model["own"] or model["name"] in referred
    ]
    used = {
        field["type"] for model in models for field in model["fields"] if field["kind"] == "enum"
    }
    return {
        **schema,
        "models": models,
        "enums": [enum for enum in schema["enums"] if enum["name"] in used],
        "relations": relations,
    }


def _stub(model: dict[str, Any], fields: set[str]) -> dict[str, Any]:
    """A model outside the export, as much of it as the project's models refer to: its key and
    the columns they name."""
    key = set(model["primaryKey"] or [])
    return {
        **model,
        "fields": [
            field
            for field in columns(model)
            if field["isId"] or field["name"] in key or field["name"] in fields
        ],
        "indexes": [],
        "genericForeignKeys": [],
        "proxies": [],
        "abstractBases": [],
        "documentation": None,
        "external": True,
    }


def external(model: dict[str, Any]) -> bool:
    """Whether a model is a stub of one outside the export (`scoped`)."""
    return bool(model.get("external"))


def related(schema: dict[str, Any]) -> list[str]:
    """The models with a relation, in the order of the schema: the ones a diagram of their own
    shows more of than the table of their columns does."""
    names = {end for r in schema["relations"] for end in (r["from"]["model"], r["to"]["model"])}
    return [
        model["name"]
        for model in schema["models"]
        if model["name"] in names and not external(model)
    ]


def neighborhood(schema: dict[str, Any], name: str) -> dict[str, Any]:
    """The schema of one model's diagram: the model, the models it joins, the relations between
    it and them, and the enums of the model's own fields. A neighbour's enums are its own
    diagram's: its card names the enum as the field's type, and a model with many neighbours
    (a generic relation's target) would otherwise be a picture of their enums."""
    relations = [
        relation
        for relation in schema["relations"]
        if name in (relation["from"]["model"], relation["to"]["model"])
    ]
    names = {name, *(end for r in relations for end in (r["from"]["model"], r["to"]["model"]))}
    models = [model for model in schema["models"] if model["name"] in names]
    used = {
        field["type"]
        for model in models
        if model["name"] == name
        for field in model["fields"]
        if field["kind"] == "enum"
    }
    return {
        **schema,
        "models": models,
        "relations": relations,
        "enums": [enum for enum in schema["enums"] if enum["name"] in used],
    }


def columns(model: dict[str, Any]) -> list[dict[str, Any]]:
    """The fields of a model that are columns of its table."""
    return [field for field in model["fields"] if field["kind"] != "object"]


def column_name(field: dict[str, Any]) -> str:
    return field["dbName"] or field["name"]


def is_key(model: dict[str, Any], field: dict[str, Any]) -> bool:
    """Whether a column is the primary key, or one of the columns of a composite one."""
    return field["isId"] or field["name"] in (model["primaryKey"] or [])


def relation_columns(
    tables: dict[str, dict[str, Any]], relation: dict[str, Any]
) -> tuple[list[str], list[str]]:
    """The columns of each end of a relation, the referred one's first. A foreign key has one
    at each end; a `ForeignObject` to a composite key names the columns it reads in its
    relation (`order_id`, `item_id` → the same on the other model)."""
    parent = tables[relation["from"]["model"]]
    child = tables[relation["to"]["model"]]
    for field in child["fields"]:
        found = field["relation"]
        if field["name"] == relation["to"]["field"] and found and len(found["fromFields"]) > 1:
            return (
                [_column_of(parent, name) for name in found["toFields"]],
                [_column_of(child, name) for name in found["fromFields"]],
            )
    return (
        [_column_of(parent, relation["from"]["field"])],
        [_column_of(child, relation["to"]["field"])],
    )


def loose(relation: dict[str, Any]) -> bool:
    """Whether a relation Django follows has no foreign key in the database behind it: a
    ForeignKey with `db_constraint=False`, a ForeignObject. A generic relation is a kind of its
    own, and a many-to-many is its table's."""
    return relation["origin"] == "inferred" and not relation.get("constrained", True)


def referring_fields(tables: dict[str, dict[str, Any]], relation: dict[str, Any]) -> list[str]:
    """The fields of the referring model a relation reads: its foreign key's column, or the
    columns a ForeignObject names."""
    child = tables[relation["to"]["model"]]
    for field in child["fields"]:
        found = field["relation"]
        if field["name"] == relation["to"]["field"] and found and len(found["fromFields"]) > 1:
            return list(found["fromFields"])
    return [relation["to"]["field"]]


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
        referred, referring = relation_columns(tables, relation)
        label = f"({', '.join(referred)}) - ({', '.join(referring)})"
        if relation.get("parentLink"):
            label = f"is a, by {', '.join(referring)}"
        elif loose(relation):
            label += ", no constraint"
        # Dotted: nothing in the database backs a generic relation, nor a loose one.
        line = ".." if relation["origin"] == "generic" or loose(relation) else "--"
        lines.append(
            f"    {_identifier(parent['dbName'])} {left}{line}{right} "
            f'{_identifier(child["dbName"])} : "{label}"'
        )
    for model in schema["models"]:
        lines.append(f"    {_identifier(model['dbName'])} {{")
        for field in columns(model):
            key = "PK" if is_key(model, field) else "FK" if field["isForeignKey"] else ""
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
    return _dbml_native(field["nativeType"] or field["type"])


def _dbml_native(text: str) -> str:
    """A type as the database names it. A plain name (`text`, `varchar(254)`, `text[]`) is
    written as it is; anything else is quoted: several words (`double precision`), a sized
    array (`varchar(64)[]`), which DBML does not take bare."""
    plain = re.fullmatch(r"\w+(\(\d+(,\d+)?\)|\[\])?", text)
    return text if plain else '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dbml_string(text: str) -> str:
    """A string of one line between quotes; one of several lines (a `help_text` with a line
    break) between three, as DBML takes no line break in the other."""
    if "\n" in text or "\r" in text:
        return _dbml_note(text)
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


def _dbml_note(text: str) -> str:
    """A note of several lines, between three quotes: a quote or a backslash in it escaped, so
    a docstring that ends with a quote does not end the note."""
    return "'''" + text.replace("\\", "\\\\").replace("'", "\\'") + "'''"


def _dbml_quoted(text: str) -> str:
    """A name DBML takes whatever it holds: `"Asia/Tokyo"`, `"IN PROGRESS"`, `"-1"`."""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _dbml_enum_values(values: list[dict[str, Any]]) -> list[str]:
    """The values of an enum, as they are stored, each once.

    Choices may share a stored value under several labels (`mysql` for MySQL and for MariaDB),
    which DBML takes as the same value twice: it is written once, with its labels in a note.
    DBML has no name for the empty string, so that one is a comment: still there to read, and
    no error to the parser.
    """
    labels: dict[str, list[str]] = {}
    groups: dict[str, str] = {}
    for value in values:
        stored = value["name"] if value["dbName"] is None else value["dbName"]
        labels.setdefault(stored, []).append(value["name"])
        if value.get("group"):
            groups.setdefault(stored, value["group"])
    lines = []
    for stored, names in labels.items():
        notes = [" / ".join(names)] if len(names) > 1 else []
        # Grouped choices: the group a value is listed under.
        if stored in groups:
            notes.append(f"group: {groups[stored]}")
        if stored == "":
            lines.append(f'  // "" ({" / ".join(names)}): the empty string, which DBML cannot name')
        elif notes:
            lines.append(f"  {_dbml_quoted(stored)} [note: {_dbml_string('; '.join(notes))}]")
        else:
            lines.append(f"  {_dbml_quoted(stored)}")
    return lines


def _dbml_index(model: dict[str, Any], index: dict[str, Any]) -> str:
    """An index of a table's `indexes` block: its columns and its expressions, in backticks."""
    parts = [_column_of(model, name) for name in index["fields"]]
    parts += [f"`{expression}`" for expression in index["expressions"]]
    settings = ["unique"] if index["type"] == "unique" else []
    # DBML names two methods; the others (gin, brin, hnsw…) go in the note.
    if index["method"] in ("btree", "hash"):
        settings.append(f"type: {index['method']}")
    if index["name"]:
        settings.append(f"name: {_dbml_string(index['name'])}")
    # DBML has neither partial indexes nor operator classes: they go in the note, not lost.
    notes = ["exclusion constraint"] if index["type"] == "exclusion" else []
    if index["method"] and index["method"] not in ("btree", "hash"):
        notes.append(f"using {index['method']}")
    if index["descending"]:
        notes.append(f"descending: {', '.join(index['descending'])}")
    notes += index["opclasses"]
    if index["include"]:
        notes.append(f"include ({', '.join(index['include'])})")
    if index["parameters"]:
        notes.append(f"with ({', '.join(index['parameters'])})")
    if index["condition"]:
        notes.append(f"where {index['condition']}")
    if index["nullsDistinct"] is not None:
        notes.append("nulls distinct" if index["nullsDistinct"] else "nulls not distinct")
    if index["deferrable"]:
        notes.append(f"deferrable, initially {index['deferrable']}")
    if notes:
        settings.append(f"note: {_dbml_string('; '.join(notes))}")
    suffix = f" [{', '.join(settings)}]" if settings else ""
    return f"    ({', '.join(parts)}){suffix}"


def _dbml_through(relation: dict[str, Any], tables: dict[str, dict[str, Any]]) -> list[str]:
    """A many-to-many as what the database has: the table that joins the two, and its two
    references. A `<>` between the keys would be the same line twice for two many-to-many
    between one pair of models, and no line at all for one from a model to itself."""
    through = relation["through"]
    source = tables[relation["from"]["model"]]
    target = tables[relation["to"]["model"]]
    table = through["dbName"]

    lines = [f"Table {table} {{", *(_dbml_column(field) for field in through["fields"])]
    if through["indexes"]:
        # The columns of the table are its fields' names already: nothing to look up.
        lines += ["", "  indexes {", *(_dbml_index({"fields": []}, i) for i in through["indexes"])]
        lines.append("  }")
    lines.append("}")
    refs = [
        f"Ref {table}_{column}_fk: {table}.{column} > {model['dbName']}.{_key(model)} "
        "[delete: cascade]"
        for column, model in ((through["fromColumn"], source), (through["toColumn"], target))
    ]
    return ["\n".join(lines), *refs]


def _dbml_default(field: dict[str, Any]) -> str | None:
    """The default of a column: the database's own (`db_default`, as SQL) first, else the one
    Python gives a new row."""
    db_default = field["dbDefault"]
    if db_default is not None:
        if re.fullmatch(r"-?\d+(\.\d+)?", db_default):
            return db_default
        if db_default.upper() in ("TRUE", "FALSE"):
            return db_default.lower()
        if re.fullmatch(r"'(?:[^']|'')*'", db_default):
            return _dbml_string(db_default[1:-1].replace("''", "'"))
        return f"`{db_default}`"
    default = field["default"]
    if default is None or default == "autoincrement()":
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?", default) or default in ("True", "False"):
        return default.lower()
    if default == "None":
        return "null"
    if (default.startswith("'") and default.endswith("'")) or (
        default.startswith('"') and default.endswith('"')
    ):
        return _dbml_string(default[1:-1])
    # A callable (`dict()`, `now()`): Python calls it for a new row, the database has no default.
    # A backticked default would read as an SQL expression; the column's note says it instead.
    return None


def _python_default(field: dict[str, Any]) -> str | None:
    """What the note of a column says of a default only Python gives: a callable's."""
    default = field["default"]
    if field["dbDefault"] is not None or default in (None, "autoincrement()"):
        return None
    if _dbml_default(field) is not None:
        return None
    return f"default in Python: {default}"


def _dbml_column(field: dict[str, Any], note: str | None = None) -> str:
    return f"  {column_name(field)} {_dbml_type(field)}{_dbml_settings(field, note)}"


def _dbml_settings(field: dict[str, Any], note: str | None = None) -> str:
    """The settings of a column; `note` is said of it beside its documentation."""
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
    notes = [
        text
        for text in (
            field["documentation"],
            generated(field),
            _python_default(field),
            _declared(field),
            note,
        )
        if text
    ]
    if notes:
        settings.append(f"note: {_dbml_string('. '.join(notes))}")
    return f" [{', '.join(settings)}]" if settings else ""


def generated(field: dict[str, Any]) -> str | None:
    """What a generated column is computed from, and whether it is stored or computed on read:
    `generated (stored): "price" + "tax"`."""
    if not field["generated"]:
        return None
    kind = {True: " (stored)", False: " (virtual)"}.get(field.get("stored"), "")
    return f"generated{kind}: {field['generated']}"


def digits(field: dict[str, Any]) -> str | None:
    """The precision a DecimalField declares, `(10, 2)`, None for any other field."""
    if field.get("maxDigits") is None and field.get("decimalPlaces") is None:
        return None
    return f"({field.get('maxDigits')}, {field.get('decimalPlaces')})"


def _declared(field: dict[str, Any]) -> str | None:
    """What the column's type in DBML does not say of it: its collation, and the precision of a
    decimal whose type has none (SQLite's `decimal`)."""
    parts = []
    if field.get("collation"):
        parts.append(f"collation {field['collation']}")
    native = field["nativeType"] or ""
    if digits(field) and "(" not in native:
        parts.append(
            f"declared max_digits={field['maxDigits']}, decimal_places={field['decimalPlaces']}, "
            "which the database does not enforce"
        )
    return ", ".join(parts) or None


def _relation_notes(schema: dict[str, Any]) -> dict[tuple[str, str], str]:
    """What DBML says of a column whose relation no `Ref` says: one with no foreign key in the
    database (`db_constraint=False`, a ForeignObject), whose `Ref` would read as one; and the
    link of a child to its parent in multi-table inheritance."""
    tables = _tables(schema)
    notes: dict[tuple[str, str], str] = {}
    for relation in schema["relations"]:
        if relation.get("parentLink"):
            child, parent = relation["to"]["model"], relation["from"]["model"]
            notes[(child, relation["to"]["field"])] = (
                f"parent link: a {child} is a {parent} (multi-table inheritance)"
            )
            continue
        if not loose(relation):
            continue
        parent = tables[relation["from"]["model"]]
        referred, _referring = relation_columns(tables, relation)
        target = f"{parent['dbName']}.{_dbml_columns(referred)}"
        fields = referring_fields(tables, relation)
        # A ForeignObject reads columns that may be keys of their own: it is named.
        what = f"{relation['to']['field']}: " if len(fields) > 1 else ""
        for name in fields:
            key = (relation["to"]["model"], name)
            text = f"{what}refers to {target}, with no foreign key in the database"
            notes[key] = f"{notes[key]}. {text}" if key in notes else text
    return notes


def _generic_notes(schema: dict[str, Any]) -> dict[tuple[str, str], str]:
    """What DBML says of the key column of a generic foreign key, which no reference can say:
    with its content type it names a row of any model, and which models point back to it."""
    back: dict[tuple[str, str], list[str]] = {}
    for relation in schema["relations"]:
        if relation["origin"] == "generic":
            key = (relation["to"]["model"], relation["to"]["field"])
            back.setdefault(key, []).append(f"{relation['from']['model']}.{relation['name']}")
    notes = {}
    for model in schema["models"]:
        for generic in model["genericForeignKeys"]:
            key = (model["name"], generic["objectIdField"])
            note = (
                f"{generic['name']}: with {generic['contentTypeField']}, "
                "a generic foreign key to a row of any model"
            )
            if back.get(key):
                note += f" (from {', '.join(back[key])})"
            notes[key] = note
    return notes


def dbml(schema: dict[str, Any]) -> str:
    """A DBML document: enums, tables with their indexes and notes, then the references."""
    tables = _tables(schema)
    generic = _generic_notes(schema)
    for key, text in _relation_notes(schema).items():
        generic[key] = f"{generic[key]}. {text}" if key in generic else text
    blocks: list[str] = []
    for enum in schema["enums"]:
        values = "\n".join(_dbml_enum_values(enum["values"]))
        blocks.append(f"Enum {enum['name']} {{\n{values}\n}}")
    for model in schema["models"]:
        lines = [f"Table {model['dbName']} {{"]
        lines += [
            _dbml_column(field, generic.get((model["name"], field["name"])))
            for field in columns(model)
        ]
        composite = model["primaryKey"] or []
        if model["indexes"] or composite:
            lines += ["", "  indexes {"]
            if composite:
                # A key of several columns is an index in DBML, `pk` on each would be one each.
                lines.append(f"    ({', '.join(_column_of(model, c) for c in composite)}) [pk]")
            lines += [_dbml_index(model, index) for index in model["indexes"]]
            lines.append("  }")
        if model["checks"]:
            lines += ["", "  checks {"]
            lines += [
                f"    `{check['expression']}` [name: {_dbml_string(check['name'])}]"
                for check in model["checks"]
            ]
            lines.append("  }")
        unmanaged = None if model["managed"] else "Not managed by Django (managed = False)."
        outside = (
            f"Not in these docs: a model of the {model['app']} app, shown as far as it is referred to."
            if external(model)
            else None
        )
        texts = (outside, unmanaged, model["documentation"], *inheritance(model))
        note = "\n\n".join(text for text in texts if text)
        if note:
            lines += ["", f"  Note: {_dbml_note(note)}"]
        lines.append("}")
        blocks.append("\n".join(lines))
    for relation in schema["relations"]:
        parent = tables[relation["from"]["model"]]
        child = tables[relation["to"]["model"]]
        if relation["origin"] == "implicit-many-to-many":
            if relation["through"] is not None:
                blocks += _dbml_through(relation, tables)
            continue
        if relation["origin"] == "generic" or loose(relation):
            # No foreign key backs it, and a Ref would read as one: the column's note says it.
            continue
        referred, referring = relation_columns(tables, relation)
        arrow = "-" if relation["to"]["cardinality"] == "zero-one" else ">"
        # SET(None) is what the database's `set null` does; SET of anything else has no action.
        action = DBML_ACTIONS.get(
            "SET_NULL" if relation["onDelete"] == "SET(None)" else relation["onDelete"] or ""
        )
        settings = f" [delete: {action}]" if action else ""
        name = relation["to"]["field"] if len(referring) > 1 else referring[0]
        blocks.append(
            f"Ref {child['dbName']}_{name}_fk: {child['dbName']}.{_dbml_columns(referring)} "
            f"{arrow} {parent['dbName']}.{_dbml_columns(referred)}{settings}"
        )
    return "\n\n".join(blocks) + "\n"


def inheritance(model: dict[str, Any]) -> list[str]:
    """What a model's note says of the models it shares its rows or its columns with: its proxy
    models, and the abstract models its columns come from."""
    out = []
    if model.get("proxies"):
        out.append(f"Proxy models: {', '.join(p['name'] for p in model['proxies'])}.")
    for base in model.get("abstractBases") or []:
        out.append(f"Columns from {base['name']} (abstract): {', '.join(base['fields'])}.")
    return out


def _dbml_columns(names: list[str]) -> str:
    """One column, or several in parentheses: `(order_id, item_id)`."""
    return names[0] if len(names) == 1 else f"({', '.join(names)})"


def _key(model: dict[str, Any]) -> str:
    return next((column_name(field) for field in columns(model) if field["isId"]), "id")
