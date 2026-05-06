---
name: wikidata-sparql
description: Query Wikidata via the SPARQL endpoint. Use whenever the user wants to find entities (people, films, places), look up Wikidata IDs or properties, disambiguate names, discover relationships between entities, or run knowledge-graph queries — even if they don't explicitly mention "SPARQL" or "Wikidata."
---

# Wikidata SPARQL

Query `https://query.wikidata.org/sparql` to explore Wikidata's knowledge graph. The endpoint accepts SPARQL via POST with the `query` form-encoded parameter, and returns JSON when the `Accept: application/sparql-results+json` header is set.

## query script

Prefex the bundled `scripts/query` over raw curl. It handles the curl invocation, Accept header, POST body encoding, and JSON formatting:

```
# inline query
./scripts/query -q 'SELECT * WHERE { ?s ?p ?o } LIMIT 5'

# from stdin (no args)
echo 'SELECT * WHERE { ?s ?p ?o } LIMIT 5' | ./scripts/query

# from file
./scripts/query -f my_query.sparql
```

## Entity discovery

### Find a Wikidata ID by name

Search by exact English label:

```sparql
SELECT ?item ?itemLabel WHERE {
  ?item rdfs:label "Kevin Bacon"@en .
}
```

### Disambiguate names (get descriptions too)

Add `schema:description` — the one-line summary that tells you which "Kevin Bacon" is which:

```sparql
SELECT ?item ?itemLabel ?description WHERE {
  ?item rdfs:label "Kevin Bacon"@en .
  ?item schema:description ?description .
  FILTER(LANG(?description) = "en")
}
```

### List an entity's properties

Once you have a Q-ID, discover what properties are available on it:

```sparql
SELECT ?property ?propertyLabel WHERE {
  wd:Q3454165 ?p ?o .
  ?property wikibase:directClaim ?p .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
} GROUP BY ?property ?propertyLabel
```

## Relationship queries

### Top 10 actors who've worked most with Kevin Bacon

**Prompt:** "Find the top 10 actors who have co-starred with Kevin Bacon the most times."

```sparql
SELECT ?actor ?actorLabel (COUNT(?film) AS ?count) WHERE {
  ?film wdt:P161 wd:Q3454165 .
  ?film wdt:P161 ?actor .
  FILTER(?actor != wd:Q3454165)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
GROUP BY ?actor ?actorLabel
ORDER BY DESC(?count)
LIMIT 10
```

Key pattern: `wdt:P161` is "cast member" — but it lives on the *film* entity, pointing *to* the actor. The direction is `?film wdt:P161 ?actor`, never the reverse.

### Find people who connect Kevin Bacon and Sitting Bull

**Prompt:** "Find people who connect Kevin Bacon and Sitting Bull."

A multi-query research arc: **disambiguate both entities → follow outgoing edges → widen to indirect intersection**. Direct intersections often return empty, so the final query checks for *shared co-stars* rather than shared films.

**Step 1 — Disambiguate Kevin Bacon:**

```sparql
SELECT ?item ?itemLabel ?description WHERE {
  ?item rdfs:label "Kevin Bacon"@en .
  ?item schema:description ?description .
  FILTER(LANG(?description) = "en")
}
```

→ Pick Q3454165, "American actor (born 1958)".

**Step 2 — Disambiguate Sitting Bull:**

```sparql
SELECT ?item ?itemLabel ?description WHERE {
  ?item rdfs:label "Sitting Bull"@en .
  ?item schema:description ?description .
  FILTER(LANG(?description) = "en")
}
```

→ Pick Q43527, "Hunkpapa Lakota medicine man and holy man (1831–1890)".

**Step 3 — What works is Sitting Bull in, and who's in them:**

```sparql
SELECT ?work ?workLabel ?actor ?actorLabel WHERE {
  wd:Q43527 wdt:P1441 ?work .
  ?work wdt:P161 ?actor .
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

→ Sitting Bull (1954 film, Q3821227), 9 cast members.

**Step 4 — Which of those 9 share a film with any of Kevin Bacon's castmates:**

```sparql
SELECT DISTINCT ?sbActor ?sbActorLabel ?sharedFilm ?sharedFilmLabel
                ?baconCoStar ?baconCoStarLabel ?kevinFilm ?kevinFilmLabel WHERE {
  VALUES ?sbActor { wd:Q529541 wd:Q587113 wd:Q642876 wd:Q957639
                    wd:Q1157865 wd:Q1252367 wd:Q3181945 wd:Q3568991
                    wd:Q6237453 }
  ?sharedFilm wdt:P161 ?sbActor .
  ?sharedFilm wdt:P161 ?baconCoStar .
  ?kevinFilm wdt:P161 ?baconCoStar .
  ?kevinFilm wdt:P161 wd:Q3454165 .
  FILTER(?baconCoStar != wd:Q3454165)
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
```

→ Every cast member connects through bridge people like Glenn Ford, Walter Matthau, Rance Howard, and Robert Wagner. The key insight: when the direct intersection returns nothing, widen one hop — check their co-stars' co-stars.

## Property direction gotcha

Many Wikidata properties are directional. If a query with `wdt:Pxxx` returns empty, flip the subject and object. For example: `?actor wdt:P161 ?film` returns nothing, but `?film wdt:P161 ?actor` finds cast lists. When you hit an empty result, flip the triple before assuming the ID is wrong.

## Finding property IDs

If you don't know a property's ID, search by label:

```sparql
SELECT ?property ?propertyLabel WHERE {
  ?property rdf:type wikibase:Property .
  ?property rdfs:label ?propertyLabel .
  FILTER(CONTAINS(LCASE(?propertyLabel), "cast member"))
  FILTER(LANG(?propertyLabel) = "en")
}
```

## Label service

Almost every query benefits from `SERVICE wikibase:label` to resolve Q-IDs into human-readable English names. Always add it unless you specifically want raw URIs:

```sparql
SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
```
