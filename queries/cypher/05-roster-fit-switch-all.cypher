// Basketball Knowledge Model -- example query
// question : Which players fit a switch-everything scheme?
// intent   : fit
// slots    : scheme=scheme:switch-all
// note     : Joins the scheme's archetype requirements against player archetypes.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Roster fit: players carrying the archetypes a scheme needs
MATCH (s:Scheme {id: 'scheme:switch-all'})-[:REQUIRES]->(arch)
MATCH (pl:Player)-[:HAS_ARCHETYPE]->(arch)

OPTIONAL MATCH (pl)-[:PLAYS_FOR]->(team:Team)
OPTIONAL MATCH (pl)-[:OCCUPIES_POSITION]->(pos:Position)
RETURN pl.label AS player, team.label AS team, pos.abbreviation AS position,
       count(DISTINCT arch) AS matches, collect(DISTINCT arch.label) AS archetypes
ORDER BY matches DESC, player;
