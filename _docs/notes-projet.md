# Notes Projet — Pipeline Data Engineer (Brief DataTalent)

**Créé le :** 2025-03-08
**Dernière mise à jour :** 2026-03-28 (D38-D40 — endpoint export Opendatasoft, renommage colonnes à l'ingestion, skip conditionnel Sirene ; P1 et P3 implémentés, spike BMO complété)

---

## Contexte

- **Brief :** Pipeline end-to-end cloud pour analyser le marché de l'emploi Data Engineer en France
- **Sources brief :** API France Travail (OAuth2), Stock Sirene INSEE (Parquet, multi-Go), API Géo (libre)
- **Sources complémentaires (D35) :** URSSAF effectifs commune × APE, BMO France Travail, URSSAF masse salariale × NA88
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

- **Choix :** Cloud Run **Job** (pas Service)
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
- **Rate limiting (mis à jour 2026-03-17) :** limite réelle = **10 req/s** (constatée sur le portail francetravail.io, application DataTalent-Greg). L'ancienne valeur de 3 req/s provenait d'une documentation obsolète.
- **Throttle préventif :** `time.sleep(0.15)` entre requêtes (~6.6 req/s, conservateur). Remplace le `sleep(0.35)` initial qui était basé sur la limite de 3 req/s.
- Retry exponentiel via `tenacity` : en cas d'échec (429, 500, 503), réessayer après 1s → 2s → 4s → 8s → abandon

### D11 — Stock Sirene : chargement complet (pas de pré-filtrage)

- **Fichiers retenus :** StockEtablissement (Parquet, ~2-3 Go) + StockUniteLegale (Parquet)
- **Tables raw :** `raw.sirene_etablissement`, `raw.sirene_unite_legale`
- **Stratégie :** upload Parquet complet → GCS → BigQuery raw, filtrage en dbt staging
- **Justification :** conforme au pattern Medallion (raw = brut intégral), simple, idempotent, coût négligeable. StockUniteLegale ajouté car le fallback de jointure par nom d'entreprise (D14) nécessite `denominationUniteLegale` qui n'est pas dans StockEtablissement
- **Pas de filtrage par codes NAF** dans Sirene : un Data Engineer peut être recruté par n'importe quel secteur (banque, retail, industrie...). Le NAF sert à enrichir, pas à filtrer.

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
- **Write disposition :** `WRITE_APPEND` pour France Travail (accumulation hebdomadaire, déduplication ROW_NUMBER en staging par `id` + `_ingestion_date DESC`), `WRITE_TRUNCATE` pour toutes les autres sources (données statiques ou annuelles, écrasement idempotent). Paramètre `write_disposition` optionnel dans `shared/bigquery.py` avec défaut `WRITE_TRUNCATE`.

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

### D30 à D34 — Cadrage Terraform import

Voir `cadrage-terraform-import.md` pour les décisions D30 (structure modulaire), D31 (import incrémental), D32 (IAM `google_project_iam_member`), D33 (Secret Manager conteneur only), D34 (modules Bloc 2-3 à la demande).

### D35 — Sources complémentaires data.gouv.fr (exploration MCP 2026-03-25)

Exploration systématique via le MCP `mcp.data.gouv.fr` — 8 sources évaluées, 3 retenues. Voir `exploration-mcp-datagouv.md` pour les fiches détaillées, `croisement-mcp-x-france-travail.md` pour les impacts croisés avec les findings France Travail.

**Sources retenues :**

| Priorité | Source | Dataset ID | Accès | Valeur | Action |
|---|---|---|---|---|---|
| P1 | URSSAF effectifs commune × APE | `5efd242c72595ba1a48628f2` | API Opendatasoft (`open.urssaf.fr`) | **Élevée** — seule source NAF5 × commune, compense l'absence de SIRET (D14-bis) | Ingérer (script Python, ~3-4h) |
| P2 | BMO France Travail (tensions recrutement) | `561fa564c751df4f2acdbb48` | XLSX téléchargement direct | **Élevée** — tensions recrutement IT par bassin d'emploi | Spike d'abord (~1h), intégration conditionnelle |
| P3 | URSSAF masse salariale × NA88 | `61d784a161825aaf438b8e9e` | API Opendatasoft | **Moyenne** — salaire brut moyen secteur 62 comme benchmark | Ingérer (script Python, workflow classique GCS → BQ raw, ~1h) |

**Sources écartées :**
- **BTS INSEE (salaires secteur privé)** — NAF agrégé A17 (`J` = tout le secteur Information & Communication). Granularité insuffisante pour un benchmark Data Engineer. Dataset ID `67f85d13377ef83a019ac73f`.
- **APEC (rémunération cadres)** — Données non structurées sur data.gouv.fr (XLSX "humain", 37 onglets, 1 seul lisible via Tabular API). Édition 2022, données 2021. Aucune ventilation par fonction visible.
- **DARES (emplois vacants)** — Indicateur macro par grand secteur, pas de granularité métier.
- **Adzuna** — Évaluée et écartée : scope creep hors brief (4ème source non mandatée), déduplication avec France Travail irrésoluble (pas de clé commune), salaires estimés par ML (mélange méthodologique), double pipeline staging pour gain marginal.

**APIs projet confirmées via `search_dataservices` (aucun changement d'URL) :**
- France Travail Offres : `https://francetravail.io/produits-partages/catalogue/offres-emploi`
- Recherche Entreprises : `https://recherche-entreprises.api.gouv.fr`
- API Géo : `https://geo.api.gouv.fr`

**Découverte bonus — NAF 2025 :** la colonne `activitePrincipaleNAF25Etablissement` est déjà diffusée dans Sirene à titre informatif. Transition officielle au 1er janvier 2027. Aucun impact immédiat sur le projet mais bon à savoir.

### D36 — ~~Seeds dbt pour tables référentielles~~ — ANNULÉE (2026-03-27)

- **Décision initiale :** les tables < 1000 lignes devaient être chargées via `dbt seed` (CSV versionné dans Git, court-circuit du chemin GCS → BQ raw).
- **Annulation :** toutes les sources suivent désormais le workflow classique d'ingestion (`ingestion/{source}/ingest.py` → `shared/gcs.py` → `shared/bigquery.py` → raw → dbt staging), quelle que soit la volumétrie.
- **Justification :** uniformité architecturale (un seul flux à comprendre, documenter, automatiser), automatisation homogène via Cloud Run Job (`main.py` appelle chaque `run()`), pas de chemin parallèle à maintenir. Le surcoût d'un script d'ingestion pour ~30 lignes est négligeable face au gain en cohérence.
- **Conséquence :** pas de répertoire `dbt/seeds/`, pas de `_seeds.yml`. BMO (P2, conditionnel) suit aussi le workflow classique si le spike valide.

### D37 — URSSAF effectifs : filtrage codes APE IT à l'ingestion

- **Principe :** on ne télécharge pas l'intégralité du dataset URSSAF (toutes communes × tous secteurs) — on filtre à la source via les paramètres API Opendatasoft.
- **Codes APE retenus :**
  - `62.01Z` — Programmation informatique
  - `62.02A` — Conseil en systèmes et logiciels informatiques
  - `62.03Z` — Gestion d'installations informatiques
  - `62.09Z` — Autres activités informatiques
- **Justification :** réduire le volume de ~95% à l'ingestion. Le dataset complet couvre tous les secteurs NAF × toutes les communes × toutes les années depuis 2006. Seuls les 4 codes APE IT sont pertinents pour le projet.
- **Conséquence :** le filtrage IT est fait à l'ingestion (pas en staging). La table raw `urssaf_effectifs_commune_ape` ne contient que les données IT. C'est un écart assumé avec le pattern Medallion (raw = brut intégral) — justifié par la réduction de volume et le fait que les autres secteurs n'ont aucune utilité pour le projet, même potentielle.
- **Table intermediate :** `int_densite_sectorielle_commune` agrège les 4 codes APE en un seul total IT par commune × année. Voir `couche-intermediate-datatalent.md`.

### D38 — URSSAF effectifs : endpoint export au lieu de pagination records

- **Contexte :** lors de l'implémentation de P1 (URSSAF effectifs commune × APE), la pagination `limit`/`offset` sur l'endpoint `/records` échoue en 400 Bad Request à `offset=10000` — limite hard imposée par Opendatasoft, indépendante du filtre appliqué.
- **Décision :** utiliser l'endpoint `/exports/json` qui retourne le dataset filtré complet en une seule requête, sans limite de pagination.
- **Conséquence :** `client.py` simplifié — plus de boucle de pagination, une seule requête GET avec `timeout=120s`. La réponse est une liste JSON directe (pas d'enveloppe `total_count`/`results`).
- **Applicable à :** toute source Opendatasoft dont le volume filtré dépasse 10 000 lignes. Pour P3 (masse salariale, ~27 lignes), l'endpoint `/records` reste utilisable sans problème.

### D39 — Renommage sémantique des colonnes à l'ingestion (écart Medallion)

- **Principe :** les scripts d'ingestion des sources complémentaires (P1, P2, P3) renomment les colonnes en snake_case sémantique (ex: `met` → `projets_recrutement`, `Dept` → `code_departement`) avant écriture JSONL, au lieu de conserver les noms source bruts dans raw et renommer en staging dbt.
- **Justification technique :** BigQuery autodetect rejette ou mutile les noms avec espaces et accents (ex: `Code métier BMO`, `Libellé de famille de métier`). Un renommage minimal est obligatoire pour que le load job fonctionne. Le renommage sémantique est fait dans la foulée car l'ingestion touche déjà chaque champ (cast types, gestion nulls, filtrage).
- **Conséquence sur dbt staging :** les modèles staging des sources complémentaires sont réduits à un rôle de validation (tests `not_null`, `unique`, `accepted_values`) et de colonnes calculées (ex: `part_difficile_pct` pour BMO). Pas de renommage ni de cast en staging — c'est fait en amont.
- **Écart avec Medallion pur :** en Medallion strict, raw = copie fidèle de la source, staging = renommage + typage. Ici, raw est déjà nettoyé. Compromis assumé — documenté, cohérent sur les 3 sources complémentaires.
- **Sources primaires non concernées :** France Travail, Sirene et API Géo stockent le JSON brut complet en raw (D8/D11/D13). L'écart ne concerne que P1, P2, P3.

### D40 — Sirene : skip conditionnel dans `run()` (optimisation coût/temps)

- **Contexte :** Sirene (~2-3 Go Parquet, ~40M lignes) pèse 99% du temps d'exécution de `main.py` pour 0% de valeur analytique dans les marts (jointure SIRET morte, D14-bis). La source n'est mise à jour que mensuellement (D12), mais `main.py` est exécuté chaque semaine (D19).
- **Décision :** `sirene/ingest.py` vérifie la date du dernier fichier GCS (`sirene/` prefix). Si un fichier existe depuis moins de 30 jours, skip avec log `sirene_skip_recent`. Sinon, exécution normale.
- **Justification :** évite 3 re-téléchargements inutiles par mois (chacun = 2-3 Go download + upload GCS + load BQ 40M lignes). Le check GCS coûte 1 appel API (négligeable). Pas de changement d'architecture (pas de deuxième Cloud Run Job).
- **Alternative écartée :** Cloud Run Job séparé avec Scheduler mensuel — complexité disproportionnée (nouveau job, nouveau scheduler, Terraform, CI/CD) pour le même résultat fonctionnel.
- **Fallback :** si le check GCS échoue (erreur réseau, permissions), l'ingestion se fait normalement — pire cas, on recharge pour rien.
- **Implémentation :** ~10 lignes dans `sirene/ingest.py`, utilise `google.cloud.storage` (déjà en dépendance).

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
| J3 | Modèles intermediate (enrichissement géo API Géo, densité sectorielle URSSAF) | **Daily 10 min** |
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
- **Risque Bloc 2 :** ~~Jointure SIRET faible taux~~ Résolu par D14-bis (SIRET absent, enrichissement via codeNAF offre + URSSAF). Nouveau risque : intégration URSSAF effectifs (API Opendatasoft à découvrir) + spike BMO (granularité FAP incertaine)
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

- OAuth2 client_credentials + pagination `range` (plafond 1150/combinaison) + rate limit 10 req/s (D10, mis à jour)
- 4 codes ROME retenus, classification `categorie_metier` par regex sur titre en staging (D8-bis) — 20 offres data sur 2589 IT
- **SIRET absent de 100% des offres** — jointure Sirene morte (D14-bis)
- `codeNAF` présent dans 47.8% des offres, biaisé intérim (38.3% = codes 78.10Z/78.20Z)
- Salaire : `salaire.libelle` présent à 29.6%, 100% parsable mécaniquement (6 patterns regex). `salaire.commentaire` = texte libre, parsing non recommandé

### Stock Sirene

- StockEtablissement Parquet (~40M lignes, ~2-3 Go) + StockUniteLegale (~25M lignes, ~1 Go)
- Chargement complet des deux fichiers dans BigQuery raw (D11), filtrage `etatAdministratifEtablissement = 'A'` en staging
- **Rôle actuel :** livrable technique (démonstration dbt sur source volumineuse) + référentiel NAF. Aucune jointure en intermediate — la jointure SIRET est morte (D14-bis), l'enrichissement sectoriel vient de `codeNAF` dans l'offre France Travail et des données URSSAF (D35)
- Pas de filtrage NAF dans Sirene — enrichissement seulement
- RGPD : `statutDiffusionEtablissement = 'P'` → adresse masquée, à gérer en staging
- Refresh mensuel automatisé prévu pour Bloc 3 (D12)

### Jointure offres ↔ Sirene — D14-bis (caduque)

- **Constat exploration (2026-03-24) :** `entreprise.siret` absent de 100% des 2589 offres collectées. Le champ n'existe pas dans le JSON — ni dans `entreprise`, ni à la racine, ni sous un autre nom.
- **D14 (ancien) :** LEFT JOIN sur SIRET, taux estimé 20-40%, plan B matching par nom en Bloc 3.
- **D14-bis (nouveau) :** jointure SIRET abandonnée (0% de match). Matching par nom reporté sine die (effort disproportionné : noms d'intérimaires dominants, casse incohérente, ambiguïtés).
- **Enrichissement sectoriel :** repose sur `codeNAF` et `secteurActiviteLibelle` présents directement dans l'offre (47.8%), complété par URSSAF effectifs commune × APE (D35/D37) comme contexte géo-sectoriel.
- **Sirene reste ingéré** — livrable brief, staging dbt sur source volumineuse, mais aucune jointure dans le modèle intermediate.

### API Géo

- Snapshot complet : 3 niveaux (régions, départements, communes) — D13
- Ingestion Bloc 1 : 3 requêtes GET, ~5 Mo total, aucune authentification
- Refresh : sur événement politique uniquement, pas d'automatisation

### Enrichissement géographique

- Jointure primaire : `lieuTravail.commune` → `communes.code` (API Géo) — **92.7% couverture** (D15, confirmé Axe 3)
- Fallback : code département extrait de `lieuTravail.libelle` par regex — **100% couverture**
- Validation croisée : 100% concordance entre les deux sources sur les 2399 offres où les deux sont présentes (zéro discordance)
- Lat/lon disponibles à 89.3% — cartographie faisable directement
- Enrichissement obtenu via API Géo : nom commune, nom département, nom région, population
- Enrichissement complémentaire via URSSAF (D35) : densité d'établissements IT et effectifs salariés par commune

### URSSAF effectifs commune × APE (P1 — implémenté 2026-03-28)

- Format wide confirmé : colonnes `effectifs_salaries_{YYYY}` et `nombre_d_etablissements_{YYYY}` de 2006 à 2024
- Unpivot Python (regex sur noms de colonnes) → format long (95 283 lignes après unpivot)
- Limite hard offset=10000 sur `/records` → endpoint `/exports/json` retenu (D38)
- **Paris : codes arrondissements (75101–75120), pas code commune centrale (75056)** — à gérer dans `int_densite_sectorielle_commune` en Bloc 2
- Spot check 2024 : 97 806 effectifs IT sur Paris arrondissements
- Voir `ingestion-urssaf-effectifs.md`

### URSSAF masse salariale × NA88 (P3 — implémenté 2026-03-28)

- 27 lignes (une par année 1998–2024), une seule page suffisante
- Champ filtré : `secteur_na88i` (pas `na88`), format `"62 Programmation, conseil..."` — split sur premier espace
- Champ masse salariale : `masse_salariale` (pas `masse_salariale_brute`)
- `annee` retourné comme string par l'API — casté en int à l'ingestion
- Spot check 2024 : salaire moyen = 55 070 € ✓
- Voir `ingestion-urssaf-masse-salariale.md`

---

## Stratégie personnelle

- **Approche parallèle :** Jouer le jeu de l'équipe + prototyper en avance avec Claude Code
- **Découplage phases :** 5 jours = produire (livrable prioritaire), 3 semaines = digérer + affiner workflow CC + préparer bloc suivant
- **Claude Code :** Utilisé comme outil de développement pour TOUT le projet (Python, SQL/dbt, Terraform, Docker, CI/CD, README)
- **Feedback loop :** Les frictions notées pendant les rush alimentent les ajustements workflow pendant les pauses (friction-driven, pas theory-driven)
- **Garde-fou :** Zéro méta-travail CC pendant les blocs de 5 jours

---

## Points à explorer

- [x] Mapping codes ROME pour Data Engineer (voir D8, révisé D8-bis — 20 offres data sur 2589 IT)
- [x] Stratégie filtrage Sirene (voir D11, pas de filtrage NAF — enrichissement seulement)
- [x] Architecture GCP détaillée (quels services exactement)
- [x] Mapping phases brief → 3 blocs de 5 jours
- [x] Découpage tâches pour travail en équipe de 4 (voir D23, D24, D25)
- [x] Structure repo GitHub (voir D16, D17)
- [x] Taux de présence SIRET dans les offres (voir D14-bis — 0%, jointure morte)
- [x] Sources complémentaires data.gouv.fr (voir D35 — URSSAF effectifs, BMO, masse salariale)
- [x] Adzuna comme source complémentaire (évaluée et écartée, voir D35)
- [x] Intégration URSSAF masse salariale × NA88 — P3 implémenté (2026-03-28) — voir `ingestion-urssaf-masse-salariale.md`
- [x] Intégration URSSAF effectifs commune × APE — P1 implémenté (2026-03-28) — voir `ingestion-urssaf-effectifs.md`
- [x] Spike BMO : granularité FAP2021 vérifiée (2026-03-28) — M2Z n'existe plus, 6 codes IT par préfixe M1X/M2X, pas de distinction data/dev/infra, source validée. Voir `exploration-spike-bmo.md`
- [ ] Mise à jour `exploration-sources.md` avec sections B5-B7
- [ ] Mise à jour `structure-repo.md` avec nouveaux dossiers ingestion + dbt
- [ ] Mise à jour `architecture-datatalent.mermaid` avec sources complémentaires

---

*Détails d'exploration des sources (B1-B4) : voir `exploration-sources.md`.*
*Sources complémentaires data.gouv.fr (B5-B7) : voir `exploration-mcp-datagouv.md`.*
*Croisement des findings : voir `croisement-mcp-x-france-travail.md`.*
*Construction couche intermediate : voir `couche-intermediate-datatalent.md`.*
