#!/usr/bin/env python3
"""Generate the example query library in ``queries/``.

Every ``.rq`` (SPARQL) and ``.cypher`` file is rendered from the templates in
``basketball_kg.queries``, so the published examples cannot drift from the code.
Run it after changing a template::

    python scripts/gen_queries.py [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basketball_kg.queries import INTENTS, QueryPlan  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SPARQL_DIR = ROOT / "queries" / "sparql"
CYPHER_DIR = ROOT / "queries" / "cypher"

#: (slug, intent, slots, natural-language question, note)
EXAMPLES = [
    (
        "01-pick-and-roll-steps",
        "play_steps",
        {"play": "play:pick-and-roll"},
        "Walk me through the pick and roll.",
        "Ordered action graph: who does what, where, under which constraint.",
    ),
    (
        "02-zone-2-3-responsibilities",
        "zone_responsibility",
        {"scheme": "play:zone-defense-2-3"},
        "What are the 2-3 zone assignments?",
        "Area duties are reified as Assignment nodes so they survive the trip to RDF.",
    ),
    (
        "03-attack-the-2-3-zone",
        "counters",
        {"target": "scheme:zone-2-3"},
        "How do you attack a 2-3 zone?",
        "Counters carry the vulnerability they exploit and a rationale.",
    ),
    (
        "04-rules-for-screening",
        "rules",
        {"target": "atype:set-on-ball-screen"},
        "What rules govern setting a screen?",
        "Rules attach to action *types*, so every screening action inherits them.",
    ),
    (
        "05-roster-fit-switch-all",
        "fit",
        {"scheme": "scheme:switch-all"},
        "Which players fit a switch-everything scheme?",
        "Joins the scheme's archetype requirements against player archetypes.",
    ),
    (
        "06-short-corner-geometry",
        "spatial",
        {"zone": "zone:short-corner-left"},
        "What is next to the short corner?",
        "Adjacency is the 'one pass away' relation used for spacing and zone rotation.",
    ),
    (
        "07-after-the-roll",
        "sequence",
        {"action": "pnr:s5-roll"},
        "What happens after the roll?",
        "precedes / follows: the temporal spine of a play.",
    ),
    (
        "08-beating-drop-coverage",
        "counters",
        {"target": "coverage:drop"},
        "What beats drop coverage?",
        "The branch steps of the pick-and-roll read the same coverage vocabulary.",
    ),
    (
        "09-motion-offence-requirements",
        "requirements",
        {"target": "play:motion-offense"},
        "What kind of players does motion offence need?",
        "Requirements roll up from steps and from the action types they instantiate.",
    ),
    (
        "10-late-clock-options",
        "situations",
        {"situation": "sit:late-clock"},
        "What should we run late in the shot clock?",
        "appliesIn ties schemes and plays to the game situation they are built for.",
    ),
]


def render(plan: QueryPlan, question: str, note: str, kind: str) -> str:
    body = plan.to_sparql() if kind == "sparql" else plan.to_cypher()
    comment = "#" if kind == "sparql" else "//"
    slots = ", ".join(f"{k}={v}" for k, v in plan.slots.items()) or "(none)"
    header = [
        f"{comment} Basketball Knowledge Model -- example query",
        f"{comment} question : {question}",
        f"{comment} intent   : {plan.intent}",
        f"{comment} slots    : {slots}",
        f"{comment} note     : {note}",
        f"{comment} generated: python scripts/gen_queries.py (do not edit by hand)",
        "",
    ]
    return "\n".join(header) + body.strip() + "\n"


def write_nl_catalogue() -> Path:
    """Write ``queries/nl_to_query.json``: natural language -> structured query.

    Each entry records what the parser produced (intent, slots, confidence, the
    rule that fired), the three renderings of the same plan, and how many rows
    the in-memory execution returns -- so the catalogue doubles as a test fixture.
    """
    from basketball_kg.model import load_graph
    from basketball_kg.nlq import VocabularyIndex, parse

    kg = load_graph()
    index = VocabularyIndex(kg)
    entries = []
    for slug, intent, slots, question, note in EXAMPLES:
        plan = parse(kg, question, index=index)
        result = plan.execute(kg)
        entries.append(
            {
                "question": question,
                "expected_intent": intent,
                "expected_slots": slots,
                "parsed": {
                    "intent": plan.intent,
                    "slots": plan.slots,
                    "confidence": plan.confidence,
                    "evidence": plan.evidence,
                },
                "rows_returned": len(result.rows),
                "summary": result.summary,
                "graph_pattern": plan.to_graph_pattern(),
                "sparql": plan.to_sparql(),
                "cypher": plan.to_cypher(),
                "query_file": f"queries/sparql/{slug}.rq",
            }
        )
    payload = {
        "generated": "python scripts/gen_queries.py -- do not edit by hand",
        "note": "Natural-language questions resolved by basketball_kg.nlq.parse, "
                "with every rendering of the resulting query plan.",
        "intents": INTENTS,
        "examples": entries,
    }
    path = ROOT / "queries" / "nl_to_query.json"
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="fail if any file is out of date")
    args = parser.parse_args()

    SPARQL_DIR.mkdir(parents=True, exist_ok=True)
    CYPHER_DIR.mkdir(parents=True, exist_ok=True)
    stale = []
    for slug, intent, slots, question, note in EXAMPLES:
        plan = QueryPlan(intent=intent, slots=dict(slots))
        targets = {
            "sparql": (SPARQL_DIR / f"{slug}.rq", render(plan, question, note, "sparql")),
            "cypher": (CYPHER_DIR / f"{slug}.cypher", render(plan, question, note, "cypher")),
        }
        for kind, (path, content) in targets.items():
            if args.check:
                if not path.exists() or path.read_text(encoding="utf-8") != content:
                    stale.append(str(path.relative_to(ROOT)))
                continue
            path.write_text(content, encoding="utf-8")
            print(f"wrote {path.relative_to(ROOT)}")
    if not args.check:
        catalogue = write_nl_catalogue()
        print(f"wrote {catalogue.relative_to(ROOT)}")
    if args.check:
        if stale:
            print("out of date: " + ", ".join(stale), file=sys.stderr)
            return 1
        print(f"OK: {len(EXAMPLES) * 2} query files up to date")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
