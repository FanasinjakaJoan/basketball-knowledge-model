// Basketball Knowledge Model -- example query
// question : What should we run late in the shot clock?
// intent   : situations
// slots    : situation=sit:late-clock
// note     : appliesIn ties schemes and plays to the game situation they are built for.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Schemes and plays used in a game situation
MATCH (s)-[:APPLIES_IN]->(sit:Situation {id: 'sit:late-clock'})
OPTIONAL MATCH (s)-[:HAS_FORMATION]->(f:Formation)
OPTIONAL MATCH (s)-[:HAS_COVERAGE]->(c:Coverage)
RETURN labels(s) AS kind, s.label AS scheme, f.label AS formation, c.label AS coverage
ORDER BY kind, scheme;
