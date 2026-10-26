"""Tests for the web explorer's API layer (no sockets: the handlers are tested directly)."""

import json
import re
import unittest

from basketball_kg.serve import WEB_DIR, KnowledgeGraphServer


class TestApi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = KnowledgeGraphServer()

    def test_stats(self):
        stats = self.app.stats()
        self.assertEqual(stats["nodes"], len(self.app.kg))
        self.assertEqual(stats["validation"], {"dangling": [], "bad_ids": [], "bad_types": []})
        self.assertIn("Zone", stats["types"])
        self.assertTrue(stats["datasets"])

    def test_ask_returns_a_plan_and_rows(self):
        payload = self.app.ask("How do you attack a 2-3 zone?")
        self.assertEqual(payload["intent"], "counters")
        self.assertEqual(payload["slots"]["target"], "scheme:zone-2-3")
        self.assertTrue(payload["rows"])
        self.assertTrue(payload["evidence"])
        self.assertIn("SELECT", payload["sparql"])
        self.assertTrue(payload["cypher"].strip().endswith(";"))
        self.assertTrue(payload["pattern"])

    def test_ask_rejects_an_empty_question(self):
        payload = self.app.ask("   ")
        self.assertIn(payload["intent"], {"search", "describe"})

    def test_search_respects_the_type_filter(self):
        payload = self.app.search("corner", types=["Zone"])
        self.assertTrue(payload["rows"])
        self.assertTrue(all(r["type"] == "Zone" for r in payload["rows"]))

    def test_node_detail_has_outgoing_and_incoming(self):
        detail = self.app.node("z23:a4-bottom-middle")
        self.assertEqual(detail["type"], "Assignment")
        self.assertIn("role:rim-protector", str(detail["outgoing"].get("heldBy", "")))
        self.assertIn("zone:paint", str(detail["outgoing"].get("coversZone", "")))
        self.assertTrue(detail["incoming"])
        self.assertIn("digraph", detail["dot"])

    def test_node_falls_back_to_search(self):
        detail = self.app.node("Drop")
        self.assertEqual(detail["id"], "coverage:drop")

    def test_node_missing(self):
        self.assertIn("error", self.app.node("zone:not-a-zone-at-all"))

    def test_graph_focus(self):
        payload = self.app.graph(focus="play:pick-and-roll", depth=1)
        ids = {n["id"] for n in payload["nodes"]}
        self.assertIn("play:pick-and-roll", ids)
        self.assertIn("pnr:s5-roll", ids)
        self.assertNotIn("zone:backcourt", ids)
        self.assertTrue(all("predicate" in link for link in payload["links"]))

    def test_graph_whole_model_is_capped(self):
        payload = self.app.graph()
        self.assertLessEqual(len(payload["nodes"]), 220)

    def test_court_with_scheme_highlights_covered_zones(self):
        payload = self.app.court(scheme="scheme:zone-2-3")
        self.assertIn("zone:corner-three-left", payload["highlighted"])
        self.assertIn("[C3<]", payload["court"])

    def test_court_plain(self):
        self.assertIn("PNT", self.app.court()["court"])

    def test_intents_and_examples(self):
        self.assertIn("counters", self.app.intents()["intents"])
        examples = self.app.examples()
        self.assertTrue(examples["questions"])
        self.assertTrue(examples["plays"])
        # every advertised question must actually return rows
        for question in examples["questions"]:
            with self.subTest(question):
                self.assertTrue(self.app.ask(question)["rows"])

    def test_payloads_are_json_serialisable(self):
        for payload in (self.app.stats(), self.app.ask("what beats drop coverage?"),
                        self.app.graph(focus="play:motion-offense"), self.app.examples()):
            json.dumps(payload, ensure_ascii=False)


class TestLocalizedApi(unittest.TestCase):
    """`lang=` localises the generated explanations (summaries, purposes, court)."""

    @classmethod
    def setUpClass(cls):
        cls.app = KnowledgeGraphServer()

    def test_ask_summary_follows_lang(self):
        en = self.app.ask("How do you attack a 2-3 zone?", lang="en")["summary"]
        fr = self.app.ask("How do you attack a 2-3 zone?", lang="fr")["summary"]
        mg = self.app.ask("How do you attack a 2-3 zone?", lang="mg")["summary"]
        self.assertIn("tactical answer(s) to Zone 2-3", en)
        self.assertIn("réponse(s) tactique(s) contre Zone 2-3", fr)
        self.assertIn("valy taktika", mg)
        # unknown locales fall back to English
        self.assertEqual(self.app.ask("How do you attack a 2-3 zone?", lang="de")["summary"], en)

    def test_ask_lang_is_optional(self):
        self.assertEqual(self.app.ask("What beats drop coverage?")["summary"],
                         self.app.ask("What beats drop coverage?", lang="en")["summary"])

    def test_intents_purpose_follows_lang(self):
        en = self.app.intents()["intents"]["counters"]["purpose"]
        fr = self.app.intents(lang="fr")["intents"]["counters"]["purpose"]
        mg = self.app.intents(lang="mg")["intents"]["counters"]["purpose"]
        self.assertTrue(en.startswith("Tactical answers"))
        self.assertTrue(fr.startswith("Réponses tactiques"))
        self.assertTrue(mg.startswith("Valy taktika"))

    def test_court_title_follows_lang(self):
        for lang, needle in [("en", "Half court"), ("fr", "Demi-terrain"), ("mg", "Tapany kianja")]:
            court = self.app.court(scheme="scheme:zone-2-3", lang=lang)["court"]
            self.assertIn(needle, court.splitlines()[0], lang)


class TestIndexI18n(unittest.TestCase):
    """The explorer's navigation ships in English, French and Malagasy.

    Basketball / graph terminology stays English by design; these tests only
    guarantee that the *chrome* dictionary is well-formed and complete.
    """

    @classmethod
    def setUpClass(cls):
        cls.html = (WEB_DIR / "index.html").read_text(encoding="utf-8")

    def _dictionary(self):
        match = re.search(r"const I18N = (\{.*?\n\});", self.html, re.S)
        self.assertIsNotNone(match, "const I18N dictionary not found in index.html")
        return json.loads(match.group(1))  # strict JSON: fails on trailing commas etc.

    def test_dictionary_has_matching_key_sets(self):
        i18n = self._dictionary()
        self.assertLessEqual({"en", "fr", "mg"}, set(i18n),
                             "navigation must exist in English, French and Malagasy")
        keysets = {frozenset(keys) for keys in i18n.values()}
        self.assertEqual(len(keysets), 1, "all languages must define the same key set")

    def test_every_used_key_is_defined(self):
        i18n = self._dictionary()
        used = set(re.findall(r'data-i18n(?:-ph)?="([^"]+)"', self.html))
        used |= set(re.findall(r't\("([^"]+)"\)', self.html))
        missing = used - set(i18n["en"])
        self.assertEqual(missing, set(), f"i18n keys used in markup/JS but undefined: {sorted(missing)}")

    def test_technical_terms_stay_english(self):
        """The instruction: technical terms in English, navigation localized."""
        i18n = self._dictionary()
        for lang in ("fr", "mg"):
            self.assertEqual(i18n[lang]["ask.placeholder"].split(":")[-1].strip(),
                             i18n["en"]["ask.placeholder"].split(":")[-1].strip(),
                             "the example tactical question must not be translated")
            self.assertIn("scheme", i18n[lang]["scheme.none"],
                          "'scheme' is a technical term and must stay English")


if __name__ == "__main__":
    unittest.main()
