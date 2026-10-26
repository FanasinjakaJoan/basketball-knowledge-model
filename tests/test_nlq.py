"""Tests for the natural-language -> structured-query parser."""

import unittest

from basketball_kg.model import load_graph
from basketball_kg.nlq import SYNONYMS, VocabularyIndex, answer, parse

#: (question, expected intent, expected slot key, expected node id)
QUESTIONS = [
    ("How do you attack a 2-3 zone?", "counters", "target", "scheme:zone-2-3"),
    ("What beats drop coverage?", "counters", "target", "coverage:drop"),
    ("How do we score against a blitz?", "counters", "target", "coverage:blitz"),
    ("Who covers the corner in a 2-3 zone?", "zone_responsibility", "zone", "zone:corner-three-left"),
    ("Who guards the high post in a 2-3 zone?", "zone_responsibility", "zone", "zone:high-post"),
    ("What are the 2-3 zone assignments?", "zone_responsibility", "scheme", None),
    ("Walk me through the pick and roll.", "play_steps", "play", "play:pick-and-roll"),
    ("What are the steps of motion offence?", "play_steps", "play", "play:motion-offense"),
    ("What rules govern setting a screen?", "rules", "target", "atype:set-on-ball-screen"),
    ("Is a moving screen legal?", "rules", "target", "rule:legal-screen"),
    ("What rules constrain the roll man?", "rules", "target", None),
    ("What happens after the roll?", "sequence", "action", "pnr:s5-roll"),
    ("What is next to the short corner?", "spatial", "zone", "zone:short-corner-left"),
    ("Which zone has the highest shot value?", "spatial", None, None),
    ("What kind of player can run a short roll?", "requirements", "target", None),
    ("Who on Harbour fits switch all?", "fit", "scheme", "scheme:switch-all"),
    ("What should we run against a press?", "situations", "situation", "sit:press"),
    ("What should we run late in the shot clock?", "situations", "situation", "sit:late-clock"),
    ("Compare drop and blitz.", "compare", "a", "coverage:drop"),
    ("What is drop coverage?", "describe", "target", "coverage:drop"),
    ("What is a hub playmaker?", "describe", "target", "arch:hub-playmaker"),
]

ANSWERABLE = [q for q, *_ in QUESTIONS] + [
    "Tell me about the short corner",
    "nail help",
    "spacing",
    "how is the 2-3 zone beaten",
    "who guards the corner three",
    "what does a switchable defender do",
]


class TestParsing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()
        cls.index = VocabularyIndex(cls.kg)

    def test_intent_and_slot_resolution(self):
        for question, intent, slot, node_id in QUESTIONS:
            with self.subTest(question):
                plan = parse(self.kg, question, index=self.index)
                self.assertEqual(plan.intent, intent, f"{question!r} -> {plan.intent} ({plan.evidence})")
                if slot is not None:
                    self.assertIn(slot, plan.slots, f"{question!r} has no {slot}")
                if node_id is not None:
                    self.assertEqual(plan.slots[slot], node_id)
                self.assertTrue(plan.evidence)
                self.assertGreater(plan.confidence, 0.5)

    def test_every_question_returns_rows(self):
        for question in ANSWERABLE:
            with self.subTest(question):
                result = answer(self.kg, question, index=self.index)
                self.assertTrue(result.rows, f"{question!r} -> {result.intent} returned nothing")
                self.assertTrue(result.summary)

    def test_unknown_question_falls_back_to_search(self):
        plan = parse(self.kg, "quantum tunnelling in the low post", index=self.index)
        self.assertIn(plan.intent, {"search", "describe"})

    def test_empty_question_is_safe(self):
        plan = parse(self.kg, "   ", index=self.index)
        self.assertEqual(plan.intent, "search")

    def test_synonyms_point_at_real_nodes(self):
        for alias, node_id in SYNONYMS.items():
            with self.subTest(alias):
                self.assertIn(node_id, self.kg, f"{alias!r} -> {node_id} does not exist")

    def test_index_prefers_the_longest_alias(self):
        hit = self.index.lookup("how do you attack a 2-3 zone", ("Scheme", "DefensiveScheme", "Play"))
        self.assertIsNotNone(hit)
        self.assertIn("2 3", hit.text)

    def test_index_respects_type_filters(self):
        hit = self.index.lookup("the corner", ("Zone",))
        self.assertEqual(hit.node_id, "zone:corner-three-left")
        self.assertIsNone(self.index.lookup("the corner", ("Rule",)))

    def test_lookup_many_returns_distinct_hits(self):
        hits = self.index.lookup_many("compare drop and blitz", ("Coverage",), limit=2)
        self.assertEqual([h.node_id for h in hits], ["coverage:drop", "coverage:blitz"])


if __name__ == "__main__":
    unittest.main()
