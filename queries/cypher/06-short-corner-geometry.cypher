// Basketball Knowledge Model -- example query
// question : What is next to the short corner?
// intent   : spatial
// slots    : zone=zone:short-corner-left
// note     : Adjacency is the 'one pass away' relation used for spacing and zone rotation.
// generated: python scripts/gen_queries.py (do not edit by hand)
// Spatial neighbourhood of a zone
MATCH (z:Zone {id: 'zone:short-corner-left'})
OPTIONAL MATCH (z)-[:ADJACENT_TO]->(n:Zone)
OPTIONAL MATCH (z)-[:PART_OF]->(p:Zone)
OPTIONAL MATCH (z)-[:HAS_ZONE_TYPE]->(zt:ZoneType)
RETURN z.label AS zone, z.shotValue AS shotValue, z.courtSide AS side,
       z.distanceFromRimFt AS distanceFt, zt.label AS zoneType, p.label AS partOf,
       collect(n.label) AS adjacentTo;
