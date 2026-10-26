// Basketball Knowledge Model -- example query
// question : What rules govern setting a screen?
// intent   : rules
// slots    : target=atype:set-on-ball-screen
// note     : Rules attach to action *types*, so every screening action inherits them.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Rules constraining a play / action / zone
MATCH (t {id: 'atype:set-on-ball-screen'})
OPTIONAL MATCH (t)-[:CONSTRAINED_BY|:HAS_STEP|]->(x)
OPTIONAL MATCH (x)-[:CONSTRAINED_BY]->(r:Rule)
OPTIONAL MATCH (t)<-[:GOVERNS]-(r2:Rule)
OPTIONAL MATCH (t)-[:HAS_ACTION_TYPE]->(at)-[:CONSTRAINED_BY]->(r3:Rule)
WITH collect(DISTINCT r) + collect(DISTINCT r2) + collect(DISTINCT r3) AS rules
UNWIND rules AS rule
WITH DISTINCT rule WHERE rule IS NOT NULL
OPTIONAL MATCH (rule)-[:HAS_RULE_TYPE]->(rt:RuleType)
RETURN rule.label AS rule, rt.label AS ruleType, rule.threshold AS threshold, rule.penaltyText AS penalty;
