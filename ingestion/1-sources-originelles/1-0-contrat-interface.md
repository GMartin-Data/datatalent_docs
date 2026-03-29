# Contrat d'interface — `ingestion/shared/`

## Vue d'ensemble

> **⚠ Vue partielle** — seuls les fichiers pertinents au contrat d'interface sont affichés.
> Fichiers omis par source : `__init__.py`, `config.py`, `client.py` (France Travail uniquement).
> Fichiers omis à la racine : `Dockerfile`, `pyproject.toml`, `uv.lock`, `tests/`.
> Arborescence complète : voir `structure-repo.md`.

```
ingestion/
├── shared/                     ← Greg — interface commune, ne pas modifier
│   ├── gcs.py                  upload_to_gcs(local_path, gcs_prefix) → str
│   ├── bigquery.py             load_gcs_to_bq(gcs_uri, dataset, table) → None
│   └── logging.py              get_logger(name) → structlog.BoundLogger
│
├── france_travail/
│   └── ingest.py               expose run()
├── sirene/
│   └── ingest.py               expose run()
├── geo/
│   └── ingest.py               expose run()
│
└── main.py                     ← Greg — appelle run() de chaque source
```

Chaque source importe depuis `shared/`, implémente sa logique métier, et expose `run()`. `main.py` orchestre le tout.

## Principe

`ingestion/shared/` expose 3 modules que chaque script d'ingestion appelle pour interagir avec GCP. Les collègues n'ont pas besoin de savoir comment GCS ou BigQuery fonctionnent — ils appellent deux fonctions et passent le minimum d'arguments.

## Parcours d'une ingestion

Prenons le parcours d'une source — France Travail — pour montrer comment `shared/` intervient.

```
france_travail/ingest.py (logique métier)
        │
        │  1. Extraction : OAuth2 → pagination → données JSON en mémoire
        │
        │  2. Écriture locale : JSON → fichier temporaire
        │
        │  3. Upload GCS
        │     └── shared/gcs.py : upload_to_gcs(local_path, gcs_prefix)
        │         → gs://datatalent-raw/france_travail/2026-03-09/offres.json
        │
        │  4. Chargement BQ
        │     └── shared/bigquery.py : load_gcs_to_bq(gcs_uri, dataset, table)
        │         → raw.france_travail (avec _ingestion_date)
        │
        │  (tout du long)
        │     └── shared/logging.py : logger structuré
        │
        ▼
      Terminé → main.py passe à sirene
```

## Exemple concret dans le code d'un collègue

```python
# ingestion/geo/ingest.py

import json
from pathlib import Path

import httpx
from ingestion.shared.gcs import upload_to_gcs
from ingestion.shared.bigquery import load_gcs_to_bq
from ingestion.shared.logging import get_logger

logger = get_logger(__name__)

def run():
    # 1. Extraction (logique métier propre à cette source)
    regions = httpx.get("https://geo.api.gouv.fr/regions").json()

    # 2. Écriture locale temporaire
    local_path = "/tmp/geo_regions.json"
    Path(local_path).write_text(json.dumps(regions, ensure_ascii=False))

    # 3. Upload GCS — appel shared
    gcs_uri = upload_to_gcs(local_path, "geo/regions")
    logger.info("gcs_upload_done", uri=gcs_uri)

    # 4. Chargement BQ — appel shared
    load_gcs_to_bq(gcs_uri, dataset="raw", table="geo_regions")
    logger.info("bq_load_done", table="raw.geo_regions")
```

## Ce que `shared/` masque

Le collègue n'a pas besoin de savoir :

- **`gcs.py`** : comment s'authentifier auprès de GCS, quel bucket utiliser, comment construire le path avec la date, comment gérer les erreurs d'upload
- **`bigquery.py`** : comment configurer le load job BQ, le write disposition, l'ajout de `_ingestion_date`, le schéma auto-detect
- **`logging.py`** : le format structuré, la configuration structlog

Il appelle deux fonctions, il passe le minimum d'arguments. Le reste est standardisé.

## L'entrypoint `main.py` — pourquoi `run()`

`ingestion/main.py` est le point d'entrée unique que Cloud Run Job exécute. C'est un script séquentiel qui appelle les 3 ingestions l'une après l'autre :

```python
# ingestion/main.py

from ingestion.france_travail.ingest import run as run_france_travail
from ingestion.sirene.ingest import run as run_sirene
from ingestion.geo.ingest import run as run_geo
from ingestion.shared.logging import get_logger

logger = get_logger(__name__)

def main():
    logger.info("ingestion_start")
    run_france_travail()
    run_sirene()
    run_geo()
    logger.info("ingestion_end")

if __name__ == "__main__":
    main()
```

Sans `main.py`, Cloud Run devrait savoir quel script lancer pour quelle source. Avec `main.py`, la commande Docker est toujours la même : `python main.py`. Un seul conteneur, une seule commande, toutes les sources ingérées en séquence.

**Convention `run()` :** chaque source expose une fonction `run()` sans arguments dans `{source}/ingest.py`. C'est le contrat entre `main.py` et les scripts d'ingestion. Greg est le seul owner de `main.py` — les collègues ne le modifient pas, ils exportent juste leur `run()`.

## Le contrat en résumé

| Fonction | Le collègue fournit | `shared/` gère |
|---|---|---|
| `upload_to_gcs(local_path, gcs_prefix)` | Fichier local + préfixe source | Bucket, datation du path, auth, upload |
| `load_gcs_to_bq(gcs_uri, dataset, table)` | URI GCS + dataset + table | Load job config, `_ingestion_date`, auth |
| `get_logger(__name__)` | Nom du module | Format structuré, niveau, sortie |
