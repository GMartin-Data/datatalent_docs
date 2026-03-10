# Setup GCP manuel — Bloc 1

Ce guide couvre la création manuelle de l'infrastructure GCP nécessaire au Bloc 1 (ingestion).
Ces ressources seront importées dans Terraform au Bloc 2 (`terraform import`).

**Responsable :** Collègue 4 (T0.1, 0.5j)
**Région :** `europe-west1` (colocalisation données françaises, cohérence architecture)

## Prérequis

- Un compte Google avec facturation activée (carte bancaire requise, mais tout reste en free tier)
- `gcloud` CLI installé et authentifié

## Étape 1 — Créer le projet GCP

```bash
gcloud projects create datatalent --name="DataTalent"
gcloud config set project datatalent
```

Activer la facturation sur le projet (obligatoire même en free tier) :
Console → Billing → lier le projet au compte de facturation.

## Étape 2 — Activer les APIs nécessaires

```bash
gcloud services enable \
  storage.googleapis.com \
  bigquery.googleapis.com \
  secretmanager.googleapis.com
```

Seules ces 3 APIs sont nécessaires au Bloc 1. Cloud Run, Scheduler, Artifact Registry seront activés aux Blocs 2-3.

## Étape 3 — Créer le bucket GCS

```bash
gcloud storage buckets create gs://datatalent-raw \
  --location=europe-west1 \
  --default-storage-class=STANDARD \
  --uniform-bucket-level-access
```

Le bucket accueillera les 3 sous-dossiers créés automatiquement par les scripts d'ingestion :
`france_travail/`, `sirene/`, `geo/`.

## Étape 4 — Créer les datasets BigQuery

```bash
bq mk --dataset --location=europe-west1 datatalent:raw
bq mk --dataset --location=europe-west1 datatalent:staging
bq mk --dataset --location=europe-west1 datatalent:intermediate
bq mk --dataset --location=europe-west1 datatalent:marts
```

Seul `raw` est utilisé au Bloc 1. Les 3 autres sont créés maintenant pour que la structure soit visible et que dbt puisse être configuré dès la pause 1.

## Étape 5 — Créer le service account ingestion

```bash
gcloud iam service-accounts create sa-ingestion \
  --display-name="Service Account Ingestion"
```

Attribuer les rôles nécessaires :

```bash
PROJECT_ID=datatalent

# Lecture/écriture GCS
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:sa-ingestion@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/storage.objectAdmin"

# Chargement dans BigQuery (load jobs + écriture tables)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:sa-ingestion@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.dataEditor"

# Exécution de jobs BigQuery
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:sa-ingestion@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/bigquery.jobUser"

# Lecture des secrets (credentials France Travail)
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:sa-ingestion@${PROJECT_ID}.iam.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Étape 6 — Stocker les credentials France Travail dans Secret Manager

```bash
echo -n "ton_client_id" | gcloud secrets create ft-client-id \
  --data-file=- --replication-policy=user-managed \
  --locations=europe-west1

echo -n "ton_client_secret" | gcloud secrets create ft-client-secret \
  --data-file=- --replication-policy=user-managed \
  --locations=europe-west1
```

## Étape 7 — Générer une clé pour le dev local

Pour que les scripts locaux s'authentifient en tant que `sa-ingestion` :

```bash
gcloud iam service-accounts keys create sa-ingestion-key.json \
  --iam-account=sa-ingestion@datatalent.iam.gserviceaccount.com
```

Chaque dev configure ensuite :

```bash
export GOOGLE_APPLICATION_CREDENTIALS=/chemin/vers/sa-ingestion-key.json
```

**Ne jamais commiter ce fichier.** Il est dans le `.gitignore`.

## Vérification

```bash
# Bucket existe
gcloud storage ls gs://datatalent-raw

# Datasets existent
bq ls --project_id=datatalent

# Service account existe et a les bons rôles
gcloud projects get-iam-policy datatalent \
  --filter="bindings.members:sa-ingestion" \
  --format="table(bindings.role)"

# Secrets existent
gcloud secrets list
```

## Récapitulatif des ressources créées

| Ressource | Identifiant | Usage Bloc 1 |
|---|---|---|
| Projet | `datatalent` | Conteneur de tout |
| Bucket GCS | `datatalent-raw` (europe-west1) | Landing zone fichiers bruts |
| Dataset BQ | `raw` | Tables miroir GCS |
| Dataset BQ | `staging` | Placeholder (Bloc 2) |
| Dataset BQ | `intermediate` | Placeholder (Bloc 2) |
| Dataset BQ | `marts` | Placeholder (Bloc 2) |
| Service Account | `sa-ingestion` | Auth scripts d'ingestion |
| Secret | `ft-client-id` | Client ID OAuth2 France Travail |
| Secret | `ft-client-secret` | Client secret OAuth2 France Travail |

## Hors scope Bloc 1

- Cloud Run Job + Cloud Scheduler (Bloc 3)
- Artifact Registry (Bloc 3)
- Billing export + budget alerts (Bloc 3)
- Service account `sa-dbt` (Bloc 2)

## Décisions de référence

- D5 : structure BigQuery 4 datasets
- D6 : Secret Manager + IAM + service accounts
- D7 : Collègue 4 responsable du setup GCP
- D26 : free tier confirmé, europe-west1
