"""End-to-end tests for the command line interface."""

import io
import json
import unittest
from contextlib import redirect_stdout

from basketball_kg.cli import main


def run(*argv):
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(list(argv))
    return code, buffer.getvalue()


class TestCli(unittest.TestCase):
    def test_validate_is_clean(self):
        code, out = run("validate")
        self.assertEqual(code, 0, out)
        self.assertIn("no dangling references", out)

    def test_stats(self):
        code, out = run("stats")
        self.assertEqual(code, 0)
        self.assertIn("node types", out)
        self.assertIn("predicates", out)

    def test_intents_listing(self):
        code, out = run("intents")
        self.assertEqual(code, 0)
        self.assertIn("counters", out)
        self.assertIn("zone_responsibility", out)

    def test_ask_text(self):
        code, out = run("ask", "How do you attack a 2-3 zone?")
        self.assertEqual(code, 0)
        self.assertIn("counters", out)
        self.assertIn("high post", out.lower())

    def test_ask_json(self):
        code, out = run("ask", "How do you attack a 2-3 zone?", "-f", "json")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertEqual(payload["intent"], "counters")
        self.assertTrue(payload["rows"])

    def test_ask_sparql_and_cypher(self):
        code, sparql = run("ask", "Who covers the corner in a 2-3 zone?", "-f", "sparql")
        self.assertEqual(code, 0)
        self.assertIn("SELECT", sparql)
        code, cypher = run("ask", "Who covers the corner in a 2-3 zone?", "-f", "cypher")
        self.assertEqual(code, 0)
        self.assertIn("MATCH", cypher)

    def test_ask_with_parse_trace(self):
        code, out = run("ask", "What beats drop coverage?", "--show-query")
        self.assertEqual(code, 0)
        self.assertIn("rule:counters", out)
        self.assertIn("slot:target", out)

    def test_structured_query(self):
        code, out = run("query", "play_steps", "--play", "play:motion-offense")
        self.assertEqual(code, 0)
        self.assertIn("Pass the ball", out)

    def test_structured_query_list(self):
        code, out = run("query", "list")
        self.assertEqual(code, 0)
        self.assertIn("play_steps", out)

    def test_export_dot_to_file(self, ):
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "pnr.dot"
            code, out = run("export", "-f", "dot", "--focus", "play:pick-and-roll", "--out", str(target))
            self.assertEqual(code, 0)
            self.assertTrue(target.exists())
            self.assertIn("digraph", target.read_text())

    def test_export_jsonld(self):
        code, out = run("export", "-f", "jsonld")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertIn("@graph", payload)

    def test_export_json(self):
        code, out = run("export", "-f", "json", "--focus", "play:zone-defense-2-3")
        self.assertEqual(code, 0)
        payload = json.loads(out)
        self.assertTrue(payload["nodes"])
        self.assertIn("play:zone-defense-2-3", [n["id"] for n in payload["nodes"]])

    def test_export_dot_focus_keeps_the_neighbourhood(self):
        code, out = run("export", "-f", "dot", "--focus", "play:zone-defense-2-3")
        self.assertEqual(code, 0)
        self.assertIn("play:zone-defense-2-3", out)
        self.assertIn("z23:a4-bottom-middle", out)
        self.assertNotIn("pnr:s5-roll", out)

    def test_court(self):
        code, out = run("court")
        self.assertEqual(code, 0)
        self.assertIn("PNT", out)

    def test_court_with_scheme(self):
        code, out = run("court", "--scheme", "scheme:zone-2-3")
        self.assertEqual(code, 0)
        self.assertIn("covers", out)
        self.assertIn("[C3<]", out)

    def test_sparql_file(self):
        code, out = run("sparql", "--file", "queries/sparql/04-rules-for-screening.rq")
        self.assertEqual(code, 0)
        self.assertIn("Legal screening", out)


if __name__ == "__main__":
    unittest.main()
