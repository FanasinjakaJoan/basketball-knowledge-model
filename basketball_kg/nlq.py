"""Natural language -> structured query.

``parse(kg, question)`` turns a coaching question into a :class:`QueryPlan`:
an intent plus filled slots, which can then be executed in memory, rendered as
SPARQL, or rendered as Cypher. It is deliberately transparent: every plan
carries the rule that fired and the alias that matched, so the answer can always
be traced back to the text.

The parser is rule-based (no model calls, no network): ordered intent regexes,
then longest-n-gram alias matching against a vocabulary index. That keeps it
deterministic, testable and cheap -- and it makes the failure mode obvious.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from .model import KnowledgeGraph, Node, _normalise
from .queries import QueryPlan, QueryResult

__all__ = ["VocabularyIndex", "parse", "answer", "INTENT_RULES", "SYNONYMS"]

# --------------------------------------------------------------------------- #
# Hand-written synonyms: phrases that do not appear verbatim in any label
# --------------------------------------------------------------------------- #

SYNONYMS: Dict[str, str] = {
    # schemes / plays
    "pnr": "scheme:pick-and-roll",
    "pick and roll": "play:pick-and-roll",
    "pick n roll": "play:pick-and-roll",
    "ball screen": "play:pick-and-roll",
    "on ball screen": "play:pick-and-roll",
    "screen and roll": "play:pick-and-roll",
    "2 3 zone": "scheme:zone-2-3",
    "2 3": "scheme:zone-2-3",
    "23 zone": "scheme:zone-2-3",
    "two three zone": "scheme:zone-2-3",
    "two three": "scheme:zone-2-3",
    "zone d": "scheme:zone-2-3",
    "zone defense": "scheme:zone-2-3",
    "zone defence": "scheme:zone-2-3",
    "motion": "play:motion-offense",
    "motion offense": "play:motion-offense",
    "motion offence": "play:motion-offense",
    "switch everything": "scheme:switch-all",
    "switch all": "scheme:switch-all",
    "switching": "scheme:switch-all",
    "press": "scheme:full-court-press",
    "full court press": "scheme:full-court-press",
    # coverages
    "drop": "coverage:drop",
    "drop coverage": "coverage:drop",
    "ice": "coverage:ice",
    "ice coverage": "coverage:ice",
    "blue": "coverage:ice",
    "blitz": "coverage:blitz",
    "trap": "coverage:blitz",
    "hedge": "coverage:show-and-recover",
    "show and recover": "coverage:show-and-recover",
    "at the level": "coverage:at-the-level",
    "switch": "coverage:switch",
    # actions
    "screening": "atype:set-on-ball-screen",
    "setting a screen": "atype:set-on-ball-screen",
    "set a screen": "atype:set-on-ball-screen",
    "set an on ball screen": "atype:set-on-ball-screen",
    "screen": "atype:set-on-ball-screen",
    "roll": "pnr:s5-roll",
    "the roll": "pnr:s5-roll",
    "rolling": "pnr:s5-roll",
    "roll man": "role:roll-man",
    "short roll": "pnr:s10-shortroll-vs-blitz",
    "skip pass": "pnr:s11-skip-vs-blitz",
    "pocket pass": "pnr:s19-pocket-pass",
    "slip": "pnr:s13-slip-vs-switch",
    "reject": "pnr:s17-reject-vs-ice",
    "ball reversal": "atype:ball-reversal",
    "kick out": "atype:kick-out-pass",
    "hand off": "atype:dribble-handoff",
    "dho": "atype:dribble-handoff",
    "backdoor": "atype:backdoor-cut",
    "cut": "atype:basket-cut",
    "post up": "atype:post-up",
    "posting up": "atype:post-up",
    "spacing": "atype:spacing",
    # zones
    "corner": "zone:corner-three-left",
    "the corner": "zone:corner-three-left",
    "corner three": "zone:corner-three-left",
    "short corner": "zone:short-corner-left",
    "high post": "zone:high-post",
    "the hole": "zone:high-post",
    "nail": "zone:high-post",
    "paint": "zone:paint",
    "the paint": "zone:paint",
    "lane": "zone:paint",
    "rim": "zone:restricted-area",
    "basket": "zone:restricted-area",
    "elbow": "zone:elbow-left",
    "top of the key": "zone:top-of-key-three",
    "top of key": "zone:top-of-key-three",
    "wing": "zone:midrange-left-wing",
    "weak side": "role:help-defender",
    "weakside": "role:help-defender",
    # roles / archetypes
    "ball handler": "role:ball-handler",
    "screener": "role:screener",
    "hub": "role:hub",
    "rim protector": "arch:rim-protector",
    "anchor": "arch:rim-protector",
    "stretch big": "arch:roll-and-pop-big",
    "stretch five": "arch:roll-and-pop-big",
    "stretch 5": "arch:roll-and-pop-big",
    "three and d": "arch:three-and-d-wing",
    "3 and d": "arch:three-and-d-wing",
    "sharpshooter": "arch:off-ball-sharpshooter",
    "point guard": "pos:point-guard",
    "center": "pos:center",
    "centre": "pos:center",
    # rules
    "three seconds": "rule:offensive-three-seconds",
    "three second": "rule:offensive-three-seconds",
    "3 second": "rule:offensive-three-seconds",
    "moving screen": "rule:legal-screen",
    "illegal screen": "rule:legal-screen",
    "shot clock": "rule:shot-clock-24",
    "24 second": "rule:shot-clock-24",
    "8 second": "rule:backcourt-8-seconds",
    "eight second": "rule:backcourt-8-seconds",
    "backcourt": "rule:backcourt-8-seconds",
    "travel": "rule:traveling-gather",
    "traveling": "rule:traveling-gather",
    "goaltend": "rule:goaltending",
    "goaltending": "rule:goaltending",
    "charge": "rule:restricted-area-charge",
    "restricted area": "rule:restricted-area-charge",
    # situations
    "late clock": "sit:late-clock",
    "late shot clock": "sit:late-clock",
    "out of bounds": "sit:slob",
    "sideline out of bounds": "sit:slob",
    "baseline out of bounds": "sit:blob",
    "after timeout": "sit:ato",
    "ato": "sit:ato",
    "transition": "sit:transition",
    "clutch": "sit:clutch",
    "half court": "sit:half-court",
}


# --------------------------------------------------------------------------- #
# Vocabulary index
# --------------------------------------------------------------------------- #


@dataclass
class AliasHit:
    node_id: str
    text: str
    weight: float
    length: int


class VocabularyIndex:
    """normalised alias -> node ids, built once from the graph."""

    def __init__(self, kg: KnowledgeGraph) -> None:
        self.kg = kg
        self.index: Dict[str, List[Tuple[str, float]]] = {}
        self._build()

    def _add(self, alias: str, node_id: str, weight: float) -> None:
        key = _normalise(alias)
        if not key:
            return
        bucket = self.index.setdefault(key, [])
        if not any(nid == node_id for nid, _ in bucket):
            bucket.append((node_id, weight))

    def _build(self) -> None:
        for node in self.kg.nodes.values():
            self._add(node.label, node.id, 3.0)
            self._add(node.local_name.replace("-", " "), node.id, 2.0)
            self._add(node.props.get("abbreviation", ""), node.id, 2.5)
            for alias in node.props.get("aliases", []) or []:
                self._add(alias, node.id, 2.5)
        for alias, node_id in SYNONYMS.items():
            if node_id in self.kg.nodes:
                self._add(alias, node_id, 3.5)  # curated synonyms outrank raw labels

    # -- lookup ------------------------------------------------------------ #
    def lookup(self, text: str, types: Optional[Sequence[str]] = None, max_ngram: int = 5) -> Optional[AliasHit]:
        """Return the best (longest, then highest-weight) alias match in ``text``."""
        tokens = _normalise(text).split()
        allowed = set(types) if types else None
        best: Optional[AliasHit] = None
        for size in range(min(max_ngram, len(tokens)), 0, -1):
            for start in range(0, len(tokens) - size + 1):
                gram = " ".join(tokens[start : start + size])
                candidates = self.index.get(gram)
                if not candidates:
                    continue
                for node_id, weight in candidates:
                    node = self.kg.get(node_id)
                    if node is None:
                        continue
                    if allowed and node.type not in allowed:
                        continue
                    hit = AliasHit(node_id, gram, weight + 0.35 * size, size)
                    if best is None or (hit.length, hit.weight) > (best.length, best.weight):
                        best = hit
            if best is not None:
                break  # prefer the longest n-gram that matched
        return best

    def lookup_many(self, text: str, types: Optional[Sequence[str]] = None, limit: int = 2, max_ngram: int = 5) -> List[AliasHit]:
        """Return up to ``limit`` distinct matches (longest first)."""
        tokens = _normalise(text).split()
        allowed = set(types) if types else None
        hits: List[AliasHit] = []
        used_spans: List[Tuple[int, int]] = []
        for size in range(min(max_ngram, len(tokens)), 0, -1):
            for start in range(0, len(tokens) - size + 1):
                span = (start, start + size)
                if any(_overlaps(span, used) for used in used_spans):
                    continue
                gram = " ".join(tokens[start : start + size])
                for node_id, weight in self.index.get(gram, []):
                    node = self.kg.get(node_id)
                    if node is None or (allowed and node.type not in allowed):
                        continue
                    hits.append(AliasHit(node_id, gram, weight + 0.35 * size, size))
                    used_spans.append(span)
                    break
                if len(hits) >= limit:
                    return hits
        return hits


def _overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
    return not (a[1] <= b[0] or b[1] <= a[0])


# --------------------------------------------------------------------------- #
# Intent rules
# --------------------------------------------------------------------------- #

#: (intent, regex, {slot: allowed types or None})
INTENT_RULES: List[Tuple[str, str, Dict[str, Optional[Sequence[str]]]]] = [
    (
        "zone_responsibility",
        r"\b(who|which (player|defender|role|man))\b.*\b(cover(s|ed|ing)?|guard(s|ing|ed)?|responsib\w*|pick(s|ing)? up|defend(s|er|ing)?|take(s|n)?)\b|\b(assignment(s)?|responsibilit(y|ies)|dut(y|ies))\b",
        {"zone": ("Zone",), "scheme": ("DefensiveScheme", "DefensivePlay", "Scheme", "Play")},
    ),
    (
        "counters",
        r"\b(attack(s|ing)?|beat(s|ing|en)?|break(s|ing)?|exploit(s|ing)?|counter(s|ed|ing)?|vulnerab\w*|weakness(es)?|bother(s)?|solve(s)?|stop(s)?|score against|guard against|answer(s)? to)\b",
        {"target": ("Scheme", "OffensiveScheme", "DefensiveScheme", "DefensivePlay", "OffensivePlay", "Play", "Coverage", "Archetype")},
    ),
    (
        "rules",
        r"\b(rule(s)?|legal(ly)?|illegal(ly)?|violation(s)?|foul(s)?|three second(s)?|3 second|shot clock (rule|violation)|travel\w*|charging|charge(s|d)?|goaltend\w*|restricted area|clear path|five second(s)?)\b",
        {"target": ("Action", "Play", "Scheme", "Zone", "ActionType", "Rule", "Assignment")},
    ),
    (
        "spatial",
        r"\b(adjacent|next to|near|beside|between|where (is|are)|shot value|how far|which zone(s)?|what zone(s)?|highest value|furthest|closest|spacing)\b",
        {"zone": ("Zone",)},
    ),
    (
        "sequence",
        r"\b(after|before|then what|what happens (after|next|then)|what('s|s)? next|follow(s|ed|ing)?|come(s)? (after|next)|lead(s)? to|precede(s|d)?)\b",
        {"action": ("Action", "Decision")},
    ),
    (
        "requirements",
        r"\b(what kind of|which archetype|what type of player|who can (run|execute|play)|requirement(s)?|need(ed|s)? to (run|execute|play)|requires|do you need|what does .* (need|require))\b",
        {"target": ("Play", "Scheme", "OffensiveScheme", "DefensiveScheme", "Action", "Role", "ActionType")},
    ),
    (
        "fit",
        r"\b(roster|who on|which players?|who fits|line ?up|personnel)\b",
        {"scheme": ("Scheme", "OffensiveScheme", "DefensiveScheme", "Play"), "team": ("Team",)},
    ),
    (
        "play_steps",
        r"\b(step(s)?|sequence|walk me through|break ?down|how (is|does|do) .*(run|work|executed)|structure|break it down)\b",
        {"play": ("Play", "OffensivePlay", "DefensivePlay")},
    ),
    (
        "situations",
        r"\b(when (should|do|to)|situation(s)?|late clock|out of bounds|inbound|transition|clutch|press(ed|ing)?|shot clock|what (should|do|can) (we|i) (run|do)|best (play|option|set))\b",
        {"situation": ("Situation",)},
    ),
    (
        "compare",
        r"\b(compare|comparison|difference between|versus|vs\.?|rather than)\b",
        {"a": None, "b": None},
    ),
    (
        "describe",
        r"\b(what is|what are|what's|describe|explain|tell me about|define|meaning of)\b",
        {"target": None},
    ),
]

_SEARCH_TYPES = None


# --------------------------------------------------------------------------- #
# Parsing
# --------------------------------------------------------------------------- #


def _fill_slot(
    kg: KnowledgeGraph,
    index: VocabularyIndex,
    text: str,
    types: Optional[Sequence[str]],
) -> Tuple[Optional[str], str]:
    """Resolve one slot: exact alias first, then a type-filtered ranked search."""
    hit = index.lookup(text, types)
    if hit is not None:
        return hit.node_id, f"'{hit.text}' ({hit.node_id})"
    if types:
        results = kg.search(_content_words(text), types)
        if results:
            node, score = results[0]
            runner_up = results[1][1] if len(results) > 1 else 0.0
            # accept a fuzzy hit only if it is both plausible and clearly the best
            if score >= 1.0 and score >= 1.5 * runner_up:
                return node.id, f"search '{node.label}' ({node.id}, score {score})"
    return None, ""


#: words that carry no basketball meaning and dilute a similarity search
STOPWORDS = {
    "what", "whats", "when", "where", "who", "whom", "whose", "which", "how", "why",
    "do", "does", "did", "should", "shall", "can", "could", "would", "will", "is",
    "are", "was", "were", "be", "been", "being", "i", "we", "you", "they", "them",
    "us", "me", "he", "she", "it", "the", "a", "an", "of", "in", "on", "at", "to",
    "for", "and", "or", "that", "this", "with", "against", "into", "from", "about",
    "tell", "show", "give", "explain", "describe", "walk", "through", "me", "there",
}


def _content_words(text: str) -> str:
    """Strip question scaffolding so similarity search sees the basketball words."""
    return " ".join(w for w in _normalise(text).split() if w not in STOPWORDS) or _normalise(text)


def parse(kg: KnowledgeGraph, question: str, index: Optional[VocabularyIndex] = None) -> QueryPlan:
    """Parse ``question`` into a :class:`QueryPlan`."""
    index = index or VocabularyIndex(kg)
    text = str(question or "").strip()
    lowered = _normalise(text)
    if not lowered:
        return QueryPlan(intent="search", slots={"text": text}, description="empty question", confidence=0.0)

    for intent, pattern, slot_types in INTENT_RULES:
        match = re.search(pattern, lowered)
        if not match:
            continue
        slots: Dict[str, Any] = {}
        evidence: List[str] = []
        evidence.append(f"rule:{intent} matched /{pattern[:48]}.../" if len(pattern) > 48 else f"rule:{intent} matched /{pattern}/")
        filled = 0
        for slot, types in slot_types.items():
            if intent == "compare" and slot in ("a", "b"):
                continue
            node_id, how = _fill_slot(kg, index, text, types)
            if node_id is not None:
                slots[slot] = node_id
                evidence.append(f"slot:{slot} <- {how}")
                filled += 1
        if intent == "compare":
            hits = index.lookup_many(text, ("Coverage", "Scheme", "DefensiveScheme", "OffensiveScheme", "Archetype", "Play", "Action"), limit=2)
            if len(hits) >= 2:
                slots["a"], slots["b"] = hits[0].node_id, hits[1].node_id
                evidence.append(f"slot:a <- '{hits[0].text}' ({hits[0].node_id})")
                evidence.append(f"slot:b <- '{hits[1].text}' ({hits[1].node_id})")
                filled = 2
        # require at least one slot for the slot-driven intents
        mandatory = intent not in {"spatial", "situations", "describe", "search"}
        if mandatory and filled == 0:
            continue
        confidence = 0.55 + 0.15 * filled + (0.1 if intent in {"counters", "zone_responsibility", "play_steps"} else 0.0)
        return QueryPlan(
            intent=intent,
            slots=slots,
            description=f"{intent} parsed from: {text!r}",
            confidence=round(min(confidence, 0.98), 2),
            evidence=evidence,
        )

    target = index.lookup(text)
    if target is not None:
        return QueryPlan(
            intent="describe",
            slots={"target": target.node_id},
            description=f"describe {target.node_id}",
            confidence=0.6,
            evidence=[f"fallback:describe <- '{target.text}' ({target.node_id})"],
        )
    return QueryPlan(
        intent="search",
        slots={"text": text},
        description=f"search for {text!r}",
        confidence=0.4,
        evidence=["fallback:search"],
    )


def answer(kg: KnowledgeGraph, question: str, index: Optional[VocabularyIndex] = None, lang: str = "en") -> QueryResult:
    """Parse and execute a question in one call (``lang`` localises the summary)."""
    plan = parse(kg, question, index=index)
    return plan.execute(kg, lang=lang)
