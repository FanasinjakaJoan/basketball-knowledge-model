"""Server-side localisation of the *generated explanations*.

Scope (by project convention):

* Everything the app itself **explains** — answer summaries, intent purposes,
  the court header — is available in English, French and Malagasy.
* Basketball and graph **terminology stays English in every locale**
  ("pick and roll", "drop coverage", "scheme", "node", "play", "rule",
  intent names…), and so does all graph *content* (labels, definitions).
  Only the sentence frames around those terms are translated.

Templates use ``str.format`` named placeholders. Tests enforce that every
locale defines the same key set *and* the same placeholder names per key.
"""

from __future__ import annotations

from typing import Any, Dict

__all__ = ["LOCALES", "DEFAULT_LANG", "normalize_lang", "Translator"]

LOCALES = ("en", "fr", "mg")
DEFAULT_LANG = "en"

_CATALOG: Dict[str, Dict[str, str]] = {
    # ------------------------------------------------------------------ EN -- #
    "en": {
        # intent purposes -------------------------------------------------
        "intent.purpose.describe": "Explain any node: a play, scheme, zone, archetype, rule or coverage.",
        "intent.purpose.play_steps": "List the ordered steps of a play with actor, zones, requirements and constraints.",
        "intent.purpose.zone_responsibility": "Which defender/role is responsible for a zone in a defensive scheme.",
        "intent.purpose.counters": "Tactical answers to a scheme, coverage or play, and the weakness each exploits.",
        "intent.purpose.rules": "The rules that constrain a play, action type or zone.",
        "intent.purpose.requirements": "The archetypes and skills a scheme, play or action demands.",
        "intent.purpose.fit": "Which players on a roster satisfy a scheme's archetype requirements.",
        "intent.purpose.situations": "Which schemes or plays apply in a given game situation.",
        "intent.purpose.spatial": "Geometry of a zone: neighbours, shot value, containment and distance.",
        "intent.purpose.sequence": "What happens before and after a given step.",
        "intent.purpose.compare": "Put two schemes, coverages or archetypes side by side.",
        "intent.purpose.search": "Fallback ranked search across the whole graph.",
        # intent listing ---------------------------------------------------
        "help.title": "Basketball knowledge query intents",
        "help.eg": "e.g.",
        # answer summaries -------------------------------------------------
        "summary.describe": "{name} [{type}] — {definition}",
        "summary.describe.key": "coaching key",
        "summary.describe.steps": "{n} steps",
        "summary.play_steps": "{name}: {steps} steps, {decisions} decision point(s). Formation: {formation}",
        "summary.play_steps.none": "No play matched.",
        "summary.zone_responsibility.zone": "{name} is covered by {n} assignment(s)",
        "summary.zone_responsibility.in": " in {schemes}",
        "summary.zone_responsibility.scheme": "{name}: {n} area assignments",
        "summary.counters": "{n} tactical answer(s) to {target}",
        "summary.counters.none": "No target matched.",
        "summary.rules": "{n} rule(s) constrain {target}",
        "summary.rules.none": "No target matched.",
        "summary.requirements": "{target} requires {n} archetype(s)/skill(s)",
        "summary.requirements.none": "No target matched.",
        "summary.fit": "{name} needs: {items}",
        "summary.fit.none": "No scheme matched.",
        "summary.situations": "{n} scheme(s)/play(s) apply in {sit}",
        "summary.situations.none": "No situation matched.",
        "summary.spatial.all": "All scorable zones, highest shot value first.",
        "summary.spatial.zone": "{name}: shot value {value}, {n} adjacent zone(s)",
        "summary.sequence": "{name}: {prev} predecessor(s), {next} successor(s)",
        "summary.sequence.none": "No step matched.",
        "summary.compare": "{a} vs {b}",
        "summary.compare.none": "(not found)",
        "summary.search": "{n} match(es) for {text}",
        # court -------------------------------------------------------------
        "court.title": "Half court (offensive basket at the bottom)",
        "court.covers": "# {name} covers {n} zone(s): {zones}",
    },
    # ------------------------------------------------------------------ FR -- #
    "fr": {
        "intent.purpose.describe": "Explique n'importe quel node : un play, un scheme, une zone, un archetype, une rule ou une coverage.",
        "intent.purpose.play_steps": "Liste les steps ordonnés d'un play : acteur, zones, requirements et contraintes.",
        "intent.purpose.zone_responsibility": "Quel défenseur / role est responsable d'une zone dans un scheme défensif.",
        "intent.purpose.counters": "Réponses tactiques contre un scheme, une coverage ou un play, et la faiblesse exploitée par chacune.",
        "intent.purpose.rules": "Les rules qui encadrent un play, un action type ou une zone.",
        "intent.purpose.requirements": "Les archetypes et skills qu'exige un scheme, un play ou une action.",
        "intent.purpose.fit": "Quels joueurs d'un roster satisfont les archetype requirements d'un scheme.",
        "intent.purpose.situations": "Quels schemes ou plays s'appliquent dans une situation de jeu donnée.",
        "intent.purpose.spatial": "Géométrie d'une zone : voisins, valeur de tir, containment et distance.",
        "intent.purpose.sequence": "Ce qui se passe avant et après un step donné.",
        "intent.purpose.compare": "Compare deux schemes, coverages ou archetypes côte à côte.",
        "intent.purpose.search": "Recherche classée de secours dans tout le graphe.",
        "help.title": "Intents de requête sur la base de connaissances basketball",
        "help.eg": "ex.",
        "summary.describe": "{name} [{type}] — {definition}",
        "summary.describe.key": "clé de coaching",
        "summary.describe.steps": "{n} steps",
        "summary.play_steps": "{name} : {steps} steps, {decisions} point(s) de décision. Formation : {formation}",
        "summary.play_steps.none": "Aucun play correspondant.",
        "summary.zone_responsibility.zone": "{name} est couverte par {n} affectation(s)",
        "summary.zone_responsibility.in": " dans {schemes}",
        "summary.zone_responsibility.scheme": "{name} : {n} affectations de zones",
        "summary.counters": "{n} réponse(s) tactique(s) contre {target}",
        "summary.counters.none": "Aucune cible correspondante.",
        "summary.rules": "{n} rule(s) encadrent {target}",
        "summary.rules.none": "Aucune cible correspondante.",
        "summary.requirements": "{target} exige {n} archetype(s)/skill(s)",
        "summary.requirements.none": "Aucune cible correspondante.",
        "summary.fit": "{name} nécessite : {items}",
        "summary.fit.none": "Aucun scheme correspondant.",
        "summary.situations": "{n} scheme(s)/play(s) s'appliquent dans {sit}",
        "summary.situations.none": "Aucune situation correspondante.",
        "summary.spatial.all": "Toutes les zones scorables, de la meilleure valeur de tir à la plus faible.",
        "summary.spatial.zone": "{name} : valeur de tir {value}, {n} zone(s) adjacente(s)",
        "summary.sequence": "{name} : {prev} prédécesseur(s), {next} successeur(s)",
        "summary.sequence.none": "Aucun step correspondant.",
        "summary.compare": "{a} vs {b}",
        "summary.compare.none": "(introuvable)",
        "summary.search": "{n} correspondance(s) pour {text}",
        "court.title": "Demi-terrain (panier offensif en bas)",
        "court.covers": "# {name} couvre {n} zone(s) : {zones}",
    },
    # ------------------------------------------------------------------ MG -- #
    "mg": {
        "intent.purpose.describe": "Manazava node iray na maro : play, scheme, zone, archetype, rule na coverage.",
        "intent.purpose.play_steps": "Mampiseho ny steps mifandimby ao amin'ny play : mpandray anjara, zones, requirements ary famerana.",
        "intent.purpose.zone_responsibility": "Iza amin'ny mpilalao / role no tompon'andraikitra amin'ny zone iray ao amin'ny defensive scheme.",
        "intent.purpose.counters": "Valy taktika mifanohitra amin'ny scheme, coverage na play iray, miaraka amin'ny tsy fahampiana ampiasain'ny tsirairay.",
        "intent.purpose.rules": "Ny rules mifehy ny play, action type na zone iray.",
        "intent.purpose.requirements": "Ny archetypes sy skills takiana amin'ny scheme, play na action iray.",
        "intent.purpose.fit": "Iza amin'ny mpilalao ao amin'ny roster no mifanaraka amin'ny archetype takian'ny scheme.",
        "intent.purpose.situations": "Inona ny schemes na plays mihatra amin'ny toe-javatra iray amin'ny lalao.",
        "intent.purpose.spatial": "Jeografin'ny zone iray : mpifanila, lanjan'ny baoty, containment ary halavirana.",
        "intent.purpose.sequence": "Inona no mitranga aloha sy aorian'ny step iray.",
        "intent.purpose.compare": "Ampitahana amin'ny lafiny iray ny schemes, coverages na archetypes roa.",
        "intent.purpose.search": "Fikarohana misokatra manerana ny graph manontolo.",
        "help.title": "Intents fanontaniana amin'ny graph fahalalana basketball",
        "help.eg": "ohatra:",
        "summary.describe": "{name} [{type}] — {definition}",
        "summary.describe.key": "fanalahidin'ny coaching",
        "summary.describe.steps": "{n} steps",
        "summary.play_steps": "{name}: {steps} steps, {decisions} teboka fanapahan-kevitra. Formation: {formation}",
        "summary.play_steps.none": "Tsy nisy play mifanaraka.",
        "summary.zone_responsibility.zone": "{name} dia rakotry ny {n} assignment",
        "summary.zone_responsibility.in": " ao amin'ny {schemes}",
        "summary.zone_responsibility.scheme": "{name}: {n} assignments amin'ny faritra",
        "summary.counters": "{n} valy taktika mifanohitra amin'ny {target}",
        "summary.counters.none": "Tsy nisy tanjona mifanaraka.",
        "summary.rules": "{n} rule mifehy {target}",
        "summary.rules.none": "Tsy nisy tanjona mifanaraka.",
        "summary.requirements": "{target} mitaky {n} archetype/skill",
        "summary.requirements.none": "Tsy nisy tanjona mifanaraka.",
        "summary.fit": "{name} mila: {items}",
        "summary.fit.none": "Tsy nisy scheme mifanaraka.",
        "summary.situations": "{n} scheme/play mihatra ao amin'ny {sit}",
        "summary.situations.none": "Tsy nisy situation mifanaraka.",
        "summary.spatial.all": "Ny zone rehetra azo baotina, ny lanjan'ny baoty ambony indrindra aloha.",
        "summary.spatial.zone": "{name}: lanjan'ny baoty {value}, {n} zone mifanila aminy",
        "summary.sequence": "{name}: {prev} eo aloha, {next} eo aoriany",
        "summary.sequence.none": "Tsy nisy step mifanaraka.",
        "summary.compare": "{a} vs {b}",
        "summary.compare.none": "(tsy hita)",
        "summary.search": "{n} valiny mifanaraka amin'ny {text}",
        "court.title": "Tapany kianja (ny panier hanafihana eo ambany)",
        "court.covers": "# {name} mandrakotra {n} zone : {zones}",
    },
}


def normalize_lang(value: Any) -> str:
    """Map any incoming value to a supported locale (fallback: English)."""
    lang = str(value or "").strip().lower().replace("-", "_").split("_")[0]
    return lang if lang in LOCALES else DEFAULT_LANG


class Translator:
    """``t(key, **kw)`` renders a catalog template in the chosen locale."""

    def __init__(self, lang: Any = DEFAULT_LANG) -> None:
        self.lang = normalize_lang(lang)

    def __call__(self, key: str, **kwargs: Any) -> str:
        template = _CATALOG[self.lang].get(key) or _CATALOG[DEFAULT_LANG][key]
        return template.format(**kwargs) if kwargs else template

    def purpose(self, intent: str) -> str:
        return self(f"intent.purpose.{intent}")
