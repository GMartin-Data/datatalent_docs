# Onboarding — uv

**Rôle :** Gestionnaire de packages et de versions Python. Remplace pip, pip-tools, pyenv et virtualenv en un seul outil.

---

## Installer uv

```bash
# Linux / macOS
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows
powershell -ExecutionPolicy BypassProcess -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Vérifier : `uv --version`

---

## Ce que uv gère automatiquement

| Responsabilité | Avant (outils séparés) | Avec uv |
|---|---|---|
| Version Python | pyenv, mise | Lit `.python-version`, télécharge si absent |
| Environnement virtuel | `python -m venv` | Crée `.venv/` automatiquement au premier `uv sync` |
| Dépendances | pip + requirements.txt | `pyproject.toml` + `uv.lock` |
| Lock déterministe | pip-tools, pip freeze | `uv.lock` (généré automatiquement) |
| Outils CLI globaux | pipx | `uv tool install` |

---

## Commandes quotidiennes dans DataTalent

### Installer / synchroniser les dépendances

```bash
cd ingestion
uv sync              # Installe tout (prod + dev)
uv sync --no-dev     # Installe prod uniquement (Docker)
```

`uv sync` fait tout d'un coup : vérifie Python, crée `.venv/` si nécessaire, installe les deps depuis `uv.lock`. C'est la commande à lancer après chaque `git pull` si `pyproject.toml` ou `uv.lock` ont changé.

### Ajouter / supprimer une dépendance

```bash
cd ingestion

# Dépendance de production
uv add httpx                     # ajoute dans [dependencies]
uv remove httpx                  # supprime

# Dépendance de développement
uv add --group dev pytest        # ajoute dans [dependency-groups] dev
uv remove --group dev pytest     # supprime
```

`uv add` et `uv remove` modifient `pyproject.toml` **et** regénèrent `uv.lock` en une seule opération. Toujours committer les deux fichiers ensemble.

### Exécuter du code dans l'environnement

```bash
cd ingestion

# Exécuter un script
uv run python main.py

# Lancer les tests
uv run pytest

# Lancer ruff manuellement
uv run ruff check .
uv run ruff format .

# Shell interactif
uv run python
```

`uv run` exécute la commande dans le `.venv/` du projet sans avoir à l'activer manuellement. Pas besoin de `source .venv/bin/activate`.

### Installer un outil CLI global

```bash
uv tool install pre-commit       # accessible partout
uv tool install ruff             # si besoin de ruff hors projet
uv tool list                     # voir les outils installés
```

Équivalent de `pipx install`. Les outils sont dans `~/.local/bin/`, isolés les uns des autres et du projet.

---

## Fichiers uv dans le repo

| Fichier | Rôle | Versionné ? |
|---|---|---|
| `ingestion/pyproject.toml` | Déclare les dépendances | Oui |
| `ingestion/uv.lock` | Lock déterministe (versions exactes + hashes) | Oui |
| `ingestion/.venv/` | Environnement virtuel local | Non (`.gitignore`) |
| `.python-version` | Version Python cible | Oui (racine du repo) |

**Règle d'or :** ne jamais éditer `uv.lock` manuellement. C'est `uv` qui le génère.

---

## Différences avec pip

| Situation | pip | uv |
|---|---|---|
| Installer les deps | `pip install -r requirements.txt` | `uv sync` |
| Ajouter une dep | Éditer requirements.txt + `pip install` | `uv add <package>` |
| Lock des versions | `pip freeze > requirements.txt` | Automatique via `uv.lock` |
| Reproductibilité | Fragile (pas de vrai lock) | Garantie (hashes dans `uv.lock`) |
| Exécuter un script | Activer le venv d'abord | `uv run python script.py` |
| Vitesse | Lent (résolution en Python) | 10-100x plus rapide (écrit en Rust) |

---

## Dépannage

| Symptôme | Cause probable | Solution |
|---|---|---|
| `uv sync` télécharge Python | Version demandée par `.python-version` absente | Normal au premier run, automatique |
| `uv run` dit "no such command" | Pas dans le bon dossier | `cd ingestion` puis réessayer |
| Conflit de deps après `git pull` | `uv.lock` modifié par un collègue | `uv sync` (il relit le lock) |
| `uv add` échoue sur une version | Version incompatible avec `requires-python` | Vérifier la compatibilité Python 3.12 du package |
