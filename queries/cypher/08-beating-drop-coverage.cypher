// Basketball Knowledge Model -- example query
// question : What beats drop coverage?
// intent   : counters
// slots    : target=coverage:drop
// note     : The branch steps of the pick-and-roll read the same coverage vocabulary.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Tactical answers to a scheme or coverage
MATCH (t {id: 'coverage:drop'})
MATCH (c:Counter) WHERE (t)-[:HAS_COUNTER]->(c) OR (c)-[:ANSWERS]->(t) OR (c)-[:EXPLOITS]->(t)
OPTIONAL MATCH (c)-[:EXPLOITS]->(w)
RETURN c.label AS counter, c.vulnerability AS vulnerability, c.rationale AS rationale,
       c.effectiveness AS effectiveness, collect(DISTINCT w.label) AS exploits
ORDER BY c.effectiveness DESC;
