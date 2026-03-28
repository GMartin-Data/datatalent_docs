# Exploration spike BMO — Findings détaillés

> **Projet :** DataTalent
> **Date :** 2026-03-28
> **Source :** `Base_open_data_BMO_2025.xlsx` téléchargé depuis francetravail.org
> **Outil :** openpyxl en Python, exécuté dans l'environnement Claude.ai
> **Résultat :** GO — source validée pour intégration

---

## 1. Structure du fichier XLSX

| Attribut | Valeur |
|---|---|
| Taille | ~quelques Mo |
| Onglets | 2 : `Description_des_variables` (métadonnées) + `BMO_2025_open_data` (données) |
| Format données | Long — 1 ligne = 1 bassin × 1 métier |
| Lignes (hors header) | 50 076 |
| En-têtes | Ligne 1, directement exploitables (pas de titre fusionné au-dessus) |

---

## 2. En-têtes exactes (BMO 2025)

```
annee, Code métier BMO, Nom métier BMO, Famille_met, Lbl_fam_met,
REG, NOM_REG, Dept, NomDept, BE25, NOMBE25, met, xmet, smet
```

### Comparaison avec le BMO 2019

| BMO 2019 | BMO 2025 | Changement |
|---|---|---|
| `Famille_metier` | `Famille_met` | Tronqué |
| `Libellé de famille de métier` | `Lbl_fam_met` | Raccourci agressif |
| `code métier BMO` | `Code métier BMO` | Majuscule initiale |
| `nom_metier BMO` | `Nom métier BMO` | Majuscule initiale |
| `BE19` | `BE25` | Suffixe année |
| `NOMBE19` | `NOMBE25` | Suffixe année |
| `Dept`, `NomDept`, `REG`, `NOM_REG` | Identiques | Pas de changement |
| `met`, `xmet`, `smet` | Identiques | Pas de changement |

La structure est identique, seuls certains labels ont changé. Le suffixe année sur les colonnes bassin (`BE25`, `NOMBE25`) se confirme.

---

## 3. Nomenclature FAP2021 — rupture majeure

### Familles de métier (BMO 2025)

Le BMO 2025 utilise la nomenclature FAP2021. Les familles ne sont plus des codes comme `M2Z` (Informatique et télécommunications). Elles sont remplacées par 8 lettres génériques :

| Code | Libellé | Nb métiers |
|---|---|---|
| A | Fonctions administratives | 9 |
| C | Fonctions d'encadrement | 54 |
| I | Ouvriers des secteurs de l'industrie | 37 |
| O | Ouvriers de la construction et du bâtiment | 18 |
| S | Fonctions sociales et médico-sociales | 14 |
| T | Autres techniciens et employés | 17 |
| V | Fonctions liées à la vente, au tourisme et aux services | 44 |
| Z | Autres métiers | 24 |
| **Total** | | **217 métiers** |

### Conséquence pour le filtrage IT

L'ancien filtre `Famille_metier = 'M2Z'` ne fonctionne plus. Les métiers IT sont dispersés dans les familles `A` (techniciens) et `C` (cadres). Le seul moyen de les identifier est par le **préfixe du code métier** : `M1X` (techniciens informatiques) et `M2X` (cadres informatiques).

---

## 4. Codes métier IT identifiés

6 codes, répartis dans 2 familles :

| Code | Intitulé | Famille | Nb lignes | En langage courant |
|---|---|---|---|---|
| `M1X80` | Techniciens d'étude et de développement en informatique | A | 228 | Développeurs (niveau technicien) |
| `M1X81` | Techniciens de production, exploitation, installation, maintenance, support et services aux utilisateurs en informatique | A | 276 | Ops, support, sysadmin (niveau technicien) |
| `M2X90` | Ingénieurs et cadres d'étude, recherche et développement en informatique et télécom | C | 207 | Développeurs, architectes (niveau ingénieur) |
| `M2X91` | Chefs de projet et directeurs de service informatique | C | 130 | Management IT |
| `M2X92` | Responsables et cadres de la production, de l'exploitation et de la maintenance informatique et télécom | C | 110 | Ops, infra (niveau cadre) |
| `M2X93` | Experts et consultants en systèmes d'information | C | 161 | Consultants SI, experts |
| **Total** | | | **1 112** | |

### Granularité data vs dev vs infra

Aucun code ne distingue "data engineer" de "développeur web" de "administrateur système". La granularité la plus fine est :
- Développement (M1X80, M2X90)
- Exploitation/maintenance (M1X81, M2X92)
- Management (M2X91)
- Conseil/expertise (M2X93)

C'est suffisant pour l'objectif du projet : fournir un indicateur de **tension IT globale** par département, pas une analyse par sous-spécialité.

---

## 5. Secret statistique (valeurs `*`)

France Travail masque les chiffres en dessous d'un seuil de diffusion avec un `*` pour protéger la confidentialité des entreprises dans les petits bassins.

| Champ | Lignes masquées (`*`) | % sur 1 112 lignes IT | Impact |
|---|---|---|---|
| `met` (projets recrutement) | 415 | 37.3% | Petits bassins ruraux — les grands bassins sont exploitables |
| `xmet` (projets difficiles) | 641 | 57.6% | Sous-ensemble de `met`, seuil atteint plus vite |
| `smet` (projets saisonniers) | 1 056 | 95.0% | Quasi inexploitable — l'IT a très peu de postes saisonniers |

**Lignes exploitables** (met ≠ `*`) : **697 / 1 112** (62.7%). Ce sont les bassins d'emploi significatifs pour l'IT. Les données masquées concernent les bassins ruraux avec quelques projets IT.

**Traitement recommandé :** `*` → `null` dans le JSONL (pas `0`, qui fausserait les agrégats). Le champ `smet` est conservé par exhaustivité mais sa valeur analytique est quasi nulle pour le périmètre IT.

---

## 6. Département — présent dans les données

Les colonnes `Dept` (code) et `NomDept` (libellé) sont directement dans chaque ligne du BMO. Le "problème de mapping bassin → département" identifié dans le doc cadre initial **n'existe pas**.

Un bassin d'emploi peut couvrir plusieurs départements. Dans ce cas, le bassin apparaît sur plusieurs lignes avec des départements différents. La donnée est déjà dupliquée par département à la source.

---

## 7. Top 15 départements — projets de recrutement IT

Agrégat sur les lignes exploitables (met ≠ `*`), tous codes IT confondus :

| Dept | Nom | Projets recrutement IT | Projets difficiles | Taux difficulté |
|---|---|---|---|---|
| 75 | Paris | 10 654 | 5 932 | 55.7% |
| 92 | Hauts-de-Seine | 10 445 | 6 304 | 60.4% |
| 69 | Rhône | 3 387 | 2 173 | 64.2% |
| 59 | Nord | 3 250 | 1 452 | 44.7% |
| 31 | Haute-Garonne | 3 036 | 1 776 | 58.5% |
| 44 | Loire-Atlantique | 2 485 | 1 119 | 45.0% |
| 13 | Bouches-du-Rhône | 2 221 | 1 266 | 57.0% |
| 94 | Val-de-Marne | 1 728 | 745 | 43.1% |
| 35 | Ille-et-Vilaine | 1 543 | 684 | 44.3% |
| 93 | Seine-Saint-Denis | 1 485 | 650 | 43.8% |
| 78 | Yvelines | 1 420 | 556 | 39.2% |
| 06 | Alpes-Maritimes | 1 405 | 737 | 52.5% |
| 34 | Hérault | 1 377 | 514 | 37.3% |
| 33 | Gironde | 1 367 | 822 | 60.1% |
| 67 | Bas-Rhin | 1 123 | 717 | 63.8% |

Les résultats sont cohérents avec la géographie connue de l'emploi IT en France : domination Île-de-France (Paris + Hauts-de-Seine = ~21 000 projets), suivie des métropoles régionales (Lyon, Lille, Toulouse, Nantes, Marseille). Le taux de difficulté varie de 37% (Hérault) à 64% (Rhône, Bas-Rhin).

---

## 8. Exemples de lignes brutes

```
annee=2025 | Code métier BMO=M1X80 | Nom métier BMO=Techniciens d'étude et de développement en informatique
Famille_met=A | Lbl_fam_met=Fonctions administratives
REG=01 | NOM_REG=Guadeloupe | Dept=971 | NomDept=Guadeloupe
BE25=101 | NOMBE25=BASSIN BASSE-TERRE
met=227 | xmet=80 | smet=128

annee=2025 | Code métier BMO=M2X90 | Nom métier BMO=Ingénieurs et cadres d'étude, recherche et développement en informatique et télécom
Famille_met=C | Lbl_fam_met=Fonctions d'encadrement
REG=11 | NOM_REG=Ile-de-France | Dept=75 | NomDept=Paris
BE25=5001 | NOMBE25=T1 Paris
met=2824 | xmet=1158 | smet=11

annee=2025 | Code métier BMO=M2X93 | Nom métier BMO=Experts et consultants en systèmes d'information
Famille_met=C | Lbl_fam_met=Fonctions d'encadrement
REG=84 | NOM_REG=Auvergne-Rhone-Alpes | Dept=69 | NomDept=Rhône
BE25=8201 | NOMBE25=LYON
met=526 | xmet=371 | smet=*
```

---

## 9. Verdict

**GO — source intégrée au pipeline.**

| Critère | Résultat |
|---|---|
| Format exploitable | ✅ En-têtes en ligne 1, format long, openpyxl suffit |
| Département disponible | ✅ Colonnes `Dept` et `NomDept` présentes |
| Codes IT identifiables | ✅ 6 codes par préfixe `M1X`/`M2X` |
| Volume gérable | ✅ 1 112 lignes filtrées |
| Données exploitables | ✅ 697 lignes avec `met` non masqué |
| Cohérence métier | ✅ Top départements plausibles, taux de difficulté 37–64% |
| Distinction data/dev/infra | ❌ Non — mais acceptable pour un indicateur de tension IT globale |
