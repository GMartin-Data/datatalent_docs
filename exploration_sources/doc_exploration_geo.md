**T4.1 Identifier les endpoints utiles : /regions, /departements, /communes — 0.25j**
- /regions
- /departements
- /communes

**T4.2 Explorer les réponses : champs disponibles, format, volume (~35k communes) — 0.25j**
- *champs disponibles* :
régions : code, nom  
départements : code, codeRegion, nom  
communes : code, codeDepartement, codeEpci, codeRegion, codesPostaux, nom, population, siren , longitude, latitude...

- *format* : JSONL pour Big Querry

- *volumes* :
régions = 18
communes = 34969
départements = 100

**T4.3 Implémenter le script : 3 appels GET → JSON → upload GCS via shared/gcs.py — 0.5j**
Ok

**T4.4 Charger dans BigQuery raw via shared/bigquery.py — 0.25j**
En attente concertation groupe

**T4.5 Ajouter logging structuré (shared/logging.py), gestion d'erreurs, idempotence — 0.25j**
Ok