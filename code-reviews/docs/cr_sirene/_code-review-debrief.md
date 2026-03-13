# Code Review — PR ingestion-sirene

**Reviewer :** Greg
**Auteur :** Quentin
**Scope :** `ingestion/sirene/ingest.py`, `config.py`, `test_sirene_ingestion.py`
**Référence :** component document `ingestion-sirene.md`, contrat `ingestion-shared.md`

---

## Synthèse

Le code est bien écrit en isolation — bonne décomposition en fonctions unitaires, défenses robustes (fichier vide, téléchargement incomplet, format inattendu), tests structurés. Le problème n'est pas la qualité du code, c'est l'alignement avec l'architecture du projet.

Trois écarts bloquants empêchent le merge.

---

## ❌ Bloquants

### 1. Aucun appel à `shared/` — les données ne quittent jamais le disque local

Le contrat d'interface exige que chaque source appelle `upload_to_gcs()` puis `load_gcs_to_bq()`. Le code actuel télécharge le Parquet, le transforme localement, et retourne des chemins de fichiers. La table `raw.sirene` dans BigQuery ne sera jamais alimentée.

**Flux attendu :** download → `upload_to_gcs(local_path, "sirene")` → `load_gcs_to_bq(gcs_uri, "raw", "sirene")`
**Flux actuel :** download → `data/raw/` → sélection colonnes → `data/prepared/` → return paths

### 2. Sélection de colonnes en raw — viole D11

La décision D11 est explicite : chargement complet, pas de sélection de colonnes. Le component doc précise : "Règle raw : chargement du Parquet complet tel quel."

`transform_parquet_keep_columns()` sélectionne ~28 colonnes sur ~100+. Cette logique appartient à dbt staging (Bloc 2). Toute la mécanique `PREPARED_DIR` / `_light.parquet` / `RESOURCE_SELECTED_COLUMNS` doit être retirée.

> **Note :** le travail d'identification des colonnes utiles n'est pas perdu — c'est l'input du futur modèle `stg_sirene`. Voir l'ADR dédié (`adr-raw-complet-vs-filtrage-sirene.md`).

### 3. StockUniteLegale inclus — hors périmètre sans validation

Le component doc retient uniquement StockEtablissement. Justification : le SIRET identifie un établissement, et les offres France Travail référencent le SIRET de l'établissement qui recrute.

`config.py` déclare deux ressources (`unite_legale` + `etablissement`) et `run()` itère sur les deux. L'ajout est peut-être pertinent, mais c'est une décision d'architecture — à trancher en équipe, pas à introduire silencieusement dans une PR.

---

## ⚠️ À corriger

### 4. `print()` au lieu de `get_logger`

La fonction `log()` fait un `print()` brut. Le contrat exige `get_logger(__name__)` de `shared/logging.py` (structlog). Sans ça, les logs Cloud Run seront inconsistants entre sources et impossibles à parser en JSON.

### 5. Pas de retry tenacity

Aucun décorateur `@retry` sur les appels réseau (`fetch_dataset_metadata`, `download_file`). Sur un fichier de 2-3 Go, un timeout ou une coupure réseau est probable. Le script crashe immédiatement au lieu de retenter.

### 6. `requests` au lieu de `httpx`

Le component doc spécifie httpx. Les deux font le job pour du download streaming, mais l'équipe (France Travail, Géo) utilise httpx. Harmoniser.

### 7. Idempotence locale, pas GCS

L'idempotence du projet repose sur le path GCS daté (`YYYY-MM-DD`) : même jour = même path = écrasement. Le code utilise un tag mensuel (`YYYY-MM`) et un nettoyage de fichiers locaux. Ce modèle disparaît naturellement quand `shared/` est branché (Step 2 de la roadmap).

### 8. Seuil de fraîcheur trop serré

`validate_resource_freshness()` lève une exception si la ressource a plus de 45 jours. La publication Sirene est mensuelle (le 1er du mois). Un fichier publié le 1er mars sera "vieux" de 45 jours le 15 avril → crash sur des données parfaitement à jour. Passer à ~62 jours, ou transformer en warning au lieu d'exception.

### 9. Validation parquet par URL fragile (mineur)

Le check dans `download_file()` vérifie l'URL finale et le content-type. Si data.gouv redirige vers un CDN avec query params (`?token=xxx`), `final_url.endswith(".parquet")` échouera. Préférer une vérification du magic number (`PAR1`) après écriture.

---

## ✅ Conforme

- **`run()` sans arguments** — signature conforme au contrat
- **Décomposition** — fonctions unitaires testables, séparation config/logique, dataclass `ResourceInfo`
- **Type hints** — présents partout, `from __future__ import annotations`, nommage snake_case
- **Sécurité** — aucune credential en dur (data.gouv est public, pas de clé GCP)
- **Défenses non-réseau** — fichier vide après download, téléchargement incomplet (content-length), aucune colonne trouvée, format inattendu
- **Tests** — happy path + edge cases couverts, monkeypatch correct sur `run()`, bonne utilisation de `tmp_path`

---

## Verdict

**Corrections nécessaires avant merge.**

La base est saine. Le collègue a produit du code robuste et bien testé. Les problèmes sont des écarts d'alignement avec l'architecture, pas des défauts de compétence. La roadmap de résolution est dans `roadmap-review-sirene.md`.