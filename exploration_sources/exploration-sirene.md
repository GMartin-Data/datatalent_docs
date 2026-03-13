# Exploration des sources de données - Projet DataTalent

**Dernière mise à jour :** 2026-03-13

---

## Objectif du document

Ce document synthétise :

1. L'exploration des fichiers Sirene utilisés dans le projet.
2. Les choix d'implémentation retenus pour l'ingestion.
3. La logique actuelle du script d'ingestion branché sur GCS et BigQuery.
4. La distinction entre **exploration des données** et **ingestion technique**.

L'objectif est de conserver une base claire sur :

- les deux sources Sirene retenues ;
- leur intérêt dans le projet ;
- le fonctionnement réel du pipeline d'ingestion ;
- les responsabilités respectives de l'ingestion, du stockage raw et des futures couches de transformation.

---

## 1. Contexte général

Le projet exploite les fichiers mensuels **Sirene** publiés par l'Insee au format **Parquet**.

Deux ressources sont utilisées :

- **StockEtablissement**
- **StockUniteLegale**

Ces deux fichiers sont récupérés à partir des ressources officielles publiées sur data.gouv.

L'architecture retenue a évolué : l'ingestion n'est plus pensée comme une simple étape locale avec fichier brut puis fichier allégé. Elle est désormais alignée sur le pipeline projet :

- récupération des métadonnées du dataset ;
- identification des deux ressources suivies ;
- téléchargement local technique du fichier Parquet complet ;
- validation minimale du fichier téléchargé ;
- upload dans **Google Cloud Storage** ;
- chargement dans **BigQuery raw**.

Le filtrage de colonnes n'est **plus réalisé dans l'ingestion raw**.
Cette responsabilité est désormais reportée à la couche de transformation aval, notamment **dbt staging**.

---

## 2. Logique actuelle du code

### 2.1 Principe

Le code d'ingestion actuel fait les opérations suivantes :

1. Interroger les métadonnées du dataset Sirene.
2. Identifier les deux ressources suivies (`StockEtablissement` et `StockUniteLegale`).
3. Vérifier que la ressource est bien au format **Parquet**.
4. Télécharger le fichier complet.
5. Vérifier le fichier téléchargé via son **magic number Parquet** (`PAR1`).
6. Enregistrer temporairement ce fichier localement.
7. Uploader ce fichier dans **GCS**.
8. Charger le fichier GCS dans **BigQuery raw**.

### 2.2 Ce que le script fait

Le script :

- télécharge la dernière version disponible des deux ressources ;
- conserve le **Parquet complet** ;
- ne filtre aucune colonne ;
- utilise **httpx** pour les appels HTTP ;
- utilise **tenacity** pour les retries sur les appels réseau ;
- utilise `get_logger(__name__)` pour des logs structurés homogènes ;
- charge chaque ressource dans une table BigQuery dédiée.

### 2.3 Ce que le script ne fait pas

Le script **ne fait aucune transformation métier** sur les données.

Il ne :

- renomme pas les colonnes ;
- ne filtre pas les lignes ;
- ne modifie pas les valeurs ;
- ne nettoie pas les chaînes ;
- ne calcule pas de nouvelles colonnes ;
- ne réduit plus le nombre de colonnes ;
- ne construit pas encore les tables de staging ou de marts.

Autrement dit :

> **L'ingestion raw transporte désormais le fichier complet, sans logique de sélection métier.**

---

## 3. Arborescence actuelle du projet Sirene

```text
sirene/
├── __init__.py
├── config.py
├── ingest.py
└── data/
    └── raw/

tests/
└── test_sirene_ingestion.py
```

### 3.1 Rôle des fichiers

#### `sirene/config.py`

Contient :

- l'identifiant du dataset Sirene ;
- les paramètres techniques ;
- les identifiants des deux ressources suivies ;
- le préfixe de nommage local ;
- la table BigQuery cible pour chaque ressource.

#### `sirene/ingest.py`

Contient :

- la récupération des métadonnées ;
- la validation du format ;
- le téléchargement des fichiers ;
- la validation Parquet ;
- l'upload vers GCS ;
- le chargement dans BigQuery raw ;
- les logs structurés ;
- les retries sur les appels réseau.

#### `tests/test_sirene_ingestion.py`

Contient les tests unitaires exécutés avec `pytest` pour vérifier notamment :

- le parsing des dates ;
- le nommage des fichiers ;
- la validation du format attendu ;
- la validation du magic number Parquet ;
- les erreurs sur les métadonnées incomplètes ;
- l'orchestration de `process_one_resource()` sans appel réel au réseau, à GCS ou à BigQuery ;
- l'orchestration de la fonction `run()` sans dépendance externe.

---

## 4. Évolution de l'architecture

### 4.1 Ancienne logique

La première version du pipeline fonctionnait selon une logique locale :

- téléchargement du fichier brut ;
- stockage dans `raw/` ;
- sous-sélection de colonnes ;
- création d'un fichier `prepared/` allégé.

### 4.2 Nouvelle logique retenue

La logique actuelle est désormais :

- téléchargement du fichier complet ;
- validation du format Parquet ;
- upload du fichier vers GCS ;
- chargement du fichier dans BigQuery raw ;
- transformations reportées à la couche aval.

### 4.3 Conséquences

Cela implique les changements suivants :

- suppression du dossier `prepared/` ;
- suppression de la logique de sous-sélection de colonnes ;
- suppression de la logique locale d'allègement ;
- conservation des deux sources complètes ;
- `raw` = copie technique complète de la source ;
- `staging` = futur endroit du filtrage et de la standardisation.

---

## 5. B2 - Stock Sirene INSEE (Etablissements)

### 5.1 Accès

- **Source :** ressource Parquet officielle data.gouv / Insee
- **Téléchargement local temporaire :** `sirene/data/raw`
- **Format :** Parquet
- **Authentification source :** aucune
- **Fréquence de mise à jour théorique :** mensuelle
- **Destination GCS :** préfixe `sirene/`
- **Destination BigQuery :** `raw.sirene_etablissement`

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
|---|---:|
| Colonnes disponibles dans le fichier brut | 54 |
| Lignes explorées | 100 000 |

### 5.4 Interprétation

- La géographie française est bien couverte grâce à `codeCommuneEtablissement`, `libelleCommuneEtablissement` et `codePostalEtablissement`.
- Les identifiants `siret` et `siren` sont centraux pour les jointures.
- Les colonnes de nom d'usage au niveau établissement restent secondaires et servent surtout de fallback.
- Les coordonnées Lambert peuvent servir d'enrichissement cartographique.

### 5.5 Point d'architecture

Même si l'exploration a permis d'identifier les colonnes les plus utiles, elles ne sont plus filtrées au niveau `raw`.
Le fichier complet est désormais conservé tel quel dans le pipeline d'ingestion.

---

## 6. B2-bis - Stock Sirene INSEE (Unités légales)

### 6.1 Accès

- **Source :** ressource Parquet officielle data.gouv / Insee
- **Téléchargement local temporaire :** `sirene/data/raw`
- **Format :** Parquet
- **Authentification source :** aucune
- **Fréquence de mise à jour théorique :** mensuelle
- **Destination GCS :** préfixe `sirene/`
- **Destination BigQuery :** `raw.sirene_unite_legale`

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
|---|---:|
| Colonnes disponibles dans le fichier brut | 35 |
| Lignes explorées | 100 000 |

### 6.4 Interprétation

- `denominationUniteLegale` reste un très bon candidat pour représenter le nom de l'entreprise dans les couches aval.
- Les autres colonnes de nom restent utiles comme fallback.
- `categorieEntreprise` et `categorieJuridiqueUniteLegale` restent intéressantes pour les analyses futures.

### 6.5 Point d'architecture

Comme pour `StockEtablissement`, l'exploration a servi à comprendre la structure du fichier, mais aucune sous-sélection de colonnes n'est plus appliquée pendant l'ingestion `raw`.

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

### 7.4 Rôle actuel de ces constats

Ces constats restent utiles pour les futures couches :

- staging ;
- modélisation ;
- jointures ;
- enrichissements ;
- marts.

Ils n'ont simplement plus vocation à piloter une réduction de colonnes dans le `raw`.

---

## 8. Recommandations de pipeline

### 8.1 Ce que fait la couche actuelle

La couche actuelle produit :

- un téléchargement du Parquet complet ;
- une validation technique minimale ;
- un upload vers GCS ;
- un chargement dans BigQuery raw.

### 8.2 Ce que la couche actuelle ne fait pas encore

Les traitements suivants restent pour une étape ultérieure :

- filtrer uniquement les établissements actifs ;
- filtrer uniquement les unités légales actives ;
- construire les couches staging et marts ;
- enrichir avec France Travail ;
- enrichir avec API Géo ;
- standardiser les colonnes d'intérêt pour l'analyse.

### 8.3 Recommandation pour la suite

La suite logique du projet est désormais :

- stabiliser l'ingestion raw complète ;
- charger les deux sources dans BigQuery raw ;
- construire ensuite une couche staging avec les filtres métier ;
- appliquer les réductions de colonnes et normalisations dans dbt ;
- construire les tables analytiques aval.

---

## 9. Robustesse technique de l'ingestion

### 9.1 Client HTTP

Les téléchargements utilisent **httpx**, conformément à l'alignement souhaité dans le projet.

### 9.2 Retry

Les appels réseau critiques utilisent **tenacity** avec retry exponentiel.

### 9.3 Validation du fichier téléchargé

La validation du fichier téléchargé repose sur le magic number Parquet (`PAR1`), ce qui est plus robuste qu'une simple vérification de l'URL finale.

### 9.4 Logs

Les logs passent par `get_logger(__name__)`, ce qui homogénéise la journalisation avec le reste du projet et permet une bonne exploitation dans les environnements cloud.

### 9.5 Fraîcheur

Le contrôle bloquant de fraîcheur a été retiré dans l'implémentation retenue.
Le pipeline recharge la source disponible au moment de l'exécution, puis l'écrasement logique est géré par le flux GCS/BigQuery.

---

## 10. Tests

Le projet contient également un fichier de test :

- `tests/test_sirene_ingestion.py`

Ce fichier ne s'exécute jamais automatiquement lors du lancement de l'ingestion.

### 10.1 Exécution du script principal

Pour exécuter l'ingestion réelle :

```bash
python -m sirene.ingest
```

### 10.2 Exécution des tests

Pour lancer les tests :

```bash
pytest
```

Ou :

```bash
pytest tests/test_sirene_ingestion.py
```

### 10.3 Rôle des tests

Les tests servent à vérifier :

- le parsing des dates ;
- le nommage des fichiers ;
- la validation du format ;
- la validation du magic number Parquet ;
- les erreurs sur des métadonnées incomplètes ;
- l'orchestration de l'ingestion sans connexion réelle aux services externes.

Ils servent donc à sécuriser le code, pas à exécuter l'ingestion mensuelle réelle.

---

## 11. Synthèse finale

### 11.1 Ce que nous faisons aujourd'hui

Nous ingérons deux fichiers Sirene :

- `StockEtablissement`
- `StockUniteLegale`

Chaque exécution :

- télécharge la version source complète ;
- valide le fichier ;
- l'envoie dans GCS ;
- le charge dans BigQuery raw.

### 11.2 Ce que contient réellement la couche raw

La couche raw :

- conserve le format Parquet ;
- ne modifie pas les valeurs ;
- ne filtre pas les lignes ;
- ne filtre pas les colonnes ;
- reste au plus proche de la source publiée.

### 11.3 Décision de conception retenue

La logique actuelle est donc :

> **ingestion technique complète de la source, sans réduction de colonnes dans le raw**

Toute logique métier complémentaire sera gérée dans les étapes suivantes du pipeline, en particulier dans la couche de staging.
