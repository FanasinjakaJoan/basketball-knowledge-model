"""Tests for the JSON data model and the loader."""

import json
import unittest
from pathlib import Path

from basketball_kg.model import INVERSES, ONTOLOGY_CLASSES, KnowledgeGraph, load_graph

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"


class TestLoading(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()

    def test_graph_loads(self):
        self.assertGreater(len(self.kg), 250)
        self.assertIn("zone:corner-three-left", self.kg)
        self.assertIn("play:pick-and-roll", self.kg)

    def test_every_json_file_is_valid_and_loaded(self):
        files = sorted(DATA.rglob("*.json"))
        self.assertTrue(files)
        dataset_ids = {d.id for d in self.kg.datasets}
        self.assertEqual(len(dataset_ids), len(files))
        for path in files:
            json.loads(path.read_text(encoding="utf-8"))

    def test_no_dangling_or_unknown_types(self):
        problems = self.kg.validate()
        for kind, items in problems.items():
            self.assertEqual(items, [], f"{kind}: {items[:5]}")

    def test_all_types_declared_in_ontology(self):
        self.assertTrue(ONTOLOGY_CLASSES)
        for node in self.kg.nodes.values():
            self.assertIn(node.type, ONTOLOGY_CLASSES, node.id)

    def test_inverses_are_derived(self):
        play = self.kg["play:pick-and-roll"]
        self.assertIn("pnr:s3-screen", play.out("hasStep"))
        self.assertEqual(self.kg["pnr:s3-screen"].out("stepOf"), ["play:pick-and-roll"])

    def test_adjacency_is_symmetric(self):
        for node in self.kg.by_type("Zone"):
            for neighbour in node.out("adjacentTo"):
                self.assertIn(node.id, self.kg[neighbour].out("adjacentTo"), f"{node.id} <-> {neighbour}")

    def test_inverse_pairs_are_consistent(self):
        for forward, inverse in INVERSES.items():
            for node in self.kg.nodes.values():
                for target in node.out(forward):
                    self.assertIn(node.id, self.kg[target].out(inverse))

    def test_play_steps_are_ordered_and_typed(self):
        steps = self.kg["play:pick-and-roll"].out("hasStep")
        self.assertGreaterEqual(len(steps), 15)
        for step_id in steps:
            step = self.kg[step_id]
            if step.type == "Action":
                self.assertTrue(step.out("hasActionType"), f"{step_id} has no action type")
                self.assertTrue(step.out("actor"), f"{step_id} has no actor")
                self.assertIsInstance(step.props.get("order"), int)

    def test_zones_have_geometry(self):
        for zone in self.kg.by_type("Zone"):
            if zone.id in {"zone:frontcourt"}:
                continue
            self.assertIn("courtX", zone.props, zone.id)
            self.assertIn("courtY", zone.props, zone.id)
            self.assertIn("shotValue", zone.props, zone.id)

    def test_three_point_zones(self):
        three = [z for z in self.kg.by_type("Zone") if z.props.get("shotValue") == 3]
        self.assertEqual(len(three), 5)
        corners = {z.id for z in three if "corner" in z.id}
        self.assertEqual(len(corners), 2)

    def test_search_ranks_exact_labels_first(self):
        hits = self.kg.search("drop coverage", types=["Coverage"])
        self.assertEqual(hits[0][0].id, "coverage:drop")

    def test_resolve_accepts_curie_label_or_alias(self):
        self.assertEqual(self.kg.resolve("zone:paint").id, "zone:paint")
        self.assertEqual(self.kg.resolve("Paint (Lane)").id, "zone:paint")
        self.assertEqual(self.kg.resolve("corner three").id, "zone:corner-three-left")

    def test_duplicate_ids_rejected(self):
        kg = KnowledgeGraph()
        self.kg.nodes["zone:paint"]
        with self.assertRaises(ValueError):
            from basketball_kg.model import Node

            kg.add(Node(id="zone:paint", type="Zone"))
            kg.add(Node(id="zone:paint", type="Zone"))


if __name__ == "__main__":
    unittest.main()
