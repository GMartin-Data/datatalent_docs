# Notes Projet — Pipeline Data Engineer (Brief DataTalent)

**Créé le :** 2025-03-08
**Dernière mise à jour :** 2026-03-09 (D26 ajoutée)

---

## Contexte

- **Brief :** Pipeline end-to-end cloud pour analyser le marché de l'emploi Data Engineer en France
- **Sources :** API France Travail (OAuth2), Stock Sirene INSEE (Parquet, multi-Go), API Géo (libre)
- **Équipe :** 4 personnes (2 en présentiel, 2 en distanciel), 3 × 5 jours espacés de 3 semaines
- **Évaluation :** Démo technique (70%) + Revue code/architecture (30%)

---

## Décisions prises

### D1 — Cloud Provider : GCP

- **Choix :** Google Cloud Platform
- **Data Warehouse :** BigQuery
- **Justification :** Free tier BigQuery (1 To requêtes/mois, 10 Go stockage), bon rapport coût/fonctionnalités pour un projet pédagogique

### D2 — IaC : Terraform

- **Choix :** Terraform
- **Justification :** Syntaxe identique à OpenTofu, mais écosystème GCP plus documenté (provider `hashicorp/google`), pas de contrainte de licence pour un projet pédagogique
- **Détails :** voir D18

### D3 — GCS comme landing zone

- **Choix :** GCS est un passage obligé dans le flux (pas un simple backup)
- **Justification :** Idempotence (rechargement BQ sans re-appeler les APIs), conforme au pattern Medallion (raw = brut), découplage ingestion/chargement

### D4 — Cloud Run pour l'orchestration

- **Choix :** Cloud Run Job (conteneur Docker) déclenché par Cloud Scheduler
- **Justification :** Pas de limite de 9 min (contrairement à Cloud Functions), robuste pour l'ingestion France Travail (101 départements + rate limiting), coût identique (free tier généreux)
- **Détails :** voir D19

### D5 — Structure BigQuery en 4 datasets

- **raw** — tables miroir GCS, données brutes horodatées, intouchées
- **staging** — dbt, nettoyage mono-source (cast, rename, nulls, dédoublonnage)
- **intermediate** — dbt, jointures inter-sources, enrichissement
- **marts** — dbt, agrégats métier orientés consommation (dashboard)
- **Justification :** Le brief demande 3 couches, la couche intermediate isole la logique de jointure (bonne pratique dbt, justifiable en soutenance)

### D6 — Secrets et IAM

- **Secret Manager** = stocke les valeurs sensibles (credentials France Travail)
- **Service Accounts** = identités non-humaines (sa-ingestion, sa-dbt)
- **IAM** = permissions par service account (GCS r/w, BQ editor, Secret Manager accessor)

### D7 — Répartition équipe Bloc 1

- **Greg** : ingestion France Travail (source la plus complexe — OAuth2, pagination, rate limiting)
- **Collègue 2** : ingestion Sirene
- **Collègue 3** : ingestion API Géo
- **Collègue 4** : setup GCP initial (projet, bucket GCS, datasets BigQuery)

### D8 — Codes ROME pour "Data Engineer"

- **ROME = Répertoire Opérationnel des Métiers et des Emplois** (nomenclature France Travail, ~530 fiches, code = lettre + 4 chiffres)
- **Stratégie retenue : collecte large (4 codes) + filtrage mots-clés en staging**
  - Collecte les 4 codes → raw (sur-collecter)
  - Filtrage dbt staging par mots-clés : `data engineer`, `ingénieur data`, `développeur data`, `data engineering`, `ingénieur de données`
- **Codes impliqués :**
  - **M1805** — Études et développement informatique (le plus fréquent)
  - **M1810** — Production et exploitation de systèmes d'information
  - **M1806** — Conseil et maîtrise d'ouvrage en systèmes d'information
  - **M1801** — Administration de systèmes d'information
- **Alternative restreinte (non retenue) :** M1805 + M1810 seulement — moins de requêtes mais risque de manquer des offres

### D9 — Stratégie de pagination France Travail

- **Itération :** par département (101) × code ROME (4 codes, envoyés groupés ou un par un selon volume)
- **Pagination :** paramètre `range` (0-149, 150-299, ..., max 1000-1149 = 1150 résultats/combinaison)
- **Garde-fou :** si Content-Range indique > 1150, subdiviser par plage de dates (`minCreationDate`/`maxCreationDate`)
- **Volume estimé :** ~400-800 requêtes, ~5-8 min d'exécution (dans la limite Cloud Run)

### D10 — Wrapper Python maison (pas de lib tierce)

- Le package PyPI `api-offres-emploi` date de 2020, non maintenu → coder directement (~50 lignes)
- Helper `get_token()` avec cache + renouvellement avant expiration (token ~25 min)
- Rate limiting : `time.sleep(0.35)` entre requêtes (limite API = 3 req/s → 1 req/333ms, 350ms = marge de sécurité)
- Retry exponentiel via `tenacity` : en cas d'échec (429, 500, 503), réessayer après 1s → 2s → 4s → 8s → abandon

### D11 — Stock Sirene : chargement complet (pas de pré-filtrage)

- **Fichiers retenus :** StockEtablissement (~2-3 Go, ~40M lignes) + StockUniteLegale (~1 Go, ~25M lignes), tous deux en Parquet
- **Justification des deux fichiers :** StockEtablissement fournit la jointure SIRET avec les offres et la dimension géographique. StockUniteLegale apporte des dimensions BI indisponibles autrement : `categorieEntreprise` (PME/ETI/GE), `categorieJuridiqueUniteLegale`, `trancheEffectifsUniteLegale`, `denominationUniteLegale`. La jointure Etablissement → UniteLegale se fait sur le champ `siren` (présent des deux côtés).
- **Stratégie :** upload Parquet complet de chaque fichier → GCS → BigQuery raw (deux tables : `raw.sirene_etablissement`, `raw.sirene_unite_legale`), filtrage en dbt staging
- **Justification raw complet :** conforme au pattern Medallion (raw = brut intégral), simple, idempotent, coût négligeable (free tier)
- **Pas de filtrage par codes NAF** dans Sirene : un Data Engineer peut être recruté par n'importe quel secteur. Le NAF sert à enrichir, pas à filtrer.

### D12 — Refresh mensuel Sirene (automatisation Bloc 3)

- Stock publié le 1er de chaque mois (image au dernier jour du mois précédent)
- Bloc 1 : chargement unique du stock courant (suffisant)
- Bloc 3 (automatisation) : Cloud Scheduler cron `0 6 2 * *` → Cloud Run re-télécharge le Parquet, upload GCS avec prefix daté (`sirene/YYYY-MM/`), recharge BigQuery raw

### D13 — API Géo : snapshot complet en raw

- **Stratégie :** 3 appels GET (régions, départements, communes) → JSON dans GCS → BigQuery raw
- **Justification :** données quasi-statiques (dernier redécoupage régional = 2016), volume négligeable (~5 Mo), élimine la dépendance API à runtime
- **Refresh :** sur événement politique uniquement (fusion de communes, redécoupage régional), pas d'automatisation

### D14 — Jointure offres ↔ Sirene : SIRET seul en Bloc 2

- **Type :** LEFT JOIN (pas INNER JOIN — ne pas perdre les 60-80% d'offres sans SIRET)
- **Clé :** `entreprise.siret` (offres) ↔ `siret` (Sirene)
- **Taux de matching estimé :** 20-40%
- **Matching par nom d'entreprise :** reporté à Bloc 3, décision après mesure du taux réel sur données ingérées
- **Si matching par nom insuffisant :** on accepte la limitation et on documente le caveat dans le dashboard

### D15 — Enrichissement géographique : code commune INSEE

- **Jointure primaire :** `lieuTravail.commune` (offres) → `communes.code` (API Géo)
- **Fallback :** code département extrait de `lieuTravail.libelle` (format "XX - Ville")
- **Enrichissement obtenu :** nom département, nom région, population, coordonnées centre

### D16 — Structure du repo GitHub

- **5 dossiers racine :** `ingestion/`, `dbt/`, `infra/`, `docs/`, `.github/workflows/`
- **Principe :** un sous-dossier par source dans `ingestion/`, un module Terraform par ressource GCP dans `infra/modules/`
- **Risque de conflit principal :** `ingestion/shared/` → à stabiliser en J1 du Bloc 1
- **Entrypoint Cloud Run Job :** `python main.py` — script Python séquentiel (tranché en D19)
- **Arborescences et conventions de nommage :** voir `structure-repo.md`

### D17 — Gestion de profiles.yml (dbt)

- **`profiles.yml.example`** versionné dans `dbt/` — sert de template documenté (structure, noms des datasets)
- **`profiles.yml`** dans `.gitignore` — jamais commité
- **CI :** `DBT_PROFILES_DIR` pointe vers un `profiles.yml` généré dynamiquement avec les secrets GitHub Actions
- **Dev local :** chaque dev copie le `.example` et remplace le project ID
- **Même principe pour Terraform :** `terraform.tfvars.example` versionné, `terraform.tfvars` dans `.gitignore`

### D18 — IaC : Terraform (pas OpenTofu)

- **Choix :** Terraform
- **Justification :** Syntaxe HCL identique à OpenTofu, providers identiques (`hashicorp/google`). Avantage Terraform = documentation et exemples massivement indexés pour GCP. Licence BSL 1.1 sans impact pour un projet pédagogique non commercial.
- **Argument soutenance :** "Écosystème plus mature, pas de contrainte licence pour notre contexte."

### D19 — Orchestration : Cloud Run Job, fréquence hebdomadaire

- **Choix :** Cloud Run **Job** (pas Service)
- **Justification :** Le cas d'usage est du batch one-shot. Un Service nécessiterait FastAPI + endpoint HTTP + healthcheck = complexité gratuite sans valeur ajoutée. Job = `python main.py`, sort quand c'est fini.
- **Fréquence :** Hebdomadaire, cron `0 6 * * 1` (lundi 6h). Aucune source ne justifie du quotidien (offres FT changent lentement, Sirene = mensuel D12, Géo = quasi-statique D13).
- **Entrypoint :** `python main.py` — script Python séquentiel orchestrant les 3 ingestions, avec gestion d'erreurs et logging. Pas de FastAPI.
- **Terraform :** `google_cloud_run_v2_job` + `google_cloud_scheduler_job` (target HTTP vers API Cloud Run Admin `/run`)
- **Argument soutenance :** "Job parce que c'est du batch, pas un service HTTP."

### D20 — Conteneurisation et gestion de dépendances

- **Package manager :** `uv` (résolution rapide, lockfile déterministe, gestion de version Python intégrée)
- **Fichiers dépendances :** `pyproject.toml` + `uv.lock` remplacent `requirements.txt`
- **Dockerfile ingestion :** Single-stage, pattern `COPY --from=ghcr.io/astral-sh/uv:latest` (pas de `pip install uv`), `uv sync --frozen --no-dev`
- **Dockerfile dbt :** Image officielle `ghcr.io/dbt-labs/dbt-bigquery:latest` + COPY modèles (pas de uv ici)
- **docker-compose.yml :** À la racine, 2 services (ingestion + dbt)
- **Compatibilité brief :** Le brief mentionne `requirements.txt` — `uv export` permet de le générer si nécessaire, mentionné dans le README
- **Onboarding équipe :** 10 min J1 matin, installation = une commande (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### D21 — Outil de BI : Looker Studio

- **Choix :** Looker Studio (gratuit, natif GCP)
- **Connexion :** Directe BigQuery → marts, zéro config intermédiaire
- **Accès public :** Lien de rapport partagé (paramètre natif Looker Studio, 1 clic)
- **Pas d'infra supplémentaire :** pas de conteneur, pas de Terraform, pas de Cloud Run Service 24/7
- **Contenu minimum :** 3 pages/onglets — axe géographique (carte + filtres), axe sectoriel (NAF, top entreprises), axe temporel (évolution offres)
- **Alternatives écartées :** Metabase (Cloud Run 24/7 + config JDBC = overhead infra disproportionné), Streamlit (tout à coder en Python, c'est du dev pas de la BI, 2-3 jours de travail)
- **Argument soutenance :** "Natif GCP, gratuit, public nativement, zéro maintenance, cohérent avec la stack BigQuery."

### D22 — CI/CD : 2 workflows GitHub Actions

- **`ci.yml`** — Validation sur PR (`pull_request` sur `main`)
  - **Job lint-python :** `astral-sh/setup-uv@v4` → `uv sync --frozen --no-dev` → `ruff check ingestion/` + `ruff format --check ingestion/`
  - **Job dbt-validate :** `dbt compile` + `dbt test` (pas `dbt run` — éviter coûts BQ sur chaque PR). Profil généré dynamiquement via secrets (pattern D17)
  - **Job terraform-validate :** `terraform init -backend=false` + `terraform fmt -check` + `terraform validate` (dans `infra/`)
  - Les 3 jobs tournent en parallèle
- **`deploy.yml`** — Déploiement sur merge (`push` sur `main`)
  - **Job build-push :** Build Docker image ingestion → push vers Artifact Registry (`$REGION-docker.pkg.dev/$PROJECT/$REPO/ingestion:$GITHUB_SHA`)
  - **Job deploy-job :** `gcloud run jobs update datatalent-ingestion --image=...` (⚠ `jobs update`, pas `deploy` — c'est un Job, D19)
  - **Terraform apply :** Manuel (pas d'auto-approve en CI). `terraform plan` en PR pour review, apply humain.
- **Auth GCP :** Service account key (JSON, base64) en GitHub Secret (`GCP_SA_KEY`), action `google-github-actions/auth@v2`. Workload Identity Federation mentionné dans le README comme évolution cible.
- **Secrets GitHub nécessaires :** `GCP_PROJECT_ID`, `GCP_SA_KEY`, `GCP_REGION`
- **Pre-commit hooks :** `.pre-commit-config.yaml` à la racine avec 2 hooks (commitlint + ruff). Filet de sécurité local complémentaire au CI — defense in depth. Onboarding J1 : `pre-commit install` après clone.

### D23 — Répartition du travail : hybride source → couche

- **Stratégie :** par source au Bloc 1 (parallélisme maximal), par compétence/couche aux Blocs 2-3 (dépendances séquentielles)
- **Justification :** Le Bloc 1 est parallélisable (chaque source est indépendante). Les Blocs 2-3 ont des dépendances séquentielles (staging → intermediate → marts → dashboard) — la répartition par source ne fonctionne plus.
- **Bloc 1 (par source) :** conforme à D7
- **Bloc 2 (par compétence) :** Greg = dbt intermediate + marts, Collègue 2 = stg_sirene + stg_france_travail, Collègue 3 = stg_geo + tests dbt, Collègue 4 = Terraform complet
- **Bloc 3 (par livrable) :** Greg = CI/CD + Docker, Collègue 2 = dashboard Looker Studio, Collègue 3 = documentation, Collègue 4 = Terraform finalize + cost dashboard + démo
- **Réattribution entre blocs :** chaque dev a touché une source ET une couche transverse → crédible en soutenance

### D24 — Syncs et coordination (contrainte distanciel)

- **Contrainte :** 2 personnes en présentiel, 2 en distanciel → pas de conversations informelles pour les 2 distants
- **Principe :** synchrone pour aligner, asynchrone pour avancer. Ne pas essayer d'aligner par écrit ni de se synchroniser pour coder ensemble.
- **Fréquence des syncs guidée par la topologie des dépendances, pas par une règle agile générique :**
  - **Bloc 1 (parallèle) — 3 syncs :** J1 matin (kickoff + contrat `shared/`, 20 min), J3 matin (transitions — qui a fini, qui bascule, 15 min), J5 matin (plan d'intégration `main.py`, ordre des PRs, 15 min). J2 et J4 : pas de sync, les gens codent. Questions ponctuelles sur Slack/Discord.
  - **Bloc 2 (séquentiel) — daily 10 min :** les dépendances sont en chaîne (staging → intermediate → marts), un retard d'1 jour se propage. Le daily vérifie si les maillons amont sont à l'heure.
  - **Bloc 3 (par livrable) — à calibrer au retour :** moins de dépendances que Bloc 2, plus que Bloc 1.
- **Convention branching :** `{type}/{scope}` (déjà posé dans `structure-repo.md`). Branches par feature, pas par personne. Max 1-2 jours. Squash merge sur main. `main` protégé : merge uniquement via PR avec 1 approval minimum.

### D25 — Survie du contexte entre blocs

- **Risque principal :** la perte de contexte après 3 semaines de pause, amplifiée par le distanciel (pas de conversations informelles)
- **Artefact : doc de transition (Google Docs)** — 1 doc partagé, 1 section par personne par bloc. Rempli le J5 après-midi, dernière heure. Template par personne :
  - **Livré :** branches mergées / tâches Trello fermées (3-5 lignes max)
  - **Découvertes :** ce qui n'est documenté nulle part ailleurs — les surprises terrain
  - **Bloquant pour la suite :** ce que le prochain doit savoir avant de commencer
- **Kickoff synchrone J1 matin de chaque bloc (30 min) :** chacun résume ses découvertes à l'oral (pas relit son doc), on clarifie les dépendances du bloc, on confirme la répartition
- **Le doc prépare le kickoff, le kickoff crée l'alignement.** Sans le doc, le kickoff prend 2h. Sans le kickoff, le doc dort dans le Drive.

### D26 — Optimisation coûts : free tier confirmé, pas de transformation data lake

- **Constat :** Le pipeline opère entièrement dans le free tier GCP. Estimation mensuelle :

| Service | Usage estimé | Free tier | Coût |
|---------|-------------|-----------|------|
| BigQuery stockage | ~4-5 Go | 10 GiB | $0 |
| BigQuery requêtes | ~50 Go/mois (dev intensif) | 1 TiB | $0 |
| GCS | ~3 Go | 5 Go (Standard, us) | $0 |
| Cloud Run Job | ~30 min/mois | 240k vCPU-s | $0 |
| Cloud Scheduler | 1 job | 3 jobs | $0 |
| Secret Manager | 3 secrets | 6 versions actives | $0 |
| Artifact Registry | ~300 Mo | 500 Mo | $0 |
| GitHub Actions | CI/CD sur PR + deploy | Illimité (repo public) | $0 |

- **GitHub Actions :** Gratuit car repo public (brief l'exige). Sur un repo privé, le free tier serait 2 000 min/mois puis $0.008/min (Linux runners). Le choix D22 (pas de `dbt run` en CI, seulement `compile` + `test`) limite aussi la consommation de minutes GA.
- **Transformation data lake (GCS/Python) :** Non pertinente. Les volumes sont dans le free tier BQ → aucune économie réelle. On perdrait dbt (tests, doc, lignage) qui est un critère d'évaluation du brief. Le cas d'usage data lake = volumes To/Po où le scan BQ coûte cher.
- **Optimisations BigQuery retenues :**
  - **Partitioning :** `raw.france_travail` et `raw.sirene` par `_ingestion_date`, `stg_offres` par `date_creation`, marts temporels par mois
  - **Clustering :** `stg_sirene` par `siret`, `stg_offres` par `code_commune`/`code_rome`, `int_offres_enrichies` par `code_region`/`code_naf`
  - **SELECT explicite** (pas `*`) dans tous les modèles dbt, particulièrement `stg_sirene` (~10 colonnes utiles sur des dizaines)
- **Sirene raw refresh (Bloc 3) :** WRITE_TRUNCATE à chaque refresh mensuel (pas d'accumulation de snapshots). Un snapshot Sirene n'est pas un flux événementiel — l'historique n'a pas de valeur analytique ici.
- **Monitoring coûts (livrable brief) :**
  - **Billing export → BigQuery → Looker Studio** : coût par service, évolution temporelle (méthode standard GCP)
  - **INFORMATION_SCHEMA.JOBS_BY_PROJECT** : coût par requête BQ, octets scannés par run (granularité fine, bonus soutenance)
  - **Budget alerts Terraform** : seuils à 50%, 90%, 100% d'un budget de 10€ (`google_billing_budget`)
- **Argument soutenance :** "Pipeline entièrement free tier. Pas de transformation data lake car volumes insuffisants — on aurait perdu dbt pour économiser zéro euro. Optimisations BQ (partitioning, clustering, SELECT explicite) appliquées pour démontrer la maîtrise, pas par nécessité de coût. Monitoring coûts via billing export + INFORMATION_SCHEMA pour deux niveaux de granularité."

### D27 — Dev local : ADC par développeur (pas de clé JSON partagée)

- **Choix :** Chaque dev s'authentifie avec son propre compte Google via `gcloud auth application-default login`. Le service account `sa-ingestion` est réservé à Cloud Run (Bloc 3).
- **Justification :** Traçabilité individuelle dans les audit logs, révocation par compte sans impact sur les autres, zéro secret à distribuer. La clé JSON partagée posait des problèmes de sécurité (surface d'attaque × 4), de traçabilité (toutes les actions = `sa-ingestion`) et de rotation (pénible, coordonnée).
- **Prérequis :** `gcloud` CLI installé sur chaque machine locale + rôles IAM accordés à chaque compte Gmail.
- **Voir :** `setup-gcp-bloc1-v2.md` (étape 7), `onboarding-gcp-datatalent.md`

### D28 — Stratégie documentation : repo externe → `docs/` IaC-driven

- **Constat :** La documentation vit actuellement dans un repo externe (`datatalent_docs`) pendant les Blocs 1-2. Le livrable final (brief) exige : README, schéma d'architecture, catalogue de données, instructions de déploiement — le tout dans le repo projet.
- **Stratégie en 3 temps :**
  1. **Blocs 1-2 :** doc dans `datatalent_docs` (brouillon vivant, itérations libres)
  2. **Pause 2 :** tri livrable (brief) vs. interne (tutoriels, onboarding, notes de travail)
  3. **Bloc 3, J4 :** docs finales raffinées copiées dans `docs/` du repo projet
- **Point clé :** Le `docs/setup-gcp.md` livrable sera réécrit autour de Terraform (`terraform apply`), pas autour des commandes `gcloud` manuelles. Les guides manuels actuels (`setup-gcp-bloc1-v2.md`) deviennent des artefacts historiques. La structure Terraform (modules bien nommés, outputs clairs) conditionne la qualité de cette doc finale.
- **Ce qui reste dans le repo externe :** tutoriels onboarding, notes d'exploration, guides internes — utiles mais hors périmètre d'évaluation.

### D29 — Variables d'environnement : `.env` racine, `direnv` différé

- **Choix :** Un seul `.env` à la racine du projet, consommé par les 3 composants (ingestion via `os.getenv()`, dbt via `env_var()`, Terraform via `TF_VAR_*`). Format standard sans `export`, compatible `uv run --env-file`, `docker-compose`, et `direnv`.
- **Justification :** Defense in depth — un seul fichier sensible à protéger. Les fichiers de config (`profiles.yml`, `terraform.tfvars`) deviennent versionnables car ils référencent des variables, pas des valeurs.
- **Dev local (immédiat) :** depuis `ingestion/`, `uv run --env-file ../.env python -m ...`. Depuis la racine, `set -a && source .env && set +a` avant `dbt` ou `terraform`.
- **Dev local (ultérieur) :** `direnv` ajouté via un `.envrc` d'une ligne (`dotenv`), zéro breaking change. Charge les variables automatiquement quel que soit le sous-répertoire.
- **Production (Cloud Run) :** pas de `.env`. Credentials FT via Secret Manager, auth GCP via SA `sa-ingestion`.
- **Fichiers versionnés :** `.env.example` (template), `profiles.yml` avec `env_var()`. `.env` et `.envrc` dans `.gitignore`.

---

## Mapping des 3 blocs

### Bloc 1 (5 jours) — Phases 1 + 2 du brief : Cadrage + Ingestion

| Jour | Objectif | Sync |
|------|----------|------|
| J1 matin | T0 : kickoff synchrone (20 min), contrat `shared/`, setup GCP, onboarding (pre-commit, .example) | **Kickoff** |
| J1 après-midi | Exploration sources, début scripts d'ingestion (US2, US3, US4 en parallèle) | — |
| J2 | Scripts d'ingestion, setup GCP finalisé | — |
| J3 | Scripts d'ingestion. Collègue 3 bascule sur cartographie (US1), Collègue 4 paire avec Greg | **Sync transitions (15 min)** |
| J4 | Scripts d'ingestion, tests unitaires | — |
| J5 | Intégration `main.py`, tests bout en bout, données dans GCS + BigQuery raw, doc de transition | **Sync intégration (15 min)** |

**Sortie Bloc 1 :** Données brutes dans GCS et BigQuery (raw), scripts versionnés, cartographie documentée, Trello vivant, doc de transition rempli.

### Pause 1 (3 semaines) — Préparation Bloc 2

- Prototyper les modèles dbt staging/intermediate sur les données réelles
- Explorer la qualité des données (SIRET manquant, salaires, etc.)
- Commencer le Terraform en local
- Affiner le workflow Claude Code si frictions notées au Bloc 1
- **Découper les tâches US5-US7 à la lumière des données réelles**

### Bloc 2 (5 jours) — Phase 3 + début Phase 4 : Transformations + IaC

| Jour | Objectif | Sync |
|------|----------|------|
| J1 | Kickoff (30 min), modèles dbt staging | **Kickoff + daily** |
| J2 | Modèles dbt staging (fin) + tests | **Daily 10 min** |
| J3 | Modèle intermediate (jointure offres ↔ Sirene) | **Daily 10 min** |
| J4 | Modèles marts (agrégats géo, secteur, temporel) | **Daily 10 min** |
| J5 | Modules Terraform, doc de transition | **Daily 10 min** |

**Sortie Bloc 2 :** `dbt run` + `dbt test` passent, marts répondent à la question centrale, premiers modules Terraform, doc de transition rempli.

### Pause 2 (3 semaines) — Préparation Bloc 3

- Prototyper le dashboard Looker Studio
- Préparer les workflows GitHub Actions
- Rédiger le README et le catalogue de données
- **Découper les tâches US8-US11 à la lumière des marts réels**

### Bloc 3 (5 jours) — Fin Phase 4 + Phase 5 : CI/CD + Dashboard + Polish

| Jour | Objectif |
|------|----------|
| J1 | Kickoff (30 min), finaliser IaC, Dockerfile fonctionnel |
| J2 | GitHub Actions (lint, dbt test, tf validate, deploy) |
| J3 | Dashboard analytique Looker Studio connecté aux marts (US8) + dashboard coûts cloud (US11) |
| J4 | Documentation : README, schéma archi, catalogue données |
| J5 | Démo 5 min, corrections finales, polish, doc de transition finale |

**Sortie Bloc 3 :** Pipeline bout en bout fonctionnel, dashboard analytique public, dashboard coûts cloud, repo documenté, démo prête.

### Risques et tampons

- **Risque Bloc 1 :** France Travail résiste → J5 = tampon ingestion
- **Risque Bloc 2 :** Jointure SIRET faible taux → besoin d'un plan B en intermediate
- **Risque Bloc 3 :** IaC déborde → sacrifier le catalogue de données (bonus dans le brief)
- **Risque transverse :** Perte de contexte après pause → mitigé par doc de transition + kickoff synchrone (D25)

---

## Zones de conflit Git et ownership

| Zone | Risque | Mitigation |
|------|--------|-----------|
| `ingestion/shared/` | Haut — 4 devs en dépendent | Greg freeze l'interface J1 matin. Après : PR obligatoire pour tout changement |
| `ingestion/main.py` | Moyen — entrypoint séquentiel | Greg seul owner. Les autres exportent une fonction `run()` depuis leur module |
| `dbt/models/staging/` | Faible — 1 sous-dossier par source | Isolation naturelle par répertoire |
| `infra/` | Faible en Bloc 2 | Collègue 4 seul owner |
| `.github/workflows/` | Faible | Greg seul en Bloc 3 |

---

## Outils Claude Code pour la code review

### `/simplify` — Revue post-implémentation automatique

Bundled skill (livré avec Claude Code, pas besoin de l'installer). Lance 3 agents de revue en parallèle :
1. **Code reuse** — détecte les duplications et opportunités de factorisation
2. **Code quality** — vérifie lisibilité, conventions, maintenabilité
3. **Efficiency** — identifie les problèmes de performance

Applique les corrections automatiquement. Usage : taper `/simplify` après avoir implémenté une feature, ou `/simplify focus on memory efficiency` pour cibler un aspect.

**Usage dans le projet :** Nettoyer son propre code avant de pousser une PR.

Doc : https://code.claude.com/docs/en/skills

### `/install-github-app` — Revue automatique des PR sur GitHub

Configure une GitHub App qui fait relire automatiquement chaque Pull Request par Claude. Crée un fichier `claude-code-review.yml` avec un prompt personnalisable.

**Conseil :** Le prompt par défaut est trop verbeux. Le réduire à l'essentiel (bugs + sécurité) pour éviter le bruit.

**Usage dans le projet :** Instaurer des code reviews automatiques pour l'équipe — exactement ce que le formateur attend probablement.

Doc : https://docs.anthropic.com/en/docs/claude-code/github-app

---

## Défis techniques identifiés

### API France Travail

- OAuth2 client_credentials + pagination `range` (plafond 1150/combinaison) + rate limit 3 req/s
- 4 codes ROME retenus, filtrage mots-clés en staging (D8)
- SIRET rarement présent (~20-40%) → impact jointure Sirene
- Salaire = texte libre, souvent absent → parsing regex en staging

### Stock Sirene

- StockEtablissement Parquet (~40M lignes, ~2-3 Go) + StockUniteLegale (~25M lignes, ~1 Go)
- Chargement complet des deux fichiers dans BigQuery raw (D11), filtrage `etatAdministratifEtablissement = 'A'` en staging, jointure SIREN entre les deux en intermediate
- Pas de filtrage NAF dans Sirene — enrichissement seulement
- RGPD : `statutDiffusionEtablissement = 'P'` → adresse masquée, à gérer en staging
- Refresh mensuel automatisé prévu pour Bloc 3 (D12)

### Jointure offres ↔ Sirene

- LEFT JOIN sur SIRET (D14), pas INNER JOIN — ne pas perdre les offres sans SIRET
- Taux de matching estimé : 20-40%
- Pré-traitement staging : normaliser SIRET (strip espaces, vérifier longueur 14, cast string)
- Plan B (matching nom) reporté à Bloc 3, décision après mesure du taux réel

### API Géo

- Snapshot complet : 3 niveaux (régions, départements, communes) — D13
- Ingestion Bloc 1 : 3 requêtes GET, ~5 Mo total, aucune authentification
- Refresh : sur événement politique uniquement, pas d'automatisation

### Enrichissement géographique

- Jointure primaire : code commune INSEE (offres → communes API Géo) — D15
- Fallback : code département extrait de `lieuTravail.libelle`
- Fiabilité haute : quasi toutes les offres ont une localisation

---

## Stratégie personnelle

- **Approche parallèle :** Jouer le jeu de l'équipe + prototyper en avance avec Claude Code
- **Découplage phases :** 5 jours = produire (livrable prioritaire), 3 semaines = digérer + affiner workflow CC + préparer bloc suivant
- **Claude Code :** Utilisé comme outil de développement pour TOUT le projet (Python, SQL/dbt, Terraform, Docker, CI/CD, README)
- **Feedback loop :** Les frictions notées pendant les rush alimentent les ajustements workflow pendant les pauses (friction-driven, pas theory-driven)
- **Garde-fou :** Zéro méta-travail CC pendant les blocs de 5 jours

---

## Points à explorer

- [x] Mapping codes ROME pour Data Engineer (voir D8)
- [x] Stratégie filtrage Sirene (voir D11, pas de filtrage NAF — enrichissement seulement)
- [x] Architecture GCP détaillée (quels services exactement)
- [x] Mapping phases brief → 3 blocs de 5 jours
- [x] Découpage tâches pour travail en équipe de 4 (voir D23, D24, D25)
- [x] Structure repo GitHub (voir D16, D17)

---

*Détails d'exploration des sources (B1-B4) : voir `exploration-sources.md`.*
