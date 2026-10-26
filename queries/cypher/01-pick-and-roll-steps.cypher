// Basketball Knowledge Model -- example query
// question : Walk me through the pick and roll.
// intent   : play_steps
// slots    : play=play:pick-and-roll
// note     : Ordered action graph: who does what, where, under which constraint.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Ordered steps of a play (property-graph form)
MATCH (p:Play {id: 'play:pick-and-roll'})-[:HAS_STEP]->(s:Action)
OPTIONAL MATCH (s)-[:HAS_ACTION_TYPE]->(t:ActionType)
OPTIONAL MATCH (s)-[:ACTOR]->(r:Role)
OPTIONAL MATCH (s)-[:STARTS_IN]->(z1:Zone)
OPTIONAL MATCH (s)-[:ENDS_IN]->(z2:Zone)
OPTIONAL MATCH (s)-[:PRECEDES]->(n:Action)
RETURN s.order AS order, s.label AS step, t.label AS actionType, r.label AS actor,
       z1.label AS fromZone, z2.label AS toZone, n.label AS next
ORDER BY order;
