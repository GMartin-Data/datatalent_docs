# Composant : ingestion-sirene

## Contexte

Projet DataTalent — pipeline data GCP, équipe de 4 devs.
Source la plus simple en logique mais la plus volumineuse (~3-4 Go Parquet total, deux fichiers).
Assignée à Collègue 2. Dépend de `ingestion/shared/` (composant `ingestion-shared`, implémenté en amont).

## Périmètre

### Dedans

- `ingestion/sirene/ingest.py` — téléchargement Parquet depuis data.gouv.fr → écriture locale → `shared/gcs.py` → `shared/bigquery.py`. Expose `run()`
- `ingestion/sirene/config.py` — URL data.gouv.fr, resource IDs StockEtablissement + StockUniteLegale
- `ingestion/sirene/__init__.py`

### Dehors

- `ingestion/shared/` — déjà implémenté, consommé tel quel
- `ingestion/main.py` — appelle `run()`, ne connaît pas les détails
- Filtrage `etatAdministratifEtablissement = 'A'` (établissements actifs) — dbt staging, Bloc 2
- Masquage RGPD (`statutDiffusionEtablissement = 'P'`) — dbt staging, Bloc 2
- Filtrage par codes NAF — aucun (NAF sert à enrichir en marts, pas à filtrer)
- Refresh mensuel automatisé — Bloc 3 (Cloud Scheduler cron `0 6 2 * *`)

## Source de données — Spécifications techniques

### Accès

- **Source :** data.gouv.fr, téléchargement libre, aucune authentification
- **Fichiers retenus :** StockEtablissement (Parquet) + StockUniteLegale (Parquet)
- **Justification :** StockEtablissement fournit la jointure SIRET avec les offres et la dimension géographique. StockUniteLegale apporte des dimensions BI indisponibles autrement : `categorieEntreprise` (PME/ETI/GE), `categorieJuridiqueUniteLegale`, `trancheEffectifsUniteLegale`, `denominationUniteLegale` (nom officiel). Jointure entre les deux sur `siren`.
- **Fréquence publication :** mensuel — image au dernier jour du mois précédent, publiée le 1er du mois suivant
- **Volume :** StockEtablissement ~2-3 Go (~40M lignes), StockUniteLegale ~1 Go (~25M lignes)

### Schéma StockEtablissement (champs utiles)

| Champ | Description | Usage projet |
|-------|-------------|-------------|
| `siret` | Identifiant établissement (14 chiffres) | **Clé de jointure France Travail** |
| `siren` | Identifiant entreprise (9 chiffres) | Regroupement par entreprise |
| `denominationUniteLegale` | Nom juridique officiel | Plan B jointure par nom |
| `denominationUsuelleEtablissement` | Nom d'usage | Plan B jointure par nom |
| `activitePrincipaleEtablissement` | Code NAF/APE | Enrichissement secteur |
| `trancheEffectifsEtablissement` | Tranche d'effectifs | Dimension taille |
| `etatAdministratifEtablissement` | A (actif) / F (fermé) | Filtrage staging |
| `codePostalEtablissement` | Code postal | Dimension géographique |
| `libelleCommuneEtablissement` | Nom commune | Dashboard |
| `codeCommuneEtablissement` | Code INSEE commune | Jointure API Géo |
| `statutDiffusionEtablissement` | O (diffusible) / P (partiel) | RGPD — masquer adresses si P |

### Schéma StockUniteLegale (champs utiles)

| Champ | Description | Usage projet |
|-------|-------------|-------------|
| `siren` | Identifiant entreprise (9 chiffres) | **Clé de jointure Etablissement** |
| `denominationUniteLegale` | Nom juridique officiel | Dashboard, plan B jointure par nom |
| `categorieEntreprise` | PME / ETI / GE | **Dimension BI taille entreprise** |
| `categorieJuridiqueUniteLegale` | Forme juridique (SA, SAS, SARL…) | Dimension BI structure |
| `trancheEffectifsUniteLegale` | Tranche effectifs entreprise | Dimension taille (niveau entreprise) |
| `activitePrincipaleUniteLegale` | Code NAF entreprise | Enrichissement secteur |
| `etatAdministratifUniteLegale` | A (actif) / C (cessé) | Filtrage staging |
| `economieSocialeSolidaireUniteLegale` | O / N / null | Enrichissement |

**Règle raw :** chargement du Parquet complet tel quel pour chaque fichier. Pas de filtrage, pas de sélection de colonnes. Les schémas ci-dessus documentent les champs utiles pour les couches aval.

### Volume par étape

| Étape | Volume estimé |
|-------|--------------|
| StockEtablissement brut (raw) | ~40M lignes |
| StockUniteLegale brut (raw) | ~25M lignes |
| Après filtre actifs (staging) | ~15M établissements, ~12M unités légales |
| Après jointure avec offres (intermediate) | ~500-2000 lignes |

## Flux d'exécution

```
run()
  │
  ├── Pour chaque fichier (StockEtablissement, StockUniteLegale) :
  │     │
  │     ├── 1. Téléchargement du Parquet depuis data.gouv.fr → /tmp/{fichier}.parquet
  │     │
  │     ├── 2. shared/gcs.py → upload_to_gcs(local_path, "sirene")
  │     │       → gs://datatalent-raw/sirene/YYYY-MM-DD/{fichier}.parquet
  │     │
  │     └── 3. shared/bigquery.py → load_gcs_to_bq(gcs_uri, "raw", "{table}")
  │             → raw.sirene_etablissement / raw.sirene_unite_legale
  │
  └── Terminé
```

## Idempotence

- Ré-exécuter le script le même jour écrase le fichier GCS (même path daté) et recharge BQ sans doublons

## Entrées / Sorties

| Entrée | Fournisseur |
|---|---|
| Fichiers StockEtablissement + StockUniteLegale sur data.gouv.fr | INSEE (libre) |
| Interface `shared/` stable | Composant `ingestion-shared` |

| Sortie | Consommateur |
|---|---|
| `gs://datatalent-raw/sirene/YYYY-MM-DD/StockEtablissement.parquet` | BigQuery load job |
| `gs://datatalent-raw/sirene/YYYY-MM-DD/StockUniteLegale.parquet` | BigQuery load job |
| Table `raw.sirene_etablissement` partitionnée par `_ingestion_date` | dbt staging (Bloc 2) |
| Table `raw.sirene_unite_legale` partitionnée par `_ingestion_date` | dbt staging (Bloc 2) |

## Contraintes techniques

- Python 3.12+, httpx (téléchargement), structlog (logging)
- Téléchargement de deux fichiers (~2-3 Go + ~1 Go) — prévoir gestion mémoire (streaming vers disque, pas en RAM)
- Auth GCP : Application Default Credentials
- Retry réseau via tenacity (backoff exponentiel) sur le téléchargement

## Ownership

- **Owner : Collègue 2** (J1 après-midi → J4)
- Bascule sur tests + aide intégration à partir de ~J4

## Décisions de référence

- D11 : chargement complet des deux fichiers, pas de pré-filtrage NAF ni statut
- D12 : refresh mensuel automatisé (Bloc 3)
- D14 : jointure SIRET offres ↔ Sirene, LEFT JOIN, taux estimé 20-40%