// Basketball Knowledge Model -- example query
// question : How do you attack a 2-3 zone?
// intent   : counters
// slots    : target=scheme:zone-2-3
// note     : Counters carry the vulnerability they exploit and a rationale.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Tactical answers to a scheme or coverage
MATCH (t {id: 'scheme:zone-2-3'})
MATCH (c:Counter) WHERE (t)-[:HAS_COUNTER]->(c) OR (c)-[:ANSWERS]->(t) OR (c)-[:EXPLOITS]->(t)
OPTIONAL MATCH (c)-[:EXPLOITS]->(w)
RETURN c.label AS counter, c.vulnerability AS vulnerability, c.rationale AS rationale,
       c.effectiveness AS effectiveness, collect(DISTINCT w.label) AS exploits
ORDER BY c.effectiveness DESC;
