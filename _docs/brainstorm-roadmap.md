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

### B1. API France Travail ✅ (exploration complétée 2026-03-24)
- [x] Inscription et obtention des credentials OAuth2
- [x] Mapping codes ROME pour "Data Engineer" (M1805, M1810, M1806, M1801)
- [x] Schéma de réponse de l'API (champs disponibles, champs utiles)
- [x] Stratégie de pagination (par département × par code ROME)
- [x] Rate limiting : **10 req/s** (constaté, remplace 3 req/s de la doc obsolète) — voir D10
- [x] Présence du SIRET : **absent de 100% des offres** — voir D14-bis
- [x] **Exploration Axe 1 :** 9 matchs D8 (0.3%) → D8-bis : garder 2589 offres IT, classifier par `categorie_metier` (20 offres data)
- [x] **Exploration Axe 2 :** taux de présence confirmés — codeNAF 47.8% (biaisé intérim 38.3%), salaire.libelle 29.6% (100% parsable, 6 patterns), entreprise.nom 36.2%
- [x] **Exploration Axe 3 :** 99/101 départements couverts, code_commune 92.7%, fallback département 100%, 100% concordance croisée
- [x] **Adzuna évaluée et écartée :** scope creep hors brief, déduplication irrésoluble, salaires estimés ML, double staging

### B2. Stock Sirene INSEE ✅ (rôle repositionné post-exploration)
- [x] Format exact des fichiers Parquet sur data.gouv.fr — confirmé via MCP : StockEtablissement 2 Go, 54 colonnes, colonne NAF2025 présente
- [x] Volume brut vs volume après filtrage (codes NAF pertinents, statut actif)
- [x] Champs utiles pour le projet (SIRET, raison sociale, code NAF, adresse, statut)
- [x] Stratégie de chargement dans BigQuery (chargement complet, D11)
- [x] **Rôle repositionné :** livrable technique (démonstration dbt sur source volumineuse) — aucune jointure intermediate (D14-bis). Enrichissement sectoriel via codeNAF offre + URSSAF (D35)

### B3. API Géo
- [x] Endpoints utiles (régions, départements, communes)
- [x] Schéma de réponse
- [x] Stratégie : snapshot complet en raw (D13)

### B4. Jointure inter-sources ✅ (révisé post-exploration)
- [x] ~~Clé de jointure offres ↔ Sirene (SIRET — LEFT JOIN, taux estimé 20-40%, D14)~~ **CADUQUE** — SIRET absent à 100% (D14-bis)
- [x] ~~Plan B si SIRET absent (matching par nom reporté à Bloc 3)~~ **Reporté sine die** — effort disproportionné (intérimaires dominants, casse incohérente)
- [x] Enrichissement géographique via API Géo : code_commune 92.7%, fallback département 100%, 100% concordance (D15, confirmé Axe 3)
- [x] **Nouvelle jointure contextuelle :** URSSAF effectifs commune × APE → densité sectorielle IT par commune (D35)
- [x] **Nouvelle jointure contextuelle (conditionnelle) :** BMO → tensions recrutement IT par département (D35, spike requis)
- [x] **Enrichissement sectoriel :** codeNAF directement dans l'offre (47.8%) + URSSAF comme contrepoint non biaisé

### B5. Sources complémentaires — exploration MCP data.gouv.fr ✅ (2026-03-25)
- [x] Exploration systématique via MCP `mcp.data.gouv.fr` — 8 sources évaluées
- [x] **URSSAF effectifs commune × APE (P1)** : dataset `5efd242c72595ba1a48628f2`, API Opendatasoft, NAF5 × commune, depuis 2006 — **retenue, ingérer** (~3-4h)
- [x] **BMO France Travail (P2)** : dataset `561fa564c751df4f2acdbb48`, XLSX annuel, FAP2021 × bassin d'emploi — **retenue, spike d'abord** (~1h+)
- [x] **URSSAF masse salariale × NA88 (P3)** : dataset `61d784a161825aaf438b8e9e`, ~30 lignes, NA88=62 — **retenue, ingérer** (workflow classique, ~1h)
- [x] **BTS INSEE écartée** : NAF agrégé A17 (`J`), granularité insuffisante
- [x] **APEC écartée** : XLSX "humain" (37 onglets, 1 lisible), données 2021, aucune ventilation fonction
- [x] **DARES emplois vacants écartée** : indicateur macro par grand secteur, pas de granularité métier
- [x] APIs projet confirmées via `search_dataservices` : France Travail, Recherche Entreprises, API Géo — aucun changement d'URL
- [x] Voir `exploration-mcp-datagouv.md`, `croisement-mcp-x-france-travail.md`

### B6. Architecture dbt post-exploration ✅
- [x] ~~Seeds dbt pour tables référentielles < 1000 lignes (D36)~~ — ANNULÉE (2026-03-27), toutes sources en workflow classique d'ingestion
- [x] Filtrage codes APE IT à l'ingestion URSSAF (D37) — écart assumé avec Medallion
- [x] 3 tables intermediate : `int_offres_enrichies`, `int_densite_sectorielle_commune`, `int_tensions_bassin_emploi` (conditionnel)
- [x] 2 marts : `mart_offres`, `mart_contexte_territorial` — remplacent les 3 marts par axe
- [x] Voir `couche-intermediate-datatalent.md`

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
- [x] User stories US1-US11 rédigées (voir `user-stories-datatalent.md`)
- [x] US12 ajoutée : ingestion sources complémentaires (D35) — 15 tâches, P3 → P1 → P2
- [x] US5-US6 précisées post-exploration : tâches détaillées avec estimations
- [x] Tâches T0 (setup) + US1-US4 découpées pour Bloc 1
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

| Ordre | Thème | Priorité | Statut |
|-------|-------|----------|--------|
| 1 | A1 — Architecture GCP | Critique | ✅ Complété |
| 2 | A3 — Mapping blocs/phases | Critique | ✅ Complété |
| 3 | B1-B3 — Exploration sources brief | Haute | ✅ Complété |
| 4 | A2 — Structure repo | Haute | ✅ Complété — mis à jour post-exploration (D35) |
| 5 | C1-C5 — Choix technos | Moyenne | ✅ Complété |
| 6 | D1-D2 — Stratégie équipe | Moyenne | ✅ Complété — US12 ajoutée |
| 7 | E1 — Optimisation coûts | Moyenne | ✅ Complété |
| 8 | B4 — Jointures inter-sources | Haute | ✅ **Révisé** — SIRET mort, URSSAF + BMO ajoutés |
| 9 | B5 — Sources complémentaires data.gouv.fr | Haute | ✅ Exploration terminée — 3 retenues, 4 écartées |
| 10 | B6 — Architecture dbt post-exploration | Haute | ✅ Intermediate + marts redesignés |

---

**Toutes les phases A-E sont couvertes. L'exploration post-Bloc 1 (B4-B6) a révisé l'architecture des jointures et ajouté 3 sources. Prochaines étapes : ingestion des sources complémentaires (US12) puis implémentation dbt staging/intermediate/marts (US5-US6).**

---

*Documents de référence :*
- *Décisions : `notes-projet.md` (D1-D37)*
- *Sources brief (B1-B4) : `exploration-sources.md`*
- *Sources complémentaires (B5-B7) : `exploration-mcp-datagouv.md`*
- *Croisement findings : `croisement-mcp-x-france-travail.md`*
- *Architecture dbt intermediate : `couche-intermediate-datatalent.md`*
- *Architecture Mermaid : `architecture-datatalent.mermaid` + `architecture-datatalent-details.md`*
- *Explorations France Travail : `exploration-axe1-volume-filtrage.md`, `exploration-axe2-taux-presence.md`, `exploration-axe3-distribution-geo.md`*
