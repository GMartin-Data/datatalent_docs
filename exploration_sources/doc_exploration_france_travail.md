# Documentation API France Travail

## 1. Inscription & Credentials

1. Créer un compte sur [francetravail.io](https://francetravail.io)
2. Créer une application dans l'espace développeur
3. Souscrire à l'API **"Offres d'emploi v2"**
4. Récupérer `CLIENT_ID` et `CLIENT_SECRET`

Les secrets sont à définir dans `.env` à la racine du projet :

```env
CLIENT_ID=PAR_xxxx_...
CLIENT_SECRET=...
```

Les paramètres non sensibles sont dans `ingestion/france_travail/config.py` :

```python
SCOPE = "api_offresdemploiv2 o2dsoffre"
TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire"
RAW_DATA_DIR = "raw/france_travail"
```

---

## 2. OAuth2 — Flow client_credentials

France Travail utilise le flow **machine-to-machine** (`client_credentials`). Il n'y a pas de refresh token — à expiration, un nouveau token est demandé automatiquement.

### Requête token

```http
POST https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=%2Fpartenaire
Content-Type: application/x-www-form-urlencoded

grant_type=client_credentials
&client_id=PAR_xxxx
&client_secret=...
&scope=api_offresdemploiv2 o2dsoffre
```

> ⚠️ Le paramètre `?realm=%2Fpartenaire` est obligatoire dans l'URL. Sans lui, l'API retourne une erreur 400.

### Réponse

```json
{
  "access_token": "eyJ...",
  "token_type": "Bearer",
  "expires_in": 1499
}
```

### Utilisation

```http
GET https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search
Authorization: Bearer <access_token>
```

### Comportement du cache (`auth.py`)

| Situation | Comportement |
|---|---|
| Token valide en cache | Réutilisé sans appel réseau |
| Token expirant dans < 60s | Renouvellement anticipé |
| Réponse 401 de l'API | Invalidation forcée + retry immédiat |
| Token absent ou expiré | Nouvel appel OAuth2 |

---

## 3. Endpoints

### 3.1 Recherche d'offres

```
GET /partenaire/offresdemploi/v2/offres/search
```

**Paramètres principaux :**

| Paramètre | Type | Description |
|---|---|---|
| `codeROME` | string | Code métier ROME (ex: `M1805`) |
| `departement` | string | Numéro département (ex: `75`) |
| `range` | string | Pagination (ex: `0-149`) |
| `motsCles` | string | Mots-clés libres |
| `typeContrat` | string | `CDI`, `CDD`, `MIS`... |

**Limites :**
- Batch max : **150 offres** par requête (`range: 0-149`)
- Limite dure : **3000 offres** par requête (`range: 0-2999`)
- Au-delà de 3000 résultats : affiner les filtres (département, ROME, mots-clés)

**Header de réponse :**
```
Content-Range: offres 0-149/523
```
→ `523` = nombre total d'offres disponibles pour cette recherche. Utilisé par `fetch_all_offres` pour piloter la pagination.

### 3.2 Détail d'une offre

```
GET /partenaire/offresdemploi/v2/offres/{id}
```

---

## 4. Schéma de réponse — Offre

```json
{
  "id": "187GHKL",
  "intitule": "Data Engineer H/F",
  "description": "...",
  "dateCreation": "2024-03-01T08:00:00.000Z",
  "dateActualisation": "2024-03-05T10:00:00.000Z",
  "lieuTravail": {
    "libelle": "75 - PARIS",
    "codePostal": "75008",
    "commune": "75108",
    "departement": "75"
  },
  "romeCode": "M1805",
  "romeLibelle": "Études et développement informatique",
  "entreprise": {
    "nom": "DataCorp",
    "description": "...",
    "secteurActivite": "62"
  },
  "typeContrat": "CDI",
  "typeContratLibelle": "Contrat à durée indéterminée",
  "natureContrat": "Contrat travail",
  "experienceExige": "E",
  "experienceLibelle": "3 ans et plus",
  "salaire": {
    "libelle": "Annuel de 45000 à 60000 €",
    "commentaire": "selon profil"
  },
  "competences": [
    { "code": "...", "libelle": "Python" },
    { "code": "...", "libelle": "Apache Spark" }
  ],
  "formations": [
    {
      "codeFormation": "26",
      "domaineLibelle": "informatique",
      "niveauLibelle": "Bac+5 et plus"
    }
  ],
  "nombrePostes": 1,
  "accessibleTH": false,
  "origineOffre": {
    "origine": "1",
    "urlOrigine": "https://..."
  }
}
```

---

## 5. Rate Limits

| Limite | Valeur |
|---|---|
| Offres par batch | 150 max |
| Offres par recherche | 3 000 max |
| Erreur rate limit | HTTP 429 |
| Stratégie implémentée | Backoff exponentiel : 2, 4, 8, 16, 32s (5 tentatives max) |

En cas de dépassement fréquent : affiner les requêtes par département + code ROME pour rester sous 3000 résultats.

---

## 6. Lancer l'ingestion

```bash
# Depuis la racine du projet (datatalent/)
uv run --env-file .env python -m ingestion.france_travail.ingest
```

Les fichiers JSON sont stockés dans le répertoire défini par `RAW_DATA_DIR` dans `config.py` (par défaut `raw/france_travail/`).

Pour ajouter des codes ROME ou des départements, modifier les listes dans `ingest.py` :

```python
codes_rome = ["M1805", "M1803", "M1802"]
departements = ["75", "69", "13", "33"]
```

---

## 7. Architecture des fichiers

```
ingestion/
├── france_travail/
│   ├── config.py        # Paramètres non sensibles (SCOPE, TOKEN_URL, RAW_DATA_DIR)
│   ├── auth.py          # Client OAuth2 avec cache, expiration et retry 401
│   ├── offres.py        # Pagination automatique + backoff exponentiel sur 429
│   └── ingest.py        # Point d'entrée — expose run()
├── tests/
│   ├── test_france_travail_auth.py
│   └── test_france_travail_offres.py
```