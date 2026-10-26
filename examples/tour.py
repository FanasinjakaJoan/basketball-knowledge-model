#!/usr/bin/env python3
"""A five-minute guided tour of the Basketball Knowledge Model.

    python examples/tour.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from basketball_kg import load_graph, parse  # noqa: E402
from basketball_kg.graph import graph_stats, to_networkx
from basketball_kg.nlq import answer
from basketball_kg.queries import QueryPlan
from basketball_kg.viz import ascii_court

QUESTIONS = [
    "How do you attack a 2-3 zone?",
    "Who covers the corner in a 2-3 zone?",
    "What beats drop coverage?",
    "What rules govern setting a screen?",
    "Walk me through the pick and roll.",
    "What happens after the roll?",
    "What kind of players does motion offence need?",
    "Who on Harbour fits switch all?",
    "What is next to the short corner?",
    "What should we run late in the shot clock?",
]


def rule(title: str) -> None:
    print("\n" + title)
    print("=" * len(title))


def main() -> int:
    kg = load_graph()

    rule("1. The graph")
    stats = graph_stats(to_networkx(kg))
    print(f"{stats['nodes']} nodes, {stats['edges']} edges, density {stats['density']}")
    print("node types:", ", ".join(f"{k} ({v})" for k, v in list(stats["node_types"].items())[:8]))
    print("top predicates:", ", ".join(f"{k} ({v})" for k, v in list(stats["predicates"].items())[:6]))
    problems = kg.validate()
    print("validation:", "clean" if not any(problems.values()) else problems)

    rule("2. Space")
    print(ascii_court(kg, highlight=["zone:high-post", "zone:corner-three-left"]))
    print()
    print("The 'hole' of a 2-3 zone, one query away:")
    for row in answer(kg, "where is the high post?").rows[:1]:
        print(f"  {row['label']}: shot value {row['shotValue']}, adjacent to {row['adjacentTo']}")

    rule("3. Tactics: the pick-and-roll read")
    plan = QueryPlan(intent="play_steps", slots={"play": "play:pick-and-roll"})
    result = plan.execute(kg)
    print(result.summary)
    for row in result.rows:
        if row["branch"] in {"drop", "blitz", "switch", "ice"}:
            print(f"  [{row['branch']:<6}] {row['label']}")

    rule("4. Counters")
    for target in ("scheme:zone-2-3", "coverage:drop", "coverage:switch"):
        rows = answer(kg, f"how do you beat {target}?").rows
        print(f"\n{target} -> {len(rows)} answer(s)")
        for row in rows[:3]:
            print(f"  - {row['label']}: {row['vulnerability'][:78]}")

    rule("5. Rules that bind the actions")
    for row in answer(kg, "what rules constrain the pick and roll?").rows:
        print(f"  - {row['label']} ({row['threshold']}) -> {row['penalty']}")

    rule("6. Personnel fit")
    for row in answer(kg, "Who fits switch all?").rows[:5]:
        print(f"  {row['label']:<14} {row['position']:<16} {row['coverage']}  {row['matches']}")

    rule("7. Natural language -> structured query")
    for question in QUESTIONS:
        plan = parse(kg, question)
        result = plan.execute(kg)
        slots = ", ".join(f"{k}={v}" for k, v in plan.slots.items()) or "(none)"
        print(f"  {question}")
        print(f"      -> {plan.intent} [{slots}]  {len(result.rows)} row(s), confidence {plan.confidence}")

    rule("8. The same query in three back ends")
    plan = parse(kg, "What beats drop coverage?")
    print("graph pattern:")
    for triple in plan.to_graph_pattern():
        print(f"  {triple['s']:>8} -{triple['p']}-> {triple['o']}")
    print("\nSPARQL (first 12 lines):")
    for line in plan.to_sparql().splitlines()[2:14]:
        print("  " + line)
    print("\nCypher (first 10 lines):")
    for line in plan.to_cypher().splitlines()[:10]:
        print("  " + line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
