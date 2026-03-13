# Code review `ingestion-geo` — Synthèse des issues

## ❌ Bloquants

| # | Description | Statut |
|---|-------------|--------|
| 1 | `upload_to_gcs` : signature incompatible avec le contrat `shared/` (3 args + contenu brut au lieu de `local_path, prefix`) | ✅ v1 |
| 2 | `load_gcs_to_bq` : passe le project ID (`"datatalent-glaq-2"`) au lieu du dataset `"raw"` | ✅ v2 |
| 3 | Path GCS non daté — pas de `YYYY-MM-DD`, donc pas de snapshot traçable ni d'idempotence propre | ✅ v1 (résolu par #1 — `shared/` injecte la date) |
| 4 | Aucun retry tenacity — exigé par le contrat, absent du code | ✅ v3 |

## ⚠️ À corriger

| # | Description | Statut |
|---|-------------|--------|
| 5 | `BUCKET_NAME` et `DATASET_ID` en dur dans `config.py` — valeurs d'environnement encapsulées par `shared/`, inutiles ici | ✅ v2 |
| 6 | Paramètre `fields` non utilisé — `/communes` retourne tous les champs dont `contour` (~34 Mo de polygones inutiles) | ✅ v4 |
| 7 | f-strings dans les appels logger — perd le logging structuré (kwargs structlog requis) | ✅ v5 |
| 8 | Pas de type hints ni de docstrings Google — convention d'équipe | ✅ v7 |
| 9 | `except Exception` avale les erreurs et continue — échec partiel silencieux, Cloud Run Job sort en succès | ✅ v6 |
| 10 | Logs début/fin de `run()` manquants — contrat demande : début, téléchargement, upload, load, fin | ✅ v5 |

## ⚠️ Mineurs

| # | Description | Statut |
|---|-------------|--------|
| 11 | Écriture locale `/tmp` inutile (fichier écrit puis jamais lu par `upload_to_gcs`) | ✅ v1 (résolu par #1 — `shared/` attend un `local_path`) |
| 12 | `requests` au lieu de `httpx` — divergence avec la spec du component document | ✅ v3 |

## Tests

| # | Description | Statut |
|---|-------------|--------|
| 13 | Un seul test, valeur quasi nulle — manquent : happy path `run()`, réponse vide, erreur HTTP, erreur réseau, mocks sur `shared/`, assertions sur appels `upload_to_gcs`/`load_gcs_to_bq` | ⏳ à faire |