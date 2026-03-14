# Comparatif Solutions BI — Projet DataTalent

**Contexte :** Pipeline GCP end-to-end, marts BigQuery, équipe de 4, 3 blocs de 5 jours. Dashboard public obligatoire (US8).

---

## Critères d'évaluation

| # | Critère | Pourquoi c'est important |
|---|---------|--------------------------|
| 1 | **Connexion BigQuery** | Source unique = marts BQ. Le connecteur doit être natif ou trivial. |
| 2 | **Accès public** | Contrainte brief : lien dans le README, accessible sans compte. |
| 3 | **Coût** | Projet pédagogique, budget quasi nul. |
| 4 | **Infra à maintenir** | Chaque conteneur supplémentaire = Terraform + monitoring + debugging. |
| 5 | **Temps d'implémentation** | Bloc 3 = 5 jours pour IaC + CI/CD + dashboard + docs + démo. |
| 6 | **Interactivité** | Filtres, drill-down, carte géographique (axe géo du brief). |
| 7 | **Dépendances additionnelles** | Base metadata, reverse proxy, stockage persistant, etc. |
| 8 | **Cohérence stack** | Toute la stack est GCP — un outil hors écosystème doit se justifier. |
| 9 | **Argument soutenance** | Le formateur évalue les choix et leur justification, pas l'outil en soi. |

---

## Matrice comparative

| Critère | Looker Studio | Apache Superset | Metabase | Streamlit |
|---------|:------------:|:---------------:|:--------:|:---------:|
| **Connexion BQ** | Native (1 clic) | SQLAlchemy `bigquery://` + credentials JSON | Driver JDBC, config manuelle | `google-cloud-bigquery` Python |
| **Accès public** | Lien partagé natif | Possible (public role + reverse proxy), config non triviale | Reverse proxy + désactivation auth = bricolage | Cloud Run public, OK |
| **Coût** | Gratuit | Gratuit (open-source), mais infra Cloud Run/GCE payante | Gratuit (open-source), même problème infra | Gratuit (open-source), même problème infra |
| **Infra à maintenir** | Aucune | Conteneur applicatif + base PostgreSQL metadata + volume persistent + reverse proxy | Conteneur + base H2/PostgreSQL interne | Conteneur unique |
| **Temps d'implémentation** | ~1 jour | ~2-3 jours (deploy + config + metadata DB + dashboards) | ~2 jours (deploy + config + dashboards) | ~2-3 jours (code Python complet) |
| **Interactivité** | Filtres, drill-down, carte geo, cross-filtering | Très riche : SQL Lab, filtres, drill-down, carte deck.gl | Filtres, drill-down, carte, question builder | Maximal (Python), mais tout à coder |
| **Dépendances additionnelles** | Aucune | PostgreSQL (metadata), Redis (cache, optionnel), Celery (async, optionnel) | Aucune critique (H2 embarqué suffit) | Aucune |
| **Cohérence stack GCP** | Natif GCP | Outil tiers, pas d'intégration GCP spécifique | Outil tiers | Outil tiers |
| **Argument soutenance** | "Natif, gratuit, zéro maintenance" | "Puissant, mais pourquoi cette complexité ?" | "Pourquoi pas Looker Studio ?" | "C'est du dev, pas de la BI" |

---

## Analyse par solution

### Looker Studio

Le choix par défaut pour tout projet GCP + BigQuery. Zéro friction : on connecte les marts, on construit les visualisations, on partage le lien. Pas de conteneur, pas de Terraform, pas de base metadata.

**Limites réelles :** personnalisation CSS inexistante, pas de SQL Lab intégré, visualisations moins avancées que Superset. Mais aucune de ces limites n'impacte le livrable demandé (3 axes d'analyse + carte + filtres).

### Apache Superset

L'outil le plus puissant du comparatif sur le papier. SQL Lab intégré, visualisations riches (deck.gl pour la carto), extensible, open-source Apache Foundation. C'est l'outil qu'on choisirait en production pour une équipe data qui veut un Tableau-killer gratuit.

**Le problème ici :** Superset nécessite une base PostgreSQL pour ses métadonnées (utilisateurs, dashboards, connexions). En self-hosted sur Cloud Run, ça implique soit un Cloud SQL (payant, ~7€/mois minimum), soit un PostgreSQL conteneurisé (pas persistent sans volume, donc fragile). Le deploy n'est pas trivial : image Docker ~1.5 Go, variables d'environnement nombreuses (`SUPERSET_SECRET_KEY`, `SQLALCHEMY_DATABASE_URI`, init admin user, bootstrap DB). L'accès public nécessite la création d'un rôle Public avec permissions granulaires sur chaque dashboard — ce n'est pas un lien partagé en 1 clic.

**Temps réaliste :** 2-3 jours pour un deploy fonctionnel avec dashboard public. Sur un Bloc 3 de 5 jours qui doit aussi livrer IaC, CI/CD, docs et démo, c'est un risque majeur.

### Metabase

Plus simple que Superset à déployer (image Docker légère, H2 embarqué pour les métadonnées), mais l'accès public reste un point de friction (pas de "lien public" natif sans désactiver l'auth globalement ou configurer un embedding public). La connexion BigQuery passe par un driver JDBC à configurer manuellement.

### Streamlit

Ce n'est pas un outil de BI, c'est un framework Python pour construire des apps data. Chaque visualisation, chaque filtre, chaque interaction = du code Python. Le résultat peut être impressionnant mais le ratio temps/valeur est le pire du comparatif pour un dashboard standard à 3 axes.

---

## Synthèse décisionnelle

La question n'est pas "quel est le meilleur outil de BI" mais "quel outil livre le dashboard demandé dans les contraintes du projet".

| Contrainte projet | Impact sur le choix |
|-------------------|---------------------|
| 5 jours Bloc 3 (IaC + CI/CD + dashboard + docs + démo) | Élimine tout ce qui prend > 1 jour à déployer |
| Dashboard public obligatoire | Élimine les solutions sans partage natif simple |
| Budget ~0€ | Élimine Cloud SQL pour la metadata Superset |
| Stack full GCP | Favorise l'outil natif |
| Évaluation = justification des choix | "Natif + gratuit + zéro maintenance" > "puissant mais complexe" |

**Si le projet durait 6 mois avec une équipe data dédiée**, Superset serait un choix défendable. Dans le contexte DataTalent, c'est de l'over-engineering.

---

## Décision : Looker Studio (D21)

Looker Studio est retenu. La décision repose sur trois arguments :

1. **Zéro infra** — pas de conteneur, pas de base metadata, pas de Terraform additionnel. Le dashboard est hébergé par Google, maintenu par Google, scalé par Google.
2. **Accès public natif** — un paramètre dans l'interface, un lien dans le README. Contrainte brief satisfaite en 30 secondes.
3. **Budget temps** — ~1 jour de Bloc 3 libère 4 jours pour IaC, CI/CD, documentation et préparation démo. Avec Superset ou Metabase, le ratio s'inverse.

**Mention soutenance :** "En production, on migrerait vers Apache Superset pour le SQL Lab et les visualisations avancées. Pour ce projet, Looker Studio satisfait tous les critères du brief sans infra supplémentaire."

---

*Document produit le 14 mars 2026. Décision associée : D21 dans `notes-projet.md`.*
