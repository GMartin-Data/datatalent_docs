# Architecture DataTalent — Diagrammes détaillés

> **Complément à :** `architecture-datatalent.mermaid` (vue monolithique)
> **Dernière mise à jour :** 2026-03-27 (D36 annulée — flux d'ingestion uniforme pour toutes les sources)

Trois vues complémentaires. Chacune se lit indépendamment.

---

## 1. Acquisition des données — sources et chemins d'ingestion

Un seul chemin d'ingestion : toutes les sources passent par Cloud Run → GCS → BigQuery raw.

```mermaid
graph TD
    subgraph brief["Sources brief"]
        FT["API France Travail<br/>OAuth2 · 101 depts × 4 ROME"]
        SI["Stock Sirene INSEE<br/>Parquet · ~2 Go"]
        GEO["API Géo<br/>Snapshot 3 niveaux"]
    end

    subgraph compl["Sources complémentaires D35"]
        UE["URSSAF effectifs<br/>API Opendatasoft<br/>filtré 4 codes APE IT"]
        UM["URSSAF masse salariale<br/>API Opendatasoft<br/>~30 lignes · NA88 = 62"]
        BMO["BMO France Travail<br/>XLSX annuel · FAP M2Z"]
    end

    subgraph pipeline["Pipeline d'ingestion uniforme"]
        CR["Cloud Run Job"]
        GCS["GCS<br/>datatalent-raw/"]
        RAW["BigQuery raw"]
    end

    FT --> CR
    SI --> CR
    GEO --> CR
    UE --> CR
    UM --> CR
    BMO -.->|"conditionnel · spike P2"| CR
    CR --> GCS --> RAW

    classDef brief fill:#dfe6f0,stroke:#5e81ac,stroke-width:1.5px,color:#2e3440
    classDef compl fill:#e1f5ee,stroke:#0f6e56,stroke-width:1.5px,color:#2e3440
    classDef pipeline fill:#f5edda,stroke:#c9a95a,stroke-width:1.5px,color:#2e3440

    class FT,SI,GEO brief
    class UE,UM,BMO compl
    class CR,GCS,RAW pipeline
```

**Points clés :**
- Toutes les sources suivent le même chemin : script Python dans `ingestion/{source}/` → `shared/gcs.py` → `shared/bigquery.py` → raw. Pas d'exception.
- Le BMO a un chemin conditionnel (pointillés) : le spike déterminera si cette source est intégrée.
- URSSAF masse salariale (~30 lignes) passe par le workflow classique malgré son faible volume, par souci d'uniformité architecturale et d'automatisation homogène.

---

## 2. Transformations dbt — de staging aux marts

Le cœur analytique du pipeline. Chaque flèche est une jointure ou une transformation documentée.

```mermaid
flowchart LR
    subgraph staging["Staging — nettoyage mono-source"]
        STG_FT["stg_france_travail__offres<br/>categorie_metier · salaire parsé<br/>code_naf · is_intermediaire<br/>code_commune · code_departement"]
        STG_SI["stg_sirene__etablissements<br/>filtre actifs · masquage RGPD"]
        STG_GEO["stg_geo__communes<br/>+ departements + regions"]
        STG_UE["stg_urssaf__effectifs<br/>_commune_ape"]
        STG_UM["stg_urssaf__masse<br/>_salariale_na88"]
    end

    subgraph intermediate["Intermediate — croisements"]
        INT_OFF["int_offres_enrichies<br/>offres + noms geo"]
        INT_DENS["int_densite_sectorielle<br/>_commune<br/>effectifs IT par commune"]
        INT_TENS["int_tensions_bassin<br/>_emploi<br/>difficultés recrutement"]
    end

    subgraph marts["Marts — vues dashboard"]
        MART_OFF["mart_offres<br/>dashboard principal"]
        MART_CTX["mart_contexte<br/>_territorial<br/>densité + tensions + benchmark"]
    end

    STG_FT -->|"LEFT JOIN<br/>code_commune"| INT_OFF
    STG_GEO -->|"ON communes.code"| INT_OFF
    STG_UE -->|"WHERE APE IT<br/>GROUP BY commune"| INT_DENS

    INT_OFF --> MART_OFF
    INT_OFF -->|"JOIN code_commune"| MART_CTX
    INT_DENS -->|"JOIN code_commune"| MART_CTX
    INT_TENS -.->|"JOIN code_dept"| MART_CTX
    STG_UM -.->|"JOIN NA88 = 62"| MART_CTX

    STG_SI ~~~ staging

    classDef stg fill:#dfe6f0,stroke:#5e81ac,stroke-width:1px,color:#2e3440
    classDef int fill:#f5edda,stroke:#c9a95a,stroke-width:1px,color:#2e3440
    classDef mart fill:#d8ebdd,stroke:#6b9e78,stroke-width:1.5px,color:#2e3440
    classDef dead fill:#e8e8e8,stroke:#888888,stroke-width:1px,color:#2e3440,stroke-dasharray: 5 5

    class STG_FT,STG_GEO,STG_UE,STG_UM stg
    class STG_SI dead
    class INT_OFF,INT_DENS,INT_TENS int
    class MART_OFF,MART_CTX mart
```

**Points clés :**
- `stg_sirene__etablissements` est grisé en pointillés : il est maintenu comme livrable technique mais ne participe à aucune jointure (D14-bis).
- `stg_urssaf__masse_salariale_na88` est un modèle staging classique (source = raw), plus un seed. Il rejoint directement `mart_contexte_territorial` pour le benchmark salaire.
- Les flèches pointillées (BMO via `int_tensions_bassin_emploi`, masse salariale) sont conditionnelles — dépendent du spike P2 pour BMO, et de la pertinence du benchmark pour masse salariale.
- `int_offres_enrichies` est la table pivot : chaque offre France Travail enrichie avec les noms géographiques via API Géo.
- `mart_contexte_territorial` agrège trois enrichissements contextuels : densité URSSAF, tensions BMO, benchmark salaire URSSAF.

---

## 3. Infrastructure et déploiement

Les composants transverses qui font tourner le pipeline.

```mermaid
graph TD
    subgraph trigger["Déclenchement"]
        CS["Cloud Scheduler<br/>cron 0 6 * * 1<br/>hebdomadaire"]
    end

    subgraph compute["Exécution"]
        CR["Cloud Run Job<br/>Conteneur Docker<br/>python main.py"]
        DBT["dbt run + dbt test"]
    end

    subgraph storage["Stockage"]
        GCS["GCS<br/>datatalent-raw/"]
        BQ["BigQuery<br/>4 datasets"]
    end

    subgraph security["Sécurité"]
        SM["Secret Manager<br/>client_id + client_secret FT"]
        IAM["IAM<br/>sa-ingestion · sa-dbt<br/>ADC en dev local D27"]
    end

    subgraph iac["IaC"]
        TF["Terraform<br/>modules : gcs · bigquery<br/>cloud_run · scheduler<br/>iam · secret_manager"]
        STATE["GCS backend<br/>datatalent-glaq-2-tfstate"]
    end

    subgraph cicd["CI/CD — GitHub Actions"]
        CI["ci.yml — sur PR<br/>ruff + uv lint<br/>dbt compile + test<br/>terraform validate"]
        CD["deploy.yml — sur merge<br/>Docker build + push AR<br/>gcloud run jobs update"]
    end

    CS -->|"HTTP trigger"| CR
    CR -->|"upload bruts"| GCS
    GCS -->|"load"| BQ
    CR -->|"puis"| DBT
    DBT -->|"transforme"| BQ

    SM -.->|"credentials FT"| CR
    IAM -.->|"permissions"| CR
    IAM -.->|"permissions"| BQ

    TF -.->|"provisionne tout"| storage
    TF -.->|"provisionne tout"| compute
    TF -.->|"provisionne tout"| security
    TF --- STATE

    CD -->|"déploie image"| CR
    CI -->|"valide sur PR"| DBT

    classDef trigger fill:#f2dbd8,stroke:#b55a50,stroke-width:1.5px,color:#2e3440
    classDef compute fill:#dfe6f0,stroke:#5e81ac,stroke-width:1.5px,color:#2e3440
    classDef storage fill:#f5edda,stroke:#c9a95a,stroke-width:1.5px,color:#2e3440
    classDef security fill:#e8e8e8,stroke:#888888,stroke-width:1px,color:#2e3440
    classDef iac fill:#eeedfe,stroke:#534ab7,stroke-width:1.5px,color:#2e3440
    classDef cicd fill:#d6eae4,stroke:#5d9e8a,stroke-width:1.5px,color:#2e3440

    class CS trigger
    class CR,DBT compute
    class GCS,BQ storage
    class SM,IAM security
    class TF,STATE iac
    class CI,CD cicd
```

**Points clés :**
- Cloud Scheduler déclenche le Cloud Run Job chaque lundi 6h. Le Job exécute séquentiellement l'ingestion Python puis dbt.
- Terraform provisionne l'intégralité de l'infra (sauf le bucket de state, seule ressource manuellement gérée — bootstrap problem).
- Deux workflows GitHub Actions : `ci.yml` valide sur PR (lint + dbt test + tf validate), `deploy.yml` déploie sur merge (Docker build + Cloud Run update).
- Secret Manager ne stocke que les credentials France Travail — les autres sources sont ouvertes (pas d'authentification).
