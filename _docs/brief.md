# Pitch
Vous êtes Data Engineer chez DataTalent, une startup spécialisée dans l'analyse du marché de l'emploi tech. Votre mission : concevoir et construire un pipeline de données complet sur le cloud pour répondre à la question "Où recrute-t-on des Data Engineers en France, dans quelles entreprises et à quels salaires ?", en ingérant automatiquement trois sources de données publiques et en restituant les résultats dans un tableau de bord exploitable par l'équipe produit.

# Ressources
- [Documentation officielle dbt-core](https://docs.getdbt.com/)
- [API France Travail - Guide Développeur](https://francetravail.io/data/api/offres-emploi)
- [Stock Sirene INSEE](https://www.insee.fr/fr/information/3591226)
- [API Géo](https://geo.api.gouv.fr/decoupage-administratif)
- [OpenTofu (alternative open-source à Terraform)](https://opentofu.org/docs/)
- [Terraform Registry](https://registry.terraform.io/browse/providers)
- [Infracost](https://www.infracost.io/docs/)
- [Trello - gestion de projet agile](https://trello.com/)

# Contexte du projet
DataTalent est une startup spécialisée dans l'analyse du marché de l'emploi tech. Son équipe produit publie des rapports trimestriels à destination des candidats et des recruteurs dans la data. Jusqu'à présent, la collecte et le traitement des données sont entièrement manuels : un analyste télécharge chaque semaine des fichiers depuis plusieurs sites, les consolide dans des tableurs, et produit des graphiques à la main. Le processus est long, fragile et non reproductible.

Face à la croissance du volume de données et à la demande de fraîcheur des informations, le CTO a décidé d'industrialiser ce processus. Il vous confie la mission de concevoir et de construire une infrastructure data complète sur un fournisseur cloud au choix, capable d'ingérer automatiquement les données, de les transformer en données analytiques fiables, et de les restituer dans un tableau de bord accessible à l'équipe produit.

La question centrale à laquelle votre pipeline devra permettre de répondre est : "Où recrute-t-on des Data Engineers en France, dans quelles entreprises et à quels salaires ?"

Vous disposez de trois sources de données publiques :

- [**L'API France Travail**](https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search) (ex Pôle Emploi) : offres d'emploi publiées en temps réel sur l'ensemble du territoire. L'accès nécessite une authentification OAuth2. Les offres sont interrogeables par codes ROME (familles de métiers) et par département. Le volume varie selon les périodes.

- [**Le stock Sirene de l'INSEE**](https://www.data.gouv.fr/datasets/base-sirene-des-entreprises-et-de-leurs-etablissements-siren-siret/) : registre national des entreprises et établissements français, distribué sous forme de fichiers Parquet mis à jour mensuellement. Il contient les raisons sociales, codes NAF, adresses et statuts juridiques de l'ensemble des entités économiques du pays. Le volume est conséquent (plusieurs gigaoctets).

- [**L'API Géo du gouvernement**](https://geo.api.gouv.fr/) : référentiels officiels des régions, départements et communes françaises, en accès libre et sans authentification. Elle permet d'enrichir les données géographiques avec des coordonnées et des codes INSEE normalisés.

Votre architecture devra respecter le pattern Medallion en trois couches (raw : données brutes, staging : données nettoyées et typées, marts : données agrégées prêtes pour l'analyse). L'ensemble de l'infrastructure cloud devra être provisionné via de l'Infrastructure as Code (IaC) versionné dans Git. L'ingestion devra être automatisée et planifiée sans intervention manuelle.

# Modalités pédagogiques
## Phase 1 — Cadrage, cartographie et ingestion initiale (J1-J2)
- Avant d'écrire la moindre ligne de code, organisez votre travail en mode agile : créez un tableau Kanban (Trello ou équivalent) avec vos user stories et découpez-les en tâches. 
- Documentez les trois sources de données :
    - format,
    - volume estimé,
    - fréquence de mise à jour,
    - qualité apparente,
    - contraintes d'accès.
- Quels champs sont communs entre les offres France Travail et le registre Sirene ? Comment envisagez-vous de les relier ?
- Choisissez votre fournisseur cloud et créez votre espace de travail : un bucket de stockage objet et un entrepôt de données.
- Réalisez une première ingestion manuelle des fichiers Sirene et de l'API Géo pour valider votre accès.

## Phase 2 — Automatisation de l'extraction (J3-J5)
Développez les scripts Python d'ingestion pour les trois sources. 
- Comment allez-vous gérer l'authentification OAuth2 de France Travail (expiration du token, mise en cache) ?
- Comment paginer les résultats sur les 101 départements sans déclencher de rate limiting ?
- Comment charger efficacement des fichiers Parquet de plusieurs gigaoctets vers l'entrepôt de données ?

Vos scripts doivent:
- gérer les erreurs,
- journaliser les exécutions
- être idempotents.

## Phase 3 — Transformation des données (J6-J9)
- Modélisez vos transformations SQL en trois couches :
    - staging (nettoyage et typage par source),
    - intermediate (jointure entre les offres et les entreprises Sirene)
    - marts (agrégats thématiques pour le dashboard). 
- Quels tests de qualité allez-vous mettre en place ? 
- Comment documentez-vous le lignage de vos données ?
- Votre modèle final doit permettre de répondre à la question centrale du projet.

## Phase 4 — Infrastructure, coûts et CI/CD (J10-J12)
- Provisionnez l'ensemble de votre infrastructure cloud avec un outil d'Infrastructure as Code (IaC) :
    - stockage objet,
    - entrepôt de données,
    - conteneur serverless,
    - ordonnanceur,
    - gestion des accès,
    - gestionnaire de secrets.
- Comment organisez-vous vos modules pour qu'ils soient réutilisables ? 
- Estimez et documentez les coûts de votre infrastructure à l'aide d'un outil d'estimation (ex : Infracost ou l'estimateur de coûts de votre fournisseur cloud) :
    - quelles ressources coûtent le plus cher ?
    - Quels leviers actionnez-vous pour optimiser les dépenses (requêtes ciblées, partitionnement, mise en veille des ressources inutilisées) ? 
- Configurez un pipeline CI/CD avec au minimum :
    - validation du code Python (lint),
    - compilation des transformations SQL,
    - validation de l'IaC sur les PR,
    - déploiement automatique sur la branche principale.

## Phase 5 — Dashboard analytique, gouvernance et coûts (J13-J15)
- Connectez un outil de BI à vos marts et produisez un tableau de bord répondant à la question centrale avec au moins trois angles d'analyse (géographique, sectoriel, temporel). 
- Produisez également un tableau de bord de suivi des coûts cloud :
    - coût par service,
    - évolution dans le temps,
    - alertes sur les dépassements de budget. 
- Documentez vos données dans un catalogue :
    - descriptions des tables,
    - propriétaires,
    - tags de sensibilité.    
- Préparez une démonstration de cinq minutes de votre pipeline de bout en bout. NB: La gouvernance est un bonus.

# Modalités d'évaluation
Démonstration technique (70 %) : l'apprenant présente son pipeline en conditions réelles pendant 15 minutes. Il démarre depuis le repo GitHub, montre l'exécution d'un script d'ingestion, déclenche un run, et navigue dans le dashboard final. Le formateur peut poser des questions sur n'importe quelle partie du code.

Revue de code et architecture (30 %) : le formateur consulte le repo GitHub et évalue la lisibilité du code, la qualité des tests, la structure IaC et la documentation. L'apprenant dispose de 10 minutes pour expliquer ses choix d'architecture, les compromis retenus et la maîtrise des coûts. Il devra justifier pourquoi certaines opérations coûtent plus cher que d'autres et comment il a optimisé les dépenses.

Un apprenant dont le pipeline ne fonctionne pas en démonstration mais dont le code est structuré et documenté peut valider partiellement les compétences concernées.

# Livrables
1. Repo GitHub public contenant l'intégralité du projet :
    - Scripts Python d'ingestion (avec .env.example et requirements.txt)
    - Modèles de transformation SQL organisés en staging / intermediate / marts avec tests et documentation
    - Modules IaC pour le stockage objet, l'entrepôt de données, le conteneur serverless et l'ordonnanceur
    - Workflows CI/CD (validation sur PR, déploiement sur main, jobs planifiés)
    - Dockerfile / docker-compose
    - README complet : description du projet, architecture, fournisseur cloud choisi, instructions de déploiement, auteur
    - Tableau de bord analytique accessible publiquement (lien dans le README) répondant à la question centrale

2. Tableau de bord de suivi des coûts cloud :
    - coût par service,
    - évolution dans le temps,
    - alertes budget

3. Documentation du catalogue de données :
    - descriptions des tables,
    - sources,
    - fréquences de mise à jour
    - tags

4. Schéma d'architecture (format image ou draw.io) représentant le flux de données de l'ingestion au dashboard

5. Tableau Kanban (Trello ou équivalent) accessible publiquement, avec les user stories organisées par sprint et l'historique des tâches réalisées (lien dans le README)

# Critères de performance
## Cartographier les données
- Les trois sources sont documentées (format, volume, fréquence, contraintes d'accès)
- Les champs de jointure entre sources sont identifiés et justifiés
- Les limites de qualité des données sont mentionnées

## Concevoir le cadre technique
- Le schéma d'architecture représente l'ensemble des composants cloud et leurs interactions
- Les choix technologiques (fournisseur cloud, outils de transformation, IaC) sont justifiés dans le README
- Le pattern Medallion est correctement appliqué (raw / staging / marts)

## Automatiser l'extraction
- Les trois sources sont ingérées par des scripts Python fonctionnels
- L'authentification OAuth2 France Travail est gérée avec mise en cache du token
- Les scripts gèrent les erreurs et journalisent les exécutions
- L'ingestion est planifiée sans intervention manuelle (ordonnanceur + conteneur serverless)

## Développer des requêtes SQL
- Les modèles de transformation produisent des résultats corrects et vérifiables
- Des tests sont définis sur les champs critiques (not_null, unique, accepted_values)
- Les requêtes sur l'entrepôt de données utilisent le partitionnement et le clustering disponibles

## Intégrer les ETL
- Le pipeline de transformation s'exécute sans erreur de bout en bout
- Le pipeline CI/CD exécute lint + compilation SQL + validation IaC sur chaque PR
- Le déploiement sur main est automatisé

## Intégrer les composants d'infrastructure
- L'infrastructure est entièrement provisionnée par IaC (aucune ressource créée manuellement)
- Les secrets ne sont pas exposés dans le code (gestionnaire de secrets ou variables d'environnement)
- Le Dockerfile est fonctionnel et le job s'exécute correctement en conteneur
- Un tableau de bord de suivi des coûts cloud est produit et documenté

## Gérer le catalogue
- Les tables marts sont documentées (description, propriétaire, fréquence)
- Le lignage des données est visible (outil de documentation ou catalogue)
- Les données sensibles sont identifiées et taguées