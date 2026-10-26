"""NetworkX projection of the knowledge graph (labelled property graph view)."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

import networkx as nx

from .model import KnowledgeGraph, Node, _as_list

__all__ = ["to_networkx", "subgraph_around", "graph_stats", "to_node_link"]


def to_networkx(kg: KnowledgeGraph) -> nx.MultiDiGraph:
    """Project the KG onto a ``MultiDiGraph``.

    Node attributes: ``id, type, label, definition`` plus every literal in
    ``props`` (lists are joined with ``" | "`` so the graph stays JSON-friendly).
    Edge attribute: ``predicate``; parallel edges keep their distinct predicates.
    """
    g = nx.MultiDiGraph()
    g.graph["name"] = "basketball-knowledge-model"
    for node_id, node in kg.nodes.items():
        g.add_node(node_id, **_node_attrs(node))
    for node_id, node in kg.nodes.items():
        for predicate, targets in node.edges.items():
            for target in targets:
                if target in kg.nodes:
                    g.add_edge(node_id, target, predicate=predicate)
                else:  # pragma: no cover - validate() normally catches this
                    g.add_edge(node_id, target, predicate=predicate, dangling=True)
    return g


def _node_attrs(node: Node) -> Dict[str, Any]:
    attrs: Dict[str, Any] = {
        "id": node.id,
        "type": node.type,
        "label": node.label or node.local_name,
        "definition": node.definition,
    }
    for key, value in node.props.items():
        if isinstance(value, (list, tuple, set)):
            attrs[key] = " | ".join(str(v) for v in value)
        elif value is None:
            attrs[key] = ""
        else:
            attrs[key] = value
    return attrs


def subgraph_around(
    g: nx.MultiDiGraph, seeds: Iterable[str], depth: int = 1, predicate: Optional[str] = None
) -> nx.MultiDiGraph:
    """Ego subgraph within ``depth`` hops of ``seeds`` (optionally edge-filtered)."""
    if predicate:
        view = nx.MultiDiGraph()
        view.add_nodes_from(g.nodes(data=True))
        for u, v, data in g.edges(data=True):
            if data.get("predicate") == predicate:
                view.add_edge(u, v, **data)
        source: nx.Graph = view
    else:
        source = g
    collected: Set[str] = set()
    frontier: Set[str] = {s for s in seeds if s in source}
    collected |= frontier
    for _ in range(max(depth, 0)):
        next_frontier: Set[str] = set()
        for node in frontier:
            next_frontier.update(source.successors(node))
            next_frontier.update(source.predecessors(node))
        next_frontier -= collected
        collected |= next_frontier
        frontier = next_frontier
        if not frontier:
            break
    return source.subgraph(collected).copy()


def graph_stats(g: nx.MultiDiGraph) -> Dict[str, Any]:
    """Small analytics bundle: size, density, degree and predicate histogram."""
    from collections import Counter

    predicates: Counter = Counter()
    for _, _, data in g.edges(data=True):
        predicates[data.get("predicate", "?")] += 1
    by_type: Counter = Counter(data.get("type", "?") for _, data in g.nodes(data=True))
    degree = dict(g.degree())
    top = sorted(degree.items(), key=lambda kv: -kv[1])[:10]
    return {
        "nodes": g.number_of_nodes(),
        "edges": g.number_of_edges(),
        "density": round(nx.density(g), 4),
        "node_types": dict(by_type.most_common()),
        "predicates": dict(predicates.most_common()),
        "most_connected": [{"id": n, "degree": d} for n, d in top],
    }


def to_node_link(g: nx.MultiDiGraph) -> Dict[str, Any]:
    """``node-link`` payload (D3-friendly), keeping parallel edges distinct."""
    nodes = [dict(data, id=n) for n, data in g.nodes(data=True)]
    links: List[Dict[str, Any]] = [
        {"source": u, "target": v, "predicate": data.get("predicate")}
        for u, v, data in g.edges(data=True)
    ]
    return {"directed": True, "multigraph": True, "graph": dict(g.graph), "nodes": nodes, "links": links}
