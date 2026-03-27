# Exploration des sources de données — Projet DataTalent

**Dernière mise à jour :** 2026-03-27 (B6 révisée — workflow d'ingestion classique, B7 branche seed retirée)

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

**Stratégie initiale (D8) :** collecte large (4 codes) + filtrage mots-clés en staging dbt.

**Stratégie révisée (D8-bis, post-exploration 2026-03-24) :** collecte large (4 codes) → garder les 2589 offres IT → classification `categorie_metier` par regex sur titre en staging. Le filtrage mots-clés D8 ne retournait que 9 offres (0.3%) — inutilisable. La classification par titre identifie 20 offres "data" (6 data_engineer, 6 BI, 4 data_analyst, 3 data_architect, 1 ML). Le dashboard expose un filtre sur `categorie_metier`, la vue par défaut montre le périmètre IT complet. Voir `exploration-axe1-volume-filtrage.md`.

| Code | Libellé |
|------|---------|
| M1805 | Études et développement informatique |
| M1810 | Production et exploitation de systèmes d'information |
| M1806 | Conseil et maîtrise d'ouvrage en systèmes d'information |
| M1801 | Administration de systèmes d'information |

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
| `entreprise.nom` | string | Nom de l'entreprise | Présent à 36.2% (938/2589). Dominé par intérimaires/ESN |
| `entreprise.siret` | string | SIRET | **Absent de 100% des offres** (D14-bis) — jointure Sirene morte |
| `codeNAF` | string | Code NAF de l'établissement publieur | Présent à 47.8%, biaisé intérim (38.3%) |
| `secteurActiviteLibelle` | string | Libellé du secteur | Même couverture que codeNAF |
| `salaire.libelle` | string | Format structuré : "Annuel de X Euros à Y Euros" | **Présent à 29.6%** — 100% parsable (6 patterns regex) |
| `salaire.commentaire` | string | Détails salaire (texte libre) | Présent à 15.5% — parsing non recommandé |
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

- **Limite réelle :** 10 requêtes/seconde (constatée sur le portail francetravail.io, application DataTalent-Greg). L'ancienne valeur de 3 req/s provenait d'une documentation obsolète.
- **Throttle préventif :** `time.sleep(0.15)` entre requêtes (~6.6 req/s, conservateur)
- **Retry exponentiel via `tenacity` :** sur codes 429/500/503, délai 1s → 2s → 4s → 8s → abandon
- **Volume estimé :** ~400-800 requêtes, ~5-8 min d'exécution totale

### Risques — statut post-exploration (2026-03-24)

- **SIRET :** ~~faible taux de présence (~20-40%)~~ **Absent à 100%.** Jointure Sirene morte (D14-bis). Enrichissement sectoriel via `codeNAF` de l'offre (47.8%) + URSSAF effectifs (D35).
- **Salaire :** `salaire.libelle` présent à 29.6%, 100% parsable mécaniquement (6 patterns regex). `salaire.commentaire` = texte libre non structuré (15.5%), parsing non recommandé. Couverture combinée (au moins l'un des deux) = 40.4%. Voir `exploration-axe2-taux-presence.md`.
- **Pagination :** plafond 1150 → non atteint sur le run 101 depts × 4 ROME (2589 offres totales)
- **Volume offres data :** 20 offres "data" sur 2589 IT — structurellement faible (le ROME ne distingue pas Data Engineer). Mitigé par D8-bis (classification) et accumulation hebdomadaire D19.
- **Biais intérim :** 38.3% des offres avec `codeNAF` portent le code de l'intérimaire (78.10Z/78.20Z), pas de l'employeur final. Flag `is_intermediaire` en staging.

### Décisions associées

- **D8-bis :** 4 codes ROME + classification `categorie_metier` par regex titre (remplace D8 filtrage mots-clés)
- **D9 :** Pagination par département × code ROME
- **D10 :** Wrapper Python maison, rate limit 10 req/s, tenacity pour retry

---

## B2 — Stock Sirene INSEE (Établissements)

> **Statut post-exploration :** Sirene reste ingéré comme livrable technique (brief) et démonstration dbt sur source volumineuse. La jointure SIRET avec les offres est morte (D14-bis, SIRET absent à 100%). L'enrichissement sectoriel repose sur `codeNAF` de l'offre + URSSAF effectifs (D35). Sirene ne contribue à aucun mart analytique.

### Accès

- **Source :** data.gouv.fr, téléchargement libre, aucune authentification
- **5 fichiers stock mensuels :** unités légales, établissements, historisés (×2), successions
- **Format :** CSV (ZIP) et **Parquet** (disponible depuis juin 2025)
- **Fréquence :** mensuel — image au dernier jour du mois précédent, publiée le 1er du mois suivant

### Fichiers retenus (D11)

- **StockEtablissement** (Parquet, ~2 Go) : le SIRET identifie un **établissement** (site physique). Contient 54 colonnes dont `activitePrincipaleEtablissement` (NAF rév.2), `codeCommuneEtablissement`, `trancheEffectifsEtablissement`, coordonnées Lambert.
- **StockUniteLegale** (Parquet, ~650 Mo) : ajouté pour `denominationUniteLegale` (nom juridique officiel), nécessaire si matching par nom tenté ultérieurement.
- **Colonne NAF 2025** (confirmée par exploration MCP) : `activitePrincipaleNAF25Etablissement` déjà diffusée à titre informatif. Transition officielle au 1er janvier 2027. Aucun impact immédiat.

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
| StockEtablissement brut | ~40M lignes, ~2 Go (Parquet) |
| StockUniteLegale brut | ~25M lignes, ~650 Mo (Parquet) |
| Après filtre actifs (staging) | ~15M lignes |
| ~~Après jointure avec offres France Travail~~ | ~~500-2000 lignes~~ — caduque (D14-bis, SIRET absent à 100%) |

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

## B4 — Jointures inter-sources

> **Mis à jour 2026-03-25** suite à l'exploration France Travail (Axes 1-3) et l'exploration MCP data.gouv.fr (D35). La jointure Sirene est morte. L'architecture intermediate est documentée en détail dans `couche-intermediate-datatalent.md`.

### Vue d'ensemble

```
int_offres_enrichies :
  stg_offres (France Travail)
    LEFT JOIN stg_communes (API Géo) ON offres.code_commune = communes.code

int_densite_sectorielle_commune :
  stg_urssaf_effectifs WHERE code_ape IT GROUP BY code_commune, annee

int_tensions_bassin_emploi (conditionnel, si spike BMO validé) :
  stg_bmo WHERE code_fap LIKE 'M2Z%'
```

### Jointure 1 : Offres ↔ API Géo (enrichissement géographique) — PRINCIPALE

La jointure la plus fiable du pipeline. Confirmée par l'exploration Axe 3 (2026-03-24).

| Clé de jointure | Fiabilité | Couverture confirmée |
|-----------------|-----------|---------------------|
| `lieuTravail.commune` → `communes.code` | **Haute** | 92.7% (2401/2589 offres) |
| Code département extrait de `lieuTravail.libelle` | **Haute** | 100% (2589/2589, zéro orpheline) |
| Coordonnées lat/lon | Haute | 89.3% |

Validation croisée : 100% concordance entre les deux sources sur les 2399 offres où les deux sont présentes (zéro discordance). Voir `exploration-axe3-distribution-geo.md`.

**Enrichissement obtenu :** nom commune, nom département, nom région, population, coordonnées centre.

### Jointure 2 : Offres ↔ Sirene (SIRET) — CADUQUE (D14-bis)

| Aspect | Estimation initiale (D14) | Réalité constatée |
|--------|--------------------------|-------------------|
| Taux de matching SIRET | 20-40% | **0%** — champ absent de 100% des offres |
| `entreprise.nom` | "quasi toujours présent" | 36.2% (938/2589), dominé par intérimaires |
| Plan B matching par nom | Bloc 3 | Reporté sine die (effort disproportionné) |

**D14-bis :** jointure SIRET abandonnée. L'enrichissement sectoriel repose sur :
1. `codeNAF` et `secteurActiviteLibelle` directement dans l'offre France Travail (47.8% de couverture, biaisé intérim à 38.3%)
2. URSSAF effectifs commune × APE (B5) comme contexte géo-sectoriel non biaisé

Sirene reste ingéré comme livrable technique — voir B2.

### Jointure 3 : Offres ↔ URSSAF effectifs (contextuelle) — NOUVELLE (D35)

Pas une jointure ligne-à-ligne (on ne sait pas quel établissement a publié l'offre) mais un enrichissement contextuel spatial.

| Clé de jointure | Type | Enrichissement |
|-----------------|------|----------------|
| `code_commune` (offres) → `code_commune` (URSSAF) | LEFT JOIN contextuel | nb_etablissements_it, effectifs_salaries_it dans cette commune |
| `code_departement` (offres) → agrégat URSSAF par département | Fallback | Même enrichissement au niveau département |

**Usage :** "cette offre est localisée dans une commune comptant X établissements IT employant Y salariés". Permet un ratio offres/effectifs = indicateur de dynamisme de recrutement.

### Jointure 4 : Offres ↔ BMO (contextuelle) — CONDITIONNELLE (D35)

Dépend du spike sur la granularité FAP2021.

| Clé de jointure | Type | Enrichissement |
|-----------------|------|----------------|
| `code_departement` (offres) → `code_departement` (BMO, dérivé du bassin) | LEFT JOIN contextuel | projets_recrutement_it, part_difficile_pct |

**Usage :** "dans ce département, X% des projets de recrutement IT sont jugés difficiles par les employeurs (source BMO)".

### Risques consolidés — post-exploration

| Risque | Impact | Statut |
|--------|--------|--------|
| ~~SIRET absent ~60-80% des offres~~ | ~~Enrichissement sectoriel partiel~~ | **Résolu** — SIRET absent à 100%, enrichissement via codeNAF offre + URSSAF (D14-bis, D35) |
| Salaire absent ou texte libre | Axe salarial couvert à 29.6% (parsable) + 15.5% (texte libre) | Accepté — parsing regex sur `salaire.libelle`, benchmark URSSAF masse salariale NA88 en complément |
| Code commune absent dans certaines offres | Enrichissement géo incomplet pour 7.3% | Résolu — fallback département à 100% (confirmé Axe 3) |
| Offres multi-sites | 1 offre = 1 seul `lieuTravail` | Accepté (standard API France Travail) |
| Biais intérim codeNAF | 38.3% des offres avec NAF = intérimaire | Documenté — flag `is_intermediaire` + URSSAF comme contrepoint non biaisé |
| Spike BMO incertain | Granularité FAP data vs dev vs infra inconnue | À trancher par spike avant intégration |

### Décisions associées

- **D13 :** API Géo = snapshot complet en raw (3 niveaux), pas d'appel à la volée
- **D14-bis :** Jointure SIRET abandonnée (0% match). Enrichissement sectoriel via codeNAF offre + URSSAF
- **D15 :** Enrichissement géographique = jointure sur code commune INSEE (92.7%), fallback département (100%)
- **D35 :** Sources complémentaires URSSAF + BMO
- **D37 :** Filtrage codes APE IT à l'ingestion URSSAF

---

## B5 — URSSAF effectifs par commune × APE (D35, P1)

> Source identifiée lors de l'exploration MCP data.gouv.fr (2026-03-25). Voir `exploration-mcp-datagouv.md` fiche #1.

### Accès

- **Dataset data.gouv.fr :** `5efd242c72595ba1a48628f2`
- **Producteur :** URSSAF (Unions de Recouvrement des cotisations de Sécurité Sociale et d'Allocations Familiales)
- **API :** Opendatasoft — `https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last/`
- **Authentification :** aucune (API ouverte)
- **Formats export :** CSV (`/exports/csv`), JSON (`/exports/json`), ou requêtes filtrées (`/records?where=...&limit=...&offset=...`)
- **Licence :** ODbL
- **Fréquence MAJ :** annuelle (fin d'année + ~150 jours)
- **Dernière MAJ constatée :** 30 mai 2025

### Contenu

Nombre d'établissements employeurs et effectifs salariés en fin d'année, par **code APE (NAF rév.2 niveau 5)** × **commune**, depuis 2006. Secteur privé, régime général. Apprentis inclus à compter de juin 2023.

### Filtrage à l'ingestion (D37)

On ne télécharge que les codes APE du périmètre IT :

| Code APE | Libellé |
|---|---|
| 62.01Z | Programmation informatique |
| 62.02A | Conseil en systèmes et logiciels informatiques |
| 62.03Z | Gestion d'installations informatiques |
| 62.09Z | Autres activités informatiques |

Volume filtré estimé : quelques dizaines de milliers de lignes (vs millions pour le dataset complet).

### Valeur pour le projet

Seule source identifiée croisant code NAF détaillé (NAF5) × géographie fine (commune). Compense l'absence de SIRET (D14-bis) en fournissant un **contexte géo-sectoriel** : "cette commune compte X établissements IT employant Y salariés". Permet de calculer un ratio offres/effectifs = indicateur de dynamisme de recrutement.

Contrepoint au biais intérim du `codeNAF` France Travail : les effectifs URSSAF reflètent les vrais employeurs, pas les intermédiaires de placement.

### Modèles dbt

- **Staging :** `stg_urssaf__effectifs_commune_ape` (renommage colonnes, typage)
- **Intermediate :** `int_densite_sectorielle_commune` (GROUP BY code_commune, annee — agrège les 4 codes APE IT)
- **Jointure aval :** `code_commune` → `int_offres_enrichies` en marts

### Décisions associées

- **D35 :** Source complémentaire retenue (P1, priorité élevée)
- **D37 :** Filtrage codes APE IT à l'ingestion

---

## B6 — URSSAF masse salariale × NA88 (D35, P3)

> Source identifiée lors de l'exploration MCP data.gouv.fr (2026-03-25). Voir `exploration-mcp-datagouv.md` fiche #4.

### Accès

- **Dataset data.gouv.fr :** `61d784a161825aaf438b8e9e`
- **Producteur :** URSSAF
- **API :** Opendatasoft — `https://open.urssaf.fr/api/explore/v2.1`
- **Authentification :** aucune
- **Licence :** ODbL
- **Fréquence MAJ :** annuelle (fin d'année + ~250 jours)
- **Dernière MAJ constatée :** 17 septembre 2025

### Contenu

Nombre d'établissements employeurs, effectifs salariés moyens annuels, et **masse salariale annuelle**, par secteur NA88 (avec distinction intérimaires), France entière, depuis 1998.

### Filtre

Code NA88 = `62` — Programmation, conseil et autres activités informatiques. Plus fin que NAF A17 (`J` = tout le secteur Information & Communication) mais moins que NAF5 (pas de distinction 62.01Z vs 62.02A).

### Volume

~30 lignes (une par année depuis 1998). Table de référence.

### Valeur pour le projet

Division masse salariale / effectifs = **salaire brut moyen annuel estimé** pour le secteur programmation/conseil informatique au niveau France. Benchmark contextuel dans le dashboard — les fourchettes salariales des offres (29.6% couverture) sont ancrées dans un référentiel objectif issu de données déclaratives (DADS/DSN).

**Limites :** France entière uniquement (pas de croisement géographique), toutes CSP confondues.

### Stratégie : workflow d'ingestion classique

Script Python dans `ingestion/urssaf_masse_salariale/` : requête API Opendatasoft filtrée NA88 = 62 → JSONL local → `shared/gcs.py` → `shared/bigquery.py` → raw. Staging dbt : `stg_urssaf__masse_salariale_na88`. Malgré le faible volume (~30 lignes), le workflow classique est retenu par souci d'uniformité architecturale et d'automatisation homogène via Cloud Run Job.

### Décisions associées

- **D35 :** Source complémentaire retenue (P3, priorité moyenne)
- **~~D36~~** annulée — workflow classique d'ingestion pour toutes les sources, quelle que soit la volumétrie

---

## B7 — BMO France Travail — Besoins en Main d'Œuvre (D35, P2)

> Source identifiée lors de l'exploration MCP data.gouv.fr (2026-03-25). Voir `exploration-mcp-datagouv.md` fiche #2. **Intégration conditionnelle — spike préalable requis.**

### Accès

- **Dataset data.gouv.fr :** `561fa564c751df4f2acdbb48`
- **Producteur :** France Travail
- **Format :** XLSX annuels téléchargement direct (hébergés sur francetravail.org)
- **BMO 2025 :** `https://www.francetravail.org/files/live/sites/peorg/files/documents/Statistiques-et-analyses/Open-data/BMO/Base_open_data_BMO_2025.xlsx`
- **Historique :** millésimes 2015-2025 disponibles
- **Licence :** Licence Ouverte
- **Fréquence MAJ :** annuelle

### Contenu

Projets de recrutement par métier (nomenclature **FAP2021** — Familles Professionnelles) × **bassin d'emploi** (~400 zones), avec indicateur de **difficulté de recrutement** et projets saisonniers. Enquête auprès de ~2,4 millions d'établissements, ~446 000 réponses.

### Nomenclature FAP2021

La famille **M2Z = "Informatique et télécommunications"** couvre les profils IT. Les sous-familles (M2Z80 = ingénieurs informatiques ?, M2Z60 = techniciens ?) doivent être vérifiées par spike.

### Questions ouvertes (spike)

1. Quels codes FAP existent sous M2Z ? Distinguent-ils "data" de "dev" de "infra" ?
2. Format XLSX : un onglet par année ? Par bassin ? Colonnes ?
3. Volume filtré M2Z% : combien de lignes ? Seed-able (< 1000) ou script nécessaire ?
4. Mapping bassin d'emploi → département : table de correspondance disponible dans le fichier ?

### Valeur pour le projet

Contexte macro sur les tensions de recrutement IT par territoire. Ne résout pas le problème du n=20 offres data (structurel), mais cadre les offres France Travail dans un marché plus large : "dans le bassin d'emploi de Toulouse, X% des projets de recrutement IT sont jugés difficiles par les employeurs".

### Stratégie conditionnelle

- **Si spike valide :** script d'ingestion dans `ingestion/bmo/` (workflow classique GCS → BQ raw, quelle que soit la volumétrie)
- **Si spike ne valide pas** (granularité FAP insuffisante) : documenter et écarter

### Modèles dbt (si validé)

- **Staging :** `stg_bmo__projets_recrutement`
- **Intermediate :** `int_tensions_bassin_emploi` (filtré FAP M2Z%, mapping bassin → département)
- **Jointure aval :** `code_departement` → marts

### Décisions associées

- **D35 :** Source complémentaire retenue (P2, priorité élevée, conditionnelle)
- **~~D36~~** annulée — workflow classique d'ingestion pour toutes les sources
