"""Names for values that are strings or numbers underneath, and are not interchangeable.

A `ModelName` and an `Alias` are both `str` when the code runs. To the type checker they are
different types, so one cannot be passed where the other is meant; a plain `str` becomes one
where it enters — in a model that Pydantic validates, or by calling the name: `Alias("default")`.
"""

from __future__ import annotations

from typing import NewType

# An entry of the project's DATABASES: `default`.
Alias = NewType("Alias", str)
# A model as Studio names it: `Post`, or `blog.Post` when two apps have one.
ModelName = NewType("ModelName", str)
# One SQL statement, as typed.
Sql = NewType("Sql", str)
# A Django ORM query, as typed: Python source.
OrmQuery = NewType("OrmQuery", str)
# A character offset into a query.
Offset = NewType("Offset", int)
