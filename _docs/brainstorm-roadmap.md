# Brainstorm Roadmap — Projet DataTalent

**Objectif :** Couvrir tous les sujets de réflexion ici (Claude.ai) avant de passer en production sur Claude Code.
**Output final :** Un document de cadrage technique à injecter dans Claude Code.

---

## Phase A — Architecture & décisions structurantes

### A1. Architecture GCP cible
- [x] Schéma des services : GCS, BigQuery, Cloud Run/Functions, Cloud Scheduler
- [x] Structure Medallion dans BigQuery (datasets raw / staging / marts)
- [x] Flux de données : ingestion → stockage → transformation → restitution
- [x] Gestion des secrets (Secret Manager vs variables d'environnement)
- [x] Gestion des accès (service accounts, IAM)

### A2. Structure du repo GitHub
- [x] Arborescence des dossiers (ingestion, dbt, infra, ci-cd, docs)
- [x] Conventions de nommage
- [x] Organisation des modules Terraform
- [x] Placement du Dockerfile et docker-compose

### A3. Mapping phases du brief → 3 blocs de 5 jours
- [x] Quoi livrer à la fin de chaque bloc
- [x] Dépendances entre blocs
- [x] Marge de manœuvre si retard

---

## Phase B — Exploration des sources de données

### B1. API France Travail
- [x] Inscription et obtention des credentials OAuth2
- [x] Mapping codes ROME pour "Data Engineer" (M1805, M1810, M1806, M1801)
- [x] Schéma de réponse de l'API (champs disponibles, champs utiles)
- [x] Stratégie de pagination (par département × par code ROME)
- [x] Rate limiting : limites connues, stratégie de backoff
- [x] Présence du SIRET dans les réponses (fréquence, fiabilité)

### B2. Stock Sirene INSEE
- [x] Format exact des fichiers Parquet sur data.gouv.fr
- [x] Volume brut vs volume après filtrage (codes NAF pertinents, statut actif)
- [x] Champs utiles pour le projet (SIRET, raison sociale, code NAF, adresse, statut)
- [x] Stratégie de chargement dans BigQuery (filtrage local avant upload vs chargement complet)

### B3. API Géo
- [x] Endpoints utiles (régions, départements, communes)
- [x] Schéma de réponse
- [x] Stratégie : snapshot complet en raw (D13)

### B4. Jointure inter-sources
- [x] Clé de jointure offres ↔ Sirene (SIRET — LEFT JOIN, taux estimé 20-40%, D14)
- [x] Plan B si SIRET absent (matching par nom reporté à Bloc 3 si nécessaire)
- [x] Enrichissement géographique via API Géo (code commune INSEE prioritaire, fallback code département, D15)

---

## Phase C — Choix technologiques à trancher

### C1. IaC : Terraform ✅
- [x] Différences pratiques pour ce projet → aucune (syntaxe identique à OpenTofu)
- [x] Disponibilité du provider GCP → `hashicorp/google` fonctionne avec les deux
- [x] Choix : Terraform (écosystème plus documenté, pas de contrainte licence) — voir D18

### C2. Orchestration de l'ingestion ✅
- [x] Cloud Run Job (batch one-shot) — pas Service (pas besoin de HTTP/FastAPI) — voir D19
- [x] Fréquence : hebdomadaire, cron `0 6 * * 1`
- [x] Entrypoint : `python main.py` (script séquentiel, pas FastAPI)

### C3. Outil de BI ✅
- [x] Looker Studio (natif GCP, gratuit) — voir D21
- [x] Contrainte du brief : dashboard accessible publiquement → lien de rapport partagé (natif Looker Studio)
- [x] Alternatives écartées : Metabase (overhead infra), Streamlit (tout à coder, 2-3 jours)

### C4. CI/CD ✅
- [x] GitHub Actions : 2 workflows (`ci.yml` sur PR, `deploy.yml` sur merge main) — voir D22
- [x] Jobs CI : lint Python (ruff + uv), dbt compile/test, terraform validate/fmt
- [x] Jobs deploy : build + push Docker Artifact Registry, gcloud run jobs update
- [x] Gestion des secrets GCP : service account key en GitHub Secret, `google-github-actions/auth@v2`
- [x] Pre-commit hooks : commitlint + ruff (filet de sécurité local, complémentaire au CI)

### C5. Conteneurisation ✅
- [x] Dockerfile single-stage (pas de multi-stage — pas d'étape de build) — voir D20
- [x] docker-compose : 2 services (ingestion + dbt)
- [x] Package manager : uv (`pyproject.toml` + `uv.lock`), image dbt officielle pour le service dbt

---

## Phase D — Stratégie d'équipe ✅

### D1. Découpage du travail à 4 ✅
- [x] Répartition hybride source → couche (Bloc 1 par source, Blocs 2-3 par compétence/livrable) — voir D23
- [x] Zones de conflit Git identifiées et ownership défini — voir D23
- [x] Convention de branching : `{type}/{scope}`, branches par feature, squash merge, main protégé — voir D24

### D2. Kanban / Trello ✅
- [x] User stories US1-US10 rédigées (voir `user-stories-datatalent.md`)
- [x] Tâches T0 (setup) + US1-US4 découpées pour Bloc 1 — US5-US10 visibles mais à découper pendant les pauses
- [x] Organisation : 1 sprint = 1 bloc de 5 jours, découpage un bloc d'avance (pas plus)
- [x] Syncs calibrés par topologie des dépendances (D24), doc de transition + kickoff entre blocs (D25)

---

## Phase E — Optimisation des coûts ✅

### E1. Analyse coûts et arbitrage architecture ✅
- [x] Estimation coûts par service GCP (BigQuery, GCS, Cloud Run, Scheduler, Secret Manager, Artifact Registry) — tout dans le free tier
- [x] Coût CI/CD GitHub Actions : gratuit (repo public), noté comme poste potentiel en repo privé
- [x] Transformation data lake (GCS/Python) évaluée et écartée (volumes insuffisants, perte de dbt)
- [x] Optimisations BQ retenues : partitioning, clustering, SELECT explicite
- [x] Sirene raw : WRITE_TRUNCATE au refresh Bloc 3 (pas d'accumulation de snapshots)
- [x] Monitoring coûts : billing export BQ + INFORMATION_SCHEMA + budget alerts Terraform
- [x] Voir D26 dans `notes-projet.md`

---

## Séquencement

| Ordre | Thème | Priorité | Bloquant pour |
|-------|-------|----------|---------------|
| 1 | A1 — Architecture GCP | Critique | Tout le reste |
| 2 | A3 — Mapping blocs/phases | Critique | Planification |
| 3 | B1-B4 — Exploration sources | Haute | Scripts d'ingestion |
| 4 | A2 — Structure repo | Haute | Début du code |
| 5 | C1-C5 — Choix technos | Moyenne | Phases 2+ |
| 6 | D1-D2 — Stratégie équipe | Moyenne | Bloc 1 en présentiel |
| 7 | E1 — Optimisation coûts | Moyenne | Document de cadrage |

---

**Toutes les phases A-E sont couvertes → prochaine étape : production du document de cadrage technique → injection dans Claude Code.**
