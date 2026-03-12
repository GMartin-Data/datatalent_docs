# Onboarding GCP — DataTalent

Bienvenue dans le projet DataTalent. Ce guide te permet de configurer ton poste de dev pour travailler sur le pipeline d'ingestion. Durée estimée : **15 minutes**.

## Ce qui est déjà en place

L'infrastructure GCP est créée. Tu n'as rien à provisionner. Voici ce qui t'attend :

| Ressource | Identifiant |
|---|---|
| Projet GCP | `datatalent-glaq-2` |
| Bucket GCS | `datatalent-glaq-2-raw` (europe-west1) |
| Datasets BigQuery | `raw`, `staging`, `intermediate`, `marts` |

Ton adresse Gmail a été autorisée sur le projet avec les rôles nécessaires (Storage, BigQuery, Secret Manager). Tu n'as besoin d'aucun fichier de clé — l'authentification passe par ton compte Google.

---

## Étape 1 — Installer le Google Cloud SDK

Le SDK inclut la commande `gcloud` utilisée pour l'authentification et toutes les interactions avec GCP.

### Linux (Debian/Ubuntu)

```bash
# Ajouter le dépôt Google Cloud
sudo apt-get update && sudo apt-get install -y apt-transport-https ca-certificates gnupg curl

curl https://packages.cloud.google.com/apt/doc/apt-key.gpg | sudo gpg --dearmor -o /usr/share/keyrings/cloud.google.gpg

echo "deb [signed-by=/usr/share/keyrings/cloud.google.gpg] https://packages.cloud.google.com/apt cloud-sdk main" | sudo tee /etc/apt/sources.list.d/google-cloud-sdk.list

sudo apt-get update && sudo apt-get install -y google-cloud-cli
```

### macOS

```bash
# Via Homebrew
brew install --cask google-cloud-sdk
```

### Windows

Télécharger l'installateur : https://cloud.google.com/sdk/docs/install#windows

Lancer `GoogleCloudSDKInstaller.exe` et suivre les instructions.

### ✅ Vérification

```bash
gcloud version
```

Tu dois voir le numéro de version. Exemple :

```
Google Cloud SDK 523.0.0
bq 2.1.13
core 2025.03.07
gsutil 5.33
```

Si la commande n'est pas trouvée, redémarre ton terminal ou ajoute le SDK à ton `PATH` (l'installateur indique comment).

---

## Étape 2 — S'authentifier avec gcloud

### 2a. Authentification générale

```bash
gcloud auth login
```

Un navigateur s'ouvre. Connecte-toi avec l'adresse Gmail qui t'a été communiquée.

### 2b. Configurer le projet par défaut

```bash
gcloud config set project datatalent-glaq-2
```

### 2c. Authentification Application Default Credentials (ADC)

C'est cette étape qui permet aux scripts Python de s'authentifier automatiquement auprès de GCS, BigQuery et Secret Manager, sans aucun fichier de clé.

```bash
gcloud auth application-default login
```

Un navigateur s'ouvre à nouveau. Connecte-toi avec la même adresse Gmail.

### ✅ Vérification

```bash
# Ton compte est bien actif
gcloud auth list

# Le projet est bien configuré
gcloud config get-value project
# Attendu : datatalent-glaq-2

# Tu peux lister le bucket
gcloud storage ls gs://datatalent-glaq-2-raw

# Tu peux lister les datasets BigQuery
bq ls --project_id=datatalent-glaq-2
# Attendu : raw, staging, intermediate, marts
```

Si une commande retourne une erreur `403 Forbidden`, contacte Greg — il s'agit probablement d'un rôle manquant sur ton compte.

---

## Étape 3 — Cloner le repo et installer les dépendances

```bash
git clone <URL_DU_REPO>
cd datatalent
```

Installer les dépendances Python :

```bash
# uv est le gestionnaire de paquets du projet
pip install uv
cd ingestion
uv sync
```

> **Note :** Les détails d'installation de `uv` et la structure du repo sont dans le `README.md` du projet.

### ✅ Vérification

```bash
uv run python -c "from google.cloud import storage; print('GCS OK')"
uv run python -c "from google.cloud import bigquery; print('BQ OK')"
```

Les deux commandes doivent afficher `GCS OK` et `BQ OK` sans erreur d'authentification.

---

## Résumé

| Étape | Action | Vérification |
|---|---|---|
| 1 | Installer Google Cloud SDK | `gcloud version` affiche un numéro |
| 2a | `gcloud auth login` | `gcloud auth list` montre ton compte |
| 2b | `gcloud config set project datatalent-glaq-2` | `gcloud config get-value project` |
| 2c | `gcloud auth application-default login` | `gcloud storage ls gs://datatalent-glaq-2-raw` |
| 3 | Cloner le repo + `uv sync` | Import Python GCS/BQ sans erreur |

## En cas de problème

| Symptôme | Cause probable | Solution |
|---|---|---|
| `gcloud: command not found` | SDK pas dans le PATH | Redémarrer le terminal ou ajouter manuellement |
| `403 Forbidden` sur une commande GCP | Rôle IAM manquant | Contacter Greg |
| `Could not automatically determine credentials` | ADC pas configuré | Relancer `gcloud auth application-default login` |
| Erreur d'import Python | Dépendances manquantes | Vérifier `uv sync` dans `ingestion/` |
