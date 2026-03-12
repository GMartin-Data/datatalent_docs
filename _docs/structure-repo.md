# Structure du Repo — Projet DataTalent

**Dernière mise à jour :** 2026-03-09
**Décisions associées :** D16, D17, D18, D19, D20, D21, D22 (voir `notes-projet.md`)

---

## Arborescence Bloc 1 — Vue équipe

Ce que chaque membre doit connaître pour commencer à coder.

```
datatalent/
├── README.md
├── .gitignore
├── .python-version            # Version Python (uv la respecte)
├── .pre-commit-config.yaml    # Hooks : commitlint + ruff (D22)
├── docker-compose.yml
├── .github/
│   └── workflows/
│       ├── ci.yml             # Lint + dbt validate + tf validate (sur PR)
│       └── deploy.yml         # Build Docker + deploy Cloud Run Job (sur merge main)
│
├── ingestion/
│   ├── france_travail/
│   │   ├── __init__.py
│   │   ├── client.py           # OAuth2, pagination, rate limiting
│   │   ├── ingest.py           # Extract → GCS → BQ raw
│   │   └── config.py           # Codes ROME, endpoints
│   ├── sirene/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   └── config.py
│   ├── geo/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   └── config.py
│   ├── shared/                 # ⚠ Stabiliser en J1 — interface commune
│   │   ├── __init__.py
│   │   ├── gcs.py              # upload_to_gcs(local_path, gcs_prefix)
│   │   ├── bigquery.py         # load_gcs_to_bq(gcs_uri, dataset, table)
│   │   └── logging.py          # Logging structuré
│   ├── main.py                 # Entrypoint Cloud Run Job — script Python séquentiel (D19)
│   ├── Dockerfile
│   ├── pyproject.toml          # Dépendances Python (uv — D20)
│   ├── uv.lock                 # Lockfile déterministe (uv — D20)
│   └── tests/
│
├── dbt/                        # Structure détaillée en Bloc 2
│   └── Dockerfile              # Image dbt-bigquery officielle (D20)
│
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf
│   ├── providers.tf
│   ├── terraform.tfvars.example
│   └── modules/
│       ├── gcs/
│       ├── bigquery/
│       ├── cloud_run/
│       ├── scheduler/
│       ├── iam/
│       └── secret_manager/
│
└── docs/
    ├── architecture.md
    ├── architecture.mermaid
    ├── data-catalog.md
    └── setup-gcp.md
```

---

## Arborescence complète — Référence

Inclut la sous-arborescence dbt (Bloc 2+).

```
datatalent/
├── README.md
├── .gitignore
├── .python-version
├── .pre-commit-config.yaml    # commitlint + ruff
├── docker-compose.yml
├── .github/
│   └── workflows/
│       ├── ci.yml
│       └── deploy.yml
│
├── ingestion/
│   ├── france_travail/
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── ingest.py
│   │   └── config.py
│   ├── sirene/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   └── config.py
│   ├── geo/
│   │   ├── __init__.py
│   │   ├── ingest.py
│   │   └── config.py
│   ├── shared/
│   │   ├── __init__.py
│   │   ├── gcs.py
│   │   ├── bigquery.py
│   │   └── logging.py
│   ├── main.py
│   ├── Dockerfile
│   ├── pyproject.toml
│   ├── uv.lock
│   └── tests/
│       ├── test_france_travail.py
│       ├── test_sirene.py
│       └── test_geo.py
│
├── dbt/
│   ├── Dockerfile
│   ├── dbt_project.yml
│   ├── profiles.yml.example    # Template — voir D17
│   ├── packages.yml
│   ├── models/
│   │   ├── staging/
│   │   │   ├── france_travail/
│   │   │   │   ├── _france_travail__models.yml
│   │   │   │   └── stg_france_travail__offres.sql
│   │   │   ├── sirene/
│   │   │   │   ├── _sirene__models.yml
│   │   │   │   └── stg_sirene__etablissements.sql
│   │   │   └── geo/
│   │   │       ├── _geo__models.yml
│   │   │       ├── stg_geo__regions.sql
│   │   │       ├── stg_geo__departements.sql
│   │   │       └── stg_geo__communes.sql
│   │   ├── intermediate/
│   │   │   ├── _intermediate__models.yml
│   │   │   └── int_offres__enrichies.sql
│   │   └── marts/
│   │       ├── _marts__models.yml
│   │       ├── mart_offres_par_geo.sql
│   │       ├── mart_offres_par_secteur.sql
│   │       └── mart_offres_par_periode.sql
│   ├── macros/
│   ├── seeds/
│   ├── snapshots/
│   └── tests/
│
├── infra/
│   ├── main.tf
│   ├── variables.tf
│   ├── outputs.tf
│   ├── backend.tf
│   ├── providers.tf
│   ├── terraform.tfvars.example
│   └── modules/
│       ├── gcs/
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── bigquery/
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── cloud_run/
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── scheduler/
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       ├── iam/
│       │   ├── main.tf
│       │   ├── variables.tf
│       │   └── outputs.tf
│       └── secret_manager/
│           ├── main.tf
│           ├── variables.tf
│           └── outputs.tf
│
└── docs/
    ├── architecture.md
    ├── architecture.mermaid
    ├── data-catalog.md
    └── setup-gcp.md
```

---

## Conventions de nommage

| Élément | Convention | Exemple |
|---------|-----------|---------|
| Dossiers Python | `snake_case` | `france_travail/` |
| Fichiers Python | `snake_case.py` | `client.py`, `ingest.py` |
| Modules Terraform | `snake_case` | `cloud_run/`, `secret_manager/` |
| Modèles dbt | `{layer}_{source}__{entité}.sql` | `stg_france_travail__offres.sql` |
| YAML dbt | `_{source}__models.yml` | `_sirene__models.yml` |
| Branches Git | `{type}/{scope}` | `feat/ingestion-france-travail` |
| Commits | Conventional Commits | `feat(ingestion): add OAuth2 client` |

---

## Fichiers sensibles (.gitignore)

| Fichier | Raison | Template versionné |
|---------|--------|--------------------|
| `dbt/profiles.yml` | Contient le project ID GCP | `profiles.yml.example` |
| `infra/terraform.tfvars` | Contient project ID, region | `terraform.tfvars.example` |
| `infra/.terraform/` | State local Terraform | — |
| `.env` | Variables d'environnement locales | — |
| `.venv/` | Environnement virtuel local (uv) | — |

---

## Onboarding développeur (J1)

```bash
# 1. Clone
git clone git@github.com:<org>/datatalent.git && cd datatalent

# 2. Python + dépendances
uv sync                        # dans ingestion/

# 3. Pre-commit hooks
uv tool install pre-commit
pre-commit install

# 4. Fichiers locaux
cp dbt/profiles.yml.example dbt/profiles.yml          # → remplacer PROJECT_ID
cp infra/terraform.tfvars.example infra/terraform.tfvars  # → idem
```
