"""Tests for the intent catalogue: in-memory execution, SPARQL and Cypher renderings."""

import json
import unittest
from pathlib import Path

from basketball_kg.model import load_graph
from basketball_kg.queries import INTENTS, QueryPlan, QueryResult, intent_help, run_intent

ROOT = Path(__file__).resolve().parents[1]

#: (intent, slots) pairs that must return rows
CANONICAL = [
    ("describe", {"target": "coverage:drop"}),
    ("play_steps", {"play": "play:pick-and-roll"}),
    ("play_steps", {"play": "play:motion-offense"}),
    ("play_steps", {"play": "play:zone-defense-2-3"}),
    ("zone_responsibility", {"zone": "zone:corner-three-left"}),
    ("zone_responsibility", {"scheme": "scheme:zone-2-3"}),
    ("counters", {"target": "scheme:zone-2-3"}),
    ("counters", {"target": "coverage:drop"}),
    ("counters", {"target": "coverage:switch"}),
    ("rules", {"target": "atype:set-on-ball-screen"}),
    ("rules", {"target": "play:pick-and-roll"}),
    ("requirements", {"target": "play:motion-offense"}),
    ("fit", {"scheme": "scheme:switch-all"}),
    ("fit", {"scheme": "scheme:zone-2-3", "team": "team:harbour"}),
    ("situations", {"situation": "sit:press"}),
    ("spatial", {"zone": "zone:short-corner-left"}),
    ("spatial", {}),
    ("sequence", {"action": "pnr:s5-roll"}),
    ("compare", {"a": "coverage:drop", "b": "coverage:blitz"}),
    ("search", {"text": "weak side"}),
]


class TestIntents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()

    def test_every_canonical_query_returns_rows(self):
        for intent, slots in CANONICAL:
            with self.subTest(f"{intent} {slots}"):
                result = run_intent(self.kg, intent, **slots)
                self.assertIsInstance(result, QueryResult)
                self.assertTrue(result.rows, f"{intent} {slots} returned nothing")
                self.assertTrue(result.summary)

    def test_known_intents_are_documented(self):
        help_text = intent_help()
        for intent, meta in INTENTS.items():
            with self.subTest(intent):
                self.assertIn(intent, help_text)
                self.assertTrue(meta["purpose"])
                self.assertTrue(meta["slots"])
                self.assertTrue(meta["examples"])
                plan = QueryPlan(intent=intent, slots={})
                self.assertEqual(plan.to_json()["intent"], intent)

    def test_unknown_intent_raises(self):
        with self.assertRaises(ValueError):
            run_intent(self.kg, "not_an_intent")

    def test_play_steps_are_sorted_and_complete(self):
        result = run_intent(self.kg, "play_steps", play="play:pick-and-roll")
        orders = [r["order"] for r in result.rows]
        self.assertEqual(orders, sorted(orders))
        labels = [r["label"] for r in result.rows]
        self.assertTrue(any("screen" in label.lower() for label in labels))
        self.assertTrue(any("DECISION" in label for label in labels))

    def test_decision_point_is_not_double_counted(self):
        result = run_intent(self.kg, "play_steps", play="play:pick-and-roll")
        decisions = [r for r in result.rows if "DECISION" in r["label"]]
        self.assertEqual(len(decisions), 1)

    def test_zone_responsibility_links_roles_to_zones(self):
        result = run_intent(self.kg, "zone_responsibility", scheme="play:zone-defense-2-3")
        self.assertEqual(len(result.rows), 5)
        anchor = next(r for r in result.rows if "anchor" in r["label"])
        self.assertEqual(anchor["heldBy"], "Rim Protector")
        self.assertIn("Paint (Lane)", anchor["coversZones"])

    def test_counters_expose_the_vulnerability(self):
        result = run_intent(self.kg, "counters", target="scheme:zone-2-3")
        vulnerabilities = {r["vulnerability"] for r in result.rows}
        self.assertTrue(any("free-throw line" in v.lower() for v in vulnerabilities), vulnerabilities)
        for row in result.rows:
            self.assertTrue(row["rationale"])

    def test_rules_roll_up_from_steps_to_action_types(self):
        result = run_intent(self.kg, "rules", target="play:pick-and-roll")
        labels = {r["label"] for r in result.rows}
        self.assertIn("Legal screening", labels)
        self.assertIn("Offensive three-second violation", labels)

    def test_fit_only_considers_players(self):
        result = run_intent(self.kg, "fit", scheme="scheme:switch-all")
        for row in result.rows:
            self.assertTrue(row["player"].startswith("player:"), row)
            self.assertTrue(row["label"])
        self.assertTrue(any(row["matchCount"] > 0 for row in result.rows))

    def test_spatial_without_a_zone_ranks_by_shot_value(self):
        result = run_intent(self.kg, "spatial")
        values = [r["shotValue"] for r in result.rows]
        self.assertEqual(values, sorted(values, reverse=True))
        self.assertEqual(values[0], 3)

    def test_sequence_reports_before_and_after(self):
        result = run_intent(self.kg, "sequence", action="pnr:s19-pocket-pass")
        relations = {r["relation"] for r in result.rows}
        self.assertIn("after", relations)
        self.assertIn("before", relations)

    def test_compare_has_two_sides(self):
        result = run_intent(self.kg, "compare", a="coverage:drop", b="coverage:blitz")
        self.assertEqual({r["side"] for r in result.rows}, {"a", "b"})


class TestRenderings(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()

    def test_every_intent_renders_sparql_and_cypher(self):
        for intent in INTENTS:
            slots = next((s for i, s in CANONICAL if i == intent), {})
            plan = QueryPlan(intent=intent, slots=dict(slots))
            with self.subTest(intent):
                sparql = plan.to_sparql()
                cypher = plan.to_cypher()
                self.assertIn("SELECT", sparql.upper())
                self.assertTrue(cypher.strip().endswith(";"))
                self.assertTrue(plan.to_graph_pattern())

    def test_sparql_uses_the_ontology_namespace(self):
        plan = QueryPlan(intent="play_steps", slots={"play": "play:pick-and-roll"})
        self.assertIn("https://w3id.org/basketball-kg/ontology#", plan.to_sparql())
        self.assertIn("bk:hasStep", plan.to_sparql())

    def test_cypher_uses_screaming_snake_relations(self):
        plan = QueryPlan(intent="play_steps", slots={"play": "play:pick-and-roll"})
        self.assertIn("[:HAS_STEP]", plan.to_cypher())

    def test_plan_json_is_serialisable(self):
        plan = QueryPlan(intent="counters", slots={"target": "scheme:zone-2-3"})
        payload = json.dumps(plan.to_json())
        self.assertIn("graph_pattern", json.loads(payload))


class TestCatalogue(unittest.TestCase):
    def test_nl_to_query_matches_expectations(self):
        path = ROOT / "queries" / "nl_to_query.json"
        payload = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(payload["examples"]), 10)
        for entry in payload["examples"]:
            with self.subTest(entry["question"]):
                self.assertEqual(entry["parsed"]["intent"], entry["expected_intent"])
                self.assertGreater(entry["rows_returned"], 0)
                self.assertTrue(entry["sparql"])
                self.assertTrue(entry["cypher"])
                self.assertTrue(Path(ROOT / entry["query_file"]).exists())


if __name__ == "__main__":
    unittest.main()
