from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import List, Sequence

from rdflib import Graph


PREFIXES = """\
PREFIX mc:  <http://www.semanticweb.org/lenovo/ontologies/2025/11/untitled-ontology-5#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs:<http://www.w3.org/2000/01/rdf-schema#>
PREFIX owl: <http://www.w3.org/2002/07/owl#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""

OWL_FILES = [
    "factbook_data.owl",
    "movies_from_dbpedia.owl",
    "ontology.owl",
]


@dataclass(frozen=True)
class TestQuery:
    name: str
    sparql: str
    max_rows: int = 8


def _strip_dbpedia(uri_or_lit: str) -> str:
    return uri_or_lit.replace("http://dbpedia.org/resource/", "")


def load_graph() -> Graph:
    g = Graph()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    cwd = os.getcwd()

    def resolve(path: str) -> str:
        if os.path.isabs(path):
            return path
        if os.path.exists(os.path.join(cwd, path)):
            return os.path.join(cwd, path)
        return os.path.join(base_dir, path)

    for fname in OWL_FILES:
        fpath = resolve(fname)
        print(f"Loading {fpath} …")
        if not os.path.exists(fpath):
            print(f"  ✗ Not found: {fname}")
            continue
        try:
            g.parse(fpath, format="xml")
            print(f"  ✓ Loaded {fname}")
        except Exception as e:
            # Keep going so tests can still run with partial data.
            print(f"  ✗ Failed to load {fname}: {e}")
    print(f"Total triples loaded: {len(g)}")
    return g


def run_query(g: Graph, tq: TestQuery, idx: int) -> None:
    print("=" * 80)
    print(f"[{idx:02d}] {tq.name}")
    print("Query:")
    for line in tq.sparql.strip().splitlines():
        print("  " + line)

    start = time.time()
    try:
        res = g.query(tq.sparql)
        rows = list(res)
        elapsed_ms = (time.time() - start) * 1000.0

        print("Result:")
        if not rows:
            print(f"  (0 rows) ({elapsed_ms:.1f} ms)")
            return

        vars_ = [str(v) for v in res.vars]
        print(f"  ({len(rows)} rows) ({elapsed_ms:.1f} ms)")

        for i, row in enumerate(rows[: tq.max_rows], 1):
            parts = []
            for v in res.vars:
                val = row.get(v)
                s = "-" if val is None else _strip_dbpedia(str(val))
                # keep one-line output
                s = s.replace("\n", " ")
                if len(s) > 120:
                    s = s[:117] + "…"
                parts.append(f"{v}={s}")
            print(f"  {i:>2}. " + " | ".join(parts))

        if len(rows) > tq.max_rows:
            print(f"  … {len(rows) - tq.max_rows} more row(s) not shown")

    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000.0
        print("Result:")
        print(f"  [ERROR] ({elapsed_ms:.1f} ms) {e}")


def query_suite() -> List[TestQuery]:
    q: List[TestQuery] = []

    # --- Server UI examples (rewritten to avoid SELECT projection expressions) ---

    q.append(TestQuery(
        "Find movies in a country (United States)",
        PREFIXES
        + """
SELECT DISTINCT ?movie ?title ?country ?director ?actor ?runtime ?releaseDate ?imdbId
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
  ?movie mc:producedInCountry ?country .
  OPTIONAL { ?movie mc:hasDirector ?director }
  OPTIONAL { ?movie mc:hasActor ?actor }
  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }
  OPTIONAL { ?movie mc:releaseDate ?releaseDate }
  OPTIONAL { ?movie mc:imdbId ?imdbId }
  FILTER(CONTAINS(LCASE(STR(?country)), "united_states"))
}
LIMIT 20
""",
    ))

    q.append(TestQuery(
        "Find movies directed by a director (keyword: bob)",
        PREFIXES
        + """
SELECT DISTINCT ?movie ?title ?director ?actor ?country ?runtime ?releaseDate ?imdbId
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
  ?movie mc:hasDirector ?director .
  OPTIONAL { ?movie mc:hasActor ?actor }
  OPTIONAL { ?movie mc:producedInCountry ?country }
  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }
  OPTIONAL { ?movie mc:releaseDate ?releaseDate }
  OPTIONAL { ?movie mc:imdbId ?imdbId }
  FILTER(CONTAINS(LCASE(STR(?director)), "bob"))
}
LIMIT 20
""",
    ))

    q.append(TestQuery(
        "Find actors who acted in a movie (title keyword: robocop)",
        PREFIXES
        + """
SELECT DISTINCT ?movie ?title ?actor
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
  ?movie mc:hasActor ?actor .
  FILTER(CONTAINS(LCASE(STR(?title)), "robocop"))
}
LIMIT 50
""",
    ))

    q.append(TestQuery(
        "Find movies having an actor (keyword: jackie_chan)",
        PREFIXES
        + """
SELECT DISTINCT ?movie ?title ?actor ?director ?country
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
  ?movie mc:hasActor ?actor .
  OPTIONAL { ?movie mc:hasDirector ?director }
  OPTIONAL { ?movie mc:producedInCountry ?country }
  FILTER(CONTAINS(LCASE(STR(?actor)), "jackie_chan"))
}
LIMIT 20
""",
    ))

    q.append(TestQuery(
        "Search movies by title keyword (bob)",
        PREFIXES
        + """
SELECT DISTINCT ?movie ?title ?director ?actor ?country ?runtime ?releaseDate ?imdbId
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
  OPTIONAL { ?movie mc:hasDirector ?director }
  OPTIONAL { ?movie mc:hasActor ?actor }
  OPTIONAL { ?movie mc:producedInCountry ?country }
  OPTIONAL { ?movie mc:runtimeMinutes ?runtime }
  OPTIONAL { ?movie mc:releaseDate ?releaseDate }
  OPTIONAL { ?movie mc:imdbId ?imdbId }
  FILTER(CONTAINS(LCASE(STR(?title)), "bob"))
}
LIMIT 20
""",
    ))

    q.append(TestQuery(
        "Find country facts (Factbook) for a movie title keyword (lorax)",
        PREFIXES
        + """
SELECT DISTINCT ?movieTitle ?countryUri ?capital ?population ?areaKm2 ?description
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?movieTitle .
  ?movie mc:producedInCountry ?countryUri .

  OPTIONAL {
    ?factbookCountry owl:sameAs ?countryUri .
    ?factbookCountry mc:capital ?capital .
    ?factbookCountry mc:population ?population .
    ?factbookCountry mc:areaKm2 ?areaKm2 .
    ?factbookCountry mc:description ?description .
  }

  FILTER(CONTAINS(LCASE(STR(?movieTitle)), "lorax"))
}
LIMIT 20
""",
    ))

    # --- Extra ontology sanity checks (generated) ---

    q.append(TestQuery(
        "Basic sanity: list some movies (movie IRI + title)",
        PREFIXES
        + """
SELECT ?movie ?title
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
}
LIMIT 15
""",
    ))

    q.append(TestQuery(
        "Count movies (should be > 0)",
        PREFIXES
        + """
SELECT (COUNT(DISTINCT ?movie) AS ?movieCount)
WHERE {
  ?movie rdf:type mc:Movie .
}
""",
        max_rows=3,
    ))

    q.append(TestQuery(
        "Count distinct directors and actors (basic coverage)",
        PREFIXES
        + """
SELECT (COUNT(DISTINCT ?director) AS ?directorCount) (COUNT(DISTINCT ?actor) AS ?actorCount)
WHERE {
  ?movie rdf:type mc:Movie .
  OPTIONAL { ?movie mc:hasDirector ?director }
  OPTIONAL { ?movie mc:hasActor ?actor }
}
""",
        max_rows=3,
    ))

    q.append(TestQuery(
        "Movies with runtime >= 120 minutes",
        PREFIXES
        + """
SELECT DISTINCT ?movie ?title ?runtime
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
  ?movie mc:runtimeMinutes ?runtime .
  FILTER(?runtime >= 120)
}
LIMIT 20
""",
    ))

    q.append(TestQuery(
        "Movies released after 2000-01-01",
        PREFIXES
        + """
SELECT DISTINCT ?movie ?title ?releaseDate
WHERE {
  ?movie rdf:type mc:Movie .
  ?movie mc:title ?title .
  ?movie mc:releaseDate ?releaseDate .
  FILTER(?releaseDate >= "2000-01-01"^^xsd:date)
}
LIMIT 20
""",
    ))

    q.append(TestQuery(
        "Countries that appear in both datasets via owl:sameAs",
        PREFIXES
        + """
SELECT DISTINCT ?factbookCountry ?countryUri ?capital ?population
WHERE {
  ?factbookCountry owl:sameAs ?countryUri .
  OPTIONAL { ?factbookCountry mc:capital ?capital }
  OPTIONAL { ?factbookCountry mc:population ?population }
}
LIMIT 20
""",
    ))

    return q


def main() -> int:
    g = load_graph()

    suite = query_suite()
    for i, tq in enumerate(suite, 1):
        run_query(g, tq, i)

    print("=" * 80)
    print(f"Done. Ran {len(suite)} queries.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
