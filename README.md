# Basketball Knowledge Model (BKM)

A **queryable knowledge graph of basketball tactics**: player positions, functional
roles and archetypes; a spatial half-court model; offensive and defensive schemes;
ball-screen coverages; play graphs with decision points; game situations; and the
rules of the game that constrain every action.

The same knowledge is served three ways from one source of truth:

| Projection | Module | Query language | Use it for |
|---|---|---|---|
| Canonical graph | `basketball_kg.model` | Python | authoring, validation, CLI answers |
| Property graph | `basketball_kg.graph` | Cypher (Neo4j) / NetworkX | graph analytics, visualisation, D3 |
| RDF graph | `basketball_kg.rdf` | SPARQL 1.1 | linked data, JSON-LD publishing, federation |

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

---

## Install

```bash
pip install -r requirements.txt     # rdflib, networkx, PyYAML
python -m basketball_kg.cli stats   # no build step: the graph is plain JSON
```

Python 3.9+. Tests run on the standard library alone (`python -m unittest discover -s tests`).

---

## The ontology in one page

Namespaces: `bk: = https://w3id.org/basketball-kg/ontology#` (vocabulary),
`bkr: = https://w3id.org/basketball-kg/resource/<prefix>/<local>` (individuals).

### Classes

| Class | Meaning | Examples |
|---|---|---|
| `Player`, `Coach`, `Team` | Agents | `player:harbour-1`, `coach:miles` |
| `Position`, `PositionGroup` | Nominal floor slots and their families | `pos:point-guard`, `pgroup:big` |
| `Role` | Position-agnostic functional job | `role:ball-handler`, `role:help-defender` |
| `Archetype`, `Skill` | Reproducible skill bundles; atomic capabilities | `arch:rim-protector`, `skill:screen-navigation` |
| `Zone`, `ZoneType` | 17-cell half-court model | `zone:short-corner-left`, `zonetype:three-point` |
| `Scheme`, `OffensiveScheme`, `DefensiveScheme` | Team systems | `scheme:motion-offense`, `scheme:zone-2-3` |
| `Coverage` | Two-defender answer to a ball screen | `coverage:drop`, `coverage:ice` |
| `Formation` | Starting alignment | `form:five-out`, `form:two-three-shell` |
| `Play`, `OffensivePlay`, `DefensivePlay` | Goal-directed action graphs | `play:pick-and-roll`, `play:zone-defense-2-3` |
| `Action`, `ActionType` | A step, and the reusable verb it instantiates | `pnr:s5-roll`, `atype:roll-to-rim` |
| `Decision` | A branch: a read that selects the next action | `pnr:d1-read-coverage` |
| `Assignment` | Reified area duty (who covers what) | `z23:a4-bottom-middle` |
| `Counter` | A tactical answer exploiting a named weakness | `counter:high-post-vs-2-3` |
| `Situation`, `Outcome`, `Rule`, `RuleType`, `Penalty` | Context, results, constraints | `sit:late-clock`, `rule:legal-screen` |

Three design decisions worth knowing:

1. **Nominal positions ≠ functional roles ≠ archetypes.** `pos:center` is a roster
   convention; `role:hub` is the job; `arch:hub-playmaker` is the skill bundle that
   qualifies a player for the job. Modelling them separately is what lets the graph
   say "a stretch four and a point guard can fill the same spacing role".
2. **Anything with its own semantics is a node.** Assignments, counters and decisions
   are nodes, never edge attributes, so the graph survives the trip to RDF where
   edges cannot hold data.
3. **Inverses and symmetric edges are derived, not authored.** Write `stepOf`, get
   `hasStep`; write `adjacentTo`, get it both ways. `python -m basketball_kg.cli validate`
   enforces it.

### Key properties

| Property | Domain → Range | Meaning |
|---|---|---|
| `hasStep` / `stepOf` | Play ↔ Action | composition (decision nodes share this spine) |
| `precedes` | Action → Action | ordering / dependency inside a play |
| `actor`, `target` | Action → Role/Position/Player/Zone | who acts, on whom or where |
| `startsIn`, `endsIn`, `occursIn` | Action → Zone | the spatial trace of an action |
| `hasActionType` | Action → ActionType | the reusable verb |
| `hasDecision` → `condition`, `selectedOption` | Play/Action → Decision | the read tree |
| `coversZone`, `heldBy`, `ofScheme` | Assignment | reified area responsibilities |
| `hasCounter` → `answers`, `exploits` | Scheme/Coverage → Counter | tactics and the weakness they attack |
| `constrainedBy` / `governs` | Action/Play/Scheme ↔ Rule | what the rulebook allows |
| `requires` | Scheme/Play/Action/Role → Archetype/Skill | personnel requirements |
| `appliesIn` | Scheme/Play/Coverage → Situation | when a scheme is live |
| `adjacentTo`, `partOf` | Zone → Zone | the spacing / rotation graph |
| `strongAgainst`, `vulnerableTo` | Archetype → Archetype | match-up consequences |

Full reference: [`docs/ONTOLOGY.md`](docs/ONTOLOGY.md).

---

## Quickstart

### Python

```bash
python examples/tour.py    # five-minute guided tour: graph, court, tactics, counters,
                           # rules, personnel fit, NL parsing, three back ends
```

```python
from basketball_kg import load_graph, answer, parse
from basketball_kg.queries import QueryPlan

kg = load_graph()                      # 292 nodes, 1192 edges, 9 datasets
result = answer(kg, "What beats drop coverage?")
print(result.intent, result.summary)

# the same question as a structured query, in three back ends
plan = parse(kg, "What beats drop coverage?")
print(plan.slots)                      # {'target': 'coverage:drop'}
print(plan.to_sparql())
print(plan.to_cypher())
print(plan.to_graph_pattern())
```

### CLI

```bash
python -m basketball_kg.cli stats                                  # size, types, predicates
python -m basketball_kg.cli validate                               # ids, types, dangling refs
python -m basketball_kg.cli intents                                # the 12 query intents
python -m basketball_kg.cli ask "walk me through the pick and roll"
python -m basketball_kg.cli ask "who covers the corner in a 2-3 zone?" -f sparql
python -m basketball_kg.cli query play_steps --play play:motion-offense
python -m basketball_kg.cli query counters --target coverage:switch -f cypher
python -m basketball_kg.cli sparql --file queries/sparql/03-attack-the-2-3-zone.rq
python -m basketball_kg.cli court --scheme scheme:zone-2-3         # the zone, on the floor
python -m basketball_kg.cli export -f dot --focus play:pick-and-roll --out pnr.dot
python -m basketball_kg.cli export -f jsonld --out basketball.jsonld
python -m basketball_kg.cli export -f ttl --ontology --out basketball.ttl
python -m basketball_kg.cli serve                                   # web explorer on :8000
```

### Web explorer

```bash
python -m basketball_kg.cli serve --host 0.0.0.0 --port 8000   # → http://localhost:8000
```

A single-page explorer with no build step and no CDN — stdlib `http.server` on the
back end, one `web/index.html` on the front (hand-rolled SVG force layout, so the
Court tab and the graph need no Graphviz). It asks questions in plain English and
shows its work: every answer comes with the parsed intent, the slots that were
filled, the SPARQL, the Cypher and the JSON graph pattern that produced it.

| Route | Returns |
| --- | --- |
| `/api/stats` | node/edge counts, type histogram, predicate histogram, dataset manifest, validation |
| `/api/ask?q=…` | intent, slots, confidence, evidence, summary, rows, plus `sparql` / `cypher` / `pattern` |
| `/api/search?q=&type=` | fuzzy vocabulary search (label, aliases, definitions) |
| `/api/node?id=` | label, definition, props, outgoing edges grouped by predicate, incoming edges, DOT |
| `/api/graph?focus=&depth=` | node-link JSON for the neighbourhood (capped at 220 nodes by degree) |
| `/api/court?scheme=` | ASCII half-court with the covered zones highlighted |
| `/api/intents`, `/api/examples` | the 12 intents; the sample questions and plays the UI offers |

Everything is read-only and every path is a relative `/api/…` fetch, so it sits
happily behind a proxy or on a LAN.

### The court renderer

```console
$ python -m basketball_kg.cli court --scheme scheme:zone-2-3
# Zone 2-3 covers 12 zone(s): Left Corner Three, Right Corner Three, High Post ...

|---------------------------------------- BC --------------------------------------|
|                                 ......    ......                                 |
|                      ............      [T3]    ............                      |
|           [W3<].......                                    .......  [W3>]         |
|            ... MW<                                              MW> .            |
|         ....                           [HP]                         ....         |
|      ....                 EL< ---------------------- EL>               ....      |
|    ...                    |                          |                    ...    |
|    :      [SC<]           |  [LP<]     [PNT]    [LP>]|             [SC>]    :    |
|    :[C3<]                 |      :::   [RA] :::      |                   [C3>]   |
|____:______________________|__________________________|______________________:____|
legend: RA rim | PNT paint | LP post | SC short corner | EL elbow | HP high post
        MW mid-range wing | C3 corner three | W3 wing three | T3 top of key | BC backcourt
```

The elbows (`EL`) are the seam the 2-3 concedes — the picture, not a paragraph, is
what makes that obvious.

---

## What is modelled

| Dataset | Nodes | Contents |
|---|---:|---|
| `data/court.json` | 23 | 17 zones with coordinates, shot value, adjacency, containment |
| `data/positions.json` | 60 | 5 positions, 3 groups, 18 roles, 18 archetypes, 16 skills |
| `data/action-types.json` | 59 | the verb vocabulary (offence, defence, rules-bound) |
| `data/rules.json` | 22 | 12 rules: 3-seconds, shot clock, legal screen, RA charge, … |
| `data/tactics.json` | 65 | schemes, coverages, formations, situations, outcomes, 18 counters |
| `data/plays/pick-and-roll.json` | 21 | 19 steps, 1 decision point, 4 coverage branches |
| `data/plays/motion-offense.json` | 14 | 11 steps, 1 decision point (read the defender) |
| `data/plays/zone-defense-2-3.json` | 14 | 5 area assignments, 8 movement steps, 5 counters |
| `data/players.json` | 14 | 2 illustrative teams, 10 fictional players, 2 coaches |

Play models: [`docs/PLAY_MODELS.md`](docs/PLAY_MODELS.md).

### The pick-and-roll as a graph

```
spacing ─▶ align angle ─▶ set screen ─▶ use screen ─▶ weak-side lift ─┐
                              │              │                        │
                              │              └──▶ roll to rim ────────┤
                              │                                       ▼
                              └──────────────────────────▶ ◇ read the coverage
                                                              │
        ┌─────────────────┬─────────────────┬────────────────┼─────────────────┐
        ▼                 ▼                 ▼                ▼                 ▼
   [drop]             [blitz]           [switch]          [ice]          [no help]
   pull-up 3        short roll          slip screen      reject         pocket pass
   snake dribble    └─▶ skip pass       post mismatch    └─▶ reversal       └─▶ lob
   pop to arc           └─▶ catch&shoot  step-back iso       └─▶ kick-out
```

Every branch names the coverage it answers (`pnr:s7-pullup-vs-drop -answers-> coverage:drop`),
so "what beats drop coverage?" is a graph traversal, not a text search.

---

## Retrieval: natural language → structured query

`basketball_kg.nlq` is rule-based and deterministic — ordered intent regexes, then
longest-n-gram alias matching against a vocabulary index. Every plan carries the rule
that fired and the alias that matched, so an answer can always be traced back to the text.

```console
$ python -m basketball_kg.cli ask "Who covers the corner in a 2-3 zone?" --show-query
# parsed: zone_responsibility  confidence=0.95
#   rule:zone_responsibility matched /\b(who|which (player|defender|role|man))\b.*\b(cover(s|ed|ing)?|…/
#   slot:zone <- 'the corner' (zone:corner-three-left)
#   slot:scheme <- '2 3 zone' (scheme:zone-2-3)

Left Corner Three is covered by 1 assignment(s) in Zone 2-3 Defence
label                  heldBy                          coversZones
---------------------  ------------------------------  -------------------------------------------
Bottom-left (forward)  Help Defender (Nail / Low Man)  Left Corner Three, Left Elbow, Left Low Post…
```

Twelve intents: `describe`, `play_steps`, `zone_responsibility`, `counters`, `rules`,
`requirements`, `fit`, `situations`, `spatial`, `sequence`, `compare`, `search`.
Worked examples with their SPARQL/Cypher/graph-pattern renderings:
[`docs/QUERY_COOKBOOK.md`](docs/QUERY_COOKBOOK.md) and
[`queries/nl_to_query.json`](queries/nl_to_query.json).

---

## Repository layout

```
ontology/
  basketball.ttl          OWL/RDFS TBox: classes, object & datatype properties
  basketball.jsonld       JSON-LD @context (one prefix per id namespace + @vocab)
data/
  court.json  positions.json  action-types.json  rules.json  tactics.json
  players.json             illustrative rosters (fictional)
  plays/*.json             one file per play graph
basketball_kg/
  model.py    node/graph dataclasses, loaders, validation, search
  graph.py    NetworkX projection, ego subgraphs, node-link export
  rdf.py      RDF builder, JSON-LD exporter, SPARQL runner
  queries.py  12 intents -> query plan -> SPARQL / Cypher / in-memory
  nlq.py      natural language -> query plan (rules + alias index)
  viz.py      Graphviz DOT export, ASCII half-court renderer
  serve.py    stdlib HTTP server: read-only JSON API + static files
  cli.py      command line interface
web/
  index.html  single-file explorer UI (no build, no CDN)
queries/
  sparql/*.rq            10 generated example queries (all executed by the tests)
  cypher/*.cypher        the same 10 as Cypher
  nl_to_query.json       NL -> intent -> slots -> three renderings
scripts/gen_queries.py   regenerates queries/ from the templates (--check in CI)
tests/                   93 unittest tests
docs/                    ONTOLOGY.md, PLAY_MODELS.md, QUERY_COOKBOOK.md
```

### Adding knowledge

1. Add a node to the right `data/*.json` file (or a new file — the loader globs `data/**/*.json`).
2. Use an existing class from `ONTOLOGY_CLASSES` and predicates declared in
   `ontology/basketball.jsonld`; add new ones to both if you need them.
3. Run `python -m basketball_kg.cli validate` (checks CURIE syntax, known types,
   dangling references) and `python -m unittest discover -s tests`.
4. If you touched a query template, run `python scripts/gen_queries.py`.

Node shape:

```json
{
  "id": "atype:slip-screen",
  "type": "ActionType",
  "label": "Slip the screen",
  "definition": "Fake the screen and cut early to the rim…",
  "props": { "domain": "offense" },
  "edges": { "constrainedBy": ["rule:legal-screen"] }
}
```

---

## Scope and limitations

* **Teaching model, not tracking data.** Zone coordinates are approximate feet on a
  50 ft × 47 ft half court; they exist to make adjacency and spacing computable, not
  to reproduce any league's tracking specification.
* **No statistics, no predictions.** The graph encodes *structure and meaning*: what a
  tactic is, who can execute it, what beats it, and which rules bound it. It deliberately
  contains no shot charts, ratings, or win probabilities.
* **Rosters are fictional.** `data/players.json` exists to demonstrate roster-fit and
  matchup queries; the `exemplar` field on archetypes is an editorial illustration.
* **Rules are stated for the NBA rule set**, with FIBA/WNBA differences noted in `note`.
* **The NL parser is rule-based.** It is deterministic, inspectable and dependency-free;
  it will not paraphrase like an LLM, and it says so: every answer ships with the rule
  and the alias that produced it.

## License

MIT — see [LICENSE](LICENSE).
