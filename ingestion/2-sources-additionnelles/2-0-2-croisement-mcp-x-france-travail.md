# Croisement — Exploration MCP data.gouv.fr × Exploration France Travail API

> **Date :** 25 mars 2026
> **Entrées :** `exploration-mcp-datagouv.md`, `exploration-axe1-volume-filtrage.md`, `exploration-axe2-taux-presence.md`, `exploration-axe3-distribution-geo.md`, `exploration-france-travail.ipynb`
> **Objectif :** identifier comment les sources data.gouv.fr découvertes compensent, enrichissent ou rendent caduques les constats de l'exploration France Travail.

---

## 1. Synthèse des impacts croisés

| Constat France Travail | Source data.gouv.fr | Impact |
|---|---|---|
| SIRET = 0%, jointure Sirene morte (D14-bis) | URSSAF commune × APE | **Compensation partielle** — enrichissement géo × secteur par une voie alternative |
| codeNAF présent à 47.8% mais biaisé intérim (38.3%) | URSSAF commune × APE | **Validation indépendante** — effectifs par NAF5 × commune sans biais intérim |
| 20 offres "data" sur 2589 IT (D8-bis) | BMO France Travail | **Contexte macro** — tensions recrutement IT par bassin d'emploi |
| Salaire parsable à 29.6% seulement | URSSAF masse salariale × NA88 | **Benchmark complémentaire** — salaire brut moyen secteur 62 comme référence |
| Distribution géo : 99/101 départements couverts | URSSAF commune × APE | **Enrichissement** — densité d'établissements IT par commune comme couche analytique |
| NAF 2025 en transition (Sirene) | N/A | **Anticipation** — aucun impact immédiat, colonne Sirene disponible |

---

## 2. Détail par axe

### 2.1 SIRET à 0% → URSSAF comme voie alternative d'enrichissement sectoriel

**Le problème (Axe 2, §2) :**
L'API France Travail ne fournit aucun SIRET. Zéro occurrence sur 2589 offres. La jointure Sirene prévue en D14 est caduque. Le matching par `entreprise.nom` (présent à 36.2%) a un ratio effort/valeur insuffisant : noms d'intérimaires dominants, casse incohérente, ambiguïtés.

Le `codeNAF` directement dans l'offre (47.8%) est la source primaire retenue (D14-bis), mais il est biaisé : 38.3% des offres avec NAF portent le code de l'intérimaire (78.20Z, 78.10Z), pas celui de l'employeur final.

**Ce qu'apporte l'URSSAF (commune × APE) :**
Le dataset URSSAF (`5efd242c72595ba1a48628f2`) donne le nombre d'établissements et d'effectifs salariés par **code APE détaillé (NAF5) × commune**, depuis 2006.

Concrètement, pour chaque commune présente dans les offres France Travail (92.7% ont un `lieuTravail.commune`), on peut récupérer :
- Combien d'établissements du secteur 62.01Z (programmation informatique) sont implantés dans cette commune
- Combien de salariés y travaillent dans ce secteur
- L'évolution annuelle de ces effectifs

**Ce n'est pas une jointure ligne-à-ligne** (on ne sait pas *quel* établissement a publié l'offre), mais c'est une **couche contextuelle** : "cette offre est localisée dans une commune qui compte X établissements de programmation informatique employant Y salariés". Ça compense partiellement l'absence de SIRET en ajoutant une dimension de densité sectorielle géographique.

**Impact architecture :**
- Modèle intermediate `int_densite_sectorielle_commune` : agrégation URSSAF par commune × codes APE IT (62.01Z, 62.02A, 62.03Z, 62.09Z)
- Jointure dans `int_offres_enrichies` sur `code_commune` → enrichissement contextuel, pas identifiant
- Dashboard : carte de chaleur "densité d'emploi IT par commune" superposable aux offres France Travail

**Priorité :** élevée. C'est la seule source qui compense l'absence de SIRET avec une granularité géographique fine.

---

### 2.2 Biais intérim du codeNAF → URSSAF comme contrepoint

**Le problème (Axe 2, §5.2) :**
Les deux premiers secteurs dans les offres France Travail avec NAF sont :
- 78.20Z (travail temporaire) : 319 offres (25.8% des offres avec NAF)
- 78.10Z (placement de main-d'œuvre) : 155 offres (12.5% des offres avec NAF)

Total intérim = 38.3%. Le `codeNAF` reflète le publieur de l'offre, pas l'employeur final. Hors intérim, le top est : 62.02A (conseil SI, 115), 70.22Z (conseil gestion, 100), 62.09Z (autres activités info, 43), 62.01Z (programmation, 34).

**Ce qu'apporte l'URSSAF :**
Les effectifs URSSAF par commune × APE reflètent les **établissements réels employeurs**, pas les intermédiaires de placement. Si une commune a 500 salariés en 62.01Z selon l'URSSAF mais que les offres France Travail y sont majoritairement publiées sous 78.20Z, le croisement révèle le biais d'intermédiation et offre une vue corrigée de la réalité sectorielle.

**Usage dashboard :** permettre un double filtre :
- "Secteur de l'offre" (codeNAF France Travail, avec flag `is_intermediaire`)
- "Densité employeurs IT" (URSSAF, sans biais intérim)

---

### 2.3 n=20 offres data → BMO comme contexte macro

**Le problème (Axe 1, D8-bis) :**
Le référentiel ROME ne distingue pas Data Engineer. Sur 2589 offres IT collectées via 4 codes ROME, seules 20 contiennent un intitulé "data" (6 data_engineer, 6 BI, 4 data_analyst, 3 data_architect, 1 ML engineer). Le dashboard opère donc sur les 2589 offres IT avec un filtre `categorie_metier`.

Même avec l'accumulation hebdomadaire (D19), on n'atteindra que ~200 offres data après 10 semaines — insuffisant pour des analyses géographiques fines.

**Ce qu'apporte le BMO (`561fa564c751df4f2acdbb48`) :**
L'enquête BMO mesure les **projets de recrutement** par métier (FAP2021) × bassin d'emploi, avec un indicateur de **difficulté de recrutement**. La famille FAP M2Z "Informatique et télécommunications" couvre les profils IT.

Le BMO ne résout pas le problème du n=20 (c'est un problème structurel du référentiel ROME), mais il apporte un **contexte macro** au dashboard :
- "Dans le bassin d'emploi de Toulouse, X% des projets de recrutement IT sont jugés difficiles"
- "Les bassins d'emploi avec le plus de projets de recrutement IT sont : ..."

C'est de l'information qui cadre les offres France Travail dans un contexte de marché plus large.

**Réserve :** la granularité FAP doit être vérifiée par spike (les sous-familles de M2Z distinguent-elles "ingénieurs informatiques" de "techniciens" ? Probablement oui. Distinguent-elles "data" de "dev" ? Probablement non).

**Priorité :** moyenne. Valeur réelle pour le dashboard, mais effort d'intégration non négligeable (XLSX annuel à parser, nomenclature FAP à mapper).

---

### 2.4 Salaire à 29.6% → URSSAF masse salariale comme benchmark

**Le constat (Axe 2, §3) :**
- `salaire.libelle` présent à 29.6% — 100% parsable mécaniquement (6 patterns réguliers)
- `salaire.commentaire` présent à 15.5% — texte libre, parsing non recommandé
- Au total : 40.4% des offres ont au moins une info salaire
- 59.6% n'ont aucune information salariale

Le parsing des fourchettes salariales est fiable mais ne couvre qu'un tiers des offres.

**Ce qu'apporte l'URSSAF masse salariale × NA88 (`61d784a161825aaf438b8e9e`) :**
Effectifs + masse salariale annuelle par secteur NA88 (code 62 = programmation/conseil informatique), France entière, depuis 1998. Division masse salariale / effectifs = **salaire brut moyen annuel estimé** pour le secteur.

**Usage :** benchmark de référence dans le dashboard. Quand l'utilisateur filtre les offres IT et voit les fourchettes salariales (disponibles sur ~30% des offres), le dashboard peut afficher en parallèle : "salaire brut moyen dans le secteur programmation/conseil informatique (source URSSAF) : X €/an". Ça ancre les fourchettes des offres dans un référentiel objectif.

**Limites :**
- France entière uniquement (pas de croisement géographique)
- NA88 code 62 mélange programmation, conseil, autres activités informatiques
- Salaire brut moyen toutes CSP (pas spécifique "cadre" ni "Data Engineer")
- Comparable aux offres seulement si celles-ci sont converties en brut annuel

**Priorité :** faible à moyenne. Effort d'intégration minimal (petite table de référence), mais valeur limitée à un point de comparaison contextuel.

---

### 2.5 Distribution géo × densité URSSAF

**Le constat (Axe 3) :**
La distribution géographique est exploitable : 99/101 départements couverts, concentration modérée (top 5 = 33.3%), IDF = 24.9%, trois quarts des offres IT en région. La stratégie d'extraction département (commune prioritaire, fallback libellé) donne 100% de couverture.

**Ce qu'apporte l'URSSAF commune × APE :**
Pour chaque département/commune où des offres France Travail sont localisées, l'URSSAF fournit le **tissu économique réel** du secteur IT : nombre d'établissements, effectifs salariés. Ça permet de calculer un **ratio offres / effectifs** :
- "Paris a 213 offres IT et X milliers de salariés IT → ratio Y offres pour 1000 salariés"
- "Loire-Atlantique a 135 offres IT et Z salariés IT → ratio plus élevé/faible que Paris"

Ce ratio est un indicateur de **dynamisme de recrutement** plus significatif que le nombre brut d'offres, qui reflète surtout la taille du bassin d'emploi.

**Impact dashboard :** carte choroplèthe à deux couches (offres France Travail + densité URSSAF) avec un indicateur dérivé "taux de tension" (offres/effectifs).

---

### 2.6 Sirene : maintenu mais repositionné

**Le constat croisé :**

L'exploration France Travail a tué la raison d'être initiale de Sirene dans le pipeline (jointure SIRET). L'exploration data.gouv.fr confirme que Sirene est intègre (schéma vérifié, 54 colonnes, MAJ mensuelle, Parquet 2 Go) mais son rôle opérationnel est désormais réduit.

**Rôle résiduel de Sirene dans le pipeline :**

1. **Livrable technique obligatoire** (brief) — ingestion + staging dbt sur source volumineuse
2. **Référentiel NAF** — table de correspondance codes NAF ↔ libellés, extraite de Sirene (même si le dashboard utilise `secteurActiviteLibelle` de France Travail en priorité)
3. **Validation croisée potentielle** — si un matching par nom est tenté en Bloc 3, Sirene reste la source de vérité

**Ce que Sirene ne fait plus :**
- Jointure SIRET avec les offres (impossible, 0% de SIRET)
- Source primaire d'enrichissement sectoriel (remplacé par codeNAF France Travail + URSSAF)

L'URSSAF commune × APE est fonctionnellement un **agrégat de Sirene** (les données URSSAF proviennent des déclarations d'établissements employeurs au registre), mais présenté dans un format directement exploitable pour le pipeline (effectifs agrégés par commune × NAF, pas 40M de lignes individuelles).

---

## 3. Décisions impactées

| Décision | Statut avant croisement | Impact du croisement |
|---|---|---|
| **D8-bis** — Garder 2589 offres IT | Confirmée | Renforcée : BMO + URSSAF donnent du contexte aux 2569 offres `autre_it` |
| **D14-bis** — Jointure SIRET abandonnée, codeNAF source primaire | Confirmée | Enrichie : URSSAF commune × APE = voie alternative sans SIRET |
| **D15** — Extraction département, fallback libellé | Confirmée | Élargie : le `code_commune` devient clé de jointure vers URSSAF en plus d'API Géo |
| **Sirene ingestion** | Maintenue (livrable brief) | Repositionnée : référentiel technique, plus source analytique centrale |

**Aucune décision existante n'est remise en cause.** Le croisement ajoute des sources complémentaires sans modifier l'architecture.

---

## 4. Nouvelles sources à intégrer au pipeline

Par ordre de priorité décroissante :

### P1 — URSSAF Établissements × effectifs commune × APE

| Attribut | Valeur |
|---|---|
| Dataset ID | `5efd242c72595ba1a48628f2` |
| Accès | API Opendatasoft (`open.urssaf.fr/api/explore/v2.1`) |
| Format | CSV/JSON filtrable par API |
| Modèle cible | `stg_urssaf__effectifs_commune_ape` → `int_densite_sectorielle_commune` |
| Jointure | `code_commune` × codes APE IT (62.01Z, 62.02A, 62.03Z, 62.09Z) |
| Fréquence ingestion | Annuelle (données au 31/12, disponibles ~mai N+1) |
| Bloc cible | Bloc 2 (ingestion + staging) |

### P2 — BMO France Travail

| Attribut | Valeur |
|---|---|
| Dataset ID | `561fa564c751df4f2acdbb48` |
| Accès | XLSX téléchargement direct (francetravail.org) |
| Modèle cible | `stg_bmo__projets_recrutement` → `int_tensions_bassin_emploi` |
| Jointure | Bassin d'emploi → département (mapping FAP/bassin nécessaire) |
| Spike préalable | Vérifier les codes FAP M2Z disponibles (granularité data vs dev vs infra) |
| Bloc cible | Bloc 2 (spike) → Bloc 3 (intégration si validé) |

### P3 — URSSAF Masse salariale × NA88

| Attribut | Valeur |
|---|---|
| Dataset ID | `61d784a161825aaf438b8e9e` |
| Accès | API Opendatasoft |
| Modèle cible | `stg_urssaf__masse_salariale_na88` (table de référence) |
| Usage | Benchmark contextuel : salaire brut moyen annuel secteur 62 |
| Bloc cible | Bloc 3 (effort faible, valeur cosmétique dashboard) |

---

## 5. Vue pipeline mise à jour

```
Sources primaires (déjà prévues)        Sources complémentaires (nouvelles)
─────────────────────────────────        ──────────────────────────────────
France Travail API (offres)              URSSAF commune × APE (effectifs)
Sirene (référentiel entreprises)         BMO (tensions recrutement)
API Géo (géographie)                     URSSAF masse salariale × NA88
                                         API Marché du travail FT (spike)

         ┌──────────────────────────────────────┐
         │            BigQuery raw               │
         └──────────────┬───────────────────────┘
                        │
         ┌──────────────▼───────────────────────┐
         │           dbt staging                 │
         │  stg_france_travail__offres           │
         │    → categorie_metier (D8-bis)        │
         │    → salaire_annuel_min/max           │
         │    → code_departement (100%)          │
         │    → code_naf + is_intermediaire       │
         │  stg_sirene__etablissements           │
         │  stg_geo__communes                    │
         │  stg_urssaf__effectifs_commune_ape    │  ← NOUVEAU
         │  stg_bmo__projets_recrutement         │  ← NOUVEAU (si spike ok)
         │  stg_urssaf__masse_salariale_na88     │  ← NOUVEAU
         └──────────────┬───────────────────────┘
                        │
         ┌──────────────▼───────────────────────┐
         │         dbt intermediate              │
         │  int_offres_enrichies                 │
         │    → jointure API Géo (noms dept/rég) │
         │    → PAS de jointure SIRET (D14-bis)  │
         │  int_densite_sectorielle_commune      │  ← NOUVEAU
         │    → URSSAF effectifs IT par commune  │
         │  int_tensions_bassin_emploi           │  ← NOUVEAU (si BMO validé)
         └──────────────┬───────────────────────┘
                        │
         ┌──────────────▼───────────────────────┐
         │            dbt marts                  │
         │  mart_offres (dashboard principal)    │
         │  mart_contexte_territorial            │  ← NOUVEAU
         │    → densité IT + tensions + salaire  │
         │      benchmark par zone               │
         └──────────────────────────────────────┘
```

---

## 6. Ce qui ne change pas

- **4 codes ROME** pour la collecte France Travail (M1801, M1805, M1806, M1810)
- **Classification `categorie_metier`** par regex sur titre (6 catégories + `autre_it`)
- **Parsing salaire** sur `salaire.libelle` (6 patterns, 29.6% couverture, 100% parsable)
- **Extraction géo** : `lieuTravail.commune` prioritaire, fallback regex sur `lieuTravail.libelle`
- **Sirene ingéré** comme livrable technique (staging dbt sur 40M lignes)
- **Accumulation hebdomadaire** (D19) avec déduplication ROW_NUMBER en staging
