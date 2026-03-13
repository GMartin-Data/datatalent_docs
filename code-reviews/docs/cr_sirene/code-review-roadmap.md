# Roadmap de résolution — PR ingestion-sirene

## Prérequis : décision d'équipe

Trancher **avant toute modification de code** : StockUniteLegale in ou out ?

- **Out (conforme D11)** → supprimer `unite_legale` de `SIRENE_RESOURCES` et `RESOURCE_SELECTED_COLUMNS`
- **In** → mettre à jour `ingestion-sirene.md` (périmètre, schéma, volume, justification)

## Steps de résolution

| Step | Action | Issues réglées | Détail |
|------|--------|----------------|--------|
| **1** | Supprimer la logique de sélection de colonnes | ❌ #2 (viole D11) | Retirer `PREPARED_DIR`, `RESOURCE_SELECTED_COLUMNS`, `transform_parquet_keep_columns`, `build_prepared_filename`, `select_existing_columns`, `cleanup_old_versions` sur prepared. Le raw = parquet complet tel quel. |
| **2** | Brancher `shared/` dans `run()` | ❌ #1 (GCS + BQ absents), ⚠️ #7 (idempotence) | Après download : `upload_to_gcs(raw_path, "sirene")` → `load_gcs_to_bq(gcs_uri, "raw", "sirene")`. L'idempotence découle du path GCS daté. |
| **3** | Remplacer `log()` par `get_logger(__name__)` | ⚠️ #4 (logging structuré) | Supprimer la fonction `log()`, importer `get_logger` de `shared/logging.py`, adapter les appels. |
| **4** | Ajouter tenacity + migrer vers httpx | ⚠️ #5 (retry), ⚠️ #6 (httpx) | Décorateur `@retry` sur `fetch_dataset_metadata()` et `download_file()`. Remplacer `requests` par `httpx` (cohérence équipe). |
| **5** | Ajuster `validate_resource_freshness` | ⚠️ #8 (seuil 45j) | Passer à ~62 jours ou transformer en warning (log) au lieu d'exception. |
| **6** | Adapter les tests | tous | Ajouter mocks sur `shared/` (GCS, BQ, logger). Supprimer tests liés à la sélection de colonnes. Ajouter test `download_file` avec mock réseau. |

## Dépendances entre steps

```
Décision UL → Step 1 → Step 2 → Step 6
                         Step 3 → Step 6
                         Step 4 → Step 6
                         Step 5 → Step 6
```

Steps 3, 4, 5 sont indépendants entre eux et parallélisables après Step 1. Step 6 (tests) vient en dernier car chaque step précédent invalide des tests existants.