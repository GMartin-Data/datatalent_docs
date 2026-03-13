# ADR — Raw complet vs sélection de colonnes à l'ingestion Sirene

## Contexte

La PR ingestion-sirene filtre ~28 colonnes sur ~100+ disponibles dans le Parquet StockEtablissement avant écriture locale. La décision D11 prescrit un chargement complet sans sélection de colonnes. La question : D11 est-il le bon choix, ou le filtrage a-t-il des mérites ?

## Arguments pour filtrer en raw

- **Lisibilité** — un schéma raw de 28 colonnes est plus facile à naviguer qu'un schéma de 100+
- **Performance dbt** — staging scanne moins de colonnes, réduction du volume traité par requête
- **Coût BQ à l'échelle** — sur un projet prod avec des volumes réels, chaque colonne scannée a un coût en bytes facturés

## Arguments pour le raw complet (D11)

- **Filet de sécurité** — si une colonne non retenue s'avère nécessaire en Bloc 2/3, il suffit de l'ajouter dans le modèle dbt staging. Pas besoin de modifier le code d'ingestion, re-déployer, re-ingérer
- **Séparation des responsabilités** — l'ingestion copie fidèlement la source, dbt décide quoi garder. Chaque couche a un rôle clair
- **Auditabilité** — le raw reflète exactement ce que la source fournit, sans transformation implicite

## Ce qui tranche dans le contexte DataTalent

| Facteur | Impact |
|---------|--------|
| Coût stockage BQ | Zéro (free tier) |
| Coût scan BQ | Négligeable (staging = seul consommateur du raw, SELECT explicite en dbt) |
| Coût d'une colonne manquante en Bloc 2 | ~0.5j de retravail (modifier ingestion + re-déployer + re-ingérer) |
| Re-téléchargement Sirene | Possible (snapshot public mensuel) mais évitable |
| Équipe | 4 devs, ownership croisée entre blocs — minimiser les retours en arrière |

## Décision

**Raw complet confirmé (D11 maintenu).** Le coût de stockage est nul, le risque de colonne manquante est réel, et la séparation ingestion/transformation est un standard du pattern Medallion.

## Note

Le travail d'exploration du collègue (identification des ~28 colonnes utiles) n'est pas perdu — c'est exactement l'input nécessaire pour le modèle `stg_sirene` en dbt (Bloc 2). La liste des colonnes dans `config.py` peut être conservée comme référence pour le staging.