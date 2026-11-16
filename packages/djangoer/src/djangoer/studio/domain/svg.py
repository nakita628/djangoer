"""The ER diagram as an SVG, drawn without a browser.

The look is the one of the diagram in Studio: a card per model with a dark header and a row per
column, a line per relation from the key to the column that refers to it. The layout is a
plain one: models are placed in columns by how far they are from a model that refers to no
other, parents to the left, so most lines run left to right.
"""

from __future__ import annotations

from dataclasses import dataclass
from html import escape
from typing import Any

from .er import column_name, columns

NODE_WIDTH = 340
HEADER_HEIGHT = 36
ROW_HEIGHT = 24
PADDING_BOTTOM = 8
COLUMN_GAP = 140
ROW_GAP = 40
MARGIN = 40
# How far a line travels straight out of a card before it bends.
STUB = 22
MONO = "ui-monospace, SF Mono, Menlo, Consolas, Liberation Mono, DejaVu Sans Mono, monospace"

COLORS = {
    "canvas": "#f7f8fb",
    "dots": "#d4d4dc",
    "card": "#ffffff",
    "border": "#cfd3e0",
    "header": "#1f2233",
    "header_text": "#f4f5fa",
    "table_name": "#9a9fb3",
    "text": "#16181f",
    "type": "#6b7084",
    "key": "#b45309",
    "foreign": "#4f46e5",
    "edge": "#9095ab",
    "enum": "#7c3aed",
}


@dataclass
class Card:
    """A model or an enum on the canvas: where it is, and where each of its rows is."""

    name: str
    title: str
    subtitle: str
    rows: list[tuple[str, str, str]]  # (name, type, marker): marker is PK, FK or nothing
    enum: bool = False
    x: float = 0
    y: float = 0

    @property
    def height(self) -> float:
        return HEADER_HEIGHT + ROW_HEIGHT * len(self.rows) + PADDING_BOTTOM

    def row_y(self, name: str) -> float:
        """The middle of the row of a column; the header's, for a name that is no column."""
        for index, row in enumerate(self.rows):
            if row[0] == name:
                return self.y + HEADER_HEIGHT + ROW_HEIGHT * index + ROW_HEIGHT / 2
        return self.y + HEADER_HEIGHT / 2


def _cards(schema: dict[str, Any]) -> dict[str, Card]:
    cards: dict[str, Card] = {}
    for model in schema["models"]:
        rows = [
            (
                column_name(field),
                field["type"] + ("" if field["isRequired"] else "?"),
                "PK" if field["isId"] else "FK" if field["isForeignKey"] else "",
            )
            for field in columns(model)
        ]
        cards[model["name"]] = Card(model["name"], model["name"], model["dbName"] or "", rows)
    for enum in schema["enums"]:
        rows = [(value["name"], value["dbName"] or "", "") for value in enum["values"]]
        cards[f"enum:{enum['name']}"] = Card(
            f"enum:{enum['name']}", enum["name"], "enum", rows, enum=True
        )
    return cards


def _ranks(schema: dict[str, Any], cards: dict[str, Card]) -> dict[str, int]:
    """The column of each card: one past the furthest of the models it refers to.

    A relation that would close a loop (a model that refers to itself, two that refer to each
    other) is not followed, so every model gets a column.
    """
    parents: dict[str, set[str]] = {name: set() for name in cards}
    for relation in schema["relations"]:
        parent, child = relation["from"]["model"], relation["to"]["model"]
        if parent != child and parent in cards and child in cards:
            parents[child].add(parent)
    ranks: dict[str, int] = {}

    def rank(name: str, seen: frozenset[str]) -> int:
        if name in ranks:
            return ranks[name]
        above = [rank(parent, seen | {name}) for parent in parents[name] if parent not in seen]
        ranks[name] = max(above, default=-1) + 1
        return ranks[name]

    for name, card in cards.items():
        if not card.enum:
            rank(name, frozenset())
    last = max(ranks.values(), default=-1) + 1
    for name, card in cards.items():
        if card.enum:
            ranks[name] = last
    return ranks


def layout(schema: dict[str, Any]) -> dict[str, Card]:
    """Every card with its place: columns left to right, cards of a column top to bottom."""
    cards = _cards(schema)
    ranks = _ranks(schema, cards)
    by_rank: dict[int, list[Card]] = {}
    for name, card in cards.items():
        by_rank.setdefault(ranks[name], []).append(card)
    for index, rank in enumerate(sorted(by_rank)):
        y = float(MARGIN)
        for card in by_rank[rank]:
            card.x = MARGIN + index * (NODE_WIDTH + COLUMN_GAP)
            card.y = y
            y += card.height + ROW_GAP
    return cards


def _text(
    x: float,
    y: float,
    text: str,
    *,
    size: float,
    fill: str,
    anchor: str = "start",
    weight: int = 400,
) -> str:
    return (
        f'<text x="{x:g}" y="{y:g}" font-family="{MONO}" font-size="{size:g}" '
        f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill}">{escape(text)}</text>'
    )


def _card(card: Card, index: int) -> str:
    accent = COLORS["enum"] if card.enum else COLORS["header"]
    clip = f"card-{index}"
    parts = [
        f'<g class="{"enum-node" if card.enum else "model-node"}">',
        (
            f'<clipPath id="{clip}"><rect x="{card.x:g}" y="{card.y:g}" width="{NODE_WIDTH}" '
            f'height="{card.height:g}" rx="8"/></clipPath>'
        ),
        (
            f'<rect x="{card.x:g}" y="{card.y:g}" width="{NODE_WIDTH}" height="{card.height:g}" rx="8" '
            f'fill="{COLORS["card"]}" stroke="{COLORS["border"]}" filter="url(#shadow)"/>'
        ),
        (
            f'<rect x="{card.x:g}" y="{card.y:g}" width="{NODE_WIDTH}" height="{HEADER_HEIGHT}" '
            f'fill="{accent}" clip-path="url(#{clip})"/>'
        ),
        _text(
            card.x + 12, card.y + 23, card.title, size=13, fill=COLORS["header_text"], weight=700
        ),
        _text(
            card.x + NODE_WIDTH - 12,
            card.y + 23,
            card.subtitle,
            size=10.5,
            fill=COLORS["table_name"],
            anchor="end",
        ),
    ]
    for row, (name, kind, marker) in enumerate(card.rows):
        y = card.y + HEADER_HEIGHT + ROW_HEIGHT * row + 16
        if marker:
            fill = COLORS["key"] if marker == "PK" else COLORS["foreign"]
            parts.append(_text(card.x + 12, y, marker, size=9, fill=fill, weight=700))
        parts.append(_text(card.x + 36, y, name, size=12, fill=COLORS["text"]))
        parts.append(
            _text(card.x + NODE_WIDTH - 12, y, kind, size=11, fill=COLORS["type"], anchor="end")
        )
    parts.append("</g>")
    return "".join(parts)


def _line(points: list[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{x:g} {y:g}" for x, y in points)


LANE = 9


class Router:
    """Lines between cards, in right angles, none through a card and no two on one track.

    A line to the next column bends once, in the gap between the two. A line to a card further
    away would cross the columns in between, so it rises to a track above every card, runs
    there, and comes down in the gap before its target. Each vertical run and each track is
    taken by one line: the next one gets the lane beside it.
    """

    def __init__(self, cards: dict[str, Card]):
        self.gaps: dict[float, int] = {}
        self.tracks = 0
        self.top = min((card.y for card in cards.values()), default=MARGIN)

    def _gap(self, x: float) -> float:
        """A free vertical lane in the gap that starts at `x`."""
        lane = self.gaps.get(x, 0)
        self.gaps[x] = lane + 1
        return x + STUB + lane * LANE

    def _track(self) -> float:
        self.tracks += 1
        return self.top - LANE * self.tracks - 4

    def between(self, source: Card, source_y: float, target: Card, target_y: float):
        start = (source.x + NODE_WIDTH, source_y)
        step = NODE_WIDTH + COLUMN_GAP
        distance = round((target.x - source.x) / step)
        if distance == 1:
            middle = self._gap(start[0])
            return [start, (middle, start[1]), (middle, target_y), (target.x, target_y)]
        if distance > 1:
            out = self._gap(start[0])
            # The gap before the target is the one that starts at the column before it.
            back = self._gap(target.x - COLUMN_GAP)
            track = self._track()
            return [
                start,
                (out, start[1]),
                (out, track),
                (back, track),
                (back, target_y),
                (target.x, target_y),
            ]
        # The same column, or one to the left: out to the right, and in from the right as well.
        out = self._gap(max(source.x, target.x) + NODE_WIDTH)
        return [start, (out, start[1]), (out, target_y), (target.x + NODE_WIDTH, target_y)]


def _edges(schema: dict[str, Any], cards: dict[str, Card], router: Router) -> list[str]:
    parts: list[str] = []
    by_name = {model["name"]: model for model in schema["models"]}
    for relation in schema["relations"]:
        parent = cards.get(relation["from"]["model"])
        child = cards.get(relation["to"]["model"])
        if parent is None or child is None:
            continue
        many_to_many = relation["origin"] == "implicit-many-to-many"

        def column(model_name: str, field_name: str) -> str:
            model = by_name[model_name]
            return next(
                (column_name(f) for f in model["fields"] if f["name"] == field_name), field_name
            )

        parent_y = parent.row_y(column(parent.name, relation["from"]["field"]))
        child_y = child.row_y(column(child.name, relation["to"]["field"]))
        points = router.between(parent, parent_y, child, child_y)
        dash = ' stroke-dasharray="5 4"' if many_to_many else ""
        parts.append(
            f'<path class="relation-edge" d="{_line(points)}" fill="none" '
            f'stroke="{COLORS["edge"]}" stroke-width="1.4"{dash}/>'
        )
        # The "many" end, at the column that refers: a crow's foot opening onto the card.
        x, y = points[-1]
        toward = 1 if points[-2][0] > x else -1
        if relation["to"]["cardinality"] in ("zero-many", "many") or many_to_many:
            parts.append(
                f'<path d="M{x + 12 * toward:g} {y:g} L{x:g} {y - 7:g} M{x + 12 * toward:g} {y:g} '
                f'L{x:g} {y + 7:g}" fill="none" stroke="{COLORS["edge"]}" stroke-width="1.4"/>'
            )
    for model in schema["models"]:
        card = cards[model["name"]]
        for field in columns(model):
            enum = cards.get(f"enum:{field['type']}") if field["kind"] == "enum" else None
            if enum is None:
                continue
            points = router.between(
                card, card.row_y(column_name(field)), enum, enum.y + HEADER_HEIGHT / 2
            )
            parts.append(
                f'<path class="enum-edge" d="{_line(points)}" fill="none" '
                f'stroke="{COLORS["enum"]}" stroke-width="1.2" stroke-dasharray="3 4"/>'
            )
    return parts


def render(schema: dict[str, Any]) -> str:
    """The diagram of a schema as one SVG document."""
    cards = layout(schema)
    router = Router(cards)
    edges = _edges(schema, cards, router)
    # The tracks above the cards and the lanes right of the last column are part of the picture.
    top = MARGIN + LANE * router.tracks
    right = max((lanes * LANE for lanes in router.gaps.values()), default=0) + STUB
    width = max((card.x + NODE_WIDTH for card in cards.values()), default=0) + MARGIN + right
    height = max((card.y + card.height for card in cards.values()), default=0) + MARGIN + top
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:g}" height="{height:g}" '
            f'viewBox="0 {-top:g} {width:g} {height:g}">'
        ),
        (
            "<defs>"
            f'<pattern id="dots" width="20" height="20" patternUnits="userSpaceOnUse">'
            f'<circle cx="0.7" cy="0.7" r="0.7" fill="{COLORS["dots"]}"/></pattern>'
            '<filter id="shadow" x="-5%" y="-5%" width="110%" height="115%">'
            '<feDropShadow dx="0" dy="1" stdDeviation="1" flood-color="#000000" flood-opacity="0.08"/>'
            "</filter></defs>"
        ),
        f'<rect y="{-top:g}" width="{width:g}" height="{height:g}" fill="{COLORS["canvas"]}"/>',
        f'<rect y="{-top:g}" width="{width:g}" height="{height:g}" fill="url(#dots)"/>',
        *edges,
        *[_card(card, index) for index, card in enumerate(cards.values())],
        "</svg>",
    ]
    return "\n".join(parts) + "\n"
