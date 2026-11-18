"""A schema written out as files: an ER diagram in the format a file's name asks for, and the
docs as a directory."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

from returns.result import Failure, Result, Success

from ..errors import ExportError
from ..inputs import ExportFile
from . import er, markdown, svg
from .schema import build_schema, names

# The directory of the docs that holds a diagram per model.
TABLES = "tables"
# What `djangoer er -o` writes, by the extension of the file it is given.
FORMATS = (".md", ".dbml", ".svg", ".png")


def schema_for(alias: str, root: Path, *, everything: bool) -> dict[str, Any]:
    return er.scoped(build_schema(alias, root), everything=everything)


def png(document: str) -> Result[bytes, ExportError]:
    """An SVG document as a PNG. The rasteriser is an optional dependency: `djangoer[png]`."""
    try:
        resvg = importlib.import_module("resvg_py")
    except ImportError:
        return Failure(
            ExportError(
                'A PNG needs the resvg-py package: pip install "djangoer[png]" '
                "(the SVG can be written without it)."
            )
        )
    return Success(bytes(resvg.svg_to_bytes(svg_string=document)))


def render_er(
    schema: dict[str, Any],
    suffix: str,
    *,
    enum_rows: int | None = svg.ENUM_ROWS,
    enums: bool = True,
) -> Result[bytes, ExportError]:
    """The ER diagram of a schema in the format of a file extension. In the SVG and the PNG,
    `enum_rows` is how many values an enum's card shows (None for all of them), and without
    `enums` there is no enum card."""
    match suffix.lower():
        case ".md":
            text = f"```mermaid\n{er.mermaid(schema)}```\n"
            return Success(text.encode())
        case ".dbml":
            return Success(er.dbml(schema).encode())
        case ".svg":
            return Success(svg.render(schema, enum_rows=enum_rows, enums=enums).encode())
        case ".png":
            return png(svg.render(schema, enum_rows=enum_rows, enums=enums))
        case other:
            wanted = ", ".join(FORMATS)
            return Failure(
                ExportError(f'No ER format for "{other}": the file ends in one of {wanted}.')
            )


def render_docs(
    alias: str,
    schema: dict[str, Any],
    *,
    enum_rows: int | None = svg.ENUM_ROWS,
    enums: bool = True,
) -> dict[str, bytes]:
    """The docs of a schema as the files of a directory: README.md, the diagram it opens with
    (er.svg), and one diagram per model with a relation (tables/<Model>.svg: the model and the
    models it joins), shown in the model's section."""
    sql = markdown.create_sql(schema, names(), alias)
    tables = {name: f"{TABLES}/{name}.svg" for name in er.related(schema)}
    files = {
        "README.md": markdown.render(schema, sql=sql, diagram="er.svg", tables=tables).encode(),
        "er.svg": svg.render(schema, enum_rows=enum_rows, enums=enums).encode(),
    }
    for name, path in tables.items():
        part = er.neighborhood(schema, name)
        files[path] = svg.render(part, enum_rows=enum_rows, enums=enums).encode()
    return files


# What Studio hands the browser to save, by name, with the type the browser is told it is.
DOWNLOADS = {
    "er.md": "text/markdown; charset=utf-8",
    "schema.dbml": "text/plain; charset=utf-8",
    "er.svg": "image/svg+xml",
    "er.png": "image/png",
    "docs.md": "text/markdown; charset=utf-8",
}


def download(input: ExportFile) -> Result[dict[str, Any], ExportError]:
    """One of `DOWNLOADS`, for the project's own models: its content and its media type.

    `docs.md` is the docs as a single file, so its diagram is the Mermaid block inside it.
    """
    media_type = DOWNLOADS.get(input.name)
    if media_type is None:
        wanted = ", ".join(DOWNLOADS)
        return Failure(ExportError(f'No export named "{input.name}": there is {wanted}.'))
    schema = schema_for(input.alias, input.root, everything=False)
    if input.name == "docs.md":
        sql = markdown.create_sql(schema, names(), input.alias)
        content = markdown.render(schema, sql=sql, diagram=None).encode()
        return Success({"name": input.name, "media_type": media_type, "content": content})
    return render_er(schema, Path(input.name).suffix).map(
        lambda content: {"name": input.name, "media_type": media_type, "content": content}
    )
