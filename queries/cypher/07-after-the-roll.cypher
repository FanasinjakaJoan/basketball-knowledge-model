// Basketball Knowledge Model -- example query
// question : What happens after the roll?
// intent   : sequence
// slots    : action=pnr:s5-roll
// note     : precedes / follows: the temporal spine of a play.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Before / after a step
MATCH (s {id: 'pnr:s5-roll'})
OPTIONAL MATCH (s)-[:PRECEDES]->(n)
OPTIONAL MATCH (p)-[:PRECEDES]->(s)
OPTIONAL MATCH (n)-[:HAS_ACTION_TYPE]->(nt:ActionType)
OPTIONAL MATCH (p)-[:HAS_ACTION_TYPE]->(pt:ActionType)
RETURN s.label AS step,
       collect(DISTINCT {rel: 'before', label: p.label, type: pt.label}) AS before,
       collect(DISTINCT {rel: 'after', label: n.label, type: nt.label}) AS after;
