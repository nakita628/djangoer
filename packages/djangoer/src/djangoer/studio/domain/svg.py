"""The ER diagram as an SVG, drawn without a browser.

The look is the one of the diagram in Studio: a card per model with a dark header and a row per
column, a line per relation from the key to the column that refers to it. The layout is a
plain one: models are placed in columns by how far they are from a model that refers to no
other, parents to the left, so most lines run left to right.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from html import escape
from typing import Any

from .er import column_name, columns, external, is_key

# The narrowest a card is; it widens to its longest line, up to the widest.
NODE_WIDTH = 340
MAX_NODE_WIDTH = 640
HEADER_HEIGHT = 36
ROW_HEIGHT = 24
PADDING_BOTTOM = 8
COLUMN_GAP = 140
ROW_GAP = 40
MARGIN = 40
# How far a line travels straight out of a card before it bends.
STUB = 22
# An enum with more values than this (time zones, countries) shows the first ones and how many
# are left: the docs list every value, and one card would otherwise set the height of the whole
# picture. `djangoer er --enum-values` changes it.
ENUM_ROWS = 12
# The advance of a character of a monospace font, as a share of its size, and the space kept
# between the two texts of a line.
CHAR_WIDTH = 0.62
TEXT_GAP = 16
# Where the texts of a card start and end: the name after the PK/FK marker, a margin each side.
PAD = 12
NAME_X = 36
TITLE_SIZE = 13
SUBTITLE_SIZE = 10.5
NAME_SIZE = 12
TYPE_SIZE = 11
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
    # Drawn with a dashed border: a model Django does not manage (`managed = False`), or one
    # outside the export, of which only the columns referred to are shown.
    unmanaged: bool = False
    external: bool = False
    x: float = 0
    y: float = 0
    width: float = NODE_WIDTH
    column: int = 0

    @property
    def height(self) -> float:
        return HEADER_HEIGHT + ROW_HEIGHT * len(self.rows) + PADDING_BOTTOM

    def row_y(self, name: str) -> float:
        """The middle of the row of a column; the header's, for a name that is no column."""
        for index, row in enumerate(self.rows):
            if row[0] == name:
                return self.y + HEADER_HEIGHT + ROW_HEIGHT * index + ROW_HEIGHT / 2
        return self.y + HEADER_HEIGHT / 2


def text_width(text: str, size: float) -> float:
    return len(text) * size * CHAR_WIDTH


def _fit(text: str, size: float, room: float) -> str:
    """The text, cut to the room there is with an ellipsis when it is longer."""
    if text_width(text, size) <= room + 0.01:
        return text
    keep = max(int(room / (size * CHAR_WIDTH)) - 1, 0)
    return text[:keep] + "…"


def _needed(card: Card) -> float:
    """How wide a card has to be for its longest line to fit."""
    header = (
        PAD
        + text_width(card.title, TITLE_SIZE)
        + TEXT_GAP
        + text_width(card.subtitle, SUBTITLE_SIZE)
        + PAD
    )
    rows = [
        NAME_X + text_width(name, NAME_SIZE) + TEXT_GAP + text_width(kind, TYPE_SIZE) + PAD
        for name, kind, _marker in card.rows
    ]
    return max([header, *rows])


def _enum_rows(values: list[dict[str, Any]], limit: int | None) -> list[tuple[str, str, str]]:
    """The rows of an enum's card: every value, or as many as `limit` with the last one saying
    how many more there are. None is no limit."""
    rows = [(value["name"], value["dbName"] or "", "") for value in values]
    if limit is None or len(rows) <= limit:
        return rows
    shown = rows[: max(limit - 1, 0)]
    return [*shown, (f"… {len(rows) - len(shown)} more", "", "")]


def _cards(schema: dict[str, Any], enum_rows: int | None) -> dict[str, Card]:
    cards: dict[str, Card] = {}
    for model in schema["models"]:
        rows = [
            (
                column_name(field),
                field["type"] + ("" if field["isRequired"] else "?"),
                "PK" if is_key(model, field) else "FK" if field["isForeignKey"] else "",
            )
            for field in columns(model)
        ]
        cards[model["name"]] = Card(
            model["name"],
            model["name"],
            model["dbName"] or "",
            rows,
            unmanaged=not model["managed"],
            external=external(model),
        )
    for enum in schema["enums"]:
        rows = _enum_rows(enum["values"], enum_rows)
        cards[f"enum:{enum['name']}"] = Card(
            f"enum:{enum['name']}", enum["name"], "enum", rows, enum=True
        )
    return cards


def _ranks(schema: dict[str, Any], cards: dict[str, Card]) -> dict[str, int]:
    """The column of each card: one past the furthest of the models it refers to.

    A relation that would close a loop (a model that refers to itself, two that refer to each
    other) is not followed, so every model gets a column.
    """
    # The parents of a model in the order of the relations, not of a set: where a loop is cut
    # depends on which parent is followed first, and a set's order changes from run to run.
    parents: dict[str, dict[str, None]] = {name: {} for name in cards}
    for relation in schema["relations"]:
        parent, child = relation["from"]["model"], relation["to"]["model"]
        if parent != child and parent in cards and child in cards:
            parents[child][parent] = None
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
    return ranks


def _wrap(cards: list[Card], height: float) -> list[list[Card]]:
    """Cards in columns no taller than `height` (one card at least in each): the enums of a
    diagram, no taller than its tallest column of models, or the models around one model."""
    columns: list[list[Card]] = []
    used = height
    for card in cards:
        if columns and used + card.height <= height:
            columns[-1].append(card)
            used += card.height + ROW_GAP
        else:
            columns.append([card])
            used = card.height + ROW_GAP
    return columns


def layout(
    schema: dict[str, Any], *, enum_rows: int | None = ENUM_ROWS, enums: bool = True
) -> dict[str, Card]:
    """Every card with its place: columns left to right, cards of a column top to bottom.

    The models are in columns by rank, the enums after them, in as many columns as keep them
    no taller than the models. The cards of a column are as wide as the widest of them, so the
    gaps between columns, where the lines run, are straight. Without `enums` there is no enum
    card: the docs list every value.
    """
    cards = _cards(schema, enum_rows)
    if not enums:
        cards = {name: card for name, card in cards.items() if not card.enum}
    ranks = _ranks(schema, cards)
    by_rank: dict[int, list[Card]] = {}
    for name, rank in ranks.items():
        by_rank.setdefault(rank, []).append(cards[name])
    columns = [by_rank[rank] for rank in sorted(by_rank)]

    tallest = max(map(_height, columns), default=0)
    columns += _wrap([card for card in cards.values() if card.enum], tallest)
    _place(columns)
    return cards


def _height(column: list[Card]) -> float:
    return sum(card.height for card in column) + ROW_GAP * (len(column) - 1)


def _place(columns: list[list[Card]]) -> None:
    """Columns left to right, cards of a column top to bottom, a column as wide as its widest
    card, so the gaps between columns, where the lines run, are straight."""
    x = float(MARGIN)
    for index, column in enumerate(columns):
        width = min(max([NODE_WIDTH, *map(_needed, column)]), MAX_NODE_WIDTH)
        y = float(MARGIN)
        for card in column:
            card.x, card.y, card.width, card.column = x, y, width, index
            y += card.height + ROW_GAP
        x += width + COLUMN_GAP


# A model's own diagram: the models around it in columns no taller than this many times its own
# card (and no lower than the floor), and no more than this many cards on a side, the others
# named on one card.
AROUND_HEIGHT = 3
AROUND_FLOOR = 900
AROUND_CARDS = 30


def _sides(schema: dict[str, Any], center: str, cards: dict[str, Card]) -> tuple[list, list]:
    """The models one model refers to (on its left, as parents are) and the ones that refer to
    it (on its right), in the order of the relations, each once."""
    left: list[str] = []
    right: list[str] = []
    for relation in schema["relations"]:
        parent, child = relation["from"]["model"], relation["to"]["model"]
        if parent == child or center not in (parent, child):
            continue
        other, side = (parent, left) if child == center else (child, right)
        if other in cards and other not in left and other not in right:
            side.append(other)
    return left, right


def _capped(names: list[str], cards: dict[str, Card], tables: dict[str, str]) -> list[Card]:
    """The cards of one side, the ones past `AROUND_CARDS` named on a card of their own."""
    if len(names) <= AROUND_CARDS:
        return [cards[name] for name in names]
    shown, hidden = names[: AROUND_CARDS - 1], names[AROUND_CARDS - 1 :]
    rows = [(name, tables.get(name, ""), "") for name in hidden]
    if len(rows) > ENUM_ROWS:
        rows = [*rows[: ENUM_ROWS - 1], (f"… {len(rows) - ENUM_ROWS + 1} more", "", "")]
    more = Card(f"more:{hidden[0]}", f"… {len(hidden)} more", "", rows, external=True)
    return [*(cards[name] for name in shown), more]


def layout_around(
    schema: dict[str, Any],
    center: str,
    *,
    enum_rows: int | None = ENUM_ROWS,
    enums: bool = True,
) -> dict[str, Card]:
    """The diagram of one model (`er.neighborhood`): the model in the middle, the models it
    refers to on its left and the ones that refer to it on its right, each side in columns no
    taller than a few times the model's card, and the enums after them. A model many refer to
    (a generic relation's target, a hub) is a few wide columns, not one tens of thousands of
    pixels tall."""
    cards = _cards(schema, enum_rows)
    if not enums:
        cards = {name: card for name, card in cards.items() if not card.enum}
    middle = cards[center]
    tables = {model["name"]: model["dbName"] or "" for model in schema["models"]}
    left, right = _sides(schema, center, cards)
    limit = max(middle.height * AROUND_HEIGHT, AROUND_FLOOR)
    columns = [
        # The column nearest the model first: reversed, it is the last on the left.
        *reversed(_wrap(_capped(left, cards, tables), limit)),
        [middle],
        *_wrap(_capped(right, cards, tables), limit),
    ]
    tallest = max(map(_height, columns), default=0)
    columns += _wrap([card for card in cards.values() if card.enum], tallest)
    _place(columns)
    return {card.name: card for column in columns for card in column}


def _text(
    x: float,
    y: float,
    text: str,
    *,
    size: float,
    fill: str,
    anchor: str = "start",
    weight: int = 400,
    room: float | None = None,
) -> str:
    """A line of text; cut to `room` when it is longer, with the whole of it as its tooltip."""
    shown = text if room is None else _fit(text, size, room)
    title = f"<title>{escape(text)}</title>" if shown != text else ""
    return (
        f'<text x="{x:g}" y="{y:g}" font-family="{MONO}" font-size="{size:g}" '
        f'font-weight="{weight}" text-anchor="{anchor}" fill="{fill}">{title}{escape(shown)}</text>'
    )


def _two(left: str, left_size: float, right: str, right_size: float, room: float):
    """The room each of two texts on one line gets, None for a text that fits as it is. The
    right one (a type, a table name) stays whole as long as the left one keeps half the line."""
    gap = TEXT_GAP if right else 0
    left_width, right_width = text_width(left, left_size), text_width(right, right_size)
    if left_width + gap + right_width <= room:
        return None, None
    right_room = min(right_width, max(room / 2, room - left_width - gap))
    return room - right_room - gap, right_room


def _card(card: Card, index: int) -> str:
    accent = COLORS["enum"] if card.enum else COLORS["header"]
    clip = f"card-{index}"
    width = card.width
    title_room, subtitle_room = _two(
        card.title, TITLE_SIZE, card.subtitle, SUBTITLE_SIZE, width - 2 * PAD
    )
    parts = [
        f'<g class="{"enum-node" if card.enum else "model-node"}">',
        (
            f'<clipPath id="{clip}"><rect x="{card.x:g}" y="{card.y:g}" width="{width:g}" '
            f'height="{card.height:g}" rx="8"/></clipPath>'
        ),
        (
            f'<rect x="{card.x:g}" y="{card.y:g}" width="{width:g}" height="{card.height:g}" rx="8" '
            f'fill="{COLORS["card"]}" stroke="{COLORS["border"]}" filter="url(#shadow)"/>'
        ),
        (
            f'<rect x="{card.x:g}" y="{card.y:g}" width="{width:g}" height="{HEADER_HEIGHT}" '
            f'fill="{accent}" clip-path="url(#{clip})"/>'
        ),
        _text(
            card.x + PAD,
            card.y + 23,
            card.title,
            size=TITLE_SIZE,
            fill=COLORS["header_text"],
            weight=700,
            room=title_room,
        ),
        _text(
            card.x + width - PAD,
            card.y + 23,
            card.subtitle,
            size=SUBTITLE_SIZE,
            fill=COLORS["table_name"],
            anchor="end",
            room=subtitle_room,
        ),
    ]
    for row, (name, kind, marker) in enumerate(card.rows):
        y = card.y + HEADER_HEIGHT + ROW_HEIGHT * row + 16
        if marker:
            fill = COLORS["key"] if marker == "PK" else COLORS["foreign"]
            parts.append(_text(card.x + 12, y, marker, size=9, fill=fill, weight=700))
        name_room, kind_room = _two(name, NAME_SIZE, kind, TYPE_SIZE, width - NAME_X - PAD)
        parts.append(
            _text(card.x + NAME_X, y, name, size=NAME_SIZE, fill=COLORS["text"], room=name_room)
        )
        parts.append(
            _text(
                card.x + width - PAD,
                y,
                kind,
                size=TYPE_SIZE,
                fill=COLORS["type"],
                anchor="end",
                room=kind_room,
            )
        )
    if card.unmanaged or card.external:
        # On top of the header too: the whole card says Django does not make this table.
        parts.append(
            f'<rect class="{"external" if card.external else "unmanaged"}" x="{card.x:g}" y="{card.y:g}" width="{width:g}" '
            f'height="{card.height:g}" rx="8" fill="none" stroke="{COLORS["edge"]}" '
            'stroke-width="1.5" stroke-dasharray="6 4"/>'
        )
    parts.append("</g>")
    return "".join(parts)


def _line(points: list[tuple[float, float]]) -> str:
    return "M" + " L".join(f"{x:g} {y:g}" for x, y in points)


LANE = 9


class Lanes:
    """Parallel lanes, each a run of segments that do not meet: a segment takes the first lane
    where it is clear of every other by a lane's width, and a new lane only when none is. Two
    lines whose spans do not overlap share a lane, so a large diagram has as many lanes as
    lines that run side by side, not as many as lines."""

    def __init__(self) -> None:
        self.taken: list[list[tuple[float, float]]] = []

    def take(self, low: float, high: float) -> int:
        for index, spans in enumerate(self.taken):
            if all(high + LANE <= start or low - LANE >= end for start, end in spans):
                spans.append((low, high))
                return index
        self.taken.append([(low, high)])
        return len(self.taken) - 1

    def __len__(self) -> int:
        return len(self.taken)


class Router:
    """Lines between cards, in right angles, none through a card and none on another.

    A line to the next column bends once, in the gap between the two. A line to a card further
    away would cross the columns in between, so it rises to a track above every card, runs
    there, and comes down in the gap before its target. The vertical runs of a gap and the
    tracks are lanes (`Lanes`): a line takes the first one where it meets no other.
    """

    def __init__(self, cards: dict[str, Card]):
        self.gaps: dict[float, Lanes] = {}
        self.tracks = Lanes()
        self.top = min((card.y for card in cards.values()), default=MARGIN)

    def _gap(self, x: float, low: float, high: float) -> float:
        """A lane in the gap that starts at `x`, clear from `low` to `high`."""
        lane = self.gaps.setdefault(x, Lanes()).take(low, high)
        return x + STUB + lane * LANE

    def _track(self, low: float, high: float) -> float:
        """A track above the cards, clear from `low` to `high`."""
        return self.top - LANE * (self.tracks.take(low, high) + 1) - 4

    def between(self, source: Card, source_y: float, target: Card, target_y: float):
        start = (source.x + source.width, source_y)
        distance = target.column - source.column
        low, high = min(source_y, target_y), max(source_y, target_y)
        if distance == 1:
            middle = self._gap(start[0], low, high)
            return [start, (middle, start[1]), (middle, target_y), (target.x, target_y)]
        if distance > 1:
            # Up to a track above every card: the runs reach from the top down to the rows.
            out = self._gap(start[0], -math.inf, source_y)
            # The gap before the target is the one that starts at the column before it.
            back = self._gap(target.x - COLUMN_GAP, -math.inf, target_y)
            track = self._track(min(out, back), max(out, back))
            return [
                start,
                (out, start[1]),
                (out, track),
                (back, track),
                (back, target_y),
                (target.x, target_y),
            ]
        # The same column, or one to the left: out to the right, and in from the right as well.
        right = max(source.x + source.width, target.x + target.width)
        out = self._gap(right, low, high)
        return [start, (out, start[1]), (out, target_y), (target.x + target.width, target_y)]


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
        # Dashed: no foreign key backs it. A generic relation in shorter dashes than a
        # many-to-many, which a table of its own does back.
        dashes = {"implicit-many-to-many": "5 4", "generic": "2 3"}.get(relation["origin"])
        dash = f' stroke-dasharray="{dashes}"' if dashes else ""
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
        card = cards.get(model["name"])
        if card is None:
            # A model named on the "… more" card of a model's own diagram has no card to draw from.
            continue
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


def render(
    schema: dict[str, Any],
    *,
    enum_rows: int | None = ENUM_ROWS,
    enums: bool = True,
    center: str | None = None,
) -> str:
    """The diagram of a schema as one SVG document; with `center`, the diagram of that model
    (`layout_around`)."""
    if center is None:
        cards = layout(schema, enum_rows=enum_rows, enums=enums)
    else:
        cards = layout_around(schema, center, enum_rows=enum_rows, enums=enums)
    router = Router(cards)
    edges = _edges(schema, cards, router)
    # The tracks above the cards and the lanes right of the last column are part of the picture.
    top = MARGIN + LANE * len(router.tracks)
    right = max((len(lanes) * LANE for lanes in router.gaps.values()), default=0) + STUB
    width = max((card.x + card.width for card in cards.values()), default=0) + MARGIN + right
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
