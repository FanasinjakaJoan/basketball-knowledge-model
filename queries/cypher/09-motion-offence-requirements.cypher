// Basketball Knowledge Model -- example query
// question : What kind of players does motion offence need?
// intent   : requirements
// slots    : target=play:motion-offense
// note     : Requirements roll up from steps and from the action types they instantiate.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Archetypes and skills demanded by a scheme / play / action
MATCH (t {id: 'play:motion-offense'})
OPTIONAL MATCH (t)-[:REQUIRES]->(req)
OPTIONAL MATCH (t)-[:HAS_STEP]->(s)-[:REQUIRES]->(req2)
OPTIONAL MATCH (t)-[:HAS_STEP]->(s2)-[:HAS_ACTION_TYPE]->(at)-[:REQUIRES]->(req3)
WITH collect(DISTINCT req) + collect(DISTINCT req2) + collect(DISTINCT req3) AS reqs
UNWIND reqs AS requirement
WITH DISTINCT requirement WHERE requirement IS NOT NULL
OPTIONAL MATCH (requirement)-[:REQUIRES]->(skill)
RETURN requirement.label AS requirement, labels(requirement) AS type, collect(skill.label) AS skills
ORDER BY type, requirement;
