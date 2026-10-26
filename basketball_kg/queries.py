"""Knowledge retrieval: intent -> query plan -> SPARQL / Cypher / in-memory result.

The same :class:`QueryPlan` is rendered three ways:

* **SPARQL** for the RDF graph (``basketball_kg.rdf``);
* **Cypher** for a labelled property graph (Neo4j / NetworkX via ``graph.py``);
* **in-memory** against :class:`KnowledgeGraph`, which is what the CLI answers with.

That triad is the point: one tactical question, three interchangeable back ends.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence

from .i18n import Translator
from .model import KnowledgeGraph, Node

__all__ = ["QueryPlan", "QueryResult", "INTENTS", "intent_help", "run_intent"]


# --------------------------------------------------------------------------- #
# Small helpers
# --------------------------------------------------------------------------- #


def label_of(kg: KnowledgeGraph, node_id: str) -> str:
    node = kg.get(node_id)
    if node is None:
        return node_id
    return node.label or node.local_name


def labels_of(kg: KnowledgeGraph, ids: Sequence[str]) -> List[str]:
    return [label_of(kg, i) for i in ids]


def _camel_to_screaming(name: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", name).upper()


def _order_key(kg: KnowledgeGraph, node_id: str) -> tuple:
    node = kg.get(node_id)
    if node is None:
        return (9999, node_id)
    value = node.props.get("order", 9999)
    try:
        return (float(value), node_id)
    except (TypeError, ValueError):
        return (9999.0, node_id)


def _iri(node_id: str) -> str:
    prefix, _, local = node_id.partition(":")
    if not local:
        prefix, local = "resource", prefix
    return f"https://w3id.org/basketball-kg/resource/{prefix}/{local}"


_SPARQL_PREFIXES = """PREFIX bk:   <https://w3id.org/basketball-kg/ontology#>
PREFIX bkr:  <https://w3id.org/basketball-kg/resource/>
PREFIX skos: <http://www.w3.org/2004/02/skos/core#>
"""


# --------------------------------------------------------------------------- #
# Result / plan containers
# --------------------------------------------------------------------------- #


@dataclass
class QueryResult:
    intent: str
    rows: List[Dict[str, Any]] = field(default_factory=list)
    summary: str = ""
    plan: Optional["QueryPlan"] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "summary": self.summary,
            "rows": self.rows,
            "slots": self.plan.slots if self.plan else {},
        }


@dataclass
class QueryPlan:
    """A structured, back-end-agnostic basketball query."""

    intent: str
    slots: Dict[str, Any] = field(default_factory=dict)
    description: str = ""
    confidence: float = 1.0
    evidence: List[str] = field(default_factory=list)

    # -- execution --------------------------------------------------------- #
    def execute(self, kg: KnowledgeGraph, lang: str = "en") -> QueryResult:
        handler = _EXECUTORS.get(self.intent)
        if handler is None:
            raise ValueError(f"unknown intent: {self.intent}")
        rows, summary = handler(kg, self.slots, Translator(lang))
        return QueryResult(intent=self.intent, rows=rows, summary=summary, plan=self)

    # -- renderings -------------------------------------------------------- #
    def to_sparql(self) -> str:
        renderer = _SPARQL.get(self.intent)
        if renderer is None:
            return "-- no SPARQL template for this intent"
        return renderer(self.slots)

    def to_cypher(self) -> str:
        renderer = _CYPHER.get(self.intent)
        if renderer is None:
            return "-- no Cypher template for this intent"
        return renderer(self.slots)

    def to_json(self) -> Dict[str, Any]:
        return {
            "intent": self.intent,
            "slots": self.slots,
            "description": self.description,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "graph_pattern": self.to_graph_pattern(),
            "sparql": self.to_sparql(),
            "cypher": self.to_cypher(),
        }

    def to_graph_pattern(self) -> List[Dict[str, str]]:
        """The abstract triple pattern the intent is asking for."""
        return [dict(t) for t in _PATTERNS.get(self.intent, lambda s: [])(self.slots)]


# --------------------------------------------------------------------------- #
# Intent catalogue
# --------------------------------------------------------------------------- #

INTENTS: Dict[str, Dict[str, Any]] = {
    "describe": {
        "slots": ["target"],
        "purpose": "Explain any node: a play, scheme, zone, archetype, rule or coverage.",
        "examples": ["What is drop coverage?", "Describe the short corner.", "What is a hub playmaker?"],
    },
    "play_steps": {
        "slots": ["play"],
        "purpose": "List the ordered steps of a play with actor, zones, requirements and constraints.",
        "examples": ["Walk me through the pick and roll.", "What are the steps of motion offence?"],
    },
    "zone_responsibility": {
        "slots": ["zone", "scheme"],
        "purpose": "Which defender/role is responsible for a zone in a defensive scheme.",
        "examples": ["Who covers the corner in a 2-3 zone?", "What are the 2-3 zone assignments?"],
    },
    "counters": {
        "slots": ["target"],
        "purpose": "Tactical answers to a scheme, coverage or play, and the weakness each exploits.",
        "examples": ["How do you attack a 2-3 zone?", "What beats drop coverage?", "What counters the pick and roll?"],
    },
    "rules": {
        "slots": ["target"],
        "purpose": "The rules that constrain a play, action type or zone.",
        "examples": ["What rules govern setting a screen?", "Is a moving screen legal?", "What constrains the roll man?"],
    },
    "requirements": {
        "slots": ["target"],
        "purpose": "The archetypes and skills a scheme, play or action demands.",
        "examples": ["What kind of player can run a short roll?", "What does switch-all require?"],
    },
    "fit": {
        "slots": ["scheme", "team"],
        "purpose": "Which players on a roster satisfy a scheme's archetype requirements.",
        "examples": ["Who on Harbour fits switch all?", "Which players can run the pick and roll?"],
    },
    "situations": {
        "slots": ["situation"],
        "purpose": "Which schemes or plays apply in a given game situation.",
        "examples": ["What should we run against a press?", "What works late in the shot clock?"],
    },
    "spatial": {
        "slots": ["zone"],
        "purpose": "Geometry of a zone: neighbours, shot value, containment and distance.",
        "examples": ["What is next to the short corner?", "Where is the high post?", "Which zone has the highest shot value?"],
    },
    "sequence": {
        "slots": ["action"],
        "purpose": "What happens before and after a given step.",
        "examples": ["What happens after the roll?", "What comes before the skip pass?"],
    },
    "compare": {
        "slots": ["a", "b"],
        "purpose": "Put two schemes, coverages or archetypes side by side.",
        "examples": ["Compare drop and blitz.", "What is the difference between hedge and ICE?"],
    },
    "search": {
        "slots": ["text"],
        "purpose": "Fallback ranked search across the whole graph.",
        "examples": ["nail help", "weak side"],
    },
}


def intent_help(lang: str = "en") -> str:
    t = Translator(lang)
    lines = [t("help.title"), "=" * 62]
    for name, meta in INTENTS.items():
        lines.append(f"\n{name}  ({', '.join(meta['slots'])})")
        lines.append(f"  {t.purpose(name)}")
        lines.append(f"  {t('help.eg')} {meta['examples'][0]}")
    return "\n".join(lines)


def run_intent(kg: KnowledgeGraph, intent: str, lang: str = "en", **slots: Any) -> QueryResult:
    """Build a plan for ``intent``/``slots`` and execute it against ``kg``."""
    return QueryPlan(intent=intent, slots={k: v for k, v in slots.items() if v}).execute(kg, lang=lang)


# --------------------------------------------------------------------------- #
# Executors (in-memory)
# --------------------------------------------------------------------------- #


def _describe(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    target = slots.get("target")
    node = kg.get(target) if target else None
    if node is None:
        return [], t("summary.describe.none")
    rows = [
        {
            "id": node.id,
            "type": node.type,
            "label": node.name,
            "definition": node.definition,
        }
    ]
    for key in node.keys():
        rows.append({"id": node.id, "type": "key", "label": t("summary.describe.key"), "definition": key})
    if node.type in {"Play", "OffensivePlay", "DefensivePlay"}:
        steps = sorted(node.out("hasStep"), key=lambda s: _order_key(kg, s))
        rows.append({"id": node.id, "type": "steps", "label": t("summary.describe.steps", n=len(steps)), "definition": ", ".join(labels_of(kg, steps))})
    summary = t("summary.describe", name=node.name, type=node.type, definition=node.definition)
    return rows, summary


def _play_steps(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    play_id = slots.get("play")
    play = kg.get(play_id) if play_id else None
    if play is None:
        return [], t("summary.play_steps.none")
    # `stepOf` is inverted into `hasStep`, so decisions also arrive here: split them out
    steps = sorted(
        (s for s in play.out("hasStep") if kg.get(s) and kg[s].type != "Decision"),
        key=lambda s: _order_key(kg, s),
    )
    rows = []
    for step_id in steps:
        step = kg[step_id]
        action_types = step.out("hasActionType")
        actor = step.out("actor")
        rows.append(
            {
                "order": step.props.get("order"),
                "step": step_id,
                "label": step.name,
                "actionType": ", ".join(labels_of(kg, action_types)),
                "actor": ", ".join(labels_of(kg, actor)),
                "from": ", ".join(labels_of(kg, step.out("startsIn"))),
                "to": ", ".join(labels_of(kg, step.out("endsIn"))) or ", ".join(labels_of(kg, step.out("occursIn"))),
                "requires": ", ".join(labels_of(kg, step.out("requires"))),
                "constrainedBy": ", ".join(labels_of(kg, step.out("constrainedBy"))),
                "produces": ", ".join(labels_of(kg, step.out("produces"))),
                "branch": step.props.get("branch", ""),
                "definition": step.definition,
            }
        )
    decisions = play.out("hasDecision") or kg.in_(play.id, "stepOf")
    decisions = [d for d in decisions if (kg.get(d) and kg[d].type == "Decision")]
    for dec_id in decisions:
        dec = kg[dec_id]
        rows.append(
            {
                "order": dec.props.get("order"),
                "step": dec_id,
                "label": f"DECISION — {dec.name}",
                "actionType": "read",
                "actor": "",
                "from": "",
                "to": "",
                "requires": "",
                "constrainedBy": "",
                "produces": ", ".join(labels_of(kg, dec.out("selectedOption"))),
                "branch": "",
                "definition": dec.definition,
            }
        )
    rows.sort(key=lambda r: (float(r["order"]) if r["order"] not in (None, "") else 9999, r["step"]))
    summary = t("summary.play_steps", name=play.name, steps=len(steps), decisions=len(decisions), formation=label_of(kg, play.out('hasFormation')[0]) if play.out('hasFormation') else 'n/a')
    return rows, summary


def _assignments_of(kg: KnowledgeGraph, scheme_id: str) -> List[str]:
    """Assignments attached to a scheme or play node (via ofScheme/hasAssignment)."""
    node = kg.get(scheme_id)
    found = node.out("hasAssignment") if node else []
    found += [a for a in kg.in_(scheme_id, "ofScheme") if (kg.get(a) and kg[a].type == "Assignment")]
    return found


def _zone_responsibility(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    zone_id = slots.get("zone")
    scheme_id = slots.get("scheme")
    assignments: List[str] = []
    if zone_id:
        assignments = [a for a in kg.in_(zone_id, "coversZone") if (kg.get(a) and kg[a].type == "Assignment")]
    elif scheme_id:
        assignments = _assignments_of(kg, scheme_id)
        if not assignments:
            # the area duties may live on the play graph that models the scheme
            node = kg.get(scheme_id)
            for linked in (node.out("relatedTo") + kg.in_(scheme_id, "relatedTo")) if node else []:
                assignments.extend(_assignments_of(kg, linked))
    assignments = sorted(set(assignments))
    rows = []
    for a_id in assignments:
        node = kg[a_id]
        held = node.out("heldBy")
        zones = node.out("coversZone")
        rows.append(
            {
                "assignment": a_id,
                "label": node.name,
                "heldBy": ", ".join(labels_of(kg, held)),
                "coversZones": ", ".join(labels_of(kg, zones)),
                "ofScheme": ", ".join(labels_of(kg, node.out("ofScheme"))),
                "requires": ", ".join(labels_of(kg, node.out("requires"))),
                "definition": node.definition,
            }
        )
    if zone_id:
        summary = t("summary.zone_responsibility.zone", name=label_of(kg, zone_id), n=len(rows)) + (t("summary.zone_responsibility.in", schemes=', '.join(sorted({r['ofScheme'] for r in rows}))) if rows else "")
    else:
        summary = t("summary.zone_responsibility.scheme", name=label_of(kg, scheme_id), n=len(rows))
    return rows, summary


def _counters(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    target_id = slots.get("target")
    target = kg.get(target_id) if target_id else None
    if target is None:
        return [], t("summary.counters.none")
    counter_ids = set(target.out("hasCounter"))
    counter_ids |= {c for c in kg.in_(target_id, "answers") if kg.get(c) and kg[c].type == "Counter"}
    counter_ids |= {c for c in kg.in_(target_id, "exploits") if kg.get(c) and kg[c].type == "Counter"}
    counter_ids |= set(target.out("counteredBy"))
    rows = []
    for c_id in sorted(counter_ids):
        node = kg[c_id]
        if node.type != "Counter":
            continue
        rows.append(
            {
                "counter": c_id,
                "label": node.name,
                "answers": ", ".join(labels_of(kg, node.out("answers"))),
                "exploits": ", ".join(labels_of(kg, node.out("exploits"))),
                "vulnerability": node.props.get("vulnerability", ""),
                "rationale": node.props.get("rationale", node.definition),
                "effectiveness": node.props.get("effectiveness", ""),
                "key": " | ".join(node.keys()),
            }
        )
    summary = t("summary.counters", n=len(rows), target=target.name)
    return rows, summary


def _rules(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    target_id = slots.get("target")
    target = kg.get(target_id) if target_id else None
    if target is None:
        return [], t("summary.rules.none")
    rule_ids = set(target.out("constrainedBy"))
    rule_ids |= set(kg.in_(target_id, "governs"))
    if target.type == "Rule":
        rule_ids.add(target.id)  # asking about a rule directly: describe that rule
    if target.type in {"Play", "OffensivePlay", "DefensivePlay"}:
        for step_id in target.out("hasStep"):
            step = kg[step_id]
            rule_ids |= set(step.out("constrainedBy"))
            for at in step.out("hasActionType"):
                rule_ids |= set(kg[at].out("constrainedBy")) if kg.get(at) else set()
    for at in target.out("hasActionType"):
        if kg.get(at):
            rule_ids |= set(kg[at].out("constrainedBy"))
    rows = []
    for r_id in sorted(rule_ids):
        node = kg.get(r_id)
        if node is None or node.type != "Rule":
            continue
        rows.append(
            {
                "rule": r_id,
                "label": node.name,
                "ruleType": ", ".join(labels_of(kg, node.out("hasRuleType"))),
                "threshold": node.props.get("threshold", ""),
                "penalty": node.props.get("penaltyText", ""),
                "definition": node.definition,
                "key": " | ".join(node.keys()),
            }
        )
    summary = t("summary.rules", n=len(rows), target=target.name)
    return rows, summary


def _requirements(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    target_id = slots.get("target")
    target = kg.get(target_id) if target_id else None
    if target is None:
        return [], t("summary.requirements.none")
    req_ids = set(target.out("requires"))
    if target.type in {"Play", "OffensivePlay", "DefensivePlay"}:
        for step_id in target.out("hasStep"):
            step = kg[step_id]
            req_ids |= set(step.out("requires"))
            for at in step.out("hasActionType"):
                if kg.get(at):
                    req_ids |= set(kg[at].out("requires"))
    for at in target.out("hasActionType"):
        if kg.get(at):
            req_ids |= set(kg[at].out("requires"))
    rows = []
    for r_id in sorted(req_ids):
        node = kg.get(r_id)
        if node is None:
            continue
        rows.append(
            {
                "requirement": r_id,
                "label": node.name,
                "type": node.type,
                "definition": node.definition,
                "requires": ", ".join(labels_of(kg, node.out("requires"))),
            }
        )
    summary = t("summary.requirements", target=target.name, n=len(rows))
    return rows, summary


def _fit(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    scheme_id = slots.get("scheme")
    team_id = slots.get("team")
    scheme = kg.get(scheme_id) if scheme_id else None
    if scheme is None:
        return [], t("summary.fit.none")
    needed = set(scheme.out("requires"))
    if not needed:
        return [], f"{scheme.name} declares no archetype requirements."
    players = kg.by_type("Player")
    if team_id:
        players = [p for p in players if team_id in p.out("playsFor")]
    rows = []
    for player in sorted(players, key=lambda p: p.name):
        owned = set()
        for arch_id in player.out("hasArchetype"):
            owned.add(arch_id)
            arch = kg.get(arch_id)
            if arch:
                owned |= set(arch.out("requires"))
        matched = sorted(needed & owned)
        rows.append(
            {
                "player": player.id,
                "label": player.name,
                "team": ", ".join(labels_of(kg, player.out("playsFor"))),
                "position": ", ".join(labels_of(kg, player.out("occupiesPosition"))),
                "archetypes": ", ".join(labels_of(kg, player.out("hasArchetype"))),
                "matches": ", ".join(labels_of(kg, matched)),
                "matchCount": len(matched),
                "coverage": f"{len(matched)}/{len(needed)}",
            }
        )
    rows.sort(key=lambda r: (-r["matchCount"], r["label"]))
    summary = t("summary.fit", name=scheme.name, items=', '.join(sorted(labels_of(kg, needed))))
    return rows, summary


def _situations(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    sit_id = slots.get("situation")
    sit = kg.get(sit_id) if sit_id else None
    if sit is None:
        return [], t("summary.situations.none")
    hits = [n for n in kg.in_(sit_id, "appliesIn") if kg.get(n)]
    rows = []
    for node_id in sorted(hits, key=lambda i: (kg[i].type, kg[i].name)):
        node = kg[node_id]
        rows.append(
            {
                "id": node.id,
                "type": node.type,
                "label": node.name,
                "formation": ", ".join(labels_of(kg, node.out("hasFormation"))),
                "coverage": ", ".join(labels_of(kg, node.out("hasCoverage"))),
                "definition": node.definition,
            }
        )
    summary = t("summary.situations", n=len(rows), sit=sit.name)
    return rows, summary


def _spatial(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    zone_id = slots.get("zone")
    zone = kg.get(zone_id) if zone_id else None
    if zone is None:
        rows = []
        for node in sorted(kg.by_type("Zone"), key=lambda z: z.props.get("shotValue", 0), reverse=True):
            if "shotValue" not in node.props:
                continue
            rows.append(
                {
                    "zone": node.id,
                    "label": node.name,
                    "shotValue": node.props.get("shotValue"),
                    "distanceFromRimFt": node.props.get("distanceFromRimFt"),
                    "zoneType": ", ".join(labels_of(kg, node.out("hasZoneType"))),
                }
            )
        return rows, t("summary.spatial.all")
    neighbours = sorted(zone.out("adjacentTo"), key=lambda z: _order_key(kg, z))
    rows = [
        {
            "zone": zone.id,
            "label": zone.name,
            "shotValue": zone.props.get("shotValue", ""),
            "courtSide": zone.props.get("courtSide", ""),
            "distanceFromRimFt": zone.props.get("distanceFromRimFt", ""),
            "zoneType": ", ".join(labels_of(kg, zone.out("hasZoneType"))),
            "partOf": ", ".join(labels_of(kg, zone.out("partOf"))),
            "adjacentTo": ", ".join(labels_of(kg, neighbours)),
            "definition": zone.definition,
        }
    ]
    for n_id in neighbours:
        node = kg[n_id]
        rows.append(
            {
                "zone": node.id,
                "label": f"  -> {node.name}",
                "shotValue": node.props.get("shotValue", ""),
                "courtSide": node.props.get("courtSide", ""),
                "distanceFromRimFt": node.props.get("distanceFromRimFt", ""),
                "zoneType": ", ".join(labels_of(kg, node.out("hasZoneType"))),
                "partOf": ", ".join(labels_of(kg, node.out("partOf"))),
                "adjacentTo": "",
                "definition": node.definition,
            }
        )
    summary = t("summary.spatial.zone", name=zone.name, value=zone.props.get('shotValue', '?'), n=len(neighbours))
    return rows, summary


def _sequence(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    action_id = slots.get("action")
    action = kg.get(action_id) if action_id else None
    if action is None:
        return [], t("summary.sequence.none")
    nxt = sorted(action.out("precedes"), key=lambda s: _order_key(kg, s))
    prev = sorted(kg.in_(action_id, "precedes"), key=lambda s: _order_key(kg, s))
    rows = []
    for p in prev:
        rows.append({"relation": "before", "step": p, "label": label_of(kg, p), "actionType": ", ".join(labels_of(kg, kg[p].out("hasActionType"))) if kg.get(p) else "", "branch": kg[p].props.get("branch", "") if kg.get(p) else ""})
    rows.append({"relation": "this", "step": action.id, "label": action.name, "actionType": ", ".join(labels_of(kg, action.out("hasActionType"))), "branch": action.props.get("branch", "")})
    for n in nxt:
        rows.append({"relation": "after", "step": n, "label": label_of(kg, n), "actionType": ", ".join(labels_of(kg, kg[n].out("hasActionType"))) if kg.get(n) else "", "branch": kg[n].props.get("branch", "") if kg.get(n) else ""})
    summary = t("summary.sequence", name=action.name, prev=len(prev), next=len(nxt))
    return rows, summary


def _compare(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    a = kg.get(slots.get("a")) if slots.get("a") else None
    b = kg.get(slots.get("b")) if slots.get("b") else None
    rows = []
    for role, node in (("a", a), ("b", b)):
        if node is None:
            rows.append({"side": role, "id": "", "label": t("summary.compare.none")})
            continue
        rows.append(
            {
                "side": role,
                "id": node.id,
                "label": node.name,
                "type": node.type,
                "definition": node.definition,
                "vulnerability": node.props.get("vulnerability", ""),
                "keys": " | ".join(node.keys()),
                "strongAgainst": ", ".join(labels_of(kg, node.out("strongAgainst"))),
                "vulnerableTo": ", ".join(labels_of(kg, node.out("vulnerableTo"))),
            }
        )
    summary = t("summary.compare", a=a.name if a else '?', b=b.name if b else '?')
    return rows, summary


def _search(kg: KnowledgeGraph, slots: Dict[str, Any], t: Translator = None) -> tuple:
    t = t or Translator()
    text = str(slots.get("text", ""))
    results = kg.search(text)
    rows = [
        {"id": node.id, "type": node.type, "label": node.name, "score": score, "definition": node.definition}
        for node, score in results[:25]
    ]
    return rows, t("summary.search", n=len(rows), text=repr(text))


_EXECUTORS = {
    "describe": _describe,
    "play_steps": _play_steps,
    "zone_responsibility": _zone_responsibility,
    "counters": _counters,
    "rules": _rules,
    "requirements": _requirements,
    "fit": _fit,
    "situations": _situations,
    "spatial": _spatial,
    "sequence": _sequence,
    "compare": _compare,
    "search": _search,
}


# --------------------------------------------------------------------------- #
# Graph patterns (back-end agnostic)
# --------------------------------------------------------------------------- #


def _pat_describe(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"s": "?target", "p": "rdf:type", "o": "?type"}, {"s": "?target", "p": "skos:prefLabel", "o": "?label"}]


def _pat_steps(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?play", "p": "hasStep", "o": "?step"},
        {"s": "?step", "p": "hasActionType", "o": "?actionType"},
        {"s": "?step", "p": "actor", "o": "?actor"},
        {"s": "?step", "p": "startsIn", "o": "?from"},
        {"s": "?step", "p": "endsIn", "o": "?to"},
        {"s": "?step", "p": "precedes", "o": "?next"},
    ]


def _pat_assignment(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?assignment", "p": "ofScheme", "o": "?scheme"},
        {"s": "?assignment", "p": "coversZone", "o": "?zone"},
        {"s": "?assignment", "p": "heldBy", "o": "?role"},
    ]


def _pat_counters(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?target", "p": "hasCounter", "o": "?counter"},
        {"s": "?counter", "p": "answers", "o": "?target"},
        {"s": "?counter", "p": "exploits", "o": "?weakness"},
    ]


def _pat_rules(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?target", "p": "constrainedBy", "o": "?rule"},
        {"s": "?rule", "p": "governs", "o": "?target"},
        {"s": "?rule", "p": "hasRuleType", "o": "?ruleType"},
    ]


def _pat_requirements(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?target", "p": "requires", "o": "?archetype"},
        {"s": "?target", "p": "hasStep", "o": "?step"},
        {"s": "?step", "p": "requires", "o": "?archetype"},
        {"s": "?archetype", "p": "requires", "o": "?skill"},
    ]


def _pat_fit(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?scheme", "p": "requires", "o": "?archetype"},
        {"s": "?player", "p": "hasArchetype", "o": "?archetype"},
        {"s": "?player", "p": "playsFor", "o": "?team"},
    ]


def _pat_situations(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?scheme", "p": "appliesIn", "o": "?situation"},
        {"s": "?scheme", "p": "hasFormation", "o": "?formation"},
    ]


def _pat_spatial(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?zone", "p": "adjacentTo", "o": "?neighbour"},
        {"s": "?zone", "p": "hasZoneType", "o": "?zoneType"},
        {"s": "?zone", "p": "partOf", "o": "?container"},
    ]


def _pat_sequence(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [
        {"s": "?step", "p": "precedes", "o": "?next"},
        {"s": "?next", "p": "hasActionType", "o": "?actionType"},
    ]


def _pat_compare(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"s": "?a", "p": "?predicate", "o": "?valueA"}, {"s": "?b", "p": "?predicate", "o": "?valueB"}]


def _pat_search(slots: Dict[str, Any]) -> List[Dict[str, str]]:
    return [{"s": "?node", "p": "skos:prefLabel", "o": "?label"}]


_PATTERNS = {
    "describe": _pat_describe,
    "play_steps": _pat_steps,
    "zone_responsibility": _pat_assignment,
    "counters": _pat_counters,
    "rules": _pat_rules,
    "requirements": _pat_requirements,
    "fit": _pat_fit,
    "situations": _pat_situations,
    "spatial": _pat_spatial,
    "sequence": _pat_sequence,
    "compare": _pat_compare,
    "search": _pat_search,
}


# --------------------------------------------------------------------------- #
# SPARQL renderers
# --------------------------------------------------------------------------- #


def _sparql_steps(slots: Dict[str, Any]) -> str:
    play = _iri(slots.get("play", "play:pick-and-roll"))
    return f"""{_SPARQL_PREFIXES}
# Ordered steps of a play, with actor, action type and the zones it moves through.
SELECT ?order ?step ?stepLabel ?actionType ?actor ?fromZone ?toZone ?next
WHERE {{
  ?play bk:hasStep ?step .
  FILTER(?play = <{play}>)
  ?step skos:prefLabel ?stepLabel .
  OPTIONAL {{ ?step bk:order ?order }}
  OPTIONAL {{ ?step bk:hasActionType ?actionType }}
  OPTIONAL {{ ?step bk:actor ?actor }}
  OPTIONAL {{ ?step bk:startsIn ?fromZone }}
  OPTIONAL {{ ?step bk:endsIn ?toZone }}
  OPTIONAL {{ SELECT ?step (GROUP_CONCAT(?nextLabel; SEPARATOR=", ") AS ?next)
            WHERE {{ ?step bk:precedes/skos:prefLabel ?nextLabel }}
            GROUP BY ?step }}
}}
ORDER BY ?order"""


def _sparql_assignment(slots: Dict[str, Any]) -> str:
    filters = []
    if slots.get("zone"):
        filters.append(f"  FILTER(?zone = <{_iri(slots['zone'])}>)")
    if slots.get("scheme"):
        filters.append(f"  FILTER(?scheme = <{_iri(slots['scheme'])}>)")
    joined = "\n".join(filters)
    return f"""{_SPARQL_PREFIXES}
# Who is responsible for which area, in which scheme.
SELECT ?scheme ?assignment ?assignmentLabel ?heldBy
       (GROUP_CONCAT(DISTINCT ?zoneLabel; SEPARATOR=", ") AS ?zones)
WHERE {{
  ?assignment bk:ofScheme ?scheme ;
              bk:coversZone ?zone .
  OPTIONAL {{ ?assignment bk:heldBy ?heldBy }}
  OPTIONAL {{ ?assignment skos:prefLabel ?assignmentLabel }}
  OPTIONAL {{ ?zone skos:prefLabel ?zoneLabel }}
{joined}
}}
GROUP BY ?scheme ?assignment ?assignmentLabel ?heldBy
ORDER BY ?assignment"""


def _sparql_counters(slots: Dict[str, Any]) -> str:
    target = _iri(slots.get("target", "scheme:zone-2-3"))
    return f"""{_SPARQL_PREFIXES}
# Every tactical answer to a scheme/coverage, plus the weakness it exploits.
SELECT ?kind ?counter ?counterLabel ?vulnerability ?rationale ?effectiveness ?exploits
WHERE {{
  FILTER(?target = <{target}>)
  {{
    ?target bk:hasCounter ?counter .
  }} UNION {{
    ?counter bk:answers ?target .
  }} UNION {{
    ?counter bk:exploits ?target .
  }}
  ?counter skos:prefLabel ?counterLabel .
  BIND(IF(EXISTS {{ ?counter a bk:Counter }}, "counter", "branch step") AS ?kind)
  OPTIONAL {{ ?counter bk:vulnerability ?vulnerability }}
  OPTIONAL {{ ?counter bk:rationale ?rationale }}
  OPTIONAL {{ ?counter bk:effectiveness ?effectiveness }}
  OPTIONAL {{ SELECT ?counter (GROUP_CONCAT(?weaknessLabel; SEPARATOR=", ") AS ?exploits)
            WHERE {{ ?counter bk:exploits/skos:prefLabel ?weaknessLabel }}
            GROUP BY ?counter }}
}}
GROUP BY ?kind ?counter ?counterLabel ?vulnerability ?rationale ?effectiveness
ORDER BY ?kind DESC(?effectiveness) ?counter"""


def _sparql_rules(slots: Dict[str, Any]) -> str:
    target = _iri(slots.get("target", "atype:set-on-ball-screen"))
    return f"""{_SPARQL_PREFIXES}
# Rules that constrain a target directly, through its steps, or through its action types.
SELECT DISTINCT ?rule ?ruleLabel ?ruleType ?threshold ?penaltyText
WHERE {{
  FILTER(?target = <{target}>)
  {{ ?target bk:constrainedBy ?rule }}
  UNION {{ ?rule bk:governs ?target }}
  UNION {{ ?target bk:hasStep ?step . ?step bk:constrainedBy ?rule }}
  UNION {{ ?target bk:hasStep ?step . ?step bk:hasActionType ?type . ?type bk:constrainedBy ?rule }}
  UNION {{ ?target bk:hasActionType ?type . ?type bk:constrainedBy ?rule }}
  ?rule skos:prefLabel ?ruleLabel .
  OPTIONAL {{ ?rule bk:hasRuleType ?ruleType }}
  OPTIONAL {{ ?rule bk:threshold ?threshold }}
  OPTIONAL {{ ?rule bk:penaltyText ?penaltyText }}
}}
ORDER BY ?rule"""


def _sparql_requirements(slots: Dict[str, Any]) -> str:
    target = _iri(slots.get("target", "play:pick-and-roll"))
    return f"""{_SPARQL_PREFIXES}
# Archetypes and skills a scheme/play/action demands, rolled up from its steps.
SELECT ?requirement ?reqLabel ?kind ?skills
WHERE {{
  FILTER(?target = <{target}>)
  {{ ?target bk:requires ?requirement }}
  UNION {{ ?target bk:hasStep ?step . ?step bk:requires ?requirement }}
  UNION {{ ?target bk:hasStep ?step . ?step bk:hasActionType ?type . ?type bk:requires ?requirement }}
  UNION {{ ?target bk:hasActionType ?type . ?type bk:requires ?requirement }}
  ?requirement skos:prefLabel ?reqLabel .
  BIND(IF(EXISTS {{ ?requirement a bk:Archetype }}, "archetype",
       IF(EXISTS {{ ?requirement a bk:Skill }}, "skill", "other")) AS ?kind)
  OPTIONAL {{ SELECT ?requirement (GROUP_CONCAT(?skillLabel; SEPARATOR=", ") AS ?skills)
            WHERE {{ ?requirement bk:requires/skos:prefLabel ?skillLabel }}
            GROUP BY ?requirement }}
}}
GROUP BY ?requirement ?reqLabel ?kind
ORDER BY ?kind ?reqLabel"""


def _sparql_fit(slots: Dict[str, Any]) -> str:
    scheme = _iri(slots.get("scheme", "scheme:switch-all"))
    team_filter = f"\n  FILTER(?team = <{_iri(slots['team'])}>)" if slots.get("team") else ""
    return f"""{_SPARQL_PREFIXES}
# Which players carry the archetypes a scheme requires.
SELECT ?player ?playerLabel ?team ?position ?archetype
WHERE {{
  ?scheme bk:requires ?archetype .
  FILTER(?scheme = <{scheme}>)
  ?player a bk:Player ;
          bk:hasArchetype ?archetype .
  OPTIONAL {{ ?player skos:prefLabel ?playerLabel }}
  OPTIONAL {{ ?player bk:playsFor ?team }}
  OPTIONAL {{ ?player bk:occupiesPosition ?position }}
{team_filter}
}}
ORDER BY ?playerLabel ?archetype"""


def _sparql_situations(slots: Dict[str, Any]) -> str:
    sit = _iri(slots.get("situation", "sit:late-clock"))
    return f"""{_SPARQL_PREFIXES}
# Schemes and plays used in a given game situation.
SELECT ?scheme ?schemeLabel ?formation ?coverage
WHERE {{
  ?scheme bk:appliesIn ?situation .
  FILTER(?situation = <{sit}>)
  OPTIONAL {{ ?scheme skos:prefLabel ?schemeLabel }}
  OPTIONAL {{ ?scheme bk:hasFormation ?formation }}
  OPTIONAL {{ ?scheme bk:hasCoverage ?coverage }}
}}
ORDER BY ?scheme"""


def _sparql_spatial(slots: Dict[str, Any]) -> str:
    zone = _iri(slots.get("zone", "zone:short-corner-left"))
    return f"""{_SPARQL_PREFIXES}
# Spatial neighbourhood of a zone: containment, adjacency and shot value.
SELECT ?zone ?zoneLabel ?zoneType ?partOf ?shotValue ?neighbour ?neighbourValue
WHERE {{
  FILTER(?zone = <{zone}>)
  OPTIONAL {{ ?zone skos:prefLabel ?zoneLabel }}
  OPTIONAL {{ ?zone bk:hasZoneType ?zoneType }}
  OPTIONAL {{ ?zone bk:partOf ?partOf }}
  OPTIONAL {{ ?zone bk:shotValue ?shotValue }}
  OPTIONAL {{ ?zone bk:adjacentTo ?neighbour . OPTIONAL {{ ?neighbour bk:shotValue ?neighbourValue }} }}
}}"""


def _sparql_sequence(slots: Dict[str, Any]) -> str:
    step = _iri(slots.get("action", "pnr:s5-roll"))
    return f"""{_SPARQL_PREFIXES}
# What happens before and after a given step.
SELECT ?relation ?other ?otherLabel ?actionType
WHERE {{
  FILTER(?step = <{step}>)
  {{ ?step bk:precedes ?other . BIND("after" AS ?relation) }}
  UNION {{ ?other bk:precedes ?step . BIND("before" AS ?relation) }}
  OPTIONAL {{ ?other skos:prefLabel ?otherLabel }}
  OPTIONAL {{ ?other bk:hasActionType ?actionType }}
}}
ORDER BY ?relation ?other"""


def _sparql_compare(slots: Dict[str, Any]) -> str:
    a = _iri(slots.get("a", "coverage:drop"))
    b = _iri(slots.get("b", "coverage:blitz"))
    return f"""{_SPARQL_PREFIXES}
# Side-by-side comparison of two tactical concepts.
SELECT ?subject ?predicate ?object
WHERE {{
  VALUES ?subject {{ <{a}> <{b}> }}
  ?subject ?predicate ?object .
  FILTER(?predicate != <http://www.w3.org/1999/02/22-rdf-syntax-ns#type>)
}}
ORDER BY ?subject ?predicate"""


def _sparql_describe(slots: Dict[str, Any]) -> str:
    target = _iri(slots.get("target", "play:pick-and-roll"))
    return f"""{_SPARQL_PREFIXES}
# Everything stated directly about one node.
SELECT ?predicate ?object
WHERE {{
  <{target}> ?predicate ?object .
}}
ORDER BY ?predicate"""


def _sparql_search(slots: Dict[str, Any]) -> str:
    text = str(slots.get("text", "")).replace('"', "")
    return f"""{_SPARQL_PREFIXES}
# Full-text-ish fallback search over labels and definitions.
SELECT ?node ?label ?definition
WHERE {{
  ?node skos:prefLabel ?label .
  OPTIONAL {{ ?node skos:definition ?definition }}
  FILTER(CONTAINS(LCASE(STR(?label)), LCASE("{text}")) || CONTAINS(LCASE(STR(?definition)), LCASE("{text}")))
}}
LIMIT 25"""


_SPARQL = {
    "describe": _sparql_describe,
    "play_steps": _sparql_steps,
    "zone_responsibility": _sparql_assignment,
    "counters": _sparql_counters,
    "rules": _sparql_rules,
    "requirements": _sparql_requirements,
    "fit": _sparql_fit,
    "situations": _sparql_situations,
    "spatial": _sparql_spatial,
    "sequence": _sparql_sequence,
    "compare": _sparql_compare,
    "search": _sparql_search,
}


# --------------------------------------------------------------------------- #
# Cypher renderers
# --------------------------------------------------------------------------- #


def _cypher_steps(slots: Dict[str, Any]) -> str:
    play = slots.get("play", "play:pick-and-roll")
    return f"""// Ordered steps of a play (property-graph form)
MATCH (p:Play {{id: '{play}'}})-[:HAS_STEP]->(s:Action)
OPTIONAL MATCH (s)-[:HAS_ACTION_TYPE]->(t:ActionType)
OPTIONAL MATCH (s)-[:ACTOR]->(r:Role)
OPTIONAL MATCH (s)-[:STARTS_IN]->(z1:Zone)
OPTIONAL MATCH (s)-[:ENDS_IN]->(z2:Zone)
OPTIONAL MATCH (s)-[:PRECEDES]->(n:Action)
RETURN s.order AS order, s.label AS step, t.label AS actionType, r.label AS actor,
       z1.label AS fromZone, z2.label AS toZone, n.label AS next
ORDER BY order;"""


def _cypher_assignment(slots: Dict[str, Any]) -> str:
    if slots.get("zone"):
        where = f"WHERE z.id = '{slots['zone']}'"
    else:
        where = f"WHERE s.id = '{slots.get('scheme', 'play:zone-defense-2-3')}'"
    return f"""// Area responsibilities in a defensive scheme
MATCH (a:Assignment)-[:OF_SCHEME]->(s)
MATCH (a)-[:COVERS_ZONE]->(z:Zone)
OPTIONAL MATCH (a)-[:HELD_BY]->(r:Role)
{where}
RETURN s.label AS scheme, a.label AS assignment, r.label AS heldBy, collect(z.label) AS zones
ORDER BY assignment;"""


def _cypher_counters(slots: Dict[str, Any]) -> str:
    target = slots.get("target", "scheme:zone-2-3")
    return f"""// Tactical answers to a scheme or coverage
MATCH (t {{id: '{target}'}})
MATCH (c:Counter) WHERE (t)-[:HAS_COUNTER]->(c) OR (c)-[:ANSWERS]->(t) OR (c)-[:EXPLOITS]->(t)
OPTIONAL MATCH (c)-[:EXPLOITS]->(w)
RETURN c.label AS counter, c.vulnerability AS vulnerability, c.rationale AS rationale,
       c.effectiveness AS effectiveness, collect(DISTINCT w.label) AS exploits
ORDER BY c.effectiveness DESC;"""


def _cypher_rules(slots: Dict[str, Any]) -> str:
    target = slots.get("target", "atype:set-on-ball-screen")
    return f"""// Rules constraining a play / action / zone
MATCH (t {{id: '{target}'}})
OPTIONAL MATCH (t)-[:CONSTRAINED_BY|:HAS_STEP|]->(x)
OPTIONAL MATCH (x)-[:CONSTRAINED_BY]->(r:Rule)
OPTIONAL MATCH (t)<-[:GOVERNS]-(r2:Rule)
OPTIONAL MATCH (t)-[:HAS_ACTION_TYPE]->(at)-[:CONSTRAINED_BY]->(r3:Rule)
WITH collect(DISTINCT r) + collect(DISTINCT r2) + collect(DISTINCT r3) AS rules
UNWIND rules AS rule
WITH DISTINCT rule WHERE rule IS NOT NULL
OPTIONAL MATCH (rule)-[:HAS_RULE_TYPE]->(rt:RuleType)
RETURN rule.label AS rule, rt.label AS ruleType, rule.threshold AS threshold, rule.penaltyText AS penalty;"""


def _cypher_requirements(slots: Dict[str, Any]) -> str:
    target = slots.get("target", "play:pick-and-roll")
    return f"""// Archetypes and skills demanded by a scheme / play / action
MATCH (t {{id: '{target}'}})
OPTIONAL MATCH (t)-[:REQUIRES]->(req)
OPTIONAL MATCH (t)-[:HAS_STEP]->(s)-[:REQUIRES]->(req2)
OPTIONAL MATCH (t)-[:HAS_STEP]->(s2)-[:HAS_ACTION_TYPE]->(at)-[:REQUIRES]->(req3)
WITH collect(DISTINCT req) + collect(DISTINCT req2) + collect(DISTINCT req3) AS reqs
UNWIND reqs AS requirement
WITH DISTINCT requirement WHERE requirement IS NOT NULL
OPTIONAL MATCH (requirement)-[:REQUIRES]->(skill)
RETURN requirement.label AS requirement, labels(requirement) AS type, collect(skill.label) AS skills
ORDER BY type, requirement;"""


def _cypher_fit(slots: Dict[str, Any]) -> str:
    scheme = slots.get("scheme", "scheme:switch-all")
    team_clause = f"AND (pl)-[:PLAYS_FOR]->(:Team {{id: '{slots['team']}'}})" if slots.get("team") else ""
    return f"""// Roster fit: players carrying the archetypes a scheme needs
MATCH (s:Scheme {{id: '{scheme}'}})-[:REQUIRES]->(arch)
MATCH (pl:Player)-[:HAS_ARCHETYPE]->(arch)
{team_clause}
OPTIONAL MATCH (pl)-[:PLAYS_FOR]->(team:Team)
OPTIONAL MATCH (pl)-[:OCCUPIES_POSITION]->(pos:Position)
RETURN pl.label AS player, team.label AS team, pos.abbreviation AS position,
       count(DISTINCT arch) AS matches, collect(DISTINCT arch.label) AS archetypes
ORDER BY matches DESC, player;"""


def _cypher_situations(slots: Dict[str, Any]) -> str:
    sit = slots.get("situation", "sit:late-clock")
    return f"""// Schemes and plays used in a game situation
MATCH (s)-[:APPLIES_IN]->(sit:Situation {{id: '{sit}'}})
OPTIONAL MATCH (s)-[:HAS_FORMATION]->(f:Formation)
OPTIONAL MATCH (s)-[:HAS_COVERAGE]->(c:Coverage)
RETURN labels(s) AS kind, s.label AS scheme, f.label AS formation, c.label AS coverage
ORDER BY kind, scheme;"""


def _cypher_spatial(slots: Dict[str, Any]) -> str:
    zone = slots.get("zone", "zone:short-corner-left")
    return f"""// Spatial neighbourhood of a zone
MATCH (z:Zone {{id: '{zone}'}})
OPTIONAL MATCH (z)-[:ADJACENT_TO]->(n:Zone)
OPTIONAL MATCH (z)-[:PART_OF]->(p:Zone)
OPTIONAL MATCH (z)-[:HAS_ZONE_TYPE]->(zt:ZoneType)
RETURN z.label AS zone, z.shotValue AS shotValue, z.courtSide AS side,
       z.distanceFromRimFt AS distanceFt, zt.label AS zoneType, p.label AS partOf,
       collect(n.label) AS adjacentTo;"""


def _cypher_sequence(slots: Dict[str, Any]) -> str:
    step = slots.get("action", "pnr:s5-roll")
    return f"""// Before / after a step
MATCH (s {{id: '{step}'}})
OPTIONAL MATCH (s)-[:PRECEDES]->(n)
OPTIONAL MATCH (p)-[:PRECEDES]->(s)
OPTIONAL MATCH (n)-[:HAS_ACTION_TYPE]->(nt:ActionType)
OPTIONAL MATCH (p)-[:HAS_ACTION_TYPE]->(pt:ActionType)
RETURN s.label AS step,
       collect(DISTINCT {{rel: 'before', label: p.label, type: pt.label}}) AS before,
       collect(DISTINCT {{rel: 'after', label: n.label, type: nt.label}}) AS after;"""


def _cypher_compare(slots: Dict[str, Any]) -> str:
    a = slots.get("a", "coverage:drop")
    b = slots.get("b", "coverage:blitz")
    return f"""// Side-by-side comparison of two concepts
MATCH (n) WHERE n.id IN ['{a}', '{b}']
OPTIONAL MATCH (n)-[r]->(m)
RETURN n.label AS concept, n.definition AS definition, n.vulnerability AS vulnerability,
       type(r) AS relation, collect(m.label) AS targets
ORDER BY concept, relation;"""


def _cypher_describe(slots: Dict[str, Any]) -> str:
    target = slots.get("target", "play:pick-and-roll")
    return f"""// Everything stated about one node
MATCH (n {{id: '{target}'}})
OPTIONAL MATCH (n)-[r]->(m)
RETURN n.label AS label, n.definition AS definition, type(r) AS relation, collect(m.label) AS targets
ORDER BY relation;"""


def _cypher_search(slots: Dict[str, Any]) -> str:
    text = str(slots.get("text", "")).replace("'", "")
    return f"""// Fallback search (property-graph form)
MATCH (n)
WHERE toLower(coalesce(n.label, '')) CONTAINS toLower('{text}')
   OR toLower(coalesce(n.definition, '')) CONTAINS toLower('{text}')
RETURN n.id AS id, labels(n) AS type, n.label AS label
ORDER BY label LIMIT 25;"""


_CYPHER = {
    "describe": _cypher_describe,
    "play_steps": _cypher_steps,
    "zone_responsibility": _cypher_assignment,
    "counters": _cypher_counters,
    "rules": _cypher_rules,
    "requirements": _cypher_requirements,
    "fit": _cypher_fit,
    "situations": _cypher_situations,
    "spatial": _cypher_spatial,
    "sequence": _cypher_sequence,
    "compare": _cypher_compare,
    "search": _cypher_search,
}
