"""Core data model and loaders for the Basketball Knowledge Model.

The repository stores knowledge as small, human-editable JSON files (``data/**``).
Every file is a flat list of ``nodes``; each node carries its type, labels,
literal ``props`` and outgoing ``edges`` (a predicate -> one or many node ids).
This module turns those files into a :class:`KnowledgeGraph`, which is the single
source of truth consumed by the NetworkX, RDF/SPARQL, DOT and natural-language
front ends.

Design notes
------------
* **Node ids are CURIEs** (``zone:corner-three-left``), not invented integers, so
  that the JSON, the RDF and the property graph all speak the same identifiers.
* **Reification is explicit.** Anything with its own semantics (an assignment, a
  counter, a decision) is a *node*, never an edge attribute, so the same graph
  survives the trip to RDF where edges cannot hold data.
* **Inverses are derived**, not authored: you write ``stepOf`` and get
  ``hasStep`` for free.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Sequence, Set, Tuple

__all__ = [
    "Node",
    "Dataset",
    "KnowledgeGraph",
    "load_graph",
    "ONTOLOGY_CLASSES",
    "INVERSES",
    "SYMMETRIC",
]

# --------------------------------------------------------------------------- #
# Vocabulary derived from ontology/basketball.ttl
# --------------------------------------------------------------------------- #

ONTOLOGY_CLASSES: Set[str] = {
    "Concept", "Agent", "Player", "Coach", "Team",
    "PositionGroup", "Position", "Role", "Archetype", "Skill",
    "Zone", "ZoneType",
    "Scheme", "OffensiveScheme", "DefensiveScheme", "Coverage", "Formation",
    "Play", "OffensivePlay", "DefensivePlay", "Action", "ActionType",
    "Decision", "Assignment", "Counter", "Outcome", "Situation",
    "Rule", "RuleType", "Penalty",
}

#: predicates whose inverse edge is added automatically
INVERSES: Dict[str, str] = {
    "stepOf": "hasStep",
    "hasStep": "stepOf",
    "governs": "constrainedBy",
    "constrainedBy": "governs",
    "ofScheme": "hasAssignment",
    "hasAssignment": "ofScheme",
}

#: predicates that hold in both directions by definition
SYMMETRIC: Set[str] = {"adjacentTo", "counteredBy"}

#: Search weighting: the concepts a coach means when he says "corner three" or
#: "drop coverage" outrank the bookkeeping nodes that merely mention them
#: (outcomes, counters, zone types, penalties, ...).
TYPE_PRIORITY: Dict[str, float] = {
    "Zone": 1.0, "Position": 1.0, "Role": 1.0, "Archetype": 1.0,
    "Play": 1.0, "OffensivePlay": 1.0, "DefensivePlay": 1.0,
    "Scheme": 1.0, "OffensiveScheme": 1.0, "DefensiveScheme": 1.0,
    "Coverage": 1.0, "Rule": 1.0, "Action": 1.0, "ActionType": 1.0,
    "Player": 1.0, "Coach": 1.0, "Team": 1.0,
    "Outcome": 0.45, "Counter": 0.45, "Assignment": 0.7, "Formation": 0.7,
    "Situation": 0.7, "Skill": 0.7, "Decision": 0.7, "ZoneType": 0.5,
    "RuleType": 0.5, "Penalty": 0.5, "PositionGroup": 0.6,
}

#: top-level JSON keys copied into ``props``
_TOP_LEVEL_LITERALS = ("abbreviation", "aliases", "altLabel")

_CURIE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*:[A-Za-z0-9_][A-Za-z0-9_.-]*$")


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #


@dataclass
class Node:
    """A single entity in the knowledge graph."""

    id: str
    type: str
    label: str = ""
    definition: str = ""
    props: Dict[str, Any] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)
    dataset: str = ""

    # -- convenience ------------------------------------------------------- #
    @property
    def curie_parts(self) -> Tuple[str, str]:
        prefix, _, local = self.id.partition(":")
        return prefix, local

    @property
    def local_name(self) -> str:
        return self.curie_parts[1]

    @property
    def name(self) -> str:
        return self.label or self.local_name

    def get(self, key: str, default: Any = None) -> Any:
        return self.props.get(key, default)

    def keys(self) -> List[str]:
        """Coaching keys / notes attached to the node (``props.key``)."""
        value = self.props.get("key", [])
        if isinstance(value, str):
            return [value]
        return list(value or [])

    def out(self, predicate: str) -> List[str]:
        return list(self.edges.get(predicate, []))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "label": self.label,
            "definition": self.definition,
            "props": dict(self.props),
            "edges": {k: list(v) for k, v in self.edges.items()},
        }

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<Node {self.id} ({self.type}) {self.label!r}>"


@dataclass
class Dataset:
    """One source file."""

    id: str
    path: Path
    label: str = ""
    definition: str = ""
    props: Dict[str, Any] = field(default_factory=dict)


class KnowledgeGraph:
    """An in-memory, id-addressable graph of :class:`Node` objects."""

    def __init__(self) -> None:
        self.nodes: Dict[str, Node] = {}
        self.datasets: List[Dataset] = []

    # -- building ---------------------------------------------------------- #
    def add(self, node: Node) -> None:
        if node.id in self.nodes:
            raise ValueError(f"duplicate node id: {node.id}")
        self.nodes[node.id] = node

    def add_dataset(self, dataset: Dataset) -> None:
        self.datasets.append(dataset)

    def finalize(self) -> "KnowledgeGraph":
        """Add inverse and symmetric edges, then sort every edge list."""
        additions: List[Tuple[str, str, str]] = []
        for node in self.nodes.values():
            for predicate, targets in node.edges.items():
                for target in targets:
                    if predicate in SYMMETRIC:
                        additions.append((target, predicate, node.id))
                    inverse = INVERSES.get(predicate)
                    if inverse:
                        additions.append((target, inverse, node.id))
        for source, predicate, target in additions:
            node = self.nodes.get(source)
            if node is None:
                continue
            bucket = node.edges.setdefault(predicate, [])
            if target not in bucket:
                bucket.append(target)
        for node in self.nodes.values():
            for targets in node.edges.values():
                targets.sort()
        return self

    # -- access ------------------------------------------------------------ #
    def __len__(self) -> int:
        return len(self.nodes)

    def __contains__(self, node_id: str) -> bool:
        return node_id in self.nodes

    def __getitem__(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def get(self, node_id: str) -> Optional[Node]:
        return self.nodes.get(node_id)

    def by_type(self, *types: str) -> List[Node]:
        wanted = set(types)
        return [n for n in self.nodes.values() if n.type in wanted]

    def out(self, node_id: str, predicate: Optional[str] = None) -> List[str]:
        node = self.nodes.get(node_id)
        if node is None:
            return []
        if predicate:
            return node.out(predicate)
        return sorted({t for targets in node.edges.values() for t in targets})

    def in_(self, node_id: str, predicate: Optional[str] = None) -> List[str]:
        hits: Set[str] = set()
        for node in self.nodes.values():
            for pred, targets in node.edges.items():
                if predicate and pred != predicate:
                    continue
                if node_id in targets:
                    hits.add(node.id)
        return sorted(hits)

    # -- search ------------------------------------------------------------ #
    def search(self, text: str, types: Optional[Sequence[str]] = None) -> List[Tuple[Node, float]]:
        """Ranked substring/token search over ids, labels, aliases and definitions.

        Returns a list of ``(node, score)`` sorted by descending score.
        """
        needle = _normalise(text)
        if not needle:
            return []
        tokens = [t for t in needle.split() if len(t) > 2]
        results: List[Tuple[Node, float]] = []
        for node in self.nodes.values():
            if types and node.type not in set(types):
                continue
            label_hay = _normalise(node.label)
            alias_hay = _normalise(" ".join(str(a) for a in _as_list(node.props.get("aliases"))))
            local_hay = _normalise(node.local_name.replace("-", " "))
            id_hay = _normalise(node.id)
            haystacks = [
                (label_hay, 6.0),
                (alias_hay, 3.0),
                (local_hay, 3.0),
                (id_hay, 2.0),
                (_normalise(node.definition), 1.0),
            ]
            score = 0.0
            for hay, weight in haystacks:
                if not hay:
                    continue
                if needle == hay:
                    score += weight * 3
                elif needle and needle in hay:
                    score += weight * (len(needle) / max(len(hay), 1)) * 3
            if tokens:
                # token credit only counts in naming fields: a word that merely
                # appears in a definition is a much weaker signal
                named = [label_hay, alias_hay, local_hay, id_hay]
                matched = sum(1 for t in tokens if any(t in hay for hay in named))
                score += 2.5 * matched / len(tokens)
            if score > 0:
                score *= TYPE_PRIORITY.get(node.type, 0.8)
                results.append((node, round(score, 3)))
        results.sort(key=lambda pair: (-pair[1], pair[0].id))
        return results

    def resolve(self, text: str, types: Optional[Sequence[str]] = None) -> Optional[Node]:
        """Best-effort resolution of free text to a single node."""
        text = (text or "").strip()
        if not text:
            return None
        if text in self.nodes:
            node = self.nodes[text]
            if not types or node.type in set(types):
                return node
        results = self.search(text, types)
        return results[0][0] if results else None

    # -- validation -------------------------------------------------------- #
    def validate(self) -> Dict[str, List[str]]:
        """Return a dict of problems: ``dangling``, ``bad_ids``, ``bad_types``."""
        problems: Dict[str, List[str]] = {"dangling": [], "bad_ids": [], "bad_types": []}
        for node_id, node in self.nodes.items():
            if not _CURIE_RE.match(node_id):
                problems["bad_ids"].append(node_id)
            if node.type not in ONTOLOGY_CLASSES:
                problems["bad_types"].append(f"{node_id}: {node.type}")
            for predicate, targets in node.edges.items():
                if not _CURIE_RE.match(predicate) and not predicate[0].islower():
                    problems.setdefault("bad_predicates", []).append(f"{node.id}: {predicate}")
                for target in targets:
                    if target not in self.nodes:
                        problems["dangling"].append(f"{node.id} -{predicate}-> {target}")
        return problems

    # -- serialisation ----------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "datasets": [
                {"id": d.id, "label": d.label, "definition": d.definition, "path": str(d.path)}
                for d in self.datasets
            ],
            "nodes": [n.to_dict() for n in self.nodes.values()],
        }


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return [value]


def _normalise(text: Any) -> str:
    text = str(text or "").lower()
    text = text.replace("’", "'")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def _node_from_json(raw: Dict[str, Any], dataset_id: str) -> Node:
    if "id" not in raw:
        raise ValueError(f"node without id in {dataset_id}: {raw}")
    props = dict(raw.get("props") or {})
    for key in _TOP_LEVEL_LITERALS:
        if key in raw and key not in props:
            props[key] = raw[key]
    edges: Dict[str, List[str]] = {}
    for predicate, targets in (raw.get("edges") or {}).items():
        edges[predicate] = [str(t) for t in _as_list(targets)]
    return Node(
        id=str(raw["id"]),
        type=str(raw.get("type", "Concept")),
        label=str(raw.get("label", "") or ""),
        definition=str(raw.get("definition", "") or ""),
        props=props,
        edges=edges,
        dataset=dataset_id,
    )


def _load_file(path: Path, kg: KnowledgeGraph) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    dataset_id = str(payload.get("id") or path.stem)
    dataset = Dataset(
        id=dataset_id,
        path=path,
        label=str(payload.get("label", "") or ""),
        definition=str(payload.get("definition", "") or ""),
        props=dict(payload.get("props") or {}),
    )
    raw_nodes = payload.get("nodes")
    if raw_nodes is None:
        raise ValueError(f"{path} has no 'nodes' key")
    if isinstance(raw_nodes, dict):  # allow {"pos:pg": {...}} shorthand
        raw_nodes = [dict(v, id=v.get("id", k)) for k, v in raw_nodes.items()]
    for raw in raw_nodes:
        kg.add(_node_from_json(raw, dataset_id))
    kg.add_dataset(dataset)


def load_graph(data_dir: Optional[Path] = None) -> KnowledgeGraph:
    """Load every ``*.json`` file under ``data/`` into a :class:`KnowledgeGraph`."""
    if data_dir is None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
    data_dir = Path(data_dir)
    kg = KnowledgeGraph()
    for path in sorted(data_dir.rglob("*.json")):
        _load_file(path, kg)
    return kg.finalize()


def default_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "data"


def iter_dataset_files(data_dir: Optional[Path] = None) -> Iterator[Path]:
    data_dir = Path(data_dir or default_data_dir())
    yield from sorted(data_dir.rglob("*.json"))
