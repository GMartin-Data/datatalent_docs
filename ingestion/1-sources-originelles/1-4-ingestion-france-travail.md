# Composant : ingestion-france-travail

## Contexte

Projet DataTalent — pipeline data GCP, équipe de 4 devs.
Source la plus complexe du Bloc 1 : API REST avec OAuth2, pagination par département, rate limiting.
Dépend de `ingestion/shared/` (composant `ingestion-shared`, implémenté en amont).

## Périmètre

### Dedans

- `ingestion/france_travail/client.py` — client OAuth2 (auth, cache token, renouvellement) + pagination par département avec backoff
- `ingestion/france_travail/ingest.py` — orchestration extract → écriture JSON locale → `shared/gcs.py` → `shared/bigquery.py`. Expose `run()`
- `ingestion/france_travail/config.py` — codes ROME, endpoints, constantes
- `ingestion/france_travail/__init__.py`

### Dehors

- `ingestion/shared/` — déjà implémenté, consommé tel quel
- `ingestion/main.py` — appelle `run()`, ne connaît pas les détails
- Création du compte développeur France Travail (T2.1) — fait manuellement hors CC
- Filtrage par mots-clés "data engineer" — dbt staging, Bloc 2
- Parsing du champ salaire — dbt staging, Bloc 2

## API France Travail — Spécifications techniques

### Authentification OAuth2

- **Flow :** client_credentials (machine-to-machine)
- **Token endpoint :** `POST https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire`
- **Scope :** `api_offresdemploiv2 o2dsoffre`
- **Credentials :** `client_id` + `client_secret` depuis Secret Manager GCP
- **Durée du token :** ~1500s (25 min) — implémenter cache + renouvellement avant expiration

### Endpoint principal

- **URL :** `GET https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search`
- **Paramètres clés :** `codeROME`, `departement`, `range`, `minCreationDate`, `maxCreationDate`
- **Format réponse :** JSON `{ filtresPossibles: [...], resultats: [...] }` + header `Content-Range`

### Codes ROME (D8)

Stratégie : collecte large (4 codes) → filtrage mots-clés en dbt staging.

| Code | Libellé |
|------|---------|
| M1805 | Études et développement informatique |
| M1810 | Production et exploitation de systèmes d'information |
| M1806 | Conseil et maîtrise d'ouvrage en systèmes d'information |
| M1801 | Administration de systèmes d'information |

### Pagination (D9)

- Paramètre `range` : 0-149 par défaut, max 150 résultats par requête
- Plafond absolu : 1150 résultats par combinaison de critères
- **Stratégie :** itérer par département (101) × code ROME (4). Pour chaque combinaison, paginer de 0-149 jusqu'à épuisement
- **Garde-fou :** si `Content-Range` indique > 1150 résultats, subdiviser par plage de dates (`minCreationDate`/`maxCreationDate`)

### Rate limiting (D10)

- **Limite :** 3 requêtes/seconde
- **Implémentation :** `time.sleep(0.35)` entre requêtes (333ms minimum, 350ms = marge)
- **Retry exponentiel via tenacity :** sur codes 429/500/503, délai 1s → 2s → 4s → 8s → abandon
- **Volume estimé :** ~400-800 requêtes, ~5-8 min d'exécution totale
- **Pas de lib tierce :** wrapper Python maison (~50 lignes), le package PyPI `api-offres-emploi` date de 2020, non maintenu

### Schéma d'une offre (champs à conserver en raw)

| Champ | Type | Criticité |
|-------|------|-----------|
| `id` | string | Clé primaire |
| `intitule` | string | Filtrage staging |
| `description` | string | Filtrage staging (mots-clés) |
| `dateCreation` | ISO-8601 | Dimension temporelle |
| `dateActualisation` | ISO-8601 | Fraîcheur |
| `lieuTravail.libelle` | string | Géographie |
| `lieuTravail.codePostal` | string | Jointure API Géo |
| `lieuTravail.commune` | string | Jointure API Géo (clé primaire) |
| `lieuTravail.latitude` | float | Cartographie |
| `lieuTravail.longitude` | float | Cartographie |
| `entreprise.nom` | string | Quasi toujours présent |
| `entreprise.siret` | string | Rarement présent (~20-40%) — jointure Sirene |
| `salaire.libelle` | string | Souvent absent — parsing regex en staging |
| `salaire.commentaire` | string | Idem |
| `typeContrat` | string | Dimension contrat |
| `typeContratLibelle` | string | Dashboard |
| `romeCode` | string | Filtrage |
| `romeLibelle` | string | Dashboard |
| `experienceExige` | string | D/S/E |
| `experienceLibelle` | string | Dashboard |
| `appellationlibelle` | string | Enrichissement |
| `nombrePostes` | int | Agrégation |

**Règle raw :** stocker la réponse JSON complète telle quelle. Le schéma ci-dessus documente les champs utiles, mais on ne filtre pas les colonnes à l'ingestion.

## Flux d'exécution

```
run()
  │
  ├── 1. get_token() — OAuth2, cache en mémoire, renouvellement si < 60s restantes
  │
  ├── 2. Pour chaque département (101) × code ROME (4) :
  │       ├── Requête paginée (range 0-149, 150-299, ...)
  │       ├── sleep(0.35) entre chaque requête
  │       ├── Retry tenacity sur 429/500/503
  │       └── Accumulation des résultats JSON
  │
  ├── 3. Écriture JSON locale (/tmp/france_travail_YYYY-MM-DD.json)
  │
  ├── 4. shared/gcs.py → upload_to_gcs(local_path, "france_travail")
  │       → gs://datatalent-raw/france_travail/YYYY-MM-DD/offres.json
  │
  └── 5. shared/bigquery.py → load_gcs_to_bq(gcs_uri, "raw", "france_travail")
          → raw.france_travail (partitionnée par _ingestion_date)
```

## Idempotence

- Clé de déduplication : `id` de l'offre
- Ré-exécuter le script le même jour écrase le fichier GCS (même path daté) et recharge BQ sans doublons

## Entrées / Sorties

| Entrée | Fournisseur |
|---|---|
| Credentials OAuth2 (client_id, client_secret) | Secret Manager GCP |
| Interface `shared/` stable | Composant `ingestion-shared` |

| Sortie | Consommateur |
|---|---|
| `gs://datatalent-raw/france_travail/YYYY-MM-DD/offres.json` | BigQuery load job |
| Table `raw.france_travail` partitionnée par `_ingestion_date` | dbt staging (Bloc 2) |

## Contraintes techniques

- Python 3.12+, httpx (HTTP client), tenacity (retry), structlog (logging)
- Auth GCP : Application Default Credentials
- Pas de lib tierce pour l'API France Travail — wrapper maison

## Ownership

- **Owner : Greg** (J1 après-midi → J5)
- Collègue 4 rejoint en pair programming à partir de ~J2

## Décisions de référence

- D8 : codes ROME, stratégie collecte large + filtrage staging
- D9 : pagination par département × code ROME, garde-fou 1150
- D10 : wrapper maison, tenacity, sleep(0.35)
- D14 : jointure SIRET 20-40%, LEFT JOIN (pas INNER)
