"""Tests for the DOT export and the ASCII court renderer."""

import unittest

from basketball_kg.graph import graph_stats, subgraph_around, to_networkx, to_node_link
from basketball_kg.model import load_graph
from basketball_kg.viz import ZONE_CODES, ascii_court, to_dot


class TestNetworkX(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()
        cls.g = to_networkx(cls.kg)

    def test_projection_size_matches_the_model(self):
        self.assertEqual(self.g.number_of_nodes(), len(self.kg))

    def test_every_edge_carries_a_predicate(self):
        for _, _, data in self.g.edges(data=True):
            self.assertIn("predicate", data)

    def test_stats(self):
        stats = graph_stats(self.g)
        self.assertEqual(stats["nodes"], len(self.kg))
        self.assertIn("Action", stats["node_types"])
        self.assertIn("hasStep", stats["predicates"])
        self.assertGreater(stats["most_connected"][0]["degree"], 10)

    def test_subgraph_around_a_play(self):
        sub = subgraph_around(self.g, ["play:pick-and-roll"], depth=1)
        self.assertIn("pnr:s5-roll", sub.nodes)
        self.assertNotIn("zone:backcourt", sub.nodes)

    def test_node_link_payload(self):
        payload = to_node_link(self.g)
        self.assertTrue(payload["directed"])
        self.assertEqual(len(payload["nodes"]), len(self.kg))
        self.assertTrue(all("predicate" in link for link in payload["links"]))


class TestDot(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        self_kg = load_graph()
        cls.kg = self_kg

    def test_dot_is_well_formed(self):
        dot = to_dot(self.kg)
        self.assertTrue(dot.startswith("digraph"))
        self.assertTrue(dot.rstrip().endswith("}"))
        self.assertEqual(dot.count("{"), dot.count("}"))

    def test_dot_focus_limits_the_graph(self):
        full = to_dot(self.kg)
        focused = to_dot(self.kg, node_ids={"play:pick-and-roll", "pnr:s5-roll"})
        self.assertLess(len(focused), len(full))
        self.assertIn("pnr:s5-roll", focused)
        self.assertNotIn("zone:backcourt", focused)

    def test_dot_predicate_filter(self):
        dot = to_dot(self.kg, predicates=["adjacentTo"])
        self.assertIn("adjacentTo", dot)
        self.assertNotIn("hasStep", dot)

    def test_dot_escapes_quotes(self):
        node = self.kg["zone:corner-three-left"]
        node.props["note"] = 'the "dead" spot'
        try:
            dot = to_dot(self.kg, node_ids={"zone:corner-three-left"})
            self.assertNotIn('"dead"', dot)
        finally:
            del node.props["note"]

    def test_definitions_can_be_embedded(self):
        dot = to_dot(self.kg, node_ids={"zone:high-post"}, show_definitions=True)
        self.assertIn("\\n", dot)


class TestCourt(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()

    def test_all_zones_are_drawn(self):
        court = ascii_court(self.kg)
        for code in ZONE_CODES.values():
            self.assertIn(code, court)

    def test_highlight_marks_zones(self):
        court = ascii_court(self.kg, highlight=["zone:corner-three-left"])
        self.assertIn("[C3<]", court)
        self.assertIn("highlighted: Left Corner Three", court)

    def test_highlight_accepts_labels(self):
        court = ascii_court(self.kg, highlight=["High Post (Free-Throw Line)"])
        self.assertIn("[HP]", court)

    def test_lines_are_consistent(self):
        court = ascii_court(self.kg)
        body = [line for line in court.splitlines() if line.startswith("|")]
        self.assertTrue(body)
        widths = {len(line.rstrip()) for line in body}
        self.assertLessEqual(max(widths) - min(widths), 2)


if __name__ == "__main__":
    unittest.main()
