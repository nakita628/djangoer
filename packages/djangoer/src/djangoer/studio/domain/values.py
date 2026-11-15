"""Values on their way to the browser and back.

A cell is a string, a number, a boolean or null. Whatever else a row carries is written as the
string a person would type for it: ISO dates, decimal digits, base64 bytes, JSON text.
"""

from __future__ import annotations

import base64
import datetime as dt
import decimal
import json
import uuid
from typing import Any

from django.core.exceptions import ValidationError
from django.db import models

# Past this a JavaScript number no longer holds an integer exactly.
MAX_SAFE_INTEGER = 2**53 - 1


def cell(value: Any) -> str | int | float | bool | None:
    """One value of a row, as a table cell."""
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return value if abs(value) <= MAX_SAFE_INTEGER else str(value)
    if isinstance(value, float):
        return value if value == value and abs(value) != float("inf") else str(value)
    if isinstance(value, decimal.Decimal):
        return str(value)
    if isinstance(value, (dt.datetime, dt.date, dt.time)):
        return value.isoformat()
    if isinstance(value, dt.timedelta):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, default=str, ensure_ascii=False)
    return str(value)


def to_json(value: Any, depth: int = 0) -> Any:
    """Any Python value as JSON, keeping the structure of lists and dicts."""
    if depth > 8:
        return str(value)
    if isinstance(value, dict):
        return {str(key): to_json(item, depth + 1) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [to_json(item, depth + 1) for item in value]
    if isinstance(value, models.Model):
        return instance(value)
    return cell(value)


def instance(obj: models.Model) -> dict[str, Any]:
    """A model instance as the row it was read from, plus what the query annotated it with."""
    row = {
        field.attname: cell(obj.__dict__.get(field.attname))
        for field in obj._meta.concrete_fields
        if field.attname in obj.__dict__
    }
    for key, value in obj.__dict__.items():
        if key.startswith("_") or key in row:
            continue
        row[key] = to_json(value, 1)
    return row


def from_cell(field: models.Field, value: Any) -> Any:
    """What the browser sent for a field, as the Python value the field stores."""
    if value is None:
        return None
    if isinstance(field, models.JSONField):
        if isinstance(value, str):
            try:
                return json.loads(value)
            except json.JSONDecodeError as error:
                raise ValidationError(f"not valid JSON: {error.msg}") from error
        return value
    if isinstance(field, models.BinaryField) and isinstance(value, str):
        try:
            return base64.b64decode(value, validate=True)
        except ValueError as error:
            raise ValidationError("not valid base64") from error
    if value == "" and not isinstance(field, (models.CharField, models.TextField)):
        # An emptied cell of a number or a date means "no value", not the empty string.
        return None
    target = field.target_field if field.is_relation else field
    return target.to_python(value)
