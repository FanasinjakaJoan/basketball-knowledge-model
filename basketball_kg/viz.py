"""Visualisation: Graphviz DOT export and an ASCII half-court renderer."""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Set

from .model import KnowledgeGraph, Node

__all__ = ["to_dot", "ascii_court", "ZONE_CODES", "TYPE_STYLE"]

# --------------------------------------------------------------------------- #
# DOT
# --------------------------------------------------------------------------- #

TYPE_STYLE: Dict[str, Dict[str, str]] = {
    "Play": {"shape": "box3d", "fillcolor": "#1f3b73", "fontcolor": "white"},
    "OffensivePlay": {"shape": "box3d", "fillcolor": "#1f3b73", "fontcolor": "white"},
    "DefensivePlay": {"shape": "box3d", "fillcolor": "#6b1f1f", "fontcolor": "white"},
    "Action": {"shape": "box", "fillcolor": "#dbe7ff", "fontcolor": "#10233f"},
    "ActionType": {"shape": "octagon", "fillcolor": "#f0f4ff", "fontcolor": "#10233f"},
    "Decision": {"shape": "diamond", "fillcolor": "#ffe9b0", "fontcolor": "#4a3200"},
    "Assignment": {"shape": "hexagon", "fillcolor": "#ffe0e0", "fontcolor": "#4a0000"},
    "Zone": {"shape": "ellipse", "fillcolor": "#e3f7e8", "fontcolor": "#0d3b1c"},
    "ZoneType": {"shape": "ellipse", "fillcolor": "#f2f2f2", "fontcolor": "#333333"},
    "Scheme": {"shape": "folder", "fillcolor": "#cfe3ff", "fontcolor": "#10233f"},
    "OffensiveScheme": {"shape": "folder", "fillcolor": "#cfe3ff", "fontcolor": "#10233f"},
    "DefensiveScheme": {"shape": "folder", "fillcolor": "#ffd9d9", "fontcolor": "#4a0000"},
    "Coverage": {"shape": "tab", "fillcolor": "#ffd6a5", "fontcolor": "#4a3200"},
    "Formation": {"shape": "note", "fillcolor": "#f5f0ff", "fontcolor": "#2c1a4a"},
    "Counter": {"shape": "cds", "fillcolor": "#ffe9f0", "fontcolor": "#4a0022"},
    "Outcome": {"shape": "circle", "fillcolor": "#eaffea", "fontcolor": "#0d3b1c"},
    "Situation": {"shape": "parallelogram", "fillcolor": "#f0f0ff", "fontcolor": "#22224a"},
    "Rule": {"shape": "note", "fillcolor": "#fff6d5", "fontcolor": "#4a3c00"},
    "RuleType": {"shape": "note", "fillcolor": "#f7f7f7", "fontcolor": "#333333"},
    "Penalty": {"shape": "note", "fillcolor": "#f7f7f7", "fontcolor": "#333333"},
    "Position": {"shape": "house", "fillcolor": "#d6f5ff", "fontcolor": "#00303a"},
    "PositionGroup": {"shape": "house", "fillcolor": "#eafaff", "fontcolor": "#00303a"},
    "Role": {"shape": "component", "fillcolor": "#d6ffef", "fontcolor": "#003a2c"},
    "Archetype": {"shape": "component", "fillcolor": "#ccffdd", "fontcolor": "#003a2c"},
    "Skill": {"shape": "circle", "fillcolor": "#ffffff", "fontcolor": "#333333"},
    "Player": {"shape": "box", "fillcolor": "#e8e8ff", "fontcolor": "#1a1a4a"},
    "Coach": {"shape": "box", "fillcolor": "#e8e8ff", "fontcolor": "#1a1a4a"},
    "Team": {"shape": "doubleoctagon", "fillcolor": "#eeeeee", "fontcolor": "#222222"},
}

CLUSTERS: Sequence[tuple] = (
    ("cluster_play", "Play graph", {"Play", "OffensivePlay", "DefensivePlay", "Action", "Decision", "ActionType"}),
    ("cluster_space", "Court", {"Zone", "ZoneType"}),
    ("cluster_tactics", "Tactics", {"Scheme", "OffensiveScheme", "DefensiveScheme", "Coverage", "Formation", "Counter", "Outcome", "Situation", "Assignment"}),
    ("cluster_people", "People & positions", {"Player", "Coach", "Team", "Position", "PositionGroup", "Role", "Archetype", "Skill"}),
    ("cluster_rules", "Rules", {"Rule", "RuleType", "Penalty"}),
)

DEFAULT_STYLE = {"shape": "box", "fillcolor": "#ffffff", "fontcolor": "#222222"}


def _esc(text: str) -> str:
    return str(text).replace("\\", "\\\\").replace('"', "\\'")


def _wrap(text: str, width: int = 32) -> str:
    words, lines, current = str(text).split(), [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if len(candidate) > width and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return "\\n".join(lines)


def to_dot(
    kg: KnowledgeGraph,
    node_ids: Optional[Iterable[str]] = None,
    predicates: Optional[Iterable[str]] = None,
    show_definitions: bool = False,
    rankdir: str = "LR",
    title: str = "Basketball Knowledge Model",
) -> str:
    """Render the graph (or a subset of it) as Graphviz DOT.

    Parameters
    ----------
    node_ids:
        Restrict the output to these nodes (missing neighbours are skipped).
    predicates:
        Restrict which edge predicates are drawn.
    show_definitions:
        Wrap each node's definition into the label.
    """
    keep: Optional[Set[str]] = set(node_ids) if node_ids is not None else None
    preds: Optional[Set[str]] = set(predicates) if predicates is not None else None
    selected: List[Node] = [n for n in kg.nodes.values() if keep is None or n.id in keep]

    lines: List[str] = [
        f'digraph "basketball_knowledge_model" {{',
        f'  label="{_esc(title)}";',
        "  labelloc=t;",
        "  fontsize=18;",
        f"  rankdir={rankdir};",
        "  bgcolor=white;",
        '  node [style="filled,rounded", fontname="Helvetica", fontsize=10, penwidth=1.1];',
        '  edge [fontname="Helvetica", fontsize=9, color="#666666", arrowsize=0.7];',
        "",
    ]

    bucket: Dict[str, List[Node]] = {name: [] for name, _, _ in CLUSTERS}
    bucket["cluster_other"] = []
    for node in selected:
        for name, _, types in CLUSTERS:
            if node.type in types:
                bucket[name].append(node)
                break
        else:
            bucket["cluster_other"].append(node)

    for name, caption, _ in CLUSTERS:
        members = bucket.get(name, [])
        if not members:
            continue
        lines.append(f"  subgraph {name} {{")
        lines.append(f'    label="{_esc(caption)}";')
        lines.append('    style="filled,rounded";')
        lines.append('    color="#dddddd";')
        lines.append('    fillcolor="#fbfbfe";')
        lines.append('    fontname="Helvetica";')
        lines.append("    fontsize=12;")
        for node in sorted(members, key=lambda n: n.id):
            lines.append(f"    {_dot_node(node, show_definitions)}")
        lines.append("  }")
        lines.append("")
    if bucket["cluster_other"]:
        lines.append("  subgraph cluster_other {")
        lines.append('    label="Other";')
        for node in sorted(bucket["cluster_other"], key=lambda n: n.id):
            lines.append(f"    {_dot_node(node, show_definitions)}")
        lines.append("  }")
        lines.append("")

    kept_ids = {n.id for n in selected}
    for node in selected:
        for predicate, targets in sorted(node.edges.items()):
            if preds is not None and predicate not in preds:
                continue
            for target in targets:
                if target not in kept_ids:
                    continue
                style = 'style="dashed"' if predicate in {"precedes", "selectedOption", "relatedTo"} else ""
                lines.append(f'  "{_esc(node.id)}" -> "{_esc(target)}" [label="{_esc(predicate)}" {style}];')
    lines.append("}")
    return "\n".join(lines)


def _dot_node(node: Node, show_definitions: bool) -> str:
    style = TYPE_STYLE.get(node.type, DEFAULT_STYLE)
    label = node.label or node.local_name
    if node.props.get("abbreviation"):
        label = f"{label} ({node.props['abbreviation']})"
    if show_definitions and node.definition:
        label = f"{label}\\n{_wrap(node.definition)}"
    attrs = ", ".join(
        [
            f'shape={style["shape"]}',
            f'fillcolor="{style["fillcolor"]}"',
            f'fontcolor="{style["fontcolor"]}"',
            f'label="{_esc(label)}"',
            f'tooltip="{_esc(node.id)}"',
        ]
    )
    return f'"{_esc(node.id)}" [{attrs}];'


# --------------------------------------------------------------------------- #
# ASCII court
# --------------------------------------------------------------------------- #

ZONE_CODES: Dict[str, str] = {
    "zone:backcourt": "BC",
    "zone:top-of-key-three": "T3",
    "zone:wing-three-left": "W3<",
    "zone:wing-three-right": "W3>",
    "zone:corner-three-left": "C3<",
    "zone:corner-three-right": "C3>",
    "zone:high-post": "HP",
    "zone:elbow-left": "EL<",
    "zone:elbow-right": "EL>",
    "zone:midrange-left-wing": "MW<",
    "zone:midrange-right-wing": "MW>",
    "zone:short-corner-left": "SC<",
    "zone:short-corner-right": "SC>",
    "zone:low-post-left": "LP<",
    "zone:low-post-right": "LP>",
    "zone:paint": "PNT",
    "zone:restricted-area": "RA",
}

_COLS = 21
_ROWS = 15
_CELL_W = 4
_Y_MAX = 32.0
_X_MAX = 50.0


_WIDTH = _COLS * _CELL_W  # 84 characters


def _xpos(x: float) -> int:
    return int(round(min(max(x, 0.0), _X_MAX) / _X_MAX * (_WIDTH - 1)))


def _yrow(y: float) -> int:
    return (_ROWS - 1) - int(round(min(max(y, 0.0), _Y_MAX) / _Y_MAX * (_ROWS - 1)))


def ascii_court(
    kg: KnowledgeGraph,
    highlight: Optional[Iterable[str]] = None,
    title: Optional[str] = None,
    lang: str = "en",
) -> str:
    """Render the half-court zone model as text.

    ``highlight`` takes zone ids (``zone:corner-three-left``) or labels; those
    cells are drawn in ``[brackets]`` so you can see, at a glance, which parts of
    the floor a scheme occupies, concedes or attacks. ``title`` overrides the
    localised heading (``lang``).
    """
    if title is None:
        from .i18n import Translator  # local import: viz stays dependency-light

        title = Translator(lang)("court.title")
    grid = [[" "] * _WIDTH for _ in range(_ROWS)]

    def put(row: int, pos: int, char: str) -> None:
        if 0 <= row < _ROWS and 0 <= pos < _WIDTH:
            grid[row][pos] = char

    def hline(y: float, x0: float, x1: float, char: str) -> None:
        row = _yrow(y)
        for pos in range(_xpos(x0), _xpos(x1) + 1):
            put(row, pos, char)

    def vline(x: float, y0: float, y1: float, char: str) -> None:
        pos = _xpos(x)
        for row in range(_yrow(y1), _yrow(y0) + 1):
            put(row, pos, char)

    # ---- court furniture -------------------------------------------------
    hline(_Y_MAX, 0, 50, "-")          # far boundary (towards half court)
    hline(0, 0, 50, "_")               # baseline
    vline(0, 0, _Y_MAX, "|")           # sidelines
    vline(50, 0, _Y_MAX, "|")
    vline(17, 0, 19, "|")              # lane
    vline(33, 0, 19, "|")
    hline(19, 17, 33, "-")             # free-throw line
    vline(3, 0, 14, ":")               # corner three lines
    vline(47, 0, 14, ":")

    rim_x, rim_y = 25.0, 5.25
    # three-point arc (23.75 ft) drawn as dots
    for step in range(0, 400):
        y = rim_y + step * 0.06
        dx = 23.75 ** 2 - (y - rim_y) ** 2
        if dx <= 0:
            continue
        offset = math.sqrt(dx)
        for x in (rim_x - offset, rim_x + offset):
            if 3.0 <= x <= 47.0:
                put(_yrow(y), _xpos(x), ".")
    # restricted-area arc (4 ft)
    for step in range(0, 200):
        y = rim_y + step * 0.05
        dx = 4.0 ** 2 - (y - rim_y) ** 2
        if dx <= 0:
            continue
        offset = math.sqrt(dx)
        for x in (rim_x - offset, rim_x + offset):
            put(_yrow(y), _xpos(x), ":")

    # ---- zone labels -----------------------------------------------------
    highlighted: Set[str] = set()
    for item in highlight or []:
        node = kg.get(item) or kg.resolve(str(item), types=["Zone"])
        if node is not None:
            highlighted.add(node.id)

    taken: Set[Tuple[int, int]] = set()
    ordered = sorted(
        (z for z in ZONE_CODES if z in kg.nodes),
        key=lambda z: (float(kg[z].props.get("courtY", 0)), float(kg[z].props.get("courtX", 0))),
    )
    for zone_id in ordered:
        node = kg[zone_id]
        row = _yrow(float(node.props.get("courtY", 15)))
        start = _xpos(float(node.props.get("courtX", 25))) - 1
        code = ZONE_CODES[zone_id]
        text = f"[{code}]" if zone_id in highlighted else f" {code} "
        # nudge right (then down) if the spot is already used
        for _ in range(12):
            span = {(row, (start + i) % _WIDTH) for i in range(len(text))}
            if not span & taken:
                break
            start += 4
            if start + len(text) >= _WIDTH:
                start = 1
                row = (row + 1) % _ROWS
        for i, char in enumerate(text):
            put(row, start + i, char)
            taken.add((row, start + i))

    body = ["".join(row).rstrip() for row in grid]
    width_used = max(len(line) for line in body)
    out = [title, "=" * width_used, *body, "=" * width_used]
    if highlighted:
        names = ", ".join(sorted(kg[z].label for z in highlighted if z in kg.nodes))
        out.append(f"highlighted: {names}")
    out.append("legend: RA rim | PNT paint | LP post | SC short corner | EL elbow | HP high post")
    out.append("        MW mid-range wing | C3 corner three | W3 wing three | T3 top of key | BC backcourt")
    return "\n".join(out)
