"""Basketball Knowledge Model (BKM).

A structured, queryable model of basketball tactics: positions, functional
roles, player archetypes, a spatial half-court model, offensive and defensive
schemes, ball-screen coverages, play graphs with decision points, game
situations, and the rules that constrain every action.

Quick start
-----------
>>> from basketball_kg import load_graph, answer
>>> kg = load_graph()
>>> result = answer(kg, "how do you attack a 2-3 zone?")
>>> result.intent
'counters'

The same knowledge is available three ways:

* :mod:`basketball_kg.model`  -- the canonical JSON-backed graph
* :mod:`basketball_kg.graph`  -- NetworkX (property-graph) projection
* :mod:`basketball_kg.rdf`    -- RDF / JSON-LD / SPARQL projection
"""

from __future__ import annotations

from .model import KnowledgeGraph, Node, load_graph
from .nlq import answer, parse
from .queries import QueryPlan, QueryResult

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "KnowledgeGraph",
    "Node",
    "load_graph",
    "parse",
    "answer",
    "QueryPlan",
    "QueryResult",
]
