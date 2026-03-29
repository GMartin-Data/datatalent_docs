# Composant : ingestion-bmo

## Contexte

Projet DataTalent — pipeline data GCP, équipe de 4 devs.
Source complémentaire (D35, P2) : projets de recrutement IT par bassin d'emploi × département, avec indicateur de difficulté. Identifiée lors de l'exploration MCP data.gouv.fr.
Assignée à Greg. Dépend de `ingestion/shared/` (composant `ingestion-shared`, implémenté en amont).

**Dernière mise à jour :** 2026-03-28 (spike complété — source validée, schéma confirmé)

## Spike — résumé (2026-03-28)

Source validée. Le XLSX BMO 2025 contient 50 076 lignes en format long (1 ligne = 1 bassin × 1 métier). 6 codes métier IT identifiés par préfixe `M1X`/`M2X` (nomenclature FAP2021), totalisant 1 112 lignes dont 697 exploitables (les autres sont masquées par secret statistique `*`). Le département est directement dans les données (colonnes `Dept`, `NomDept`) — pas de mapping externe nécessaire. Aucune distinction data/dev/infra dans la nomenclature, mais l'indicateur de tension IT par département est pertinent pour le dashboard. Voir `exploration-spike-bmo.md` pour le détail.

## Périmètre

### Dedans

- `ingestion/bmo/parse_xlsx.py` — ouverture XLSX, mapping colonnes, filtrage 6 codes IT, normalisation → liste de dicts
- `ingestion/bmo/ingest.py` — téléchargement XLSX → appel parse_xlsx → JSONL local → `shared/gcs.py` → `shared/bigquery.py`. Expose `run()`
- `ingestion/bmo/config.py` — URL XLSX, codes métier IT, mapping colonnes source → JSONL
- `ingestion/bmo/__init__.py`

### Dehors

- `ingestion/shared/` — déjà implémenté, consommé tel quel
- `ingestion/main.py` — appelle `run()`, ne connaît pas les détails
- Calcul `part_difficile_pct` — dbt staging
- Agrégation par département — dbt intermediate (`int_tensions_bassin_emploi`)
- Refresh annuel — XLSX publié chaque année, pas d'automatisation dédiée

## Source de données — Spécifications techniques

### Accès

- **Producteur :** France Travail
- **Dataset data.gouv.fr :** `561fa564c751df4f2acdbb48`
- **BMO 2025 :** `https://www.francetravail.org/files/live/sites/peorg/files/documents/Statistiques-et-analyses/Open-data/BMO/Base_open_data_BMO_2025.xlsx`
- **Authentification :** aucune
- **Licence :** Licence Ouverte
- **Fréquence MAJ :** annuelle

### Structure du XLSX

- **Onglet de description :** `Description_des_variables` (métadonnées, ignoré par le parsing)
- **Onglet de données :** `BMO_2025_open_data` (50 076 lignes, en-têtes en ligne 1)

### Schéma confirmé (BMO 2025)

| Colonne source | Type | Description | Colonne JSONL |
|---|---|---|---|
| `annee` | string | Année de l'enquête (`"2025"`) | `annee` (cast int) |
| `Code métier BMO` | string | Code FAP2021 (ex: `M1X80`) | `code_metier_bmo` |
| `Nom métier BMO` | string | Libellé métier | `libelle_metier_bmo` |
| `Famille_met` | string | Code famille (`A`, `C`, `T`, ...) | `code_famille_metier` |
| `Lbl_fam_met` | string | Libellé famille | `libelle_famille_metier` |
| `REG` | string | Code région INSEE | `code_region` |
| `NOM_REG` | string | Nom de la région | `nom_region` |
| `Dept` | string | Code département | `code_departement` |
| `NomDept` | string | Nom du département | `nom_departement` |
| `BE25` | string | Code bassin d'emploi (**suffixe `25`**) | `code_bassin_emploi` |
| `NOMBE25` | string | Nom du bassin d'emploi (**suffixe `25`**) | `libelle_bassin_emploi` |
| `met` | string | Nb projets de recrutement, ou `*` | `projets_recrutement` (cast int, `*` → null) |
| `xmet` | string | Nb projets jugés difficiles, ou `*` | `projets_difficiles` (cast int, `*` → null) |
| `smet` | string | Nb projets saisonniers, ou `*` | `projets_saisonniers` (cast int, `*` → null) |

**Secret statistique :** les valeurs `*` remplacent les chiffres en dessous du seuil de diffusion. Elles sont converties en `null` dans le JSONL. Le champ `smet` est masqué à 95% pour les métiers IT (très peu de postes saisonniers en informatique) — exploitabilité limitée.

### Filtrage à l'ingestion

6 codes métier IT, identifiés par préfixe `M1X`/`M2X` :

| Code | Intitulé | Famille |
|---|---|---|
| `M1X80` | Techniciens d'étude et de développement en informatique | A |
| `M1X81` | Techniciens de production, exploitation, maintenance, support | A |
| `M2X90` | Ingénieurs et cadres R&D en informatique et télécom | C |
| `M2X91` | Chefs de projet et directeurs de service informatique | C |
| `M2X92` | Responsables production, exploitation, maintenance IT | C |
| `M2X93` | Experts et consultants en systèmes d'information | C |

Le filtre est sur `Code métier BMO IN (...)`, **pas** sur `Famille_met` (les métiers IT sont dispersés dans les familles `A` et `C`).

### Volume

| Étape | Volume |
|---|---|
| XLSX complet | 50 076 lignes |
| Après filtre 6 codes IT | 1 112 lignes |
| Dont `met` exploitable (≠ `*`) | 697 lignes |

## Flux d'exécution

```
run()
  │
  ├── 1. Téléchargement XLSX → /tmp/bmo_2025.xlsx
  │       Retry tenacity sur erreurs réseau
  │
  ├── 2. parse_xlsx.py :
  │       ├── Ouverture onglet BMO_2025_open_data (openpyxl)
  │       ├── Lecture en-têtes ligne 1
  │       ├── Mapping colonnes source → JSONL (dict explicite dans config)
  │       ├── Filtrage : Code métier BMO IN (M1X80, M1X81, M2X90, M2X91, M2X92, M2X93)
  │       ├── Conversion '*' → null pour met, xmet, smet
  │       └── Cast annee → int, met/xmet/smet → int ou null
  │
  ├── 3. Écriture JSONL locale → /tmp/bmo.jsonl
  │
  ├── 4. shared/gcs.py → upload_to_gcs(local_path, "bmo")
  │       → gs://datatalent-raw/bmo/YYYY-MM-DD/bmo.jsonl
  │
  └── 5. shared/bigquery.py → load_gcs_to_bq(gcs_uri, "raw", "bmo")
          → raw.bmo (partitionnée par _ingestion_date)
```

## Idempotence

- Ré-exécuter le script le même jour écrase le fichier GCS (même path daté) et recharge BQ sans doublons
- Le XLSX source est un fichier annuel statique

## Entrées / Sorties

| Entrée | Fournisseur |
|---|---|
| XLSX BMO 2025 sur francetravail.org | France Travail (libre) |
| Interface `shared/` stable | Composant `ingestion-shared` |

| Sortie | Consommateur |
|---|---|
| `gs://datatalent-raw/bmo/YYYY-MM-DD/bmo.jsonl` | BigQuery load job |
| Table `raw.bmo` partitionnée par `_ingestion_date` | dbt staging (Bloc 2) |

## Modèles dbt

- **Staging :** `stg_bmo__projets_recrutement` — typage, calcul `part_difficile_pct = projets_difficiles / projets_recrutement × 100` (null si l'un des deux est null), tests `not_null` sur `code_departement`, `code_metier_bmo`, `annee`
- **Intermediate :** `int_tensions_bassin_emploi` — WHERE 6 codes IT, GROUP BY `code_departement`, `annee` avec SUM des projets_recrutement et projets_difficiles, puis calcul du taux de difficulté agrégé
- **Marts :** jointure dans `mart_contexte_territorial` sur `code_departement`

## Validation

| Contrôle | Critère |
|---|---|
| Nb lignes post-filtre | ~1 112 (6 codes IT) |
| Codes métier | Uniquement les 6 codes attendus |
| `met` ≥ `xmet` | Toujours vrai (quand les deux sont non-null) |
| `met` ≥ `smet` | Toujours vrai (quand les deux sont non-null) |
| Spot check Paris (dept 75) | `met` > 10 000 |
| Valeurs `*` | Converties en null, pas en 0 ni en chaîne |

## Contraintes techniques

- Python 3.12+, httpx (téléchargement), structlog (logging), openpyxl (lecture XLSX)
- Retry réseau via tenacity (backoff exponentiel) sur le téléchargement
- Auth GCP : Application Default Credentials
- **Mapping colonnes explicite** dans `config.py` — dict `{nom_source: nom_jsonl}`
- Volume XLSX modéré (~quelques Mo) — pas de contrainte mémoire

## Ownership

- **Owner : Greg** (pause inter-blocs + Bloc 2)

## Décisions de référence

- D35 : source complémentaire retenue (P2, priorité élevée)
- ~~D36~~ : annulée — workflow classique d'ingestion
