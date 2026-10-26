# Query library

Generated. **Do not edit by hand** — every file here is rendered from the templates in
`basketball_kg/queries.py`:

```bash
python scripts/gen_queries.py          # regenerate
python scripts/gen_queries.py --check  # fail in CI if anything drifted
```

| File | Question | Intent |
|---|---|---|
| `01-pick-and-roll-steps` | Walk me through the pick and roll. | `play_steps` |
| `02-zone-2-3-responsibilities` | What are the 2-3 zone assignments? | `zone_responsibility` |
| `03-attack-the-2-3-zone` | How do you attack a 2-3 zone? | `counters` |
| `04-rules-for-screening` | What rules govern setting a screen? | `rules` |
| `05-roster-fit-switch-all` | Which players fit a switch-everything scheme? | `fit` |
| `06-short-corner-geometry` | What is next to the short corner? | `spatial` |
| `07-after-the-roll` | What happens after the roll? | `sequence` |
| `08-beating-drop-coverage` | What beats drop coverage? | `counters` |
| `09-motion-offence-requirements` | What kind of players does motion offence need? | `requirements` |
| `10-late-clock-options` | What should we run late in the shot clock? | `situations` |

Each question exists as `sparql/<slug>.rq` and `cypher/<slug>.cypher` — the same query
plan rendered for the two back ends. All ten SPARQL files are executed by the test suite
(`tests/test_rdf.py`), so they are guaranteed to run against the current data.

## `nl_to_query.json`

Natural language → structured query, with everything the parser produced:

```json
{
  "question": "How do you attack a 2-3 zone?",
  "expected_intent": "counters",
  "expected_slots": { "target": "scheme:zone-2-3" },
  "parsed": {
    "intent": "counters",
    "slots": { "target": "scheme:zone-2-3" },
    "confidence": 0.8,
    "evidence": ["rule:counters matched /…/", "slot:target <- '2 3 zone' (scheme:zone-2-3)"]
  },
  "rows_returned": 5,
  "graph_pattern": [ { "s": "?target", "p": "hasCounter", "o": "?counter" }, … ],
  "sparql": "…",
  "cypher": "…"
}
```

`tests/test_queries.py` asserts that every entry parses to the expected intent and
returns rows, which makes the file both documentation and a regression fixture.
