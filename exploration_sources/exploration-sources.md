# Exploration des sources de données — Projet DataTalent

**Dernière mise à jour :** 2026-03-09

---

## B1 — API France Travail (Offres d'emploi v2)

### Accès et authentification

- **Portail :** francetravail.io → créer un compte, créer une application, s'abonner à "API Offres d'emploi v2"
- **Flow OAuth2 :** client_credentials (machine-to-machine, pas de login utilisateur)
- **Token endpoint :** `POST https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire`
- **Scope :** `api_offresdemploiv2 o2dsoffre`
- **Credentials :** `client_id` + `client_secret` → stocker dans Secret Manager (D6)
- **Durée du token :** ~1500s (25 min) — implémenter cache + renouvellement avant expiration

### Endpoint principal

- **URL :** `GET https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search`
- **Paramètres clés :** `codeROME`, `departement`, `range`, `minCreationDate`, `maxCreationDate`, `motsCles`
- **Format réponse :** JSON `{ filtresPossibles: [...], resultats: [...] }` + header `Content-Range`

### Codes ROME retenus (D8)

ROME = Répertoire Opérationnel des Métiers et des Emplois. Nomenclature France Travail (~530 fiches), code = lettre + 4 chiffres. Pas de code dédié "Data Engineer" — le métier est ventilé sur plusieurs fiches.

**Stratégie : collecte large (4 codes) + filtrage mots-clés en staging dbt.**

| Code | Libellé |
|------|---------|
| M1805 | Études et développement informatique |
| M1810 | Production et exploitation de systèmes d'information |
| M1806 | Conseil et maîtrise d'ouvrage en systèmes d'information |
| M1801 | Administration de systèmes d'information |

**Mots-clés de filtrage staging :** `data engineer`, `ingénieur data`, `développeur data`, `data engineering`, `ingénieur de données`

### Schéma d'une offre (champs utiles)

| Champ | Type | Description | Criticité projet |
|-------|------|-------------|-----------------|
| `id` | string | Identifiant unique de l'offre | Clé primaire |
| `intitule` | string | Titre du poste | Filtrage staging |
| `description` | string | Texte complet de l'offre | Filtrage staging (mots-clés) |
| `dateCreation` | ISO-8601 | Date de publication | Dimension temporelle |
| `dateActualisation` | ISO-8601 | Dernière mise à jour | Fraîcheur |
| `lieuTravail.libelle` | string | Ex: "75 - Paris" | Dimension géographique |
| `lieuTravail.codePostal` | string | Code postal | Jointure API Géo |
| `lieuTravail.commune` | string | Code commune | Jointure API Géo |
| `lieuTravail.latitude` | float | Coordonnée | Cartographie |
| `lieuTravail.longitude` | float | Coordonnée | Cartographie |
| `entreprise.nom` | string | Nom de l'entreprise | Quasi toujours présent |
| `entreprise.siret` | string | SIRET | **Rarement présent (~20-40%)** — jointure Sirene |
| `salaire.libelle` | string | Texte libre, ex: "30 - 50 k€ brut annuel" | **Souvent absent** — parsing regex |
| `salaire.commentaire` | string | Détails salaire | Idem |
| `typeContrat` | string | CDI, CDD, etc. | Dimension contrat |
| `typeContratLibelle` | string | Libellé contrat | Dashboard |
| `romeCode` | string | Code ROME de l'offre | Filtrage |
| `romeLibelle` | string | Libellé ROME | Dashboard |
| `experienceExige` | string | D (débutant), S (souhaité), E (exigé) | Dimension expérience |
| `experienceLibelle` | string | Détail expérience | Dashboard |
| `appellationlibelle` | string | Appellation fine du métier | Enrichissement |
| `nombrePostes` | int | Nombre de postes ouverts | Agrégation |

### Pagination (D9)

- Paramètre `range` : 0-149 par défaut, max 150 résultats par requête
- Plafond absolu : range max = 1000-1149, soit **1150 résultats par combinaison de critères**
- **Stratégie :** itérer par département (101) × code ROME (4). Pour chaque combinaison, paginer de 0-149 jusqu'à épuisement.
- **Garde-fou :** si `Content-Range` indique > 1150 résultats, subdiviser par plage de dates (`minCreationDate`/`maxCreationDate`)
- L'API accepte plusieurs codes ROME en une requête (`codeROME=M1805,M1810,...`), ce qui peut réduire les itérations, mais augmente le risque de dépasser le plafond 1150 par département. À valider empiriquement.

### Rate limiting

- **Limite :** 3 requêtes/seconde
- **Implémentation :** `time.sleep(0.35)` entre requêtes (333ms minimum requis, 350ms = marge)
- **Retry exponentiel via `tenacity` :** sur codes 429/500/503, délai 1s → 2s → 4s → 8s → abandon
- **Volume estimé :** ~400-800 requêtes, ~5-8 min d'exécution totale

### Risques

- **SIRET :** faible taux de présence (~20-40%) → jointure Sirene fragile, plan B nécessaire (B4)
- **Salaire :** texte libre non structuré, souvent absent → parsing regex en staging, accepter un taux de couverture partiel
- **Pagination :** plafond 1150 → subdivision par dates si dépassement (peu probable pour "Data Engineer" par département)

### Décisions associées

- **D8 :** 4 codes ROME + filtrage mots-clés staging
- **D9 :** Pagination par département × code ROME
- **D10 :** Wrapper Python maison (pas de lib tierce), tenacity pour retry

---

## B2 — Stock Sirene INSEE (Établissements)

### Accès

- **Source :** data.gouv.fr, téléchargement libre, aucune authentification
- **5 fichiers stock mensuels :** unités légales, établissements, historisés (×2), successions
- **Format :** CSV (ZIP) et **Parquet** (disponible depuis juin 2025)
- **Fréquence :** mensuel — image au dernier jour du mois précédent, publiée le 1er du mois suivant

### Fichier retenu : StockEtablissement (Parquet)

Pas StockUniteLegale. Raison : le SIRET identifie un **établissement** (site physique), pas une entreprise. Les offres France Travail référencent le SIRET de l'établissement qui recrute. Une entreprise (SIREN) peut avoir plusieurs établissements (SIRET).

### Champs utiles

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

### Codes NAF pertinents (enrichissement, PAS filtrage)

Les codes NAF classifient l'activité de l'entreprise. Utiles pour enrichir les marts, **pas pour filtrer Sirene** en amont (un Data Engineer peut être recruté par une banque, un retailer, une industrie...).

| Code | Libellé |
|------|---------|
| 6201Z | Programmation informatique |
| 6202A | Conseil en systèmes et logiciels informatiques (ESN/SSII) |
| 6202B | Tierce maintenance de systèmes et d'applications informatiques |
| 6203Z | Gestion d'installations informatiques |
| 6209Z | Autres activités informatiques |
| 6311Z | Traitement de données, hébergement et activités connexes |
| 6312Z | Portails Internet |

### Volume

| Étape | Volume estimé |
|-------|--------------|
| StockEtablissement brut | ~40M lignes, ~2-3 Go (Parquet) |
| Après filtre actifs (staging) | ~15M lignes |
| Après jointure avec offres France Travail (intermediate) | ~500-2000 lignes |

### Stratégie de chargement (D11)

- Upload du Parquet **complet** vers GCS → chargement dans BigQuery raw
- Filtrage en dbt staging : `WHERE etatAdministratifEtablissement = 'A'`
- Conforme au pattern Medallion (raw = brut intégral)
- BigQuery gère sans problème une table de 40M lignes

### Refresh (D12)

- Bloc 1 : chargement unique du stock courant
- Bloc 3 (automatisation) : Cloud Scheduler cron `0 6 2 * *` → Cloud Run re-télécharge, upload GCS avec prefix daté (`sirene/YYYY-MM/`), recharge BigQuery raw

### Point RGPD

Les établissements avec `statutDiffusionEtablissement = 'P'` ont demandé une diffusion partielle — adresse et géolocalisation masquées. À gérer en staging : ne pas exposer ces données dans le dashboard.

### Décisions associées

- **D11 :** Chargement complet, pas de pré-filtrage
- **D12 :** Refresh mensuel automatisé (Bloc 3)

---

## B3 — API Géo (Découpage administratif)

### Accès

- **Base URL :** `https://geo.api.gouv.fr`
- **Authentification :** aucune (API ouverte)
- **Rate limiting :** 50 requêtes/seconde/IP (largement suffisant)
- **Format :** JSON par défaut, GeoJSON en option (`?format=geojson`)
- **Source de la spec :** [`definition.yml`](https://github.com/datagouv/api-geo/blob/master/definition.yml) (Swagger 2.0)

### Endpoints utilisés

| Endpoint | Description | Volume |
|----------|-------------|--------|
| `GET /regions` | Liste complète des régions | ~18 entrées |
| `GET /departements` | Liste complète des départements | ~101 entrées |
| `GET /communes` | Liste complète des communes | ~35 000 entrées |

Paramètres utiles : `fields` (sélection des champs retournés, CSV), `zone` (metro, drom, com).

### Schéma Région

| Champ | Type | Description | Usage projet |
|-------|------|-------------|-------------|
| `code` | string | Code région (ex: "32") | **Clé de jointure** |
| `nom` | string | Nom (ex: "Hauts-de-France") | Dashboard |
| `zone` | string | metro, drom, com | Filtrage |

### Schéma Département

| Champ | Type | Description | Usage projet |
|-------|------|-------------|-------------|
| `code` | string | Code département (ex: "59") | **Clé de jointure** |
| `nom` | string | Nom (ex: "Nord") | Dashboard |
| `codeRegion` | string | Code région parent | Jointure région |
| `zone` | string | metro, drom, com | Filtrage |

### Schéma Commune (champs utiles)

| Champ | Type | Description | Usage projet |
|-------|------|-------------|-------------|
| `code` | string | Code INSEE commune (ex: "59350") | **Clé de jointure** offres & Sirene |
| `nom` | string | Nom commune | Dashboard |
| `codesPostaux` | array[string] | Codes postaux associés | Jointure fallback |
| `codeDepartement` | string | Code département parent | Jointure département |
| `codeRegion` | string | Code région parent | Jointure région |
| `population` | int | Population municipale | Enrichissement |
| `centre` | GeoJSON Point | Coordonnées lat/lon du centre | Cartographie |
| `surface` | float | Surface en hectares | Enrichissement |

Champs disponibles mais non retenus : `siren`, `codeEpci`, `contour` (Polygon GeoJSON, ~34 Mo pour toute la France — trop lourd, inutile pour le projet), `mairie`, `bbox`.

### Stratégie : snapshot complet en raw (D13)

- **Pourquoi pas à la volée :** les données géographiques changent très rarement (le dernier redécoupage régional date de 2016). Le guide Etalab recommande explicitement de stocker un snapshot JSON plutôt que d'appeler l'API à chaque exécution.
- **Implémentation :** 3 appels GET (régions, départements, communes) → JSON stocké dans GCS (`geo/regions.json`, `geo/departements.json`, `geo/communes.json`) → chargé dans BigQuery raw.
- **Volume :** négligeable (~3-5 Mo pour les communes avec champs centre/population, quelques Ko pour régions et départements).
- **Refresh :** annuel au mieux. Pas besoin d'automatisation Cloud Scheduler.
- **Paramètres d'appel recommandés :**
  - Régions : `GET /regions?fields=code,nom,zone`
  - Départements : `GET /departements?fields=code,nom,codeRegion,zone&zone=metro,drom,com`
  - Communes : `GET /communes?fields=code,nom,codesPostaux,codeDepartement,codeRegion,population,centre,surface&zone=metro,drom,com`

### Décision associée

- **D13 :** API Géo = snapshot complet en raw (3 niveaux), pas d'appel à la volée

---

## B4 — Jointure inter-sources

### Vue d'ensemble

Le modèle intermediate dbt doit combiner 3 sources pour répondre à "Où recrute-t-on, dans quelles entreprises, à quels salaires ?" :

```
stg_offres (France Travail)
  LEFT JOIN stg_sirene       ON offres.siret = sirene.siret
  LEFT JOIN ref_communes      ON offres.code_commune = communes.code
  LEFT JOIN ref_departements  ON communes.code_departement = departements.code
  LEFT JOIN ref_regions       ON departements.code_region = regions.code
```

### Jointure 1 : Offres ↔ Sirene (SIRET)

| Aspect | Détail |
|--------|--------|
| Clé côté offres | `entreprise.siret` (string, 14 chiffres) |
| Clé côté Sirene | `siret` (string, 14 chiffres) |
| Type de jointure | `LEFT JOIN` (ne pas perdre les offres sans SIRET) |
| Taux de matching estimé | **20-40%** (SIRET souvent absent ou masqué) |
| Enrichissement obtenu | `denominationUniteLegale`, `activitePrincipaleEtablissement` (NAF), `trancheEffectifsEtablissement` |

**Pourquoi LEFT JOIN :** un INNER JOIN éliminerait 60-80% des offres, rendant les analyses géographiques et salariales non représentatives. Les offres sans SIRET restent utiles pour les axes "où" et "à quel salaire".

**Pré-traitement staging :** normaliser le SIRET (supprimer espaces, vérifier longueur 14, cast en string), filtrer Sirene sur `etatAdministratifEtablissement = 'A'`.

### Plan B : matching par nom d'entreprise

| Pour | Contre |
|------|--------|
| Augmenterait le taux de matching | Faux positifs (noms abrégés, orthographe variable) |
| `entreprise.nom` quasi toujours présent | 15M lignes Sirene × matching flou = coût BigQuery élevé |
| | Ambiguïté SIREN/SIRET (un groupe a N établissements) |
| | Complexité dbt (fonctions BigQuery : `SOUNDEX`, `EDIT_DISTANCE`) |

**Décision (D14) :** ne PAS implémenter en Bloc 2. Mesurer le taux de matching SIRET réel sur les données ingérées, puis décider en connaissance de cause pour Bloc 3. Le matching par nom est un enrichissement optionnel, pas un prérequis pour le dashboard.

### Jointure 2 : Offres ↔ API Géo (enrichissement géographique)

C'est la jointure la plus fiable du pipeline — presque toutes les offres ont des informations de localisation.

| Clé de jointure | Fiabilité | Détail |
|-----------------|-----------|--------|
| `lieuTravail.commune` → `communes.code` | **Haute** | Code INSEE commune, même référentiel que l'API Géo |
| Code département extrait de `lieuTravail.libelle` | Moyenne | Format "XX - Ville", parsing regex en staging |
| `lieuTravail.codePostal` → `communes.codesPostaux` | Basse | Un code postal peut couvrir plusieurs communes |

**Stratégie staging :** extraire le `code_commune` et le `code_departement` en staging, joindre sur `code_commune` en priorité, fallback sur `code_departement` si commune manquante.

**Enrichissement obtenu :** nom département, nom région, population commune, coordonnées centre (lat/lon pour cartographie dashboard).

### Jointure 3 : Sirene ↔ API Géo

| Clé côté Sirene | Clé côté API Géo | Fiabilité |
|-----------------|------------------|-----------|
| `codeCommuneEtablissement` | `communes.code` | **Haute** (même référentiel INSEE) |

Pas de difficulté particulière. Utile pour géolocaliser l'établissement recruteur (qui peut différer du lieu de travail de l'offre).

### Risques consolidés

| Risque | Impact | Mitigation |
|--------|--------|------------|
| SIRET absent ~60-80% des offres | Enrichissement sectoriel partiel | LEFT JOIN + dashboard avec caveat "données disponibles" |
| Salaire absent ou texte libre | Axe salarial peu couvert | Parsing regex en staging, accepter couverture partielle |
| Code commune absent dans certaines offres | Enrichissement géo incomplet | Fallback sur code département extrait de `lieuTravail.libelle` |
| Offres multi-sites | 1 offre = 1 seul `lieuTravail` | Accepter la limitation (standard API France Travail) |

### Décisions associées

- **D13 :** API Géo = snapshot complet en raw (3 niveaux), pas d'appel à la volée
- **D14 :** Jointure offres ↔ Sirene = LEFT JOIN sur SIRET uniquement en Bloc 2, matching par nom reporté à Bloc 3 si nécessaire
- **D15 :** Enrichissement géographique = jointure sur code commune INSEE (priorité), fallback code département
