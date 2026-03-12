# Exploration des sources de données - Projet DataTalent

**Dernière mise à jour :** 2026-03-12

---

## Objectif du document

Ce document synthétise :

1. L'exploration des fichiers Sirene utilisés dans le projet.
2. Les choix de colonnes retenues pour la suite du pipeline.
3. La logique de l'implémentation actuelle du script d'ingestion local.
4. La distinction entre données **brutes** et données **allégées**.

L'objectif est de conserver une base claire avant l'intégration future dans GCP, GCS et BigQuery.

---

## 1. Contexte général

Le projet exploite les fichiers mensuels **Sirene** publiés par l'Insee au format **Parquet**.

Deux ressources sont utilisées :

- **StockEtablissement**
- **StockUniteLegale**

Ces deux fichiers sont téléchargés localement chaque mois à partir des ressources officielles data.gouv, puis stockés dans le projet.

Le pipeline actuel reste volontairement **local** :

- téléchargement du dernier fichier mensuel disponible ;
- contrôle du format et de la fraîcheur de la ressource ;
- conservation d'un fichier **raw** complet ;
- production d'un fichier **prepared** allégé contenant uniquement les colonnes utiles au projet.

À ce stade, il n'y a **pas encore d'envoi vers GCP**.

---

## 2. Logique actuelle du code

### 2.1 Principe

Le code d'ingestion actuel fait **uniquement** les opérations suivantes :

1. Interroger les métadonnées du dataset Sirene.
2. Identifier les deux ressources suivies (`StockEtablissement` et `StockUniteLegale`).
3. Vérifier que la ressource est bien au format **Parquet**.
4. Vérifier que la version publiée est suffisamment récente.
5. Télécharger le fichier brut.
6. Enregistrer ce fichier dans le dossier `raw/`.
7. Relire ce fichier et **garder uniquement les colonnes sélectionnées**.
8. Réécrire un nouveau fichier Parquet allégé dans le dossier `prepared/`.

### 2.2 Ce que le script fait

Le script :

- télécharge la dernière version disponible des deux ressources ;
- conserve une version brute locale ;
- produit une version allégée en gardant uniquement les colonnes utiles ;
- supprime les anciennes versions locales du même type après succès ;
- conserve le format **Parquet** à chaque étape.

### 2.3 Ce que le script ne fait pas

Le script **ne fait aucune transformation métier** sur les données.

Il ne :

- renomme pas les colonnes ;
- ne filtre pas les lignes ;
- ne modifie pas les valeurs ;
- ne convertit pas les types métiers ;
- ne nettoie pas les chaînes ;
- ne calcule pas de nouvelles colonnes ;
- ne filtre pas encore les établissements actifs uniquement ;
- ne traite pas encore les règles de staging et marts.

Le seul traitement appliqué aux données est donc :

> **la suppression des colonnes non retenues**

---

## 3. Arborescence actuelle du projet Sirene

```text
sirene/
├── __init__.py
├── config.py
├── ingest.py
└── data/
    ├── raw/
    └── prepared/

tests/
└── test_sirene_ingestion.py
```
### 3.1 Rôle des fichiers

#### `sirene/config.py`

Contient :

- les identifiants des ressources Sirene ;
- les paramètres techniques ;
- la liste des colonnes à conserver pour chaque fichier.

#### `sirene/ingest.py`

Contient :

- le téléchargement ;
- la validation des ressources ;
- l'écriture des fichiers raw ;
- la création des fichiers prepared allégés.

#### `tests/test_sirene_ingestion.py`
```
Contient les tests unitaires exécutés avec `pytest` pour vérifier notamment :

- le parsing de date ;
- le nommage des fichiers raw et prepared ;
- la validation du format attendu ;
- la validation de la fraîcheur de la ressource ;
- la sélection effective des colonnes existantes ;
- le fait qu'un parquet transformé ne contient bien que les colonnes attendues ;
- l'orchestration de la fonction `run()` sans appel réseau réel.

```

## 4. Différence entre raw et prepared

### 4.1 Raw

Le dossier `raw/` contient les fichiers tels qu'ils sont publiés, sans suppression de colonnes.

Exemples :

- `StockEtablissement_2026-03.parquet`
- `StockUniteLegale_2026-03.parquet`

### 4.2 Prepared

Le dossier `prepared/` contient une version allégée, obtenue en gardant uniquement les colonnes utiles au projet.

Exemples :

- `StockEtablissement_2026-03_light.parquet`
- `StockUniteLegale_2026-03_light.parquet`

### 4.3 Pourquoi garder les deux

Cette séparation permet de :

- conserver une copie brute traçable ;
- comparer facilement brut et allégé ;
- revoir plus tard la sélection de colonnes si nécessaire ;
- préparer plus proprement l'étape future vers GCP et BigQuery.

---

## 5. B2 - Stock Sirene INSEE (Etablissements)

### 5.1 Accès

- **Source :** fichier Parquet Sirene téléchargé localement
- **Dossier raw :** `sirene/data/raw`
- **Dossier prepared :** `sirene/data/prepared`
- **Fichier brut de référence :** `sirene/data/raw/StockEtablissement_2026-03.parquet`
- **Fichier allégé de référence :** `sirene/data/prepared/StockEtablissement_2026-03_light.parquet`
- **Format :** Parquet
- **Authentification :** aucune
- **Fréquence de mise à jour théorique :** mensuelle

### 5.2 Objectif dans le projet

Le fichier `StockEtablissement` sert à décrire les sites physiques des entreprises.

Dans le projet DataTalent, il est utilisé pour :

- localiser les recruteurs potentiels à l'échelle la plus fine disponible ;
- récupérer les identifiants SIRET et SIREN ;
- enrichir les offres France Travail avec une géographie normalisée ;
- rattacher les offres à une activité économique et à des caractéristiques d'employeur ;
- préparer la jointure avec l'API Géo via le code commune.

### 5.3 Couverture de l'exploration

L'exploration initiale a été réalisée sur un échantillon limité à 100 000 lignes afin de garder un notebook fluide.

| Indicateur | Valeur |
|---|---|
| Colonnes disponibles dans le fichier brut | 54 |
| Colonnes retenues dans la version allégée | 27 |
| Lignes explorées | 100 000 |

### 5.4 Colonnes retenues dans la version allégée

| Colonne | Usage projet |
|---|---|
| siren | Jointure avec StockUniteLegale |
| nic | Identifiant interne d'établissement |
| siret | Clé établissement, jointure potentielle avec France Travail |
| dateCreationEtablissement | Temporalité et ancienneté |
| trancheEffectifsEtablissement | Taille de structure |
| anneeEffectifsEtablissement | Contexte de l'effectif |
| etablissementSiege | Distinction siège et non-siège |
| numeroVoieEtablissement | Reconstruction d'adresse |
| typeVoieEtablissement | Reconstruction d'adresse |
| libelleVoieEtablissement | Reconstruction d'adresse |
| codePostalEtablissement | Géographie et fallback jointure |
| libelleCommuneEtablissement | Géographie lisible |
| codeCommuneEtablissement | Jointure principale API Géo |
| dateDebut | Temporalité administrative |
| etatAdministratifEtablissement | Filtre actif et fermé |
| enseigne1Etablissement | Nom d'usage et matching souple |
| denominationUsuelleEtablissement | Nom d'usage et matching souple |
| activitePrincipaleEtablissement | Secteur d'activité |
| nomenclatureActivitePrincipaleEtablissement | Référentiel activité |
| caractereEmployeurEtablissement | Filtre employeur |
| activitePrincipaleNAF25Etablissement | Regroupement activité |
| statutDiffusionEtablissement | Qualité et diffusion |
| dateDernierTraitementEtablissement | Fraîcheur technique |
| nombrePeriodesEtablissement | Complexité historique |
| identifiantAdresseEtablissement | Normalisation adresse |
| coordonneeLambertAbscisseEtablissement | Géolocalisation |
| coordonneeLambertOrdonneeEtablissement | Géolocalisation |

### 5.5 Colonnes volontairement exclues

| Colonne | Motif |
|---|---|
| complementAdresseEtablissement | Très peu rempli, faible utilité en V1 |
| codePaysEtrangerEtablissement | Quasi inutile pour le projet |
| libellePaysEtrangerEtablissement | Quasi inutile pour le projet |

### 5.6 Interprétation

- La géographie française est bien couverte grâce à `codeCommuneEtablissement`, `libelleCommuneEtablissement` et `codePostalEtablissement`.
- Les identifiants `siret` et `siren` sont centraux pour les jointures.
- Les colonnes de nom d'usage au niveau établissement restent secondaires et servent surtout de fallback.
- Les coordonnées Lambert sont conservées comme enrichissement cartographique potentiel.

---

## 6. B2-bis - Stock Sirene INSEE (Unités légales)

### 6.1 Accès

- **Source :** fichier Parquet Sirene téléchargé localement
- **Dossier raw :** `sirene/data/raw`
- **Dossier prepared :** `sirene/data/prepared`
- **Fichier brut de référence :** `sirene/data/raw/StockUniteLegale_2026-03.parquet`
- **Fichier allégé de référence :** `sirene/data/prepared/StockUniteLegale_2026-03_light.parquet`
- **Format :** Parquet
- **Authentification :** aucune
- **Fréquence de mise à jour théorique :** mensuelle

### 6.2 Objectif dans le projet

Le fichier `StockUniteLegale` décrit l'entreprise au sens administratif.

Dans le projet DataTalent, il sert à :

- récupérer les noms d'entreprise les plus fiables ;
- décrire la structure juridique et la catégorie d'entreprise ;
- analyser les recruteurs à l'échelle entreprise ;
- compléter les établissements via la jointure sur SIREN ;
- fournir un meilleur support au matching avec France Travail quand le SIRET est absent.

### 6.3 Couverture de l'exploration

L'exploration initiale a également été réalisée sur un échantillon de 100 000 lignes.

| Indicateur | Valeur |
|---|---|
| Colonnes disponibles dans le fichier brut | 35 |
| Colonnes retenues dans la version allégée | 22 |
| Lignes explorées | 100 000 |

### 6.4 Colonnes retenues dans la version allégée

| Colonne | Usage projet |
|---|---|
| siren | Jointure avec StockEtablissement |
| dateCreationUniteLegale | Temporalité |
| trancheEffectifsUniteLegale | Taille d'entreprise |
| anneeEffectifsUniteLegale | Contexte effectifs |
| categorieEntreprise | Segmentation entreprise |
| anneeCategorieEntreprise | Contexte catégorie |
| dateDebut | Temporalité administrative |
| etatAdministratifUniteLegale | Filtre actif et cessé |
| nomUniteLegale | Nom de personne et structure |
| nomUsageUniteLegale | Nom d'usage |
| denominationUniteLegale | Nom principal recommandé |
| denominationUsuelle1UniteLegale | Nom d'usage complémentaire |
| sigleUniteLegale | Abréviation |
| categorieJuridiqueUniteLegale | Type de structure |
| activitePrincipaleUniteLegale | Secteur d'activité |
| nomenclatureActivitePrincipaleUniteLegale | Référentiel activité |
| nicSiegeUniteLegale | Référence siège |
| activitePrincipaleNAF25UniteLegale | Regroupement activité |
| statutDiffusionUniteLegale | Qualité et diffusion |
| dateDernierTraitementUniteLegale | Fraîcheur technique |
| nombrePeriodesUniteLegale | Complexité historique |
| economieSocialeSolidaireUniteLegale | Enrichissement analytique |

### 6.5 Colonnes volontairement exclues

| Colonne | Motif |
|---|---|
| caractereEmployeurUniteLegale | Inexploitable dans l'exploration |
| societeMissionUniteLegale | Quasi inutile pour la V1 |
| identifiantAssociationUniteLegale | Quasi inutile pour la V1 |

### 6.6 Interprétation

- `denominationUniteLegale` reste le meilleur candidat pour représenter le nom de l'entreprise dans le pipeline.
- Les autres colonnes de nom sont conservées comme fallback, pas comme source principale.
- `categorieEntreprise` et `categorieJuridiqueUniteLegale` restent utiles pour les analyses futures.

---

## 7. Rappel sur l'exploration initiale

L'exploration a servi à :

- identifier les colonnes utiles pour la suite du projet ;
- distinguer les colonnes centrales des colonnes secondaires ;
- repérer les colonnes trop vides ou peu utiles ;
- confirmer les clés de jointure principales.

Les constats majeurs issus de l'exploration sont les suivants.

### 7.1 Clés de jointure

| Usage | Colonne recommandée |
|---|---|
| Jointure établissement et unité légale | `siren` |
| Jointure idéale avec France Travail | `siret` |
| Jointure avec API Géo | `codeCommuneEtablissement` |

### 7.2 Noms à utiliser

| Usage | Colonne recommandée |
|---|---|
| Nom entreprise principal | `denominationUniteLegale` |
| Nom établissement secondaire | `enseigne1Etablissement` ou `denominationUsuelleEtablissement` |

### 7.3 Activité

| Usage | Colonne recommandée |
|---|---|
| Activité entreprise | `activitePrincipaleUniteLegale` |
| Activité établissement | `activitePrincipaleEtablissement` |

---

## 8. Recommandations de pipeline

### 8.1 Ce que fait la couche actuelle

La couche actuelle produit :

- un raw complet ;
- un prepared allégé par sous-sélection de colonnes.

### 8.2 Ce que la couche actuelle ne fait pas encore

Les traitements suivants restent pour une étape ultérieure :

- filtrer uniquement les établissements actifs ;
- filtrer uniquement les unités légales actives ;
- gérer les couches staging et marts ;
- enrichir avec France Travail ;
- enrichir avec API Géo ;
- envoyer les données vers GCS puis BigQuery.

### 8.3 Recommandation pour la suite

La suite logique du projet sera :

1. finaliser et stabiliser la couche locale raw et prepared ;
2. envoyer les fichiers prepared vers GCS ;
3. charger ces fichiers dans BigQuery ;
4. construire ensuite une couche staging avec les filtres métier.

---

## 9. Tests

Le projet contient également un fichier de test :

- `tests/test_ingest.py`

Ce fichier ne s'exécute jamais automatiquement lors du lancement de l'ingestion.

### 9.1 Exécution du script principal

Pour exécuter l'ingestion réelle :

```bash
python -m sirene.ingest
```

### 9.2 Exécution des tests

Pour lancer les te#sts :

```bash
pytest
```

ou :

```bash
pytest tests/test_sirene_ingestion.py
```

### 9.3 Rôle des tests

Les tests servent à vérifier :

- le parsing des dates ;
- le nommage des fichiers ;
- la sélection correcte des colonnes ;
- la création d'un parquet allégé avec uniquement les colonnes demandées.

Ils servent donc à sécuriser le code, pas à exécuter l'ingestion mensuelle.

---

## 10. Synthèse finale

### 10.1 Ce que nous faisons aujourd'hui

Nous téléchargeons mensuellement deux fichiers Sirene :

- `StockEtablissement`
- `StockUniteLegale`

Puis nous produisons pour chacun :

- une copie brute (`raw`) ;
- une copie allégée (`prepared`).

### 10.2 Ce que contient réellement la couche prepared

La couche prepared :

- conserve le format Parquet ;
- ne modifie pas les valeurs ;
- ne filtre pas encore les lignes ;
- ne garde que les colonnes jugées utiles à partir de l'exploration.

### 10.3 Décision de conception retenue

La logique actuelle est donc :

> **ingestion locale + réduction de colonnes uniquement**

Toute logique métier complémentaire sera gérée dans une étape suivante du pipeline.
