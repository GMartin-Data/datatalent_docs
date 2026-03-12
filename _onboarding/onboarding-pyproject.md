# Onboarding — Configuration `ingestion/pyproject.toml`

**Fichier :** `ingestion/pyproject.toml`
**Rôle :** Déclarer le package Python d'ingestion, ses dépendances, et son build system.

---

## Pourquoi dans `ingestion/` et pas à la racine ?

Le repo DataTalent contient du Python (`ingestion/`), du dbt (SQL), du Terraform (HCL), et de la CI (YAML). Seul `ingestion/` est un package Python. Placer `pyproject.toml` dans `ingestion/` :

- Rend le dossier **auto-contenu pour Docker** : `COPY . /app` dans `ingestion/Dockerfile` embarque deps + lockfile sans contexte parent
- Évite la confusion "ce `pyproject.toml` gère quoi exactement ?"
- Sépare les responsabilités : dépendances dans `pyproject.toml`, config linting dans `ruff.toml` (racine)

---

## Anatomie du fichier

### `[project]` — Metadata (PEP 621)

```toml
[project]
name = "datatalent-ingestion"
version = "0.1.0"
description = "Pipeline d'ingestion DataTalent — France Travail, Sirene, Géo"
requires-python = ">=3.12"
```

Standard Python moderne (PEP 621). Toutes les metadata dans `pyproject.toml`, pas dans `setup.py` ou `setup.cfg`. Le champ `requires-python` doit être cohérent avec `.python-version` à la racine.

### `dependencies` — Dépendances de production

```toml
dependencies = [
    "google-cloud-bigquery>=3.25",
    "google-cloud-storage>=2.18",
    "httpx>=0.27",
    "tenacity>=9.0",
]
```

| Dépendance | Rôle dans le pipeline |
|------------|----------------------|
| `google-cloud-bigquery` | Client Python BigQuery — load des données depuis GCS vers les tables raw |
| `google-cloud-storage` | Client Python GCS — upload des fichiers extraits vers le bucket `datatalent-raw` |
| `httpx` | Client HTTP pour les appels API (France Travail, Géo). Choisi plutôt que `requests` : supporte l'async, meilleure API pour le streaming et les timeouts |
| `tenacity` | Décorateur de retry avec backoff exponentiel — convention projet (voir `CLAUDE.md` : "Retry réseau via tenacity") |

Ces 4 deps finissent dans l'image Docker de production.

### `[dependency-groups]` — Dépendances de développement

```toml
[dependency-groups]
dev = [
    "pytest>=8.0",
    "ruff>=0.11",
]
```

Syntaxe PEP 735, supportée nativement par `uv`. Ces deps ne sont **pas** installées en production (pas dans l'image Docker).

| Dépendance | Rôle |
|------------|------|
| `pytest` | Framework de tests |
| `ruff` | Linting/formatting en local et dans l'IDE. **Attention :** pre-commit utilise sa propre version de ruff, indépendante de celle-ci (voir `onboarding-ruff.md`) |

Pour installer avec les deps de dev :

```bash
cd ingestion
uv sync          # installe tout (prod + dev)
```

Pour installer sans (Docker, CI) :

```bash
uv sync --no-dev
```

### `[build-system]` — Build backend

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"
```

`hatchling` est le build backend par défaut de `uv`. Il remplace le vieux combo `setuptools` + `setup.py`. Léger, rapide, pas de configuration nécessaire pour notre cas d'usage. On n'a pas besoin de builder un wheel distribuable — c'est là parce que la spec PEP 621 le requiert.

---

## Ce qui n'est PAS dans ce fichier

| Élément | Où c'est configuré | Pourquoi |
|---------|-------------------|----------|
| Config ruff (`[tool.ruff]`) | `ruff.toml` à la racine | S'applique à tout le repo, pas seulement à `ingestion/` |
| Config pytest (`[tool.pytest]`) | Pas encore — à ajouter quand on écrit les tests | Restera dans ce fichier (pytest est spécifique à `ingestion/`) |

---

## Workflow quotidien

```bash
# Ajouter une dépendance de production
cd ingestion
uv add <package>              # modifie pyproject.toml + uv.lock

# Ajouter une dépendance de dev
uv add --group dev <package>

# Supprimer une dépendance
uv remove <package>

# Synchroniser après un git pull (si pyproject.toml a changé)
uv sync
```

**Règle d'or :** ne jamais éditer `uv.lock` manuellement. C'est `uv` qui le génère. Les deux fichiers (`pyproject.toml` + `uv.lock`) doivent toujours être committés ensemble.
