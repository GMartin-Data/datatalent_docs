# Exploration MCP data.gouv.fr — Résultats

> **Projet :** DataTalent — "Où recrute-t-on des Data Engineers en France, dans quelles entreprises et à quels salaires ?"
> **Date :** 25 mars 2026
> **Outil :** MCP `mcp.data.gouv.fr/mcp` (tools : `search_datasets`, `search_dataservices`, `get_dataset_info`, `list_dataset_resources`, `get_resource_info`, `query_resource_data`)

---

## Tableau récapitulatif

| # | Source | Producteur | Valeur | Granularité clé | Tabular API | Action recommandée |
|---|--------|-----------|--------|----------------|-------------|-------------------|
| 1 | URSSAF — Étab. & effectifs commune × APE | URSSAF | **Élevée** | NAF5 × commune, annuel depuis 2006 | Non (API Opendatasoft) | **Ingérer** |
| 2 | BMO — Besoins en Main d'Œuvre | France Travail | **Élevée** | FAP2021 métier × bassin emploi × difficulté | Non (XLSX externe) | **Spike approfondi** |
| 3 | Sirene — StockEtablissement | INSEE | **Critique** | SIRET, NAF5, commune, effectifs, coords Lambert | Non (2 Go Parquet) | **Ingérer** (déjà prévu) |
| 4 | URSSAF — Masse salariale France × NA88 | URSSAF | **Moyenne** | NA88 (code 62) × France entière, annuel depuis 1998 | Non (API Opendatasoft) | **Ingérer** (effort faible) |
| 5 | API Marché du travail | France Travail | **Moyenne** | Tensions par métier × territoire | N/A (API REST) | **Spike** |
| 6 | BTS INSEE — Salaires secteur privé par CSP | INSEE | **Faible** | NAF A17 (`J` = Info & Com) | Non (Melodi) | **Écarter** |
| 7 | APEC — Rémunération des cadres | APEC | **Nulle via MCP** | Agrégé national, 1 onglet sur 37 lisible | Oui (1er onglet) | **Écarter** |
| 8 | DARES — Emplois vacants | DARES | **Faible** | Grand secteur, trimestriel | Non vérifié | **Écarter** |

**APIs projet confirmées (aucun changement d'URL) :**

| API | Base URL | Dataservice ID |
|-----|----------|---------------|
| Offres d'emploi France Travail | `https://francetravail.io/produits-partages/catalogue/offres-emploi` | `672cf68826b31834a945cefe` |
| Recherche d'Entreprises | `https://recherche-entreprises.api.gouv.fr` | `672cf684c3488a0c533f7094` |
| API Géo (Découpage Administratif) | `https://geo.api.gouv.fr` | `672cf6946a8456f417812b0f` |

---

## Détail par source

### 1. URSSAF — Établissements & effectifs par commune × APE

**Dataset ID :** `5efd242c72595ba1a48628f2`
**URL data.gouv.fr :** `https://www.data.gouv.fr/datasets/nombre-detablissements-employeurs-et-effectifs-salaries-du-secteur-prive-par-commune-x-ape-au-31-12-depuis-2006`
**Licence :** ODbL
**Fréquence MAJ :** annuelle (fin d'année + ~150 jours)
**Dernière MAJ :** 30 mai 2025

**Contenu :** nombre d'établissements employeurs + effectifs salariés en fin d'année, ventilés par commune × code APE (NAF rév.2 niveau 5 = 5 positions, ex: `62.01Z`). Secteur privé, régime général. Depuis 2006. Apprentis inclus à compter de juin 2023.

**Ressources :**
- CSV via API Opendatasoft : `https://open.urssaf.fr/api/explore/v2.1/catalog/datasets/etablissements-et-effectifs-salaries-au-niveau-commune-x-ape-last/exports/csv`
- JSON via API Opendatasoft : même URL avec `/exports/json`

**Accès données :** API REST Opendatasoft (filtrable par paramètres URL). Pas de Tabular API data.gouv.fr (hébergement externe).

**Valeur projet :** c'est la seule source identifiée croisant code NAF détaillé (6201Z programmation informatique) × géographie fine (commune). Répond directement à "dans quelles communes y a-t-il des entreprises du secteur programmation informatique et combien de salariés y emploient-elles". Source non prévue dans le plan initial.

**Action :** ingérer dans le pipeline. L'API Opendatasoft permet des requêtes filtrées sans téléchargement bulk — idéal pour ne récupérer que les codes APE pertinents (62.01Z, 62.02A, 62.09Z, etc.).

---

### 2. BMO — Besoins en Main d'Œuvre

**Dataset ID :** `561fa564c751df4f2acdbb48`
**URL data.gouv.fr :** `https://www.data.gouv.fr/datasets/enquete-besoins-en-main-doeuvre-bmo`
**Licence :** Licence Ouverte
**Fréquence MAJ :** annuelle
**Producteur :** France Travail

**Contenu :** projets de recrutement par métier (nomenclature FAP2021 — Familles Professionnelles) × bassin d'emploi, avec indicateur de difficulté de recrutement et projets saisonniers. Enquête auprès de ~2,4 millions d'établissements, ~446 000 réponses.

**Ressources :** XLSX annuels de 2015 à 2025. Hébergés sur `francetravail.org` (ex `pole-emploi.org`).
- BMO 2025 : `https://www.francetravail.org/.../Base_open_data_BMO_2025.xlsx`
- BMO 2024 : ZIP sur francetravail.org
- BMO 2015-2023 : ZIP sur pole-emploi.org

**Tabular API :** indisponible (fichiers externes).

**Valeur projet :** la FAP2021 contient la famille M2Z "Informatique et télécommunications" avec des sous-familles (ingénieurs informatiques, techniciens informatiques…). Couplé aux codes ROME, ça permet d'identifier les bassins d'emploi en tension sur les profils IT. Complémentaire de l'API France Travail (offres individuelles) — le BMO donne la vision employeur agrégée.

**Point à vérifier (spike) :** télécharger le XLSX 2025 localement, identifier les codes FAP exacts disponibles pour les métiers data/IT, évaluer si la granularité distingue "data engineer" de "développeur" de "administrateur infra". Si la FAP ne descend qu'à "ingénieurs informatiques" sans distinction data/dev, la valeur est réduite (mais reste intéressante pour l'indicateur de difficulté de recrutement par bassin).

---

### 3. Sirene — Base entreprises et établissements (INSEE)

**Dataset ID :** `5b7ffc618b4c4169d30727e0`
**URL data.gouv.fr :** `https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret`
**Licence :** Licence Ouverte v2
**Fréquence MAJ :** mensuelle
**Dernière MAJ :** 1er mars 2026

**Fichier cible :** `StockEtablissement_utf8.parquet` — **2,0 Go**
**URL directe :** `https://object.files.data.gouv.fr/data-pipeline-open/siren/stock/StockEtablissement_utf8.parquet`

**Schéma confirmé via Tabular API** (dessin de fichier, 54 colonnes). Colonnes clés pour le projet :

| Colonne | Description | Usage projet |
|---------|-------------|-------------|
| `siret` | Numéro SIRET (14 car.) | Clé de jointure principale |
| `siren` | Numéro SIREN (9 car.) | Jointure unité légale |
| `activitePrincipaleEtablissement` | Code APE/NAF rév.2 (6 pos.) | Filtre secteur (62.01Z etc.) |
| `activitePrincipaleNAF25Etablissement` | Code NAF2025 (nouveau) | **Anticipation transition NAF** |
| `trancheEffectifsEtablissement` | Tranche d'effectif salarié | Segmentation taille |
| `codeCommuneEtablissement` | Code commune (5 car.) | Jointure géo |
| `codePostalEtablissement` | Code postal | Géolocalisation |
| `etatAdministratifEtablissement` | Actif/Fermé | Filtre établissements actifs |
| `etablissementSiege` | Siège oui/non | Identification siège social |
| `coordonneeLambertAbscisse/OrdonneeEtablissement` | Coordonnées Lambert | Géolocalisation précise |
| `dateCreationEtablissement` | Date de création | Analyse ancienneté |

**Info importante — NAF 2025 :** à compter du 1er janvier 2027, les codes APE évoluent vers la nouvelle nomenclature NAF2025. Le futur code est déjà diffusé à titre informatif dans la colonne `activitePrincipaleNAF25Etablissement`. Le projet (certification avril 2027) couvre la période de transition — les codes NAF rév.2 actuels (6201Z) restent valides pendant la durée du projet mais la présence anticipée du NAF2025 est un bonus pour la pérennité.

**Autres fichiers disponibles :** StockUniteLegale (901 Mo ZIP / 650 Mo Parquet), StockEtablissementHistorique (1,1 Go ZIP / 803 Mo Parquet), StockDoublons, StockEtablissementLiensSuccession. Documentation PDF et CSV de dessin de fichier pour chaque stock.

**Action :** ingérer comme prévu. Aucune surprise dans le schéma, tout est conforme à l'architecture documentée dans `ingestion-sirene.md`.

---

### 4. URSSAF — Effectifs & masse salariale France × NA88

**Dataset ID :** `61d784a161825aaf438b8e9e`
**URL data.gouv.fr :** `https://www.data.gouv.fr/datasets/nombre-detablissements-employeurs-effectifs-salaries-et-masse-salariale-du-secteur-prive-france-entiere-x-na88i-et-par-an-depuis-1998`
**Licence :** ODbL
**Fréquence MAJ :** annuelle (fin d'année + ~250 jours)
**Dernière MAJ :** 17 septembre 2025

**Contenu :** nombre d'établissements, effectifs salariés moyens annuels, masse salariale annuelle, par secteur NA88 (avec distinction intérimaires), France entière, depuis 1998.

**Intérêt :** NA88 inclut le code `62` — "Programmation, conseil et autres activités informatiques". C'est plus fin que le NAF A17 (`J` = tout le secteur Information & Communication). En divisant masse salariale / effectifs, on obtient un **salaire brut moyen annuel estimé** pour le secteur programmation/conseil informatique au niveau France.

**Limites :** pas de croisement géographique (France entière uniquement), pas de ventilation par taille d'entreprise dans ce dataset. Le salaire estimé est un brut moyen toutes CSP confondues — pas un salaire "Data Engineer".

**Action :** ingérer. Effort faible (petite table de référence, quelques dizaines de lignes par an). Utile comme benchmark contextuel dans le dashboard : "salaire brut moyen dans le secteur programmation/conseil informatique = X €".

**Datasets URSSAF connexes identifiés (non inspectés en détail) :**
- Zone d'emploi × NA88 (effectifs, sans masse salariale) : `60c7eee1e8bdf319f12ee2c1`
- Département × grand secteur × tranche effectif (effectifs + masse salariale) : `60ecd87888636149e7decb05`
- Région × APE (effectifs) : `60c2a84c312afadc272fcb3b`

---

### 5. API Marché du travail (France Travail)

**Dataservice ID :** `672cf65f739fcf87e0f02be2`
**Base URL :** `https://francetravail.io/produits-partages/catalogue/marche-travail`

**Description :** données sur les tensions par métier et la dynamique de l'emploi par territoire. Tags : acoss, ccmsa, compétences, emploi, marché du travail.

**Valeur potentielle :** si l'API expose des indicateurs de tension par code ROME × territoire, c'est un complément direct du BMO sous forme d'API temps réel (vs fichier annuel). Permettrait d'enrichir les offres France Travail avec un indicateur de tension sur le métier/territoire.

**Action :** spike — consulter la documentation de l'API (via `get_dataservice_openapi_spec` ou directement sur francetravail.io) pour identifier les endpoints disponibles et vérifier si un filtre par code ROME data/IT est possible.

---

### 6. BTS INSEE — Salaires dans le secteur privé par CSP détaillée

**Dataset ID :** `67f85d13377ef83a019ac73f`
**Producteur :** INSEE (source : Base Tous Salariés)
**Licence :** Licence Ouverte v2
**Dernière MAJ :** 5 décembre 2025

**Contenu :** salaires nets en EQTP ventilés par CSP détaillée × secteur d'activité × sexe × tranche d'âge × temps de travail × taille d'entreprise. Secteur privé France hors Mayotte.

**Fichiers :** 2 CSV hébergés sur l'API Melodi INSEE (`api.insee.fr/melodi/file/DS_DERA_PRIVE_ANNUEL/...`). Format réel : **ZIP** contenant un CSV de données (~33 500 lignes) + un CSV de métadonnées (~415 lignes).

**Granularité NAF vérifiée : NAF A17 uniquement.** Les codes ACTIVITY sont des lettres (`J` = Information et communication, `K` = Activités financières, etc.) avec quelques éclatements A38 pour l'industrie manufacturière. Le code `J` ne distingue pas la programmation informatique des télécoms, des médias, ou de l'édition.

**Tabular API :** indisponible (fichiers sur api.insee.fr, pas sur data.gouv.fr).

**Concept Melodi (pour référence) :** Melodi est la plateforme de diffusion de l'INSEE qui expose les cubes statistiques via API REST conforme SDMX. Le dataflow `DS_DERA_PRIVE_ANNUEL` = "Description des emplois et rémunérations dans le secteur privé, données annuelles". Les fichiers `/file/` sont des dumps CSV complets ; l'endpoint `/data/` permet des requêtes filtrées sur les dimensions.

**Go/no-go : NO-GO.** La granularité NAF A17 est insuffisante pour un benchmark "Data Engineer". Le salaire moyen du secteur J mélange programmation informatique, télécoms, médias — information trop bruitée.

**Action :** écarter comme source d'ingestion. Éventuellement citable dans le dashboard final comme contexte ("salaire moyen secteur Information & Communication = X €"), mais pas intégré au pipeline.

---

### 7. APEC — Évolution de la rémunération des cadres

**Dataset ID :** `630c80c6c6a3d38c07048e02`
**Producteur :** APEC (Association Pour l'Emploi des Cadres)
**Dernière MAJ :** 29 août 2022 (données 2021)
**Licence :** non spécifiée

**Contenu :** enquête annuelle "Situation professionnelle et rémunération des cadres" (13 000 cadres du privé, redressée via DSN). XLSX de 101 Ko avec "37 onglets" selon le titre.

**Ce que la Tabular API montre (1er onglet uniquement, 239 lignes) :** pourcentages d'augmentation/stabilité/diminution de rémunération, ventilés par âge × sexe × responsabilité hiérarchique × dimension internationale. Séries 2007-2021. **Aucun niveau de salaire, aucune ventilation par fonction ni secteur.**

**Les 36 autres onglets sont inaccessibles via le MCP** (la Tabular API ne lit que le premier onglet d'un XLSX). Ils pourraient contenir des données par fonction ("informatique", "data"), mais ça nécessiterait un téléchargement local du XLSX.

**Autres datasets APEC sur data.gouv.fr :** Baromètre recrutement (intentions trimestrielles, pas de salaires), Perspectives emploi cadre (prévisions macro), Pratiques de recrutement / Sourcing (canaux). Éditions 2017, 2019, 2022 — rien de plus récent.

**Action :** écarter. Les études APEC détaillées par fonction (avec une catégorie "informatique") existent mais ne sont pas sur data.gouv.fr en données structurées. Si un benchmark cadres IT est nécessaire, chercher les PDF d'études sur apec.fr directement.

---

### 8. DARES — Emplois vacants

**Dataset ID :** `66df098824d76afbdd709389`
**Producteur :** DARES (statistiques Travail)
**Dernière MAJ :** 18 mars 2026
**Licence :** Licence Ouverte v2
**Fréquence :** trimestrielle

**Contenu :** taux d'emplois vacants, nombre d'emplois occupés, nombre d'emplois vacants. Par secteur d'activité. Source : enquête Acemo trimestrielle (entreprises ≥ 10 salariés).

**Valeur :** indicateur macro conjoncturel de tension sectorielle. Pas de granularité métier — uniquement par grand secteur. Utile pour dire "le secteur X a un taux d'emplois vacants de Y%" mais pas pour cibler "Data Engineer".

**Action :** écarter du pipeline. Éventuellement citable en contexte macro.

---

## Enseignements transversaux

### Sur le MCP data.gouv.fr

- **Tabular API :** ne fonctionne que sur les fichiers CSV ≤ 100 Mo / XLSX ≤ 12,5 Mo hébergés nativement sur `static.data.gouv.fr` ou `object.files.data.gouv.fr`. Les fichiers hébergés en externe (api.insee.fr, francetravail.org, open.urssaf.fr) ne sont pas interrogeables — seules les métadonnées sont accessibles.
- **XLSX multi-onglets :** la Tabular API ne lit que le premier onglet. Pour les fichiers APEC (37 onglets), c'est très limitant.
- **Excel "humain" :** les fichiers APEC sont formatés pour lecture humaine (en-têtes sur plusieurs lignes, colonnes sans noms, tables concaténées verticalement). La Tabular API les interprète mal.
- **Fiabilité :** erreurs intermittentes sur `get_dataset_info` et `list_dataset_resources` — nécessite parfois des retry.
- **Workflow optimal :** `search_datasets` → `get_dataset_info` → `list_dataset_resources` → `get_resource_info` (vérifier `tabular_api_available`) → `query_resource_data` si disponible.

### Sur les sources salariales

L'axe "à quels salaires" du projet ne peut pas reposer sur une source unique de données salariales ouvertes avec la granularité nécessaire (métier data × géographie × taille entreprise). Les sources existantes sont soit trop agrégées (BTS = NAF A17, URSSAF = NA88) soit inaccessibles en données structurées (études APEC).

**Stratégie recommandée :** le benchmark salarial repose principalement sur le **parsing des fourchettes salariales dans les offres France Travail et Adzuna**, complété par les données URSSAF (salaire brut moyen secteur 62) comme contexte macro. Ce n'est pas un défaut — c'est cohérent avec la question du projet qui porte sur les offres d'emploi.

### Découverte principale

Les datasets **URSSAF** (effectifs par commune × APE, masse salariale par NA88) n'étaient pas dans le plan initial et sont les sources complémentaires les plus intéressantes identifiées. Ils répondent directement à l'axe "où recrute-t-on" avec une granularité géographique fine couplée au code NAF détaillé — ce que ni la BTS, ni l'APEC, ni aucune autre source salariale ne fournit.

### NAF 2025

La nouvelle nomenclature NAF2025 entre en vigueur le 1er janvier 2027. Les futurs codes sont déjà diffusés dans Sirene (colonne `activitePrincipaleNAF25Etablissement`). Le projet (certification avril 2027) opère pendant la transition — les codes NAF rév.2 (6201Z) restent valides mais la prise en compte du NAF2025 est un bonus pour la pérennité.
