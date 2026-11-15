"""The reference page: every model with its fields and an example of each ORM operation."""

from __future__ import annotations

from typing import Any

from django.db import models
from django.db.models.fields.related import ForeignObjectRel

from ..inputs import OnDatabase
from .schema import Names, build_schema, names
from .sqlanalysis import python_type


def _example_value(field: models.Field) -> str:
    kind = python_type(field)
    if field.choices:
        return repr(field.flatchoices[0][0])
    return {
        "str": '"..."',
        "int": "1",
        "float": "1.0",
        "bool": "True",
        "Decimal": 'Decimal("1.00")',
        "datetime": "timezone.now()",
        "date": "date.today()",
        "time": "time(12, 0)",
        "timedelta": "timedelta(days=1)",
        "UUID": "uuid.uuid4()",
        "bytes": 'b"..."',
    }.get(kind, "...")


def _writable(model: type[models.Model]) -> list[models.Field]:
    """The columns a create() has to be given: no default, not null, not automatic."""
    out = []
    for field in model._meta.concrete_fields:
        if field.primary_key and isinstance(field, models.AutoField):
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        # blank=True on text is "may be empty": Django stores '' when nothing is given.
        if field.has_default() or field.null or field.blank:
            continue
        out.append(field)
    return out


def _operations(model: type[models.Model], name: str) -> list[dict[str, Any]]:
    # Each example ends in an expression: opened in the playground, it runs and shows its value.
    lookups = f"{name}Lookups"
    fields_type = f"{name}Fields"
    required = _writable(model)
    creating = ", ".join(f"{field.attname}={_example_value(field)}" for field in required) or "..."
    text = next(
        (
            field
            for field in model._meta.concrete_fields
            if isinstance(field, (models.CharField, models.TextField)) and not field.choices
        ),
        None,
    )
    chosen = next((field for field in model._meta.concrete_fields if field.choices), None)
    # A lookup that finds rows when it is tried: a value the field really takes, where there is
    # one to name.
    if chosen is not None:
        by_text = f"{chosen.name}={chosen.flatchoices[0][0]!r}"
    elif text is not None:
        by_text = f'{text.name}__icontains="a"'
    else:
        by_text = "pk__gt=0"
    first_set = (
        f"{required[0].attname}={_example_value(required[0])}"
        if required
        else (f'{text.name}="..."' if text is not None else "...")
    )

    def lookup_input(required_: bool = False) -> list[dict[str, Any]]:
        return [
            {
                "name": "**lookups",
                "types": [{"type": lookups, "isList": False, "location": "inputObjectTypes"}],
                "required": required_,
            }
        ]

    def field_input(label: str = "**fields") -> list[dict[str, Any]]:
        return [
            {
                "name": label,
                "types": [{"type": fields_type, "isList": False, "location": "inputObjectTypes"}],
                "required": True,
            }
        ]

    def output(type_: str | None, *, list_: bool = False, required_: bool = True):
        return {"type": type_, "required": required_, "list": list_}

    path = f"{model.__name__}.objects"
    return [
        {
            "name": "all",
            "description": f"Every {name}",
            "usage": f"# Get every {name}\n{path}.all()",
            "inputs": None,
            "output": output(name, list_=True),
        },
        {
            "name": "filter",
            "description": f"The {name} rows that match the lookups",
            "usage": f"# Get the {name} rows that match\n{path}.filter({by_text})",
            "inputs": lookup_input(),
            "output": output(name, list_=True),
        },
        {
            "name": "exclude",
            "description": f"The {name} rows that do not match the lookups",
            "usage": f"# Get the {name} rows that do not match\n{path}.exclude({by_text})",
            "inputs": lookup_input(),
            "output": output(name, list_=True),
        },
        {
            "name": "get",
            "description": f"Exactly one {name}: DoesNotExist when none matches, MultipleObjectsReturned when several do",
            "usage": f"# Get one {name}\n{path}.get(pk=1)",
            "inputs": lookup_input(True),
            "output": output(name),
        },
        {
            "name": "first",
            "description": f"The first {name} of the ordering, or None",
            "usage": f'# Get the first {name}\n{path}.order_by("pk").first()',
            "inputs": None,
            "output": output(name, required_=False),
        },
        {
            "name": "create",
            "description": f"Insert one {name} and return it",
            "usage": f"# Create one {name}\n{path}.create({creating})",
            "inputs": field_input(),
            "output": output(name),
        },
        {
            "name": "get_or_create",
            "description": f"The {name} that matches, created from defaults when there is none",
            "usage": (
                f"# Get one {name}, or create it\n{path}.get_or_create({first_set}, defaults={{}})"
            ),
            "inputs": lookup_input(True),
            "output": output(name),
        },
        {
            "name": "update",
            "description": f"Set fields on every {name} of the queryset, in one statement",
            "usage": f"# Update the {name} rows that match\n{path}.filter(pk=1).update({first_set})",
            "inputs": field_input(),
            "output": output("int"),
        },
        {
            "name": "delete",
            "description": f"Delete every {name} of the queryset, following on_delete",
            "usage": f"# Delete the {name} rows that match\n{path}.filter(pk=1).delete()",
            "inputs": None,
            "output": output("tuple[int, dict[str, int]]"),
        },
        {
            "name": "count",
            "description": f"How many {name} rows the queryset has",
            "usage": f"# Count the {name} rows\n{path}.count()",
            "inputs": None,
            "output": output("int"),
        },
        {
            "name": "aggregate",
            "description": f"Values computed over the {name} rows",
            "usage": f'# Aggregate over the {name} rows\n{path}.aggregate(total=Count("pk"))',
            "inputs": None,
            "output": output("dict[str, Any]"),
        },
        {
            "name": "values",
            "description": f"{name} rows as dictionaries of the named fields",
            "usage": f'# Get {name} rows as dictionaries\n{path}.values("pk")',
            "inputs": None,
            "output": output("dict[str, Any]", list_=True),
        },
    ]


def _lookup_type(model: type[models.Model], known: Names, name: str) -> dict[str, Any]:
    fields = []
    for field in model._meta.get_fields():
        related = getattr(field, "related_model", None)
        if field.is_relation and related is not None:
            target = known.of(related)
            if target is None:
                continue
            fields.append(
                {
                    "name": field.name,
                    "types": [
                        {
                            "type": f"{target}Lookups",
                            "isList": False,
                            "location": "inputObjectTypes",
                        },
                        {"type": target, "isList": False, "location": "outputObjectTypes"},
                    ],
                    "nullable": bool(getattr(field, "null", True)),
                }
            )
            continue
        if isinstance(field, ForeignObjectRel):
            continue
        fields.append(
            {
                "name": field.name,
                "types": [{"type": python_type(field), "isList": False, "location": "scalar"}],
                "nullable": bool(field.null),
            }
        )
    return {"name": f"{name}Lookups", "fields": fields}


def _fields_type(model: type[models.Model], known: Names, name: str) -> dict[str, Any]:
    fields = []
    for field in model._meta.concrete_fields:
        related = (
            known.of(field.related_model) if field.is_relation and field.related_model else None
        )
        types = [{"type": python_type(field), "isList": False, "location": "scalar"}]
        if related is not None:
            fields.append(
                {
                    "name": field.name,
                    "types": [{"type": related, "isList": False, "location": "outputObjectTypes"}],
                    "nullable": bool(field.null),
                }
            )
        fields.append({"name": field.attname, "types": types, "nullable": bool(field.null)})
    return {"name": f"{name}Fields", "fields": fields}


def _output_type(model: dict[str, Any]) -> dict[str, Any]:
    fields = []
    for field in model["fields"]:
        if field["kind"] == "object":
            location = "outputObjectTypes"
        elif field["kind"] == "enum":
            location = "enumTypes"
        else:
            location = "scalar"
        fields.append(
            {
                "name": field["name"],
                "types": [{"type": field["type"], "isList": field["isList"], "location": location}],
                "nullable": not field["isRequired"],
            }
        )
    return {"name": model["name"], "fields": fields}


def _directives(model: dict[str, Any]) -> list[dict[str, Any]]:
    out = [{"name": "db_table", "values": [model["dbName"]]}] if model["dbName"] else []
    for attribute in model["attributes"]:
        name, _, value = attribute.partition(" = ")
        if name != "db_table":
            out.append({"name": name, "values": [value]})
    for index in model["indexes"]:
        out.append(
            {"name": "unique" if index["type"] == "unique" else "index", "values": index["fields"]}
        )
    return out


def _field_type(field: dict[str, Any]) -> str:
    suffix = "[]" if field["isList"] else ("" if field["isRequired"] else " | None")
    return f"{field['type']}{suffix}"


def build_docs(input: OnDatabase):
    alias = input.alias
    schema = build_schema(alias)
    known = names()
    models_out = []
    input_types = []
    output_types = []
    for model in schema["models"]:
        cls = known.get(model["name"])
        if cls is None:
            continue
        models_out.append(
            {
                "name": model["name"],
                "documentation": model["documentation"],
                "directives": _directives(model),
                "fields": [
                    {
                        "name": field["name"],
                        "type": _field_type(field),
                        "bareTypeName": field["type"],
                        "kind": field["kind"],
                        "directives": field["attributes"],
                        "documentation": field["documentation"],
                        "required": field["isRequired"],
                    }
                    for field in model["fields"]
                ],
                "operations": _operations(cls, model["name"]),
            }
        )
        input_types.append(_lookup_type(cls, known, model["name"]))
        input_types.append(_fields_type(cls, known, model["name"]))
        output_types.append(_output_type(model))
    return {
        "models": models_out,
        "inputTypes": input_types,
        "outputTypes": output_types,
        "enumTypes": [
            {"name": enum["name"], "values": [value["name"] for value in enum["values"]]}
            for enum in schema["enums"]
        ],
    }
