# Query cookbook

One model, three back ends. Every question below is parsed to an **intent + slots**,
and that plan is rendered as SPARQL, as Cypher, and executed in memory by the CLI.

```bash
python -m basketball_kg.cli ask "<question>"                 # answer
python -m basketball_kg.cli ask "<question>" -f sparql       # the SPARQL rendering
python -m basketball_kg.cli ask "<question>" -f cypher       # the Cypher rendering
python -m basketball_kg.cli ask "<question>" -f plan         # the whole plan as JSON
python -m basketball_kg.cli ask "<question>" --show-query    # the parse trace
```

## The twelve intents

| Intent | Slots | Purpose | Example question |
|---|---|---|---|
| `describe` | `target` | Explain any node | "What is drop coverage?" |
| `play_steps` | `play` | Ordered steps of a play | "Walk me through the pick and roll." |
| `zone_responsibility` | `zone`, `scheme` | Who covers which area | "Who covers the corner in a 2-3 zone?" |
| `counters` | `target` | Tactical answers and the weakness they exploit | "How do you attack a 2-3 zone?" |
| `rules` | `target` | Rules constraining a play/action/zone | "What rules govern setting a screen?" |
| `requirements` | `target` | Archetypes and skills demanded | "What does switch-all require?" |
| `fit` | `scheme`, `team` | Roster fit against a scheme | "Who on Harbour fits switch all?" |
| `situations` | `situation` | Schemes used in a game situation | "What should we run against a press?" |
| `spatial` | `zone` | Zone geometry and neighbours | "What is next to the short corner?" |
| `sequence` | `action` | Before / after a step | "What happens after the roll?" |
| `compare` | `a`, `b` | Two concepts side by side | "Compare drop and blitz." |
| `search` | `text` | Ranked fallback search | "nail help" |

`python -m basketball_kg.cli intents` prints the same list with all examples.

## How a question becomes a query

```
"Who covers the corner in a 2-3 zone?"
        │
        ▼  1. ordered intent regexes  (nlq.INTENT_RULES)
   zone_responsibility
        │
        ▼  2. longest-n-gram alias matching, type-filtered  (nlq.VocabularyIndex)
   {zone: zone:corner-three-left, scheme: scheme:zone-2-3}
        │
        ▼  3. render the same plan three ways
   ┌────┴───────────────┬─────────────────────────────┐
   ▼                    ▼                             ▼
SPARQL              Cypher                      in-memory rows
bk:coversZone       (:Assignment)-[:COVERS_ZONE]->(:Zone)   KG.in_(zone, "coversZone")
```

The plan also carries `evidence` — the rule that fired and the alias that matched — so
every answer is traceable:

```console
$ python -m basketball_kg.cli ask "Who covers the corner in a 2-3 zone?" --show-query
# parsed: zone_responsibility  confidence=0.95
#   rule:zone_responsibility matched /\b(who|which (player|defender|role|man))\b.*\b(cover(s|ed|ing)?|…/
#   slot:zone <- 'the corner' (zone:corner-three-left)
#   slot:scheme <- '2 3 zone' (scheme:zone-2-3)
```

## Worked examples

Each has a generated, tested query file in `queries/sparql/` and `queries/cypher/`
(`python scripts/gen_queries.py` regenerates them from the templates).

### 1. Walk me through the pick and roll → `play_steps`

`queries/sparql/01-pick-and-roll-steps.rq`

```sparql
SELECT ?order ?step ?stepLabel ?actionType ?actor ?fromZone ?toZone ?next
WHERE {
  ?play bk:hasStep ?step .
  FILTER(?play = <https://w3id.org/basketball-kg/resource/play/pick-and-roll>)
  ?step skos:prefLabel ?stepLabel .
  OPTIONAL { ?step bk:order ?order }
  OPTIONAL { ?step bk:hasActionType ?actionType }
  OPTIONAL { ?step bk:actor ?actor }
  OPTIONAL { ?step bk:startsIn ?fromZone }
  OPTIONAL { ?step bk:endsIn ?toZone }
  OPTIONAL { SELECT ?step (GROUP_CONCAT(?nextLabel; SEPARATOR=", ") AS ?next)
             WHERE { ?step bk:precedes/skos:prefLabel ?nextLabel }
             GROUP BY ?step }
}
ORDER BY ?order
```

```cypher
MATCH (p:Play {id: 'play:pick-and-roll'})-[:HAS_STEP]->(s:Action)
OPTIONAL MATCH (s)-[:HAS_ACTION_TYPE]->(t:ActionType)
OPTIONAL MATCH (s)-[:ACTOR]->(r:Role)
OPTIONAL MATCH (s)-[:STARTS_IN]->(z1:Zone)
OPTIONAL MATCH (s)-[:ENDS_IN]->(z2:Zone)
OPTIONAL MATCH (s)-[:PRECEDES]->(n:Action)
RETURN s.order AS order, s.label AS step, t.label AS actionType, r.label AS actor,
       z1.label AS fromZone, z2.label AS toZone, n.label AS next
ORDER BY order;
```

### 2. What are the 2-3 zone assignments? → `zone_responsibility`

Area duties are **reified**: the `Assignment` node, not an edge attribute, holds the
role, the zones and the requirements. That is what lets one query answer both
"who covers the corner?" and "what does the anchor do?".

```sparql
SELECT ?scheme ?assignment ?assignmentLabel ?heldBy
       (GROUP_CONCAT(DISTINCT ?zoneLabel; SEPARATOR=", ") AS ?zones)
WHERE {
  ?assignment bk:ofScheme ?scheme ;
              bk:coversZone ?zone .
  OPTIONAL { ?assignment bk:heldBy ?heldBy }
  OPTIONAL { ?assignment skos:prefLabel ?assignmentLabel }
  OPTIONAL { ?zone skos:prefLabel ?zoneLabel }
  FILTER(?scheme = <https://w3id.org/basketball-kg/resource/play/zone-defense-2-3>)
}
GROUP BY ?scheme ?assignment ?assignmentLabel ?heldBy
ORDER BY ?assignment
```

### 3. How do you attack a 2-3 zone? → `counters`

A `Counter` is a node with `answers` (what it answers), `exploits` (the weakness) and
`rationale`. Three UNION branches gather counters attached to the target, counters that
answer it, and counters that exploit it; `BIND(IF(EXISTS { ?counter a bk:Counter }, …))`
labels the kind of answer so branch steps and tactical counters can be told apart.

```console
$ python -m basketball_kg.cli ask "How do you attack a 2-3 zone?"
intent: counters   (confidence 0.8)
slots:  target=scheme:zone-2-3

5 tactical answer(s) to Zone 2-3

label                                      vulnerability                                 effectiveness
-----------------------------------------  --------------------------------------------  -------------
Quick ball reversal against the 2-3        A zone moves on the flight of the ball; two…  high
Occupy the high post against the 2-3       The free-throw line is the geometric hole o…  high
Crash the offensive glass against the 2-3  Zone defenders are responsible for space, n…  high
Overload one side of the 2-3               A zone must allocate one defender per area;…  high
Run before the 2-3 can set                 A zone needs time and a dead ball to organi…  high
```

### 4. What rules govern setting a screen? → `rules`

Rules attach to **action types**, so every screening action inherits them, and the
query rolls up from a play through its steps to the types of those steps.

```sparql
SELECT DISTINCT ?rule ?ruleLabel ?ruleType ?threshold ?penaltyText
WHERE {
  FILTER(?target = <https://w3id.org/basketball-kg/resource/atype/set-on-ball-screen>)
  { ?target bk:constrainedBy ?rule }
  UNION { ?rule bk:governs ?target }
  UNION { ?target bk:hasStep ?step . ?step bk:constrainedBy ?rule }
  UNION { ?target bk:hasStep ?step . ?step bk:hasActionType ?type . ?type bk:constrainedBy ?rule }
  UNION { ?target bk:hasActionType ?type . ?type bk:constrainedBy ?rule }
  …
}
```

### 5. Which players fit a switch-everything scheme? → `fit`

```console
$ python -m basketball_kg.cli ask "Who on Harbour fits switch all?"
intent: fit   (confidence 0.85)
slots:  scheme=scheme:switch-all, team=team:harbour

Switch-All (Switch Everything) needs: Switchable Defender

label         team     position        matches              coverage
------------  -------  --------------  -------------------  --------
Tobias Lund   Harbour  Small Forward   Switchable Defender  1/1
Andre Vega    Harbour  Point Guard                          0/1
…
```

### 6–10. Spatial, sequence, coverage counters, requirements, situations

| # | Question | Intent | File |
|---|---|---|---|
| 6 | What is next to the short corner? | `spatial` | `queries/sparql/06-short-corner-geometry.rq` |
| 7 | What happens after the roll? | `sequence` | `queries/sparql/07-after-the-roll.rq` |
| 8 | What beats drop coverage? | `counters` | `queries/sparql/08-beating-drop-coverage.rq` |
| 9 | What does motion offence need? | `requirements` | `queries/sparql/09-motion-offence-requirements.rq` |
| 10 | What should we run late in the shot clock? | `situations` | `queries/sparql/10-late-clock-options.rq` |

## Extending the parser

* **New vocabulary:** add a node to `data/*.json`. The alias index picks up labels,
  local names, abbreviations and `props.aliases` automatically.
* **New phrasing:** add an entry to `nlq.SYNONYMS` (`"blue": "coverage:ice"`). Curated
  synonyms outrank raw labels, which is how "drop coverage" resolves to the *coverage*
  rather than the action type of the same name.
* **New intent:** add a handler to `queries._EXECUTORS`, a SPARQL renderer to
  `_SPARQL`, a Cypher renderer to `_CYPHER`, a pattern to `_PATTERNS`, an entry to
  `INTENTS`, and a rule to `nlq.INTENT_RULES`. The tests fail loudly if one is missing.
* **Nothing matches?** The parser falls back to a type-filtered ranked search on the
  content words of the question (question scaffolding like *what / should / we / the*
  is stripped first). Every plan reports how each slot was filled in `evidence`.

## Running the queries yourself

```bash
# against the in-memory graph (CLI)
python -m basketball_kg.cli sparql --file queries/sparql/03-attack-the-2-3-zone.rq

# against any SPARQL endpoint, after publishing the RDF
python -m basketball_kg.cli export -f ttl --ontology --out basketball.ttl
#   …load basketball.ttl into GraphDB / Fuseki / Blazegraph / Apache Jena …

# Cypher: import the node-link export, or rebuild the graph directly
python -m basketball_kg.cli export -f json --out graph.json
#   node label = node.type, property `id` = the CURIE, relation type = SCREAMING_SNAKE(predicate)
```
