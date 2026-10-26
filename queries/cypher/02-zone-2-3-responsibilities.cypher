// Basketball Knowledge Model -- example query
// question : What are the 2-3 zone assignments?
// intent   : zone_responsibility
// slots    : scheme=play:zone-defense-2-3
// note     : Area duties are reified as Assignment nodes so they survive the trip to RDF.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Area responsibilities in a defensive scheme
MATCH (a:Assignment)-[:OF_SCHEME]->(s)
MATCH (a)-[:COVERS_ZONE]->(z:Zone)
OPTIONAL MATCH (a)-[:HELD_BY]->(r:Role)
WHERE s.id = 'play:zone-defense-2-3'
RETURN s.label AS scheme, a.label AS assignment, r.label AS heldBy, collect(z.label) AS zones
ORDER BY assignment;
