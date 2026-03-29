# Composant : ingestion-urssaf-effectifs

## Contexte

Projet DataTalent — pipeline data GCP, équipe de 4 devs.
Source complémentaire la plus stratégique (D35, P1) : seule source identifiée croisant code NAF détaillé (NAF5) × géographie fine (commune). Compense l'absence de SIRET (D14-bis) en fournissant un contexte géo-sectoriel : "cette commune compte X établissements IT employant Y salariés". Identifiée lors de l'exploration MCP data.gouv.fr.
Assignée à Greg. Dépend de `ingestion/shared/` (composant `ingestion-shared`, implémenté en amont).

**Dernière mise à jour :** 2026-03-28 (implémentation complète — schéma confirmé, endpoint export retenu, découverte arrondissements Paris)

## Périmètre

### Dedans

- `ingestion/urssaf_effectifs/client.py` — requête export API Opendatasoft, filtre 4 codes APE IT (D37), une seule requête sans pagination
- `ingestion/urssaf_effectifs/ingest.py` — extract filtré → **unpivot wide → long** → JSONL local → `shared/gcs.py` → `shared/bigquery.py`. Expose `run()`
- `ingestion/urssaf_effectifs/config.py` — URL export Opendatasoft, filtre ODSQL, champs dimensionnels, patterns regex colonnes wide
- `ingestion/urssaf_effectifs/__init__.py`

### Dehors

- `ingestion/shared/` — déjà implémenté, consommé tel quel
- `ingestion/main.py` — appelle `run()`, ne connaît pas les détails
- Agrégation des 4 codes APE en un total IT par commune — dbt intermediate (`int_densite_sectorielle_commune`, Bloc 2)
- Ratio offres/effectifs = indicateur de dynamisme — dbt marts (Bloc 2)
- Refresh annuel — MAJ source fin d'année + ~150 jours, pas d'automatisation dédiée (exécuté lors du run Cloud Run hebdomadaire, idempotent)

## Source de données — Spécifications techniques

### Accès

- **Producteur :** URSSAF
- **API :** Opendatasoft — `https://open.urssaf.fr/api/explore/v2.1`
- **Dataset Opendatasoft :** `etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last`
- **Dataset data.gouv.fr :** `5efd242c72595ba1a48628f2`
- **Endpoint utilisé :** `/exports/json` — `https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last/exports/json`
- **Authentification :** aucune (API ouverte)
- **Licence :** ODbL
- **Fréquence MAJ source :** annuelle (fin d'année + ~150 jours)
- **Dernière MAJ constatée :** 30 mai 2025

### Pourquoi l'endpoint export et non records

L'endpoint `/records` impose une **limite hard à offset=10000** côté Opendatasoft. Avec 11 427 records filtrés, la pagination échoue en 400 Bad Request à offset=10000. L'endpoint `/exports/json` retourne le dataset filtré complet en une seule requête sans limite de pagination — c'est la solution retenue.

### Filtrage

| Paramètre | Usage | Valeur |
|---|---|---|
| `where` | Filtre ODSQL | `code_ape IN ("6201Z", "6202A", "6203Z", "6209Z")` |

> **Note :** le filtre porte sur `code_ape` (code seul), pas sur `ape` (libellé complet). Le format du code est **sans point** : `6201Z`, pas `62.01Z`. Les guillemets doubles sont requis par ODSQL.

La réponse est une liste JSON : `[ { field: value, ... }, ... ]` (pas d'enveloppe `total_count`/`results`).

### ⚠ FORMAT WIDE — confirmé 2026-03-28

**Le dataset est en format large (wide).** Chaque record contient une commune × APE avec des colonnes par année.

### Schéma réel confirmé (une ligne = une commune × APE)

**Colonnes dimensionnelles retenues :**

| Champ API | Type | Description | Colonne JSONL |
|---|---|---|---|
| `code_commune` | string | Code INSEE commune | `code_commune` |
| `intitule_commune` | string | Code + nom commune (ex: `"94065 Rungis"`) | `intitule_commune` |
| `code_departement` | string | Code département | `code_departement` |
| `code_ape` | string | Code APE sans point (ex: `6201Z`) | `code_ape` |

**Colonnes de données (pattern par année, 2006–2024) :**

| Pattern | Type API | Description |
|---|---|---|
| `nombre_d_etablissements_{YYYY}` | int ou null | Nb établissements pour l'année YYYY |
| `effectifs_salaries_{YYYY}` | int ou null | Effectifs salariés fin d'année YYYY |

38 colonnes de données au total (2 × 19 années de 2006 à 2024).

**Colonnes ignorées :** `region`, `ancienne_region`, `departement`, `zone_d_emploi`, `epci`, `commune`, `grand_secteur_d_activite`, `secteur_na17`, `secteur_na38`, `secteur_na88`, `ape`, `code_region`, `code_ancienne_region`, `code_zone_d_emploi`, `code_epci` — redondantes avec API Géo ou non utilisées dans les modèles dbt aval.

### Unpivot wide → long

Le format JSONL cible pour BigQuery raw est en **format long** (une ligne par commune × APE × année). Le unpivot est fait à l'ingestion, pas en dbt, car :
- Le format wide est un artefact de diffusion URSSAF, pas une structure métier
- Le raw en format long est plus simple à interroger, tester et documenter
- dbt staging n'a pas à gérer un `UNPIVOT` SQL

**Colonnes JSONL cibles (format long, après unpivot) :**

| Colonne | Type | Source |
|---|---|---|
| `code_commune` | string | Champ `code_commune` de l'API |
| `intitule_commune` | string | Champ `intitule_commune` de l'API |
| `code_departement` | string | Champ `code_departement` de l'API |
| `code_ape` | string | Champ `code_ape` de l'API (sans point) |
| `annee` | int | Extrait du suffixe `_YYYY` des colonnes wide via regex |
| `nb_etablissements` | int | Valeur de `nombre_d_etablissements_{YYYY}` (null → 0) |
| `effectifs_salaries` | int | Valeur de `effectifs_salaries_{YYYY}` (null → 0) |

**Règle de filtrage null :** une année est ignorée si `effectifs_salaries_{YYYY}` ET `nombre_d_etablissements_{YYYY}` sont tous les deux null. Si l'un des deux est non-null, la ligne est conservée.

### ⚠ Paris — arrondissements, pas commune centrale

L'URSSAF utilise les **codes INSEE des arrondissements** (75101–75120), pas le code commune `75056`. La jointure avec les offres France Travail (qui utilisent probablement `75056`) devra en tenir compte dans le modèle intermediate `int_densite_sectorielle_commune` (Bloc 2).

### Filtrage à l'ingestion (D37)

On ne télécharge que les 4 codes APE du périmètre IT :

| Code APE | Libellé |
|---|---|
| 6201Z | Programmation informatique |
| 6202A | Conseil en systèmes et logiciels informatiques |
| 6203Z | Gestion d'installations informatiques |
| 6209Z | Autres activités informatiques |

C'est un écart assumé avec le pattern Medallion (raw = brut intégral) — justifié par la réduction de volume de ~95% et le fait que les autres secteurs n'ont aucune utilité pour le projet.

### Volume

| Étape | Volume constaté (2026-03-28) |
|---|---|
| Dataset complet (tous APE × toutes communes) | 1 205 366 lignes (format wide) |
| Après filtre 4 codes APE IT (format wide) | **11 427 lignes** |
| Après unpivot (format long) | **95 283 lignes** |
| Staging | ~95 283 lignes (renommage, typage) |
| Intermediate (`int_densite_sectorielle_commune`) | Quelques milliers de lignes (GROUP BY commune × année) |

### Champ et méthodologie URSSAF

- **Champ :** établissements employeurs du secteur privé, régime général
- **Nb établissements :** ensemble des employeurs ayant déclaré une masse salariale au dernier mois de l'année
- **Effectifs :** mesurés en fin d'année (un établissement peut avoir 0 salarié si la masse a été versée au dernier trimestre mais plus de contrat au 31/12)
- **Apprentis :** inclus à compter de juin 2023
- **Nomenclatures :** communes et EPCI au 1er janvier 2023, zones d'emploi au découpage 2020
- **Profondeur :** 2006–2024

## Flux d'exécution

```
run()
  │
  ├── 1. Requête export Opendatasoft filtrée (where=code_ape IN ("6201Z",...))
  │       Endpoint /exports/json — une seule requête, pas de pagination
  │       Retry tenacity sur erreurs réseau
  │
  ├── 2. Unpivot wide → long :
  │       Pour chaque record API (1 commune × 1 APE) :
  │           Détecter les années via regex sur colonnes effectifs_salaries_{YYYY}
  │           Pour chaque année non-null sur les deux colonnes :
  │               Émettre 1 ligne JSONL avec code_commune, code_ape, annee,
  │               nb_etablissements, effectifs_salaries
  │
  ├── 3. Écriture JSONL locale → /tmp/urssaf_effectifs.jsonl
  │
  ├── 4. shared/gcs.py → upload_to_gcs(local_path, "urssaf_effectifs")
  │       → gs://datatalent-raw/urssaf_effectifs/YYYY-MM-DD/urssaf_effectifs.jsonl
  │
  └── 5. shared/bigquery.py → load_gcs_to_bq(gcs_uri, "raw", "urssaf_effectifs")
          → raw.urssaf_effectifs (partitionnée par _ingestion_date)
```

## Idempotence

- Ré-exécuter le script le même jour écrase le fichier GCS (même path daté) et recharge BQ sans doublons
- Les données source changent au plus une fois par an

## Entrées / Sorties

| Entrée | Fournisseur |
|---|---|
| API Opendatasoft `open.urssaf.fr` | URSSAF (libre) |
| Interface `shared/` stable | Composant `ingestion-shared` |

| Sortie | Consommateur |
|---|---|
| `gs://datatalent-raw/urssaf_effectifs/YYYY-MM-DD/urssaf_effectifs.jsonl` | BigQuery load job |
| Table `raw.urssaf_effectifs` partitionnée par `_ingestion_date` | dbt staging (Bloc 2) |

## Modèles dbt

- **Staging :** `stg_urssaf__effectifs_commune_ape` — renommage colonnes, typage, tests `not_null` sur `code_commune`, `code_ape`, `annee`
- **Intermediate :** `int_densite_sectorielle_commune` — GROUP BY `code_commune`, `annee` → `nb_etablissements_it`, `effectifs_salaries_it`. Attention : jointure avec France Travail sur Paris nécessite une gestion des arrondissements (75101–75120 vs 75056)
- **Marts :** jointure dans `mart_contexte_territorial` sur `code_commune` pour enrichir chaque offre avec le tissu IT local

**Note sur le double filtrage APE IT :** le WHERE en intermediate est une redondance voulue. Le raw ne contient déjà que les 4 codes APE IT (filtré à l'ingestion, D37), mais le WHERE explicite en intermediate documente l'intention et protège contre un éventuel élargissement futur du périmètre d'ingestion.

## Validation

| Contrôle | Critère | Résultat constaté (2026-03-28) |
|---|---|---|
| Nb records wide | 11 427 | 11 427 ✓ |
| Nb records long (après unpivot) | > 10 000 | 95 283 ✓ |
| Codes APE | Uniquement `{6201Z, 6202A, 6203Z, 6209Z}` | ✓ |
| Années couvertes | 2006–2024 | 2006 → 2024 ✓ |
| Spot check Paris arrondissements (2024) | Effectifs IT > 50 000 | 97 806 ✓ |

## Contraintes techniques

- Python 3.12+, httpx (requêtes HTTP), structlog (logging)
- Retry réseau via tenacity (backoff exponentiel)
- Auth GCP : Application Default Credentials
- **Pas de pagination** — endpoint `/exports/json` retourne tout en une requête (limite hard offset=10000 sur `/records` contournée)
- **Unpivot en Python** : détection dynamique des années par regex sur les noms de champs (`re.compile(r'^effectifs_salaries_(\d{4})$')`)
- Timeout httpx = 120s (réponse ~4s observée pour 11 427 records)

## Ownership

- **Owner : Greg** (pause inter-blocs + Bloc 2)

## Décisions de référence

- D14-bis : jointure SIRET abandonnée — URSSAF effectifs devient la voie alternative pour le contexte géo-sectoriel
- D35 : source complémentaire retenue (P1, priorité élevée)
- D37 : filtrage codes APE IT à l'ingestion (écart Medallion assumé)
