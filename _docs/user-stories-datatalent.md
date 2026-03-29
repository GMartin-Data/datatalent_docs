# User Stories — Projet DataTalent

**Projet :** Pipeline Data Engineer — Marché de l'emploi tech en France
**Dernière mise à jour :** 2026-03-27 (US12 révisée — D36 annulée, toutes sources en workflow d'ingestion classique)

---

## Principe de découpage

Les tâches sont découpées **un bloc d'avance, pas plus**. Les US du Bloc 1 (T0, US1-US4) ont leurs tâches détaillées ci-dessous. Les US des Blocs 2-3 (US5-US12) sont partiellement précisées grâce aux findings de l'exploration France Travail (Axes 1-3) et de l'exploration MCP data.gouv.fr (D35) — le découpage fin se fera pendant les pauses inter-blocs.

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
**En tant que** Data Engineer, **je veux** documenter les sources de données (format, volume, contraintes d'accès, champs de jointure) **afin de** valider la faisabilité technique avant de coder.

> **Statut post-exploration :** 3 sources brief documentées (Bloc 1). 3 sources complémentaires identifiées via exploration MCP data.gouv.fr (D35). Jointures inter-sources révisées suite à l'exploration France Travail (D14-bis, D8-bis). Voir `exploration-sources.md` (B1-B7), `exploration-mcp-datagouv.md`, `croisement-mcp-x-france-travail.md`.

#### Tâches
- [x] **T1.1** Documenter l'API France Travail : inscription, OAuth2, endpoints, schéma de réponse, rate limits — *Greg (intégré à US2)*
- [x] **T1.2** Documenter le stock Sirene : URL data.gouv.fr, format Parquet, volume brut, champs disponibles — *Collègue 2 (intégré à US3)*
- [x] **T1.3** Documenter l'API Géo : endpoints utiles, schéma de réponse, absence d'auth — *Collègue 3 (intégré à US4)*
- [x] **T1.4** Identifier les champs de jointure — *Collègue 3, 0.5j* — **Révisé post-exploration :** jointure SIRET morte (D14-bis), jointure code_commune confirmée (92.7%, Axe 3), jointures contextuelles URSSAF/BMO documentées (B4)
- [x] **T1.5** Rédiger les limites de qualité — *Collègue 3, 0.5j* — **Complété par :** SIRET 0%, codeNAF 47.8% biaisé intérim, salaire 29.6% parsable, 20 offres data/2589 IT (Axes 1-3)
- [x] **T1.6** Explorer sources complémentaires via MCP data.gouv.fr — *Greg, pause inter-blocs* — URSSAF effectifs (B5), URSSAF masse salariale (B6), BMO (B7). Voir `exploration-mcp-datagouv.md`

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
**En tant que** Data Engineer, **je veux** charger le stock Sirene complet dans le data warehouse **afin de** démontrer dbt sur une source volumineuse et disposer d'un référentiel entreprises.

> **Statut post-exploration :** la jointure SIRET est morte (D14-bis — SIRET absent à 100% des offres). Sirene reste un livrable technique du brief mais ne contribue plus aux marts analytiques. Voir `croisement-mcp-x-france-travail.md` §2.6.

**Assigné à :** Collègue 2 (J1 après-midi → J4)

#### Tâches
- [ ] **T3.1** Localiser les fichiers Parquet sur data.gouv.fr : StockEtablissement + StockUniteLegale (D11) — *0.25j*
- [ ] **T3.2** Explorer le schéma Parquet localement (pyarrow/pandas) : colonnes, types, volume — *0.5j*
- [ ] **T3.3** Implémenter le script : téléchargement Parquet complet → upload GCS via `shared/gcs.py` (pas de filtrage NAF — D11, chargement brut intégral) — *0.5j*
- [ ] **T3.4** Charger de GCS vers BigQuery raw via `shared/bigquery.py` — *0.5j*
- [ ] **T3.5** Ajouter logging structuré (`shared/logging.py`), gestion d'erreurs, idempotence — *0.5j*

Note : aucun filtrage NAF ni par statut dans l'ingestion. Le raw reçoit le stock brut intégral (D11). Le filtrage `etatAdministratifEtablissement = 'A'` et le masquage RGPD se font en dbt staging (Bloc 2). StockUniteLegale ajouté pour `denominationUniteLegale` (référentiel noms).

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
*Précisées grâce aux explorations Axes 1-3 et MCP data.gouv.fr. Découpage fin à confirmer en début de Bloc 2.*

- [ ] **T5.1** `stg_france_travail__offres` : classification `categorie_metier` par regex titre (D8-bis), parsing `salaire.libelle` (6 patterns), extraction `code_departement` avec fallback regex (D15), colonnes `code_naf` + `is_intermediaire` (Axe 2 §5) — *1-1.5j*
- [ ] **T5.2** `stg_sirene__etablissements` : filtre actifs, masquage RGPD (`statutDiffusionEtablissement = 'P'`), SELECT colonnes utiles (~10 sur 54) — *0.5j*
- [ ] **T5.3** `stg_geo__communes`, `stg_geo__departements`, `stg_geo__regions` : renommage, typage, jointure interne code_departement → code_region si nécessaire — *0.5j*
- [ ] **T5.4** `stg_urssaf__effectifs_commune_ape` : renommage colonnes, typage, test not_null sur code_commune — *0.5j*
- [ ] **T5.5** Tests dbt : `not_null` et `unique` sur clés, `accepted_values` sur `categorie_metier` et `salaire_periodicite`, `relationships` entre code_commune offres → communes — *0.5j*
- [ ] **T5.6** Documentation dbt : description de chaque modèle et colonne dans `_*__models.yml` — *0.5j*

* * *

> **Definition of Done**
- [ ] Un modèle dbt staging par source : stg_france_travail, stg_sirene, stg_geo (×3), stg_urssaf
- [ ] Types corrigés, champs renommés, valeurs nulles traitées
- [ ] Classification `categorie_metier` fonctionnelle (6 catégories + `autre_it`)
- [ ] Parsing salaire fonctionnel (6 patterns, filtre aberrations > 10k€)
- [ ] Tests dbt sur champs critiques
- [ ] Documentation dbt (description des modèles et colonnes)

---

## US6 — Transformation intermediate et marts
**En tant que** Data Engineer, **je veux** produire des tables croisant les sources nettoyées **afin de** répondre à la question "Où recrute-t-on, dans quelles entreprises, à quels salaires ?".

> **Architecture révisée post-exploration :** la jointure Sirene est morte (D14-bis). L'intermediate repose sur API Géo (enrichissement géo) + URSSAF (densité sectorielle) + BMO conditionnel (tensions). Voir `couche-intermediate-datatalent.md` pour le détail SQL et les schémas de jointure.

#### Tâches
*Précisées grâce aux explorations. Découpage fin à confirmer en début de Bloc 2.*

- [ ] **T6.1** `int_offres_enrichies` : LEFT JOIN offres × API Géo communes sur `code_commune` — *0.5j*
- [ ] **T6.2** `int_densite_sectorielle_commune` : GROUP BY URSSAF effectifs IT par commune × année (4 codes APE agrégés) — *0.5j*
- [ ] **T6.3** `int_tensions_bassin_emploi` (conditionnel, si spike BMO validé) : filtre FAP M2Z%, mapping bassin → département — *0.5-1j*
- [ ] **T6.4** `mart_offres` : table principale dashboard, agrégats par geo/secteur/temps, filtre `categorie_metier` — *1j*
- [ ] **T6.5** `mart_contexte_territorial` : jointure densité URSSAF + tensions BMO + benchmark salaire masse salariale NA88 — *0.5j*
- [ ] **T6.6** Tests dbt sur intermediate et marts — *0.5j*

* * *

> **Definition of Done**
- [ ] `int_offres_enrichies` : chaque offre enrichie avec nom commune, département, région, population
- [ ] `int_densite_sectorielle_commune` : effectifs IT agrégés par commune
- [ ] Marts répondent aux 3 axes : géographique, sectoriel, temporel
- [ ] ~~Jointure Sirene~~ Remplacée par codeNAF offre + URSSAF (D14-bis)
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

---

## US12 — Ingestion sources complémentaires (D35)
**En tant que** Data Engineer, **je veux** ingérer les 3 sources complémentaires identifiées via l'exploration MCP data.gouv.fr **afin d'** enrichir le dashboard avec la densité sectorielle par commune, les tensions de recrutement et un benchmark salaire.

> **Voir :** `exploration-mcp-datagouv.md` (fiches détaillées), `croisement-mcp-x-france-travail.md` (impacts), prompt de transition `prompt-transition-ingestion-sources-complementaires.md`.

**Assigné à :** Greg (pause inter-blocs + Bloc 2)

#### Tâches — P3 : URSSAF masse salariale × NA88 (script ingestion, ~1h)
- [ ] **T12.1** Implémenter `ingestion/urssaf_masse_salariale/client.py` : requête API Opendatasoft filtrée NA88 = 62, pagination `limit`/`offset` — *30 min*
- [ ] **T12.2** Implémenter `ingestion/urssaf_masse_salariale/ingest.py` : extract → JSONL → `shared/gcs.py` → `shared/bigquery.py` — *15 min*
- [ ] **T12.3** `stg_urssaf__masse_salariale_na88` : renommage colonnes, typage, tests not_null + unique sur annee — *10 min*
- [ ] **T12.4** Validation : spot-check salaire brut moyen 2024 (masse/effectifs ≈ 55k€) — *5 min*

#### Tâches — P1 : URSSAF effectifs commune × APE (script ingestion, ~3-4h)
- [ ] **T12.5** Comprendre l'API Opendatasoft (`open.urssaf.fr`), paramètres de filtrage et pagination — *45 min*
- [ ] **T12.6** Implémenter `ingestion/urssaf_effectifs/client.py` : requête filtrée APE IT (D37), pagination `limit`/`offset` — *1h*
- [ ] **T12.7** Implémenter `ingestion/urssaf_effectifs/ingest.py` : extract → JSONL → `shared/gcs.py` → `shared/bigquery.py` — *30 min*
- [ ] **T12.8** `stg_urssaf__effectifs_commune_ape` : renommage, typage, test not_null — *30 min*
- [ ] **T12.9** `int_densite_sectorielle_commune` : GROUP BY commune × année — *30 min*
- [ ] **T12.10** Tests + validation (spot-check communes connues) — *30 min*

#### Tâches — P2 : BMO France Travail (spike, ~1h + intégration conditionnelle)
- [ ] **T12.11** Spike : télécharger XLSX 2025, identifier codes FAP sous M2Z, évaluer granularité data vs dev vs infra — *1h*
- [ ] **T12.12** Si validé : script ingestion dans `ingestion/bmo/` (workflow classique GCS → BQ raw) — *1h*
- [ ] **T12.13** Si validé : `stg_bmo__projets_recrutement` + `int_tensions_bassin_emploi` (mapping bassin → département) — *1h*
- [ ] **T12.14** Si spike négatif : documenter dans `exploration-sources.md` B7, passer — *15 min*

* * *

> **Definition of Done**
- [ ] P3 : table raw `urssaf_masse_salariale_na88` chargée (~30 lignes), `stg_urssaf__masse_salariale_na88` fonctionnel, tests dbt passent
- [ ] P1 : `stg_urssaf__effectifs_commune_ape` + `int_densite_sectorielle_commune` fonctionnels, tests dbt passent
- [ ] P2 : spike documenté. Si validé : staging + intermediate fonctionnels. Si non : documenté et classé.
- [ ] `main.py` mis à jour pour appeler `urssaf_masse_salariale.ingest.run()`, `urssaf_effectifs.ingest.run()` (et `bmo.ingest.run()` si applicable)
