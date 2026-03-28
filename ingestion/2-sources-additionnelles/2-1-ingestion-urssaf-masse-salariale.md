# Composant : ingestion-urssaf-masse-salariale

## Contexte

Projet DataTalent — pipeline data GCP, équipe de 4 devs.
Source complémentaire à faible volume (~30 lignes) identifiée lors de l'exploration MCP data.gouv.fr (D35, P3). Fournit un benchmark salaire brut moyen annuel pour le secteur IT (NA88 = 62).
Assignée à Greg. Dépend de `ingestion/shared/` (composant `ingestion-shared`, implémenté en amont).

## Périmètre

### Dedans

- `ingestion/urssaf_masse_salariale/client.py` — requête API Opendatasoft, filtre NA88 = 62, pagination `limit`/`offset`
- `ingestion/urssaf_masse_salariale/ingest.py` — extract → JSONL local → `shared/gcs.py` → `shared/bigquery.py`. Expose `run()`
- `ingestion/urssaf_masse_salariale/config.py` — URL API Opendatasoft, dataset ID, filtre ODSQL, colonnes à extraire
- `ingestion/urssaf_masse_salariale/__init__.py`

### Dehors

- `ingestion/shared/` — déjà implémenté, consommé tel quel
- `ingestion/main.py` — appelle `run()`, ne connaît pas les détails
- Calcul du salaire brut moyen annuel (`masse_salariale / effectifs`) — dbt marts (Bloc 2)
- Refresh annuel — MAJ source fin d'année + ~250 jours, pas d'automatisation dédiée (exécuté lors du run Cloud Run hebdomadaire, idempotent)

## Source de données — Spécifications techniques

### Accès

- **Producteur :** URSSAF
- **API :** Opendatasoft — `https://open.urssaf.fr/api/explore/v2.1`
- **Dataset Opendatasoft :** `nombre-etab-effectifs-salaries-et-masse-salariale-secteur-prive-france-x-na88`
- **Dataset data.gouv.fr :** `61d784a161825aaf438b8e9e`
- **Endpoint records :** `https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/nombre-etab-effectifs-salaries-et-masse-salariale-secteur-prive-france-x-na88/records`
- **Authentification :** aucune (API ouverte)
- **Licence :** ODbL
- **Fréquence MAJ source :** annuelle (fin d'année + ~250 jours)
- **Dernière MAJ constatée :** 17 septembre 2025

### Pagination et filtrage

L'API Opendatasoft utilise le paramétrage suivant :

| Paramètre | Usage | Valeur |
|---|---|---|
| `where` | Filtre ODSQL | `secteur_na88i LIKE "62%"` |
| `order_by` | Tri | `annee ASC` |
| `limit` | Taille de page | `100` (suffisant en une page) |
| `offset` | Décalage pagination | `0`, incrémenté de `limit` |

> **Note :** le filtre ODSQL utilise des guillemets doubles pour les littéraux de chaîne. Les guillemets simples provoquent une erreur 400.

La réponse est un objet JSON : `{ "total_count": int, "results": [ { field: value, ... }, ... ] }`.

### Schéma (champs retournés par l'API)

| Champ API | Type API | Description | Colonne JSONL | Type JSONL |
|---|---|---|---|---|
| `annee` | string | Année de référence (1998–2024) | `annee` | int (casté à l'ingestion) |
| `secteur_na88i` | string | `"62 Programmation, conseil et autres activités informatiques"` | `code_na88` (code extrait) + `libelle_na88` (libellé extrait) | int / string |
| `nombre_d_etablissements` | int | Nb moyen annuel d'établissements employeurs | `nb_etablissements` | int |
| `effectifs_salaries_moyens` | int | Effectif salarié moyen annuel | `effectifs_salaries_moyens` | int |
| `masse_salariale` | int | Masse salariale annuelle brute en euros (assiette déplafonnée Sécu) | `masse_salariale_brute` | int |

**Champs ignorés :** `grand_secteur_d_activite` (constant : GS5 Autres services marchands hors intérimaires), `secteur_na38i` (constant : JC Activités informatiques).

### Transformation à l'ingestion

Le champ composite `secteur_na88i` (ex: `"62 Programmation, conseil..."`) est éclaté en deux colonnes :
- `code_na88` : code numérique extrait via `split(" ", 1)`, casté en int
- `libelle_na88` : libellé textuel (reste après le code, accents conservés — BigQuery est full UTF-8)

Le champ `annee` est retourné comme string par l'API et casté en int à l'ingestion.

Cette transformation est faite dans le script d'ingestion (pas en dbt staging) car elle relève du parsing du format API Opendatasoft, pas d'une logique métier.

### Volume

| Étape | Volume |
|---|---|
| Dataset complet (tous secteurs NA88) | ~2 187 lignes |
| Après filtre NA88 = 62 | **27 lignes** (une par année depuis 1998) |
| Staging | 27 lignes (renommage, typage) |

### Champ et méthodologie URSSAF

- **Champ :** secteur privé, régime général, hors agriculture, hors Mayotte
- **Effectifs :** moyenne des effectifs moyens trimestriels de l'année
- **Masse salariale :** assiette déplafonnée de Sécurité sociale (exclut indemnités chômage partiel et éléments non soumis à cotisations)
- **Apprentis :** inclus à compter de 2023
- **Distinction intérimaires :** le dataset inclut les intérimaires dans les totaux du secteur d'accueil (NA88i = "avec intérimaires")

## Flux d'exécution

```
run()
  │
  ├── 1. Requête API Opendatasoft filtrée (where=secteur_na88i LIKE "62%")
  │       Pagination limit/offset (1 page suffit en pratique)
  │       Retry tenacity sur erreurs réseau
  │
  ├── 2. Transformation : éclater secteur_na88i, renommer colonnes, caster annee en int
  │
  ├── 3. Écriture JSONL locale → /tmp/urssaf_masse_salariale.jsonl
  │
  ├── 4. shared/gcs.py → upload_to_gcs(local_path, "urssaf_masse_salariale")
  │       → gs://datatalent-raw/urssaf_masse_salariale/YYYY-MM-DD/urssaf_masse_salariale.jsonl
  │
  └── 5. shared/bigquery.py → load_gcs_to_bq(gcs_uri, "raw", "urssaf_masse_salariale")
          → raw.urssaf_masse_salariale (partitionnée par _ingestion_date)
```

## Idempotence

- Ré-exécuter le script le même jour écrase le fichier GCS (même path daté) et recharge BQ sans doublons
- Les données source changent au plus une fois par an — les ré-exécutions hebdomadaires ne produisent que des écritures identiques

## Entrées / Sorties

| Entrée | Fournisseur |
|---|---|
| API Opendatasoft `open.urssaf.fr` | URSSAF (libre) |
| Interface `shared/` stable | Composant `ingestion-shared` |

| Sortie | Consommateur |
|---|---|
| `gs://datatalent-raw/urssaf_masse_salariale/YYYY-MM-DD/urssaf_masse_salariale.jsonl` | BigQuery load job |
| Table `raw.urssaf_masse_salariale` partitionnée par `_ingestion_date` | dbt staging (Bloc 2) |

## Modèles dbt

- **Staging :** `stg_urssaf__masse_salariale_na88` — renommage colonnes, typage, tests `not_null` sur toutes les colonnes, `unique` sur `annee`, `accepted_values` sur `code_na88` (= 62)
- **Intermediate :** aucun — table de référence mono-source sans croisement nécessaire
- **Marts :** jointure directe dans `mart_contexte_territorial` sur code NA88 = `62` pour afficher le salaire brut moyen sectoriel (`masse_salariale_brute / effectifs_salaries_moyens`) comme benchmark contextuel

## Validation

| Contrôle | Critère | Résultat constaté (2026-03-28) |
|---|---|---|
| Nb lignes | ≥ 20 (attendu ~27) | 27 ✓ |
| Code NA88 | Toutes les lignes = 62 | {62} ✓ |
| Spot check salaire 2024 | `masse / effectifs` entre 40 000 et 80 000 € | 55 070 € ✓ |
| Tendance effectifs | Globalement croissant de 1998 à 2024 | À vérifier en dbt |

## Contraintes techniques

- Python 3.12+, httpx (requêtes HTTP), structlog (logging)
- Retry réseau via tenacity (backoff exponentiel)
- Auth GCP : Application Default Credentials
- Volume négligeable (27 lignes) — pas de contrainte mémoire ni de streaming

## Ownership

- **Owner : Greg** (pause inter-blocs + Bloc 2)

## Décisions de référence

- D35 : source complémentaire retenue (P3, priorité moyenne)
- ~~D36~~ : annulée — workflow classique d'ingestion, pas de seed dbt
- D37 (par analogie) : filtrage NA88 = 62 à l'ingestion (seul code pertinent pour le projet)
