# Composant : ingestion-geo

## Contexte

Projet DataTalent — pipeline data GCP, équipe de 4 devs.
Source la plus simple du Bloc 1 : API ouverte, aucune auth, 3 appels GET, volume négligeable (~5 Mo).
Assignée à Collègue 3. Dépend de `ingestion/shared/` (composant `ingestion-shared`, implémenté en amont).

## Périmètre

### Dedans

- `ingestion/geo/ingest.py` — 3 appels GET → écriture JSON locale → `shared/gcs.py` → `shared/bigquery.py`. Expose `run()`
- `ingestion/geo/config.py` — base URL, endpoints, paramètres `fields`
- `ingestion/geo/__init__.py`

### Dehors

- `ingestion/shared/` — déjà implémenté, consommé tel quel
- `ingestion/main.py` — appelle `run()`, ne connaît pas les détails
- Enrichissement géographique des offres (jointure code commune) — dbt intermediate, Bloc 2
- Refresh — aucune automatisation (données quasi-statiques, dernier redécoupage régional = 2016)

## Source de données — Spécifications techniques

### Accès

- **Base URL :** `https://geo.api.gouv.fr`
- **Authentification :** aucune (API ouverte)
- **Rate limiting :** 50 requêtes/seconde/IP (largement suffisant pour 3 appels)
- **Format :** JSON
- **Spec :** [definition.yml](https://github.com/datagouv/api-geo/blob/master/definition.yml) (Swagger 2.0)

### Endpoints

| Endpoint | Description | Volume |
|----------|-------------|--------|
| `GET /regions` | Liste complète des régions | ~18 entrées |
| `GET /departements` | Liste complète des départements | ~101 entrées |
| `GET /communes` | Liste complète des communes | ~35 000 entrées |

Paramètre utile : `fields` (sélection des champs retournés, CSV).

### Schéma Région

| Champ | Type | Usage projet |
|-------|------|-------------|
| `code` | string | **Clé de jointure** |
| `nom` | string | Dashboard |
| `zone` | string (metro, drom, com) | Filtrage |

### Schéma Département

| Champ | Type | Usage projet |
|-------|------|-------------|
| `code` | string | **Clé de jointure** |
| `nom` | string | Dashboard |
| `codeRegion` | string | Jointure région |
| `zone` | string (metro, drom, com) | Filtrage |

### Schéma Commune (champs utiles)

| Champ | Type | Usage projet |
|-------|------|-------------|
| `code` | string (code INSEE) | **Clé de jointure** offres & Sirene |
| `nom` | string | Dashboard |
| `codesPostaux` | array[string] | Jointure fallback |
| `codeDepartement` | string | Jointure département |
| `codeRegion` | string | Jointure région |
| `population` | int | Enrichissement |
| `centre` | GeoJSON Point | Cartographie (lat/lon) |
| `surface` | float (hectares) | Enrichissement |

Champs disponibles mais non retenus : `siren`, `codeEpci`, `contour` (Polygon GeoJSON, ~34 Mo pour toute la France — trop lourd, inutile), `mairie`, `bbox`.

### Stratégie : snapshot complet en raw (D13)

Les données géographiques changent très rarement. Stocker un snapshot JSON élimine la dépendance API à runtime. Le guide Etalab recommande cette approche.

## Flux d'exécution

```
run()
  │
  ├── 1. GET /regions → /tmp/geo_regions.json
  ├── 2. GET /departements → /tmp/geo_departements.json
  ├── 3. GET /communes → /tmp/geo_communes.json
  │
  ├── 4. Pour chaque fichier :
  │       ├── shared/gcs.py → upload_to_gcs(local_path, "geo/{entité}")
  │       │    → gs://datatalent-raw/geo/YYYY-MM-DD/regions.json
  │       │    → gs://datatalent-raw/geo/YYYY-MM-DD/departements.json
  │       │    → gs://datatalent-raw/geo/YYYY-MM-DD/communes.json
  │       │
  │       └── shared/bigquery.py → load_gcs_to_bq(gcs_uri, "raw", table)
  │            → raw.geo_regions
  │            → raw.geo_departements
  │            → raw.geo_communes
  │
  └── Terminé
```

## Idempotence

- Ré-exécuter le script le même jour écrase les fichiers GCS (même path daté) et recharge BQ sans doublons

## Jointure avec les offres (D15) — pour référence aval

- **Jointure primaire :** `lieuTravail.commune` (offres) → `communes.code` (API Géo)
- **Fallback :** code département extrait de `lieuTravail.libelle` (format "XX - Ville")
- **Enrichissement obtenu :** nom département, nom région, population, coordonnées centre
- Cette logique est dans dbt intermediate (Bloc 2), pas dans ce composant

## Entrées / Sorties

| Entrée | Fournisseur |
|---|---|
| API Géo `https://geo.api.gouv.fr` | Gouvernement (libre) |
| Interface `shared/` stable | Composant `ingestion-shared` |

| Sortie | Consommateur |
|---|---|
| 3 fichiers JSON dans `gs://datatalent-raw/geo/YYYY-MM-DD/` | BigQuery load jobs |
| Tables `raw.geo_regions`, `raw.geo_departements`, `raw.geo_communes` | dbt staging/intermediate (Bloc 2) |

## Contraintes techniques

- Python 3.12+, httpx (HTTP client), structlog (logging)
- Auth GCP : Application Default Credentials
- Retry réseau via tenacity (backoff exponentiel) — même si l'API est très fiable
- Volume négligeable (~5 Mo total) — pas de contrainte mémoire

## Ownership

- **Owner : Collègue 3** (J1 après-midi → J2)
- Après fin US4 (~J2 après-midi) : bascule sur T1.4 + T1.5 (cartographie transverse)

## Décisions de référence

- D13 : snapshot complet en raw, pas d'appels API à runtime
- D15 : enrichissement géographique via code commune INSEE
