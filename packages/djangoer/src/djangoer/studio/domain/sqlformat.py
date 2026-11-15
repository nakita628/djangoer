"""SQL laid out one clause per line, the way the playground shows what the ORM sent."""

from __future__ import annotations

import sqlparse


def format_sql(sql: str) -> str:
    """Reindented with sqlparse, which Django itself depends on."""
    try:
        return sqlparse.format(sql, reindent=True, keyword_case="upper").strip()
    except Exception:  # noqa: BLE001 - an odd statement is shown as it was sent
        return sql
