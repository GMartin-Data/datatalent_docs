# Composant : ingestion-shared

## Contexte

Projet DataTalent — pipeline data GCP, équipe de 4 devs.
Ce composant est le **premier à implémenter** (T0.2, bloquant). Les 3 scripts d'ingestion (France Travail, Sirene, Géo) en dépendent.

## Périmètre

### Dedans

- `ingestion/shared/gcs.py` — upload de fichiers locaux vers GCS
- `ingestion/shared/bigquery.py` — chargement de GCS vers BigQuery raw
- `ingestion/shared/logging.py` — logger structuré (structlog)
- `ingestion/shared/__init__.py`
- `ingestion/main.py` — entrypoint séquentiel Cloud Run Job
- `.github/workflows/ci.yml` — workflow CI dev (lint + tests sur chaque PR)

### Dehors

- Logique métier des sources (OAuth2, parsing Parquet, appels API Géo)
- Tests des sources individuelles
- Configuration GCP (bucket, datasets) — faite par Collègue 4 (T0.1)
- Jobs CI dbt et Terraform — ajoutés aux Blocs 2-3 quand pertinent

## Contrat d'interface

### `ingestion/shared/gcs.py`

```python
def upload_to_gcs(local_path: str, gcs_prefix: str) -> str:
    """Upload un fichier local vers GCS.

    Args:
        local_path: chemin du fichier local (ex: /tmp/offres.json)
        gcs_prefix: préfixe source dans le bucket (ex: "france_travail")

    Returns:
        URI GCS complète (ex: gs://datatalent-raw/france_travail/2026-03-09/offres.json)

    La fonction construit le path final : gs://{BUCKET}/{gcs_prefix}/{YYYY-MM-DD}/{filename}
    """
```

### `ingestion/shared/bigquery.py`

```python
def load_gcs_to_bq(gcs_uri: str, dataset: str, table: str) -> None:
    """Charge un fichier GCS dans une table BigQuery.

    Args:
        gcs_uri: URI GCS retournée par upload_to_gcs
        dataset: nom du dataset BQ (ex: "raw")
        table: nom de la table BQ (ex: "france_travail")

    La fonction :
    - configure le load job (autodetect schema, write disposition)
    - ajoute la colonne _ingestion_date automatiquement
    """
```

### `ingestion/shared/logging.py`

```python
def get_logger(name: str) -> structlog.BoundLogger:
    """Retourne un logger structuré configuré pour le module donné."""
```

### `ingestion/main.py`

Entrypoint unique pour Cloud Run Job. Script séquentiel qui appelle `run()` de chaque source :

```python
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

## CI dev (`.github/workflows/ci.yml`)

Workflow minimal Bloc 1, déclenché sur chaque PR vers `main`. Périmètre limité à l'ingestion — dbt et Terraform ajoutés aux Blocs 2-3.

```yaml
# Jobs (parallèles) :
# 1. lint — ruff check + ruff format --check
# 2. test — uv run pytest
```

Ce workflow est posé dès `shared/` et s'applique automatiquement à toutes les PR suivantes (france_travail, sirene, geo). Les collègues n'ont rien à configurer — le CI tourne dès qu'ils ouvrent une PR.

## Conventions

- Bucket GCS : `datatalent-raw`
- Paths GCS : `{source}/{YYYY-MM-DD}/{filename}`
- Datasets BQ : `raw`, `staging`, `intermediate`, `marts`
- Horodatage : colonne `_ingestion_date` ajoutée automatiquement par `load_gcs_to_bq`
- Chaque source expose une fonction `run()` sans arguments dans `{source}/ingest.py`
- Auth GCP : Application Default Credentials (pas de clé en dur)

## Ownership et règles Git

- **Owner : Greg** — seul à modifier `ingestion/shared/` et `ingestion/main.py`
- Signatures figées J1 matin. Après merge dans main : **PR obligatoire** pour tout changement
- Les collègues importent `shared/` mais ne le modifient pas

## Contraintes techniques

- Python 3.12+, structlog, google-cloud-storage, google-cloud-bigquery
- Package manager : uv (pyproject.toml + uv.lock)
- Retry réseau : tenacity (backoff exponentiel)
- Scripts idempotents : ré-exécuter ne crée pas de doublons

## Entrées / Sorties

| Entrée | Fournisseur |
|---|---|
| Bucket GCS `datatalent-raw` créé | Collègue 4 (T0.1) |
| 4 datasets BQ créés | Collègue 4 (T0.1) |

| Sortie | Consommateur |
|---|---|
| Interface `shared/` stable et documentée | 3 scripts d'ingestion |
| `main.py` exécutable | Cloud Run Job / docker-compose |
| `ci.yml` opérationnel (lint + tests) | Toutes les PR suivantes |

## Décisions de référence

- D5 : structure BigQuery 4 datasets
- D16 : structure repo, `ingestion/shared/` à stabiliser J1
- D19 : Cloud Run Job, entrypoint `python main.py`
- D20 : uv, pyproject.toml + uv.lock
- D22 : CI GitHub Actions, lint + tests sur PR
