"""Server-side localisation: the generated explanations ship in en/fr/mg.

Technical terms (play, scheme, coverage, node, intent names…) and all graph
content stay English in every locale by project convention — these tests guard
the *sentence frames* only.
"""

import re
import unittest

from basketball_kg.i18n import DEFAULT_LANG, LOCALES, Translator, normalize_lang
from basketball_kg.nlq import answer
from basketball_kg.queries import INTENTS, intent_help
from basketball_kg.model import load_graph


class TestCatalogParity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from basketball_kg.i18n import _CATALOG

        cls.catalog = _CATALOG

    def test_three_locales(self):
        self.assertEqual(set(self.catalog), set(LOCALES))
        self.assertIn(DEFAULT_LANG, LOCALES)

    def test_same_key_set_everywhere(self):
        keysets = {frozenset(keys) for keys in self.catalog.values()}
        self.assertEqual(len(keysets), 1, "every locale must define the same keys")

    def test_same_placeholders_everywhere(self):
        en = self.catalog["en"]
        for key, template in en.items():
            wanted = set(re.findall(r"{(\w+)}", template))
            for loc in LOCALES:
                got = set(re.findall(r"{(\w+)}", self.catalog[loc][key]))
                self.assertEqual(got, wanted, f"placeholder mismatch for {key!r} in {loc}")

    def test_every_intent_has_a_localised_purpose(self):
        for intent in INTENTS:
            for loc in LOCALES:
                self.assertTrue(self.catalog[loc][f"intent.purpose.{intent}"])


class TestNormalizeLang(unittest.TestCase):
    def test_known_locales(self):
        for raw, want in [("en", "en"), ("fr", "fr"), ("mg", "mg"),
                          ("fr_FR", "fr"), ("fr-FR", "fr"), ("mg-MG", "mg")]:
            self.assertEqual(normalize_lang(raw), want)

    def test_fallback_is_english(self):
        for raw in ("xx", "", None, "de_DE", "english"):
            self.assertEqual(normalize_lang(raw), "en")


class TestTranslator(unittest.TestCase):
    def test_fallback_to_english_key(self):
        t = Translator("fr")
        self.assertEqual(t("summary.search", n=3, text=repr("weak side")), "3 correspondance(s) pour 'weak side'")
        self.assertEqual(Translator("mg")("summary.search", n=3, text=repr("weak side")),
                         "3 valiny mifanaraka amin'ny 'weak side'")

    def test_english_output_is_stable(self):
        t = Translator("en")
        self.assertEqual(t("summary.counters", n=5, target="Zone 2-3"), "5 tactical answer(s) to Zone 2-3")
        self.assertEqual(t("summary.play_steps", name="Pick and Roll", steps=19, decisions=1, formation="4-Out-1-In"),
                         "Pick and Roll: 19 steps, 1 decision point(s). Formation: 4-Out-1-In")


class TestLocalizedExplanations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.kg = load_graph()

    def _answer(self, question, lang):
        return answer(self.kg, question, lang=lang)

    def test_zone_responsibility_summary(self):
        en = self._answer("Who covers the corner in a 2-3 zone?", "en").summary
        fr = self._answer("Who covers the corner in a 2-3 zone?", "fr").summary
        mg = self._answer("Who covers the corner in a 2-3 zone?", "mg").summary
        self.assertTrue(en.startswith("Left Corner Three is covered by"), en)
        self.assertIn("est couverte par", fr)
        self.assertIn("dia rakotry ny", mg)
        # the graph content stays English in every locale
        for summary in (en, fr, mg):
            self.assertIn("Left Corner Three", summary)
            self.assertIn("Zone 2-3 Defence", summary)

    def test_counters_summary(self):
        fr = self._answer("How do you attack a 2-3 zone?", "fr").summary
        self.assertIn("réponse(s) tactique(s) contre Zone 2-3", fr)

    def test_play_steps_summary(self):
        fr = self._answer("Walk me through the pick and roll.", "fr").summary
        self.assertIn("point(s) de décision", fr)
        self.assertIn("Formation :", fr)

    def test_french_and_malagasy_purposes_differ_from_english(self):
        for intent in INTENTS:
            texts = {Translator(loc).purpose(intent) for loc in LOCALES}
            self.assertEqual(len(texts), 3, f"purposes for {intent} must differ per locale")

    def test_intent_help_is_localised(self):
        self.assertIn("query intents", intent_help("en").splitlines()[0])
        self.assertIn("Intents de requête", intent_help("fr").splitlines()[0])
        self.assertIn("graph fahalalana basketball", intent_help("mg").splitlines()[0])


if __name__ == "__main__":
    unittest.main()
