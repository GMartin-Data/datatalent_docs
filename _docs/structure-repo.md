# Structure du Repo — Projet DataTalent

**Dernière mise à jour :** 2026-03-27 (D36 annulée — plus de seeds dbt, urssaf_masse_salariale en workflow classique)
**Décisions associées :** D16, D17, D18, D19, D20, D21, D22, D35, D37 (voir `notes-projet.md`)

---

## Arborescence Bloc 1-2 — Vue équipe

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
│   ├── urssaf_effectifs/       # D35, P1 — effectifs commune × APE
│   │   ├── __init__.py
│   │   ├── client.py           # Requêtes API Opendatasoft, pagination
│   │   ├── ingest.py           # Extract filtré APE IT → GCS → BQ raw
│   │   └── config.py           # URL API, codes APE IT (D37)
│   ├── urssaf_masse_salariale/ # D35, P3 — masse salariale × NA88
│   │   ├── __init__.py
│   │   ├── client.py           # Requêtes API Opendatasoft, filtre NA88 = 62
│   │   ├── ingest.py           # Extract → JSONL → GCS → BQ raw
│   │   └── config.py           # URL API, filtre NA88
│   ├── bmo/                    # D35, P2 — conditionnel, si spike validé
│   │   ├── __init__.py
│   │   ├── parse_xlsx.py       # Extraction + nettoyage XLSX → JSONL
│   │   └── ingest.py           # Upload JSONL → GCS → BQ raw
│   ├── shared/                 # ⚠ Stabilisé — interface commune, inchangée
│   │   ├── __init__.py
│   │   ├── gcs.py              # upload_to_gcs(local_path, gcs_prefix)
│   │   ├── bigquery.py         # load_gcs_to_bq(gcs_uri, dataset, table)
│   │   └── logging.py          # Logging structuré
│   ├── main.py                 # Entrypoint Cloud Run Job — appelle toutes les sources (D19)
│   ├── Dockerfile
│   ├── pyproject.toml          # Dépendances Python (uv — D20)
│   ├── uv.lock                 # Lockfile déterministe (uv — D20)
│   └── tests/
│
├── dbt/
│   ├── Dockerfile              # Image dbt-bigquery officielle (D20)
│   └── ...                     # Structure détaillée ci-dessous
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

Inclut toutes les sources d'ingestion, la sous-arborescence dbt complète (staging, intermediate, marts), et les tests.

```
datatalent/
├── README.md
├── .gitignore
├── .python-version
├── .pre-commit-config.yaml    # commitlint + ruff
├── .env.example               # Template variables d'environnement (D29)
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
│   ├── urssaf_effectifs/       # D35, P1 — API Opendatasoft, filtré APE IT (D37)
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── ingest.py
│   │   └── config.py
│   ├── urssaf_masse_salariale/ # D35, P3 — API Opendatasoft, filtré NA88 = 62
│   │   ├── __init__.py
│   │   ├── client.py
│   │   ├── ingest.py
│   │   └── config.py
│   ├── bmo/                    # D35, P2 — conditionnel (spike requis)
│   │   ├── __init__.py
│   │   ├── parse_xlsx.py
│   │   └── ingest.py
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
│       ├── test_geo.py
│       ├── test_urssaf_effectifs.py
│       └── test_urssaf_masse_salariale.py
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
│   │   │   ├── geo/
│   │   │   │   ├── _geo__models.yml
│   │   │   │   ├── stg_geo__regions.sql
│   │   │   │   ├── stg_geo__departements.sql
│   │   │   │   └── stg_geo__communes.sql
│   │   │   └── urssaf/
│   │   │       ├── _urssaf__models.yml
│   │   │       ├── stg_urssaf__effectifs_commune_ape.sql
│   │   │       └── stg_urssaf__masse_salariale_na88.sql   # NOUVEAU — P3
│   │   ├── intermediate/
│   │   │   ├── _intermediate__models.yml
│   │   │   ├── int_offres_enrichies.sql                   # LEFT JOIN offres × API Géo (D15)
│   │   │   ├── int_densite_sectorielle_commune.sql        # GROUP BY URSSAF APE IT (D37)
│   │   │   └── int_tensions_bassin_emploi.sql             # Conditionnel (BMO, spike P2)
│   │   └── marts/
│   │       ├── _marts__models.yml
│   │       ├── mart_offres.sql                            # Dashboard principal
│   │       └── mart_contexte_territorial.sql              # Densité IT + tensions + benchmark salaire
│   ├── macros/
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
| Dossiers Python | `snake_case` | `france_travail/`, `urssaf_effectifs/`, `urssaf_masse_salariale/` |
| Fichiers Python | `snake_case.py` | `client.py`, `ingest.py`, `parse_xlsx.py` |
| Modules Terraform | `snake_case` | `cloud_run/`, `secret_manager/` |
| Modèles dbt staging | `stg_{source}__{entité}.sql` | `stg_france_travail__offres.sql`, `stg_urssaf__masse_salariale_na88.sql` |
| Modèles dbt intermediate | `int_{concept}.sql` | `int_offres_enrichies.sql`, `int_densite_sectorielle_commune.sql` |
| Modèles dbt marts | `mart_{domaine}.sql` | `mart_offres.sql`, `mart_contexte_territorial.sql` |
| YAML dbt modèles | `_{source}__models.yml` | `_sirene__models.yml`, `_urssaf__models.yml` |
| Branches Git | `{type}/{scope}` | `feat/ingestion-urssaf-effectifs` |
| Commits | Conventional Commits | `feat(ingestion): add URSSAF effectifs client` |

---

## Préfixes GCS

```
gs://datatalent-raw/
├── france_travail/YYYY-MM-DD/          # Offres hebdomadaires (D19)
├── sirene/YYYY-MM/                     # Stock mensuel (D12)
├── geo/                                # Snapshot quasi-statique (D13)
├── urssaf_effectifs/YYYY/              # Effectifs commune × APE, annuel (D35, P1)
├── urssaf_masse_salariale/YYYY/        # Masse salariale × NA88, annuel (D35, P3)
└── bmo/YYYY/                           # Conditionnel (D35, P2)
```

Toutes les sources transitent par GCS avant chargement BigQuery raw — pas d'exception.

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
