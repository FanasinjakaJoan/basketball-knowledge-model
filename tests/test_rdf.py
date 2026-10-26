"""Tests for the RDF / JSON-LD / SPARQL projection."""

import json
import unittest
from pathlib import Path

from basketball_kg.model import load_graph
from basketball_kg.rdf import (
    build_rdf,
    class_iri,
    jsonld_context,
    resource_iri,
    to_jsonld,
    to_turtle,
    query_sparql,
)

ROOT = Path(__file__).resolve().parents[1]


class TestIriScheme(unittest.TestCase):
    def test_resource_iri_is_stable_and_unique(self):
        self.assertEqual(
            str(resource_iri("zone:corner-three-left")),
            "https://w3id.org/basketball-kg/resource/zone/corner-three-left",
        )
        self.assertNotEqual(str(resource_iri("zone:paint")), str(resource_iri("play:paint")))

    def test_class_iri(self):
        self.assertEqual(
            str(class_iri("OffensivePlay")),
            "https://w3id.org/basketball-kg/ontology#OffensivePlay",
        )


class TestRdfGraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()
        cls.g = build_rdf(cls.kg, include_ontology=True)

    def test_graph_builds_with_triples(self):
        self.assertGreater(len(self.g), 2000)

    def test_ontology_turtle_parses(self):
        from basketball_kg.rdf import load_ontology

        onto = load_ontology()
        self.assertGreater(len(onto), 100)

    def test_turtle_round_trip(self):
        ttl = to_turtle(self.g)
        self.assertIn(str(resource_iri("zone:corner-three-left")), ttl)
        self.assertIn("skos:prefLabel", ttl)
        self.assertIn("a bk:Zone", ttl)
        # the serialised Turtle must parse back into the same number of triples
        from rdflib import Graph

        reparsed = Graph().parse(data=ttl, format="turtle")
        self.assertEqual(len(reparsed), len(self.g))

    def test_types_and_labels_present(self):
        rows = query_sparql(
            self.g,
            """
            PREFIX bk: <https://w3id.org/basketball-kg/ontology#>
            PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
            SELECT ?label WHERE {
              ?zone a bk:Zone ; skos:prefLabel ?label .
              FILTER(?zone = <https://w3id.org/basketball-kg/resource/zone/high-post>)
            }""",
        )
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["label"], "High Post (Free-Throw Line)")

    def test_iris_are_shortened_in_results(self):
        rows = query_sparql(
            self.g,
            """
            PREFIX bk: <https://w3id.org/basketball-kg/ontology#>
            SELECT ?step WHERE {
              ?play bk:hasStep ?step .
              FILTER(?play = <https://w3id.org/basketball-kg/resource/play/motion-offense>)
            } LIMIT 1""",
        )
        self.assertTrue(rows[0]["step"].startswith("mot:"))

    def test_sparql_aggregates_are_used_by_the_example_queries(self):
        rows = query_sparql(self.g, (ROOT / "queries" / "sparql" / "02-zone-2-3-responsibilities.rq").read_text())
        by_assignment = {r["assignment"]: r for r in rows}
        self.assertEqual(len(by_assignment), 5)
        anchor = by_assignment["z23:a4-bottom-middle"]
        self.assertIn("Paint (Lane)", anchor["zones"])
        self.assertEqual(anchor["heldBy"], "role:rim-protector")

    def test_every_published_sparql_example_runs(self):
        directory = ROOT / "queries" / "sparql"
        files = sorted(directory.glob("*.rq"))
        self.assertEqual(len(files), 10)
        for path in files:
            with self.subTest(path.name):
                rows = query_sparql(self.g, path.read_text(encoding="utf-8"))
                self.assertIsInstance(rows, list)
                self.assertTrue(rows, f"{path.name} returned no rows")


class TestJsonLd(unittest.TestCase):
    def test_document_shape(self):
        kg = load_graph()
        doc = json.loads(to_jsonld(kg))
        self.assertIn("@context", doc)
        self.assertEqual(len(doc["@graph"]), len(kg))
        zone = next(n for n in doc["@graph"] if n["id"] == "zone:high-post")
        self.assertEqual(zone["type"], "Zone")
        self.assertEqual(zone["shotValue"], 2)
        self.assertIn("zone:paint", zone["adjacentTo"])

    def test_context_declares_every_id_prefix(self):
        kg = load_graph()
        ctx = jsonld_context()
        prefixes = {node.id.split(":", 1)[0] for node in kg.nodes.values()}
        missing = {p for p in prefixes if p not in ctx}
        self.assertEqual(missing, set(), f"undeclared prefixes: {missing}")

    def test_context_declares_every_predicate(self):
        kg = load_graph()
        ctx = jsonld_context()
        predicates = {p for node in kg.nodes.values() for p in node.edges}
        undeclared = {p for p in predicates if p not in ctx and p not in ("type",)}
        self.assertEqual(undeclared, set(), f"undeclared predicates: {undeclared}")


if __name__ == "__main__":
    unittest.main()
