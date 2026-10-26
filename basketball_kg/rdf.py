"""RDF / JSON-LD / SPARQL front end.

Namespaces
----------
``bkr:<prefix>/<local>``
    Individuals: ``zone:paint`` -> ``https://w3id.org/basketball-kg/resource/zone/paint``
``bk:<predicate>``
    Vocabulary: ``hasActionType`` -> ``https://w3id.org/basketball-kg/ontology#hasActionType``
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Union

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, SKOS, XSD

from .model import KnowledgeGraph, Node

__all__ = [
    "BK",
    "BKR",
    "resource_iri",
    "predicate_iri",
    "class_iri",
    "literal",
    "build_rdf",
    "load_ontology",
    "to_jsonld",
    "to_turtle",
    "query_sparql",
]

BK = Namespace("https://w3id.org/basketball-kg/ontology#")
BKR = Namespace("https://w3id.org/basketball-kg/resource/")

ONTOLOGY_PATH = Path(__file__).resolve().parent.parent / "ontology" / "basketball.ttl"
JSONLD_CONTEXT_PATH = Path(__file__).resolve().parent.parent / "ontology" / "basketball.jsonld"

_JSONLD_CONTEXT = None


def resource_iri(node_id: str) -> URIRef:
    """``zone:corner-three-left`` -> ``bkr:zone/corner-three-left``."""
    prefix, _, local = str(node_id).partition(":")
    if not local:
        prefix, local = "resource", prefix
    return BKR[f"{prefix}/{local}"]


def predicate_iri(predicate: str) -> URIRef:
    return BK[predicate]


def class_iri(class_name: str) -> URIRef:
    return BK[class_name]


def literal(value: Any) -> Literal:
    """Best-effort typed literal for a Python value."""
    if isinstance(value, bool):
        return Literal(value, datatype=XSD.boolean)
    if isinstance(value, int):
        return Literal(value, datatype=XSD.integer)
    if isinstance(value, float):
        return Literal(value, datatype=XSD.decimal)
    if isinstance(value, (list, tuple, set)):
        raise TypeError("use add_literals() for multi-valued properties")
    return Literal(str(value))


def _add_literals(g: Graph, subject: URIRef, predicate: URIRef, value: Any) -> None:
    if isinstance(value, (list, tuple, set)):
        for item in value:
            _add_literals(g, subject, predicate, item)
    elif value is not None:
        g.add((subject, predicate, literal(value)))


def build_rdf(kg: KnowledgeGraph, include_ontology: bool = False) -> Graph:
    """Materialise the KG (and optionally the TBox) into an rdflib Graph."""
    g = Graph()
    g.bind("bk", BK)
    g.bind("bkr", BKR)
    g.bind("skos", SKOS)
    if include_ontology:
        onto = load_ontology()
        for triple in onto:
            g.add(triple)
    for node in kg.nodes.values():
        _add_node(g, node)
    return g


def _add_node(g: Graph, node: Node) -> None:
    iri = resource_iri(node.id)
    g.add((iri, RDF.type, class_iri(node.type)))
    if node.label:
        g.add((iri, SKOS.prefLabel, Literal(node.label)))
    if node.definition:
        g.add((iri, SKOS.definition, Literal(node.definition)))
    for key, value in node.props.items():
        _add_literals(g, iri, predicate_iri(key), value)
    for predicate, targets in node.edges.items():
        pred = predicate_iri(predicate)
        for target in targets:
            # links are added even when the target is not (yet) defined, so that
            # validate() can surface dangling references instead of hiding them
            g.add((iri, pred, resource_iri(target)))


def load_ontology(path: Optional[Path] = None) -> Graph:
    """Parse ``ontology/basketball.ttl`` (TBox only)."""
    g = Graph()
    g.parse(str(path or ONTOLOGY_PATH), format="turtle")
    g.bind("bk", BK)
    return g


def jsonld_context() -> Dict[str, Any]:
    """The JSON-LD context (also published as ``ontology/basketball.jsonld``)."""
    global _JSONLD_CONTEXT
    if _JSONLD_CONTEXT is None:
        payload = json.loads(JSONLD_CONTEXT_PATH.read_text(encoding="utf-8"))
        _JSONLD_CONTEXT = payload.get("@context", {})
    return _JSONLD_CONTEXT


def to_jsonld(kg: KnowledgeGraph, indent: int = 2, inline_context: bool = True) -> str:
    """Serialise the knowledge graph as JSON-LD.

    Node identifiers are emitted as CURIEs (``zone:corner-three-left``); the
    context declares one prefix per id namespace plus ``@vocab`` for the
    predicates, so the document is valid JSON-LD *and* readable as-is -- the
    same shape as the source files in ``data/``.
    """
    graph = []
    for node in kg.nodes.values():
        entry: Dict[str, Any] = {"id": node.id, "type": node.type}
        if node.label:
            entry["label"] = node.label
        if node.definition:
            entry["definition"] = node.definition
        for key, value in node.props.items():
            entry[key] = value
        for predicate, targets in sorted(node.edges.items()):
            entry[predicate] = targets[0] if len(targets) == 1 else list(targets)
        graph.append(entry)
    document: Dict[str, Any] = {
        "@context": jsonld_context() if inline_context else str(JSONLD_CONTEXT_PATH.name),
        "@graph": graph,
    }
    return json.dumps(document, indent=indent, ensure_ascii=False)


def to_turtle(g: Graph) -> str:
    raw = g.serialize(format="turtle")
    return raw.decode("utf-8") if isinstance(raw, bytes) else raw


def query_sparql(
    g: Graph, query: str, init_ns: Optional[Dict[str, Any]] = None, shorten: bool = True
) -> List[Dict[str, Any]]:
    """Run a SPARQL SELECT and return a list of dicts with stringified values."""
    namespaces = {"bk": BK, "bkr": BKR, "skos": SKOS}
    if init_ns:
        namespaces.update(init_ns)
    rows: List[Dict[str, Any]] = []
    for row in g.query(query, initNs=namespaces):
        rows.append(
            {
                str(var): (_shorten(_pythonise(value)) if shorten else _pythonise(value))
                for var, value in zip(row.labels, row)
            }
        )
    return rows


_RESOURCE_BASE = str(BKR)
_ONTOLOGY_BASE = str(BK)


def _shorten(value: Any) -> Any:
    """``.../resource/zone/corner-three-left`` -> ``zone:corner-three-left``."""
    if not isinstance(value, str):
        return value
    if value.startswith(_RESOURCE_BASE):
        return value[len(_RESOURCE_BASE):].replace("/", ":", 1)
    if value.startswith(_ONTOLOGY_BASE):
        return "bk:" + value[len(_ONTOLOGY_BASE):].split("/")[-1]
    return value


def _pythonise(term: Any) -> Any:
    if term is None:
        return None
    try:
        value = term.toPython()
    except Exception:  # pragma: no cover
        value = str(term)
    if isinstance(value, URIRef):
        return str(value)
    return value
