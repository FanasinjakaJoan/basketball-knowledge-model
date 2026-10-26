"""Command line interface to the Basketball Knowledge Model.

Examples
--------
    python -m basketball_kg.cli stats
    python -m basketball_kg.cli ask "how do you attack a 2-3 zone?"
    python -m basketball_kg.cli ask "who covers the corner in a 2-3 zone?" -f sparql
    python -m basketball_kg.cli query play_steps --play play:motion-offense
    python -m basketball_kg.cli export -f dot --focus play:pick-and-roll --out pnr.dot
    python -m basketball_kg.cli court --highlight zone:corner-three-left
"""

from __future__ import annotations

import argparse
import json as _json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from . import __version__
from .graph import graph_stats, subgraph_around, to_networkx, to_node_link
from .model import KnowledgeGraph, load_graph
from .nlq import VocabularyIndex, answer, parse
from .queries import INTENTS, QueryResult, intent_help, run_intent
from .rdf import build_rdf, query_sparql, to_jsonld, to_turtle
from .viz import ascii_court, to_dot

_TABLE_MAX = 44


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #


def _short(value: Any, width: int = _TABLE_MAX) -> str:
    text = "" if value is None else str(value)
    text = " ".join(text.split())
    return text if len(text) <= width else text[: width - 1] + "…"


def render_table(rows: Sequence[Dict[str, Any]], columns: Optional[Sequence[str]] = None) -> str:
    if not rows:
        return "(no results)"
    cols: List[str] = list(columns) if columns else list(rows[0].keys())
    widths = {c: len(c) for c in cols}
    for row in rows:
        for c in cols:
            widths[c] = max(widths[c], min(len(_short(row.get(c, ""))), _TABLE_MAX))
    line = "  ".join(c.ljust(widths[c]) for c in cols)
    out = [line, "  ".join("-" * widths[c] for c in cols)]
    for row in rows:
        out.append("  ".join(_short(row.get(c, "")).ljust(widths[c]) for c in cols))
    return "\n".join(out)


def render_result(result: QueryResult, fmt: str = "text") -> str:
    if fmt == "json":
        return _json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    plan = result.plan
    if fmt == "sparql":
        return plan.to_sparql() if plan else "-- no plan"
    if fmt == "cypher":
        return plan.to_cypher() if plan else "-- no plan"
    if fmt == "plan":
        return _json.dumps(plan.to_json(), indent=2, ensure_ascii=False) if plan else "-- no plan"

    # rich text
    lines: List[str] = []
    if plan:
        lines.append(f"intent: {plan.intent}   (confidence {plan.confidence})")
        if plan.slots:
            lines.append("slots:  " + ", ".join(f"{k}={v}" for k, v in plan.slots.items()))
    lines.append("")
    if result.summary:
        lines.append(result.summary)
        lines.append("")
    if result.rows:
        intent = result.intent
        columns = {
            "play_steps": ["order", "label", "actionType", "actor", "from", "to", "branch"],
            "counters": ["label", "answers", "vulnerability", "effectiveness"],
            "rules": ["label", "threshold", "penalty"],
            "requirements": ["label", "type", "requires"],
            "fit": ["label", "team", "position", "matches", "coverage"],
            "zone_responsibility": ["label", "heldBy", "coversZones"],
            "situations": ["type", "label", "formation", "coverage"],
            "spatial": ["label", "shotValue", "zoneType", "adjacentTo"],
            "sequence": ["relation", "label", "actionType", "branch"],
            "search": ["type", "label", "score"],
            "compare": ["side", "label", "vulnerability"],
            "describe": ["type", "label"],
        }.get(intent)
        lines.append(render_table(result.rows, columns))
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Commands
# --------------------------------------------------------------------------- #


def _cmd_stats(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    g = to_networkx(kg)
    stats = graph_stats(g)
    print(f"Basketball Knowledge Model v{__version__}")
    print(f"  datasets : {len(kg.datasets)}")
    for dataset in kg.datasets:
        count = sum(1 for n in kg.nodes.values() if n.dataset == dataset.id)
        print(f"             - {dataset.id:<22} {count:>4} nodes  ({dataset.path.name})")
    print(f"  nodes    : {stats['nodes']}")
    print(f"  edges    : {stats['edges']}")
    print(f"  density  : {stats['density']}")
    print("\n  node types:")
    for type_name, count in stats["node_types"].items():
        print(f"    {type_name:<20} {count:>4}")
    print("\n  predicates:")
    for predicate, count in stats["predicates"].items():
        print(f"    {predicate:<20} {count:>4}")
    print("\n  most connected nodes:")
    for item in stats["most_connected"][:8]:
        node = kg.get(item["id"])
        print(f"    {item['degree']:>4}  {item['id']:<34} {node.label if node else ''}")
    return 0


def _cmd_intents(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    print(intent_help())
    return 0


def _cmd_ask(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    index = VocabularyIndex(kg)
    result = answer(kg, args.question, index=index)
    if args.show_query:
        plan = result.plan
        print(f"# parsed: {plan.intent}  confidence={plan.confidence}")
        for item in plan.evidence:
            print(f"#   {item}")
        print()
    print(render_result(result, args.format))
    return 0


def _cmd_query(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    if args.intent == "list":
        print(intent_help())
        return 0
    meta = INTENTS.get(args.intent)
    if meta is None:
        print(f"unknown intent {args.intent!r}; run 'query list'", file=sys.stderr)
        return 2
    slots: Dict[str, Any] = {}
    for slot in meta["slots"]:
        value = getattr(args, slot, None)
        if value:
            slots[slot] = value
    missing = [s for s in meta["slots"] if s not in slots]
    if missing and missing != meta["slots"]:
        print(f"# note: no value for slot(s) {', '.join(missing)}", file=sys.stderr)
    result = run_intent(kg, args.intent, **slots)
    print(render_result(result, args.format))
    return 0


def _cmd_export(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    if args.format == "dot":
        node_ids = None
        if args.focus:
            g = to_networkx(kg)
            sub = subgraph_around(g, [args.focus], depth=args.depth)
            node_ids = list(sub.nodes)
        payload = to_dot(kg, node_ids=node_ids, show_definitions=args.definitions)
    elif args.format in {"ttl", "turtle"}:
        payload = to_turtle(build_rdf(kg, include_ontology=args.ontology))
    elif args.format in {"jsonld", "json-ld"}:
        payload = to_jsonld(kg)
    elif args.format in {"json", "node-link"}:
        g = to_networkx(kg)
        if args.focus:
            g = subgraph_around(g, [args.focus], depth=args.depth)
        payload = _json.dumps(to_node_link(g), indent=2, ensure_ascii=False)
    else:  # pragma: no cover - argparse restricts choices
        print(f"unsupported format {args.format}", file=sys.stderr)
        return 2
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"wrote {args.out} ({len(payload)} bytes)")
    else:
        print(payload)
    return 0


def _cmd_court(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    highlight: List[str] = list(args.highlight or [])
    if args.scheme:
        node = kg.get(args.scheme) or kg.resolve(args.scheme)
        if node is None:
            print(f"unknown scheme {args.scheme!r}", file=sys.stderr)
            return 2
        # a scheme's area duties may live on the scheme node itself or on the
        # play graph that models it (linked either way by `relatedTo`)
        candidates = [node.id, *node.out("relatedTo"), *kg.in_(node.id, "relatedTo")]
        zones: List[str] = []
        for cid in candidates:
            holder = kg.get(cid)
            if holder is None:
                continue
            for assignment in sorted(set(holder.out("hasAssignment") + kg.in_(cid, "ofScheme"))):
                if kg.get(assignment):
                    zones.extend(kg[assignment].out("coversZone"))
        zones = sorted(set(zones))
        highlight.extend(zones)
        print(f"# {node.label} covers {len(zones)} zone(s): {', '.join(_short(kg[z].label, 18) for z in zones if kg.get(z))}")
    print(ascii_court(kg, highlight=highlight))
    return 0


def _cmd_sparql(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    g = build_rdf(kg, include_ontology=args.ontology)
    query = Path(args.file).read_text(encoding="utf-8") if args.file else args.query
    if not query:
        print("provide --query or --file", file=sys.stderr)
        return 2
    rows = query_sparql(g, query)
    if args.format == "json":
        print(_json.dumps(rows, indent=2, ensure_ascii=False))
    else:
        print(render_table(rows) if rows else "(no results)")
    return 0


def _cmd_serve(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    """Start the web explorer (blocks until interrupted)."""
    from .serve import KnowledgeGraphServer, main as serve_main

    # reuse the graph the CLI already loaded, unless the caller pointed elsewhere
    app = KnowledgeGraphServer(kg=kg)
    argv = ["--host", args.host, "--port", str(args.port)]
    if args.data:
        argv += ["--data", str(args.data)]
    return serve_main(argv=argv, app=app)


def _cmd_validate(kg: KnowledgeGraph, args: argparse.Namespace) -> int:
    problems = kg.validate()
    total = sum(len(v) for v in problems.values())
    if total == 0:
        print(f"OK: {len(kg)} nodes, no dangling references, all types known.")
        return 0
    for kind, items in problems.items():
        if not items:
            continue
        print(f"{kind} ({len(items)}):")
        for item in items[:50]:
            print(f"  - {item}")
    return 1


# --------------------------------------------------------------------------- #
# Parser
# --------------------------------------------------------------------------- #


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m basketball_kg.cli",
        description="Query, export and visualise the Basketball Knowledge Model.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--version", action="version", version=f"basketball-kg {__version__}")
    parser.add_argument("--data", type=Path, default=None, help="directory holding the JSON datasets")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("stats", help="graph statistics").set_defaults(func=_cmd_stats)
    sub.add_parser("intents", help="list query intents").set_defaults(func=_cmd_intents)
    sub.add_parser("validate", help="check ids, types and dangling references").set_defaults(func=_cmd_validate)

    p_ask = sub.add_parser("ask", help="answer a natural-language question")
    p_ask.add_argument("question")
    p_ask.add_argument("-f", "--format", default="text", choices=["text", "json", "sparql", "cypher", "plan"])
    p_ask.add_argument("--show-query", action="store_true", help="print the parse trace")
    p_ask.set_defaults(func=_cmd_ask, format="text")

    p_query = sub.add_parser("query", help="run a structured intent directly")
    p_query.add_argument("intent", help="intent name, or 'list'")
    _all_slots: Dict[str, List[str]] = {}
    for intent, meta in INTENTS.items():
        for slot in meta["slots"]:
            _all_slots.setdefault(slot, []).append(intent)
    for slot, owners in _all_slots.items():
        p_query.add_argument(f"--{slot}", help=f"slot for: {', '.join(owners)}")
    p_query.add_argument("-f", "--format", default="text", choices=["text", "json", "sparql", "cypher", "plan"])
    p_query.set_defaults(func=_cmd_query, format="text")

    p_export = sub.add_parser("export", help="export the graph")
    p_export.add_argument("-f", "--format", default="dot", choices=["dot", "ttl", "turtle", "jsonld", "json-ld", "json", "node-link"])
    p_export.add_argument("--out", type=Path, default=None)
    p_export.add_argument("--focus", default=None, help="a node id to centre the export on")
    p_export.add_argument("--depth", type=int, default=1)
    p_export.add_argument("--ontology", action="store_true", help="include the TBox in RDF exports")
    p_export.add_argument("--definitions", action="store_true", help="put definitions in DOT labels")
    p_export.set_defaults(func=_cmd_export, format="dot")

    p_court = sub.add_parser("court", help="draw the ASCII half court")
    p_court.add_argument("--highlight", action="append", default=[], help="zone id or label to highlight")
    p_court.add_argument("--scheme", default=None, help="highlight every zone a scheme covers")
    p_court.set_defaults(func=_cmd_court, highlight=[])

    p_serve = sub.add_parser("serve", help="run the web explorer (http://0.0.0.0:8000)")
    p_serve.add_argument("--host", default="0.0.0.0")
    p_serve.add_argument("--port", type=int, default=8000)
    p_serve.add_argument("--data", type=Path, default=None, help="directory holding the data/ JSON files")
    p_serve.set_defaults(func=_cmd_serve)

    p_sparql = sub.add_parser("sparql", help="run SPARQL against the RDF projection")
    p_sparql.add_argument("--query", default=None)
    p_sparql.add_argument("--file", type=Path, default=None)
    p_sparql.add_argument("--ontology", action="store_true")
    p_sparql.add_argument("-f", "--format", default="text", choices=["text", "json"])
    p_sparql.set_defaults(func=_cmd_sparql, format="text")

    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    kg = load_graph(args.data)
    return int(args.func(kg, args) or 0)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
