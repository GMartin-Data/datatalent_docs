# User Stories — Projet DataTalent

**Projet :** Pipeline Data Engineer — Marché de l'emploi tech en France
**Dernière mise à jour :** 2026-03-09

---

## Principe de découpage

Les tâches sont découpées **un bloc d'avance, pas plus**. Les US du Bloc 1 (T0, US1-US4) ont leurs tâches détaillées ci-dessous. Les US des Blocs 2-3 (US5-US11) restent en attente de découpage — elles seront détaillées pendant les pauses inter-blocs, quand les données réelles permettent d'estimer correctement.

---

## T0 — Setup Bloc 1 (prérequis, bloquant)

Tâches d'amorçage qui conditionnent tout le reste. Rien ne démarre avant que T0 soit terminé.

#### Tâches
- [ ] **T0.1** Créer projet GCP, bucket GCS (`datatalent-raw`), 4 datasets BigQuery (raw, staging, intermediate, marts) — *Collègue 4, 0.5j*
- [ ] **T0.2** Écrire `ingestion/shared/` (gcs.py, bigquery.py, logging.py) — signatures figées, contrat d'interface — *Greg, 0.5j*
- [ ] **T0.3** Kickoff synchrone : présenter le contrat d'interface `shared/`, chaque collègue reformule comment il va l'appeler — *Tous, 20 min*
- [ ] **T0.4** Clone repo, `pre-commit install`, copie `.example` files — *Tous, 15 min*

* * *

> **Definition of Done**
- [ ] Projet GCP opérationnel, bucket et datasets créés
- [ ] `ingestion/shared/` mergé dans main avec 3 fonctions documentées
- [ ] Les 4 membres ont confirmé leur compréhension du contrat d'interface
- [ ] Environnement local fonctionnel pour chaque dev

---

## US1 — Cartographie des sources
**En tant que** Data Engineer, **je veux** documenter les 3 sources de données (format, volume, contraintes d'accès, champs de jointure) **afin de** valider la faisabilité technique avant de coder.

#### Tâches
- [ ] **T1.1** Documenter l'API France Travail : inscription, OAuth2, endpoints, schéma de réponse, rate limits — *Greg (intégré à US2)*
- [ ] **T1.2** Documenter le stock Sirene : URL data.gouv.fr, format Parquet, volume brut, champs disponibles — *Collègue 2 (intégré à US3)*
- [ ] **T1.3** Documenter l'API Géo : endpoints utiles, schéma de réponse, absence d'auth — *Collègue 3 (intégré à US4)*
- [ ] **T1.4** Identifier les champs de jointure (SIRET offres ↔ Sirene, code commune ↔ API Géo) — *Collègue 3, 0.5j (après fin US4)*
- [ ] **T1.5** Rédiger les limites de qualité connues (SIRET manquant, salaire rarement renseigné, etc.) — *Collègue 3, 0.5j (après fin US4)*

Note : T1.1 à T1.3 se font naturellement en explorant sa source. Les vraies tâches dédiées sont T1.4 et T1.5, assignées à Collègue 3 après avoir fini API Géo (~J2 après-midi).

* * *

> **Definition of Done**
- [ ] Fiche par source : format, volume estimé, fréquence MAJ, contraintes d'accès, qualité apparente
- [ ] Champs de jointure inter-sources identifiés et justifiés
- [ ] Limites de qualité documentées

---

## US2 — Ingestion France Travail
**En tant que** Data Engineer, **je veux** ingérer automatiquement les offres d'emploi Data Engineer depuis l'API France Travail **afin d'** alimenter la couche raw du data warehouse.

**Assigné à :** Greg (J1 après-midi → J5)

#### Tâches
- [ ] **T2.1** Créer un compte développeur France Travail et obtenir les credentials OAuth2 — *0.25j*
- [ ] **T2.2** Implémenter le client OAuth2 avec cache du token (expiration, refresh) — *0.5j*
- [ ] **T2.3** Confirmer les codes ROME pertinents pour "Data Engineer" (M1805, M1810, M1806, M1801 — voir D8) — *0.25j*
- [ ] **T2.4** Implémenter la pagination par département (101) avec backoff sur rate limit — *1j*
- [ ] **T2.5** Écrire le script d'ingestion : extraction → JSON → upload GCS via `shared/gcs.py` — *0.5j*
- [ ] **T2.6** Charger les données brutes de GCS vers BigQuery via `shared/bigquery.py` — *0.25j*
- [ ] **T2.7** Ajouter logging structuré (`shared/logging.py`), gestion d'erreurs, idempotence (clé de déduplication) — *0.5j*

* * *

> **Definition of Done**
- [ ] Authentification OAuth2 avec mise en cache du token
- [ ] Pagination sur les départements sans déclencher le rate limiting
- [ ] Script idempotent, gestion d'erreurs, logs d'exécution
- [ ] Données atterrissent dans GCS (raw) puis BigQuery (raw dataset)

---

## US3 — Ingestion Sirene
**En tant que** Data Engineer, **je veux** charger le stock Sirene complet dans le data warehouse **afin de** pouvoir enrichir les offres avec les informations entreprise.

**Assigné à :** Collègue 2 (J1 après-midi → J4)

#### Tâches
- [ ] **T3.1** Localiser les fichiers Parquet sur data.gouv.fr (StockEtablissement — pas StockUniteLegale, voir D11) — *0.25j*
- [ ] **T3.2** Explorer le schéma Parquet localement (pyarrow/pandas) : colonnes, types, volume — *0.5j*
- [ ] **T3.3** Implémenter le script : téléchargement Parquet complet → upload GCS via `shared/gcs.py` (pas de filtrage NAF — D11, chargement brut intégral) — *0.5j*
- [ ] **T3.4** Charger de GCS vers BigQuery raw via `shared/bigquery.py` — *0.5j*
- [ ] **T3.5** Ajouter logging structuré (`shared/logging.py`), gestion d'erreurs, idempotence — *0.5j*

Note : aucun filtrage NAF ni par statut dans l'ingestion. Le raw reçoit le stock brut intégral (D11). Le filtrage `etatAdministratifEtablissement = 'A'` et le masquage RGPD se font en dbt staging (Bloc 2).

* * *

> **Definition of Done**
- [ ] Fichier StockEtablissement Parquet téléchargé depuis data.gouv.fr
- [ ] Stock complet chargé dans GCS (raw) puis BigQuery (raw dataset) — pas de pré-filtrage
- [ ] Script idempotent, gestion d'erreurs, logs d'exécution

---

## US4 — Ingestion API Géo
**En tant que** Data Engineer, **je veux** charger le référentiel géographique **afin de** normaliser les données de localisation.

**Assigné à :** Collègue 3 (J1 après-midi → J2)

#### Tâches
- [ ] **T4.1** Identifier les endpoints utiles : /regions, /departements, /communes — *0.25j*
- [ ] **T4.2** Explorer les réponses : champs disponibles, format, volume (~35k communes) — *0.25j*
- [ ] **T4.3** Implémenter le script : 3 appels GET → JSON → upload GCS via `shared/gcs.py` — *0.5j*
- [ ] **T4.4** Charger dans BigQuery raw via `shared/bigquery.py` — *0.25j*
- [ ] **T4.5** Ajouter logging structuré (`shared/logging.py`), gestion d'erreurs, idempotence — *0.25j*

Après fin de US4 (~J2 après-midi) : Collègue 3 bascule sur T1.4 + T1.5 (cartographie transverse).

* * *

> **Definition of Done**
- [ ] Régions, départements et communes récupérés
- [ ] Snapshot complet stocké dans GCS (raw) puis BigQuery (raw dataset)
- [ ] Script idempotent, gestion d'erreurs, logs d'exécution

---

## Bascules post-tâche principale (Bloc 1)

| Qui | Bascule sur | À partir de |
|-----|-------------|-------------|
| Collègue 3 | T1.4 + T1.5 (cartographie transverse) | ~J2 après-midi |
| Collègue 4 | Paire avec Greg sur France Travail (US2) | ~J2 |
| Collègue 2 | Tests + aide intégration | ~J4 |

---

## US5 — Transformation staging
**En tant que** Data Engineer, **je veux** nettoyer et typer les données de chaque source dans une couche staging **afin de** garantir la qualité en aval.

#### Tâches
*À découper pendant la pause 1 — dépend de l'exploration des données réelles au Bloc 1.*

* * *

> **Definition of Done**
- [ ] Un modèle dbt staging par source (stg_france_travail, stg_sirene, stg_geo)
- [ ] Types corrigés, champs renommés, valeurs nulles traitées
- [ ] Tests dbt sur champs critiques (not_null, unique, accepted_values)
- [ ] Documentation dbt (description des modèles et colonnes)

---

## US6 — Transformation marts
**En tant que** Data Engineer, **je veux** produire des tables agrégées croisant offres, entreprises et géographie **afin de** répondre à la question "Où recrute-t-on, dans quelles entreprises, à quels salaires ?".

#### Tâches
*À découper pendant la pause 1 — dépend des modèles staging.*

* * *

> **Definition of Done**
- [ ] Couche intermediate : jointure offres ↔ Sirene (via SIRET)
- [ ] Marts thématiques : axe géographique, sectoriel, temporel
- [ ] Tests dbt sur les marts
- [ ] Le modèle final permet de répondre à la question centrale

---

## US7 — Infrastructure as Code
**En tant que** Data Engineer, **je veux** provisionner toute l'infrastructure GCP via Terraform **afin que** l'environnement soit reproductible et versionné.

#### Tâches
*À découper pendant la pause 1 — l'infra minimale (GCS + BigQuery) est créée manuellement au Bloc 1 (T0.1) puis codifiée.*

* * *

> **Definition of Done**
- [ ] Modules : GCS bucket, BigQuery datasets, Cloud Run, Cloud Scheduler, IAM, Secret Manager
- [ ] Aucune ressource créée manuellement
- [ ] Secrets non exposés dans le code
- [ ] Estimation des coûts documentée (Infracost ou estimateur GCP)

---

## US8 — Dashboard analytique
**En tant que** membre de l'équipe produit, **je veux** consulter un tableau de bord avec les axes géographique, sectoriel et temporel **afin de** produire mes rapports trimestriels.

#### Tâches
*À découper pendant la pause 2 — dépend des marts.*

* * *

> **Definition of Done**
- [ ] Dashboard connecté aux marts BigQuery
- [ ] Minimum 3 angles d'analyse : géo, secteur, temporel
- [ ] Accessible publiquement (lien dans le README)
- [ ] Répond visiblement à "Où, qui, à quel salaire ?"

---

## US9 — CI/CD
**En tant que** Data Engineer, **je veux** un pipeline CI/CD qui valide le code sur chaque PR et déploie sur main **afin de** garantir la qualité en continu.

#### Tâches
*À découper pendant la pause 2 — dépend de l'état du code et de l'infra après Bloc 2.*

* * *

> **Definition of Done**
- [ ] Lint Python (ruff) sur PR
- [ ] dbt compile + test sur PR
- [ ] Terraform validate/plan sur PR
- [ ] Déploiement automatique sur merge dans main
- [ ] Secrets GCP gérés via GitHub Actions secrets

---

## US10 — Documentation & démo
**En tant que** Data Engineer, **je veux** un README complet, un schéma d'architecture et un catalogue de données **afin de** rendre le projet maintenable et de réussir la soutenance.

#### Tâches
*Transverse — à alimenter progressivement sur les 3 blocs. Découpage formel pendant la pause 2.*

* * *

> **Definition of Done**
- [ ] README : description, architecture, choix cloud, instructions de déploiement, auteur
- [ ] Schéma d'architecture (image ou draw.io)
- [ ] Catalogue de données : descriptions tables, sources, fréquences MAJ, tags
- [ ] Lignage des données visible (dbt docs ou équivalent)
- [ ] Démo 5 min préparée (pipeline bout en bout)

---

## US11 — Dashboard de suivi des coûts cloud
**En tant que** formateur, **je veux** consulter un tableau de bord montrant le coût par service GCP, son évolution dans le temps et les alertes budget **afin de** vérifier que l'équipe maîtrise les coûts de son infrastructure.

**Assigné à :** Collègue 4 (Bloc 3 — voir D23)

#### Tâches
*À découper pendant la pause 2 — dépend de l'IaC et du billing export.*

* * *

> **Definition of Done**
- [ ] Billing export GCP activé et alimentant un dataset BigQuery
- [ ] Dashboard Looker Studio : coût par service, évolution temporelle, comparaison au budget
- [ ] Budget alerts configurés en Terraform (seuils 50%, 90%, 100%)
- [ ] Dashboard accessible publiquement (lien dans le README)
- [ ] Bonus : vue INFORMATION_SCHEMA (coût par requête BQ, octets scannés)
