# Gestion des doublons — Offres France Travail

**Projet :** DataTalent  
**Date :** 2026-03-13  
**Statut :** Décision à valider avant Bloc 2

---

## Contexte

Le pipeline ingère les offres France Travail via un cron hebdomadaire. Une offre publiée et toujours active la semaine suivante est ingérée deux fois, dans deux partitions `_ingestion_date` différentes. Sans traitement explicite, les marts comptent des offres en double — ce qui fausse directement la réponse à la question centrale du projet.

Ce problème ne concerne **que France Travail** :
- **Sirene** : WRITE_TRUNCATE mensuel sur stock complet — pas d'accumulation
- **API Géo** : données quasi-statiques, refresh sur événement politique uniquement

---

## Nature du problème

### Idempotence intra-journalière (couverte)

Ré-exécuter le script le même jour écrase le fichier GCS (même path daté) et recharge BigQuery en WRITE_TRUNCATE. Pas de doublon possible.

### Doublons inter-runs (non couverte)

| Run | Offre id=ABC | Partition |
|-----|-------------|-----------|
| Semaine 1 | ingérée | `_ingestion_date = 2026-03-01` |
| Semaine 2 | toujours active, ré-ingérée | `_ingestion_date = 2026-03-08` |

La table `raw.france_travail` contient deux lignes pour la même offre. Sans déduplication, chaque modèle dbt aval la compte deux fois.

---

## Alternatives évaluées

### Option 1 — Déduplication en staging (ROW_NUMBER) ✅ Retenue

```sql
-- models/staging/stg_france_travail__offres.sql
SELECT *
FROM {{ source('raw', 'france_travail') }}
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY _ingestion_date DESC
) = 1
```

**Principe :** le raw conserve l'historique complet. La déduplication se fait en staging en ne gardant que la version la plus récente de chaque offre.

| Critère | Évaluation |
|---------|-----------|
| Respect du pattern Medallion | ✅ Transformation dans dbt, pas dans l'ingestion |
| Historique raw préservé | ✅ |
| Simplicité | ✅ Une clause SQL |
| Impact sur le code Python existant | ✅ Aucun |
| Coût BigQuery | ✅ Free tier — scan de toutes les partitions staging, négligeable aux volumes du projet |
| Réversibilité | ✅ Changer la stratégie ne nécessite pas de re-ingérer |

---

### Option 2 — MERGE à l'ingestion Python (upsert)

Au lieu de WRITE_TRUNCATE, effectuer un MERGE BigQuery sur `id` : insert si nouvelle offre, update si existante.

| Critère | Évaluation |
|---------|-----------|
| Respect du pattern Medallion | ❌ Transformation dans l'ingestion |
| Historique raw préservé | ❌ Pas de traçabilité des re-vues d'offres |
| Simplicité | ❌ Complexifie le code Python |
| Impact sur le code Python existant | ❌ Refactoring `shared/bigquery.py` |
| Réversibilité | ⚠️ Historique perdu définitivement |

---

### Option 3 — Snapshot dbt (SCD Type 2)

`dbt snapshot` sur la table staging, avec `id` comme clé unique. Chaque offre obtient des colonnes `dbt_valid_from` / `dbt_valid_to` permettant de tracer sa durée de publication.

| Critère | Évaluation |
|---------|-----------|
| Valeur analytique | ✅ Durée de publication, offres retirées traçables |
| Complexité Bloc 2 | ❌ Scope élargi significatif |
| Périmètre brief | ⚠️ Probablement hors périmètre |
| Prérequis | ❌ Nécessite staging stable avant d'implémenter |

À reconsidérer en Bloc 3 si le taux de rotation des offres s'avère analytiquement pertinent.

---

## Décision retenue

**Option 1 — déduplication en staging par `ROW_NUMBER`.**

### Implémentation

La clause `QUALIFY` s'ajoute au modèle `stg_france_travail__offres.sql` lors de sa création en Bloc 2 :

```sql
SELECT
    id,
    intitule,
    dateCreation,
    entreprise.siret                        AS siret_entreprise,
    entreprise.nom                          AS nom_entreprise,
    lieuTravail.commune                     AS code_commune,
    lieuTravail.libelle                     AS lieu_travail_libelle,
    salaire.libelle                         AS salaire_libelle,
    typeContrat,
    experienceExige,
    _ingestion_date
FROM {{ source('raw', 'france_travail') }}
QUALIFY ROW_NUMBER() OVER (
    PARTITION BY id
    ORDER BY _ingestion_date DESC
) = 1
```

### Test dbt associé

```yaml
# models/staging/_france_travail__models.yml
models:
  - name: stg_france_travail__offres
    columns:
      - name: id
        tests:
          - unique
          - not_null
```

Le test `unique` sur `id` valide que la déduplication fonctionne à chaque `dbt test`.

---

## Ce qui reste hors périmètre

- **Offres retirées entre deux runs** : une offre présente en semaine 1 et absente en semaine 2 n'est pas marquée comme "expirée". Le staging garde sa dernière version connue. Acceptable pour les marts actuels (géo, sectoriel, temporel) — l'analyse porte sur les offres publiées, pas sur leur cycle de vie.
- **Matching par titre/description** : deux offres distinctes du même employeur avec des libellés similaires ne sont pas dédupliquées — elles ont des `id` différents, c'est le comportement attendu.
