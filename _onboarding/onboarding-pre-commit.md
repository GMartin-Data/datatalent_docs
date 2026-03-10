# Onboarding — Pre-commit

**Fichier :** `.pre-commit-config.yaml` (racine du repo)
**Rôle :** Exécuter automatiquement des vérifications sur le code avant chaque commit.

---

## Le concept en une phrase

Pre-commit intercepte `git commit`, lance des hooks de vérification, et **bloque le commit si un hook échoue**. Le code qui arrive sur `main` est garanti conforme aux conventions.

---

## Installation (à faire une seule fois après le clone)

```bash
pre-commit install
pre-commit install --hook-type commit-msg
```

**Les deux commandes sont nécessaires.** La première installe les hooks du stage `pre-commit` (ruff). La seconde installe le stage `commit-msg` (validation Conventional Commits). Sans la deuxième, les messages de commit ne sont jamais validés — c'est un piège classique.

---

## Nos hooks

### 1. `ruff` — Linting avec auto-fix

- **Quand :** stage `pre-commit` (avant le commit, sur les fichiers stagés)
- **Ce qu'il fait :** Détecte les erreurs de style, imports inutilisés, bugs probables. Corrige automatiquement ce qu'il peut (`--fix`).
- **Si un fichier est modifié :** Le commit est bloqué. C'est normal. Ruff a corrigé le fichier en place → vérifier les changements → re-stager (`git add`) → recommit.
- **Config :** `ruff.toml` à la racine (voir `onboarding-ruff.md`)

### 2. `ruff-format` — Formatting automatique

- **Quand :** stage `pre-commit`, après le linting
- **Ce qu'il fait :** Reformate le code (indentation, guillemets, longueur de ligne). Équivalent de Black, intégré dans ruff.
- **Même comportement :** Si le fichier change → commit bloqué → re-stager → recommit.

### 3. `conventional-pre-commit` — Validation du message de commit

- **Quand :** stage `commit-msg` (après rédaction du message, avant finalisation)
- **Ce qu'il fait :** Vérifie que le message respecte le format Conventional Commits.
- **Messages valides :** `feat: add OAuth2 client`, `fix(sirene): handle empty response`, `docs: update README`
- **Messages rejetés :** `added stuff`, `WIP`, `fix bug`

Format attendu :

```
type(scope): description

# type obligatoire, scope optionnel
# types courants : feat, fix, docs, chore, refactor, test, ci
```

---

## Workflow typique d'un commit

```
git add ingestion/shared/gcs.py
git commit -m "feat(ingestion): add GCS upload helper"
        │
        ▼
┌─ stage pre-commit ─────────────────┐
│  1. ruff check --fix               │
│     → OK ou modifie le fichier     │
│  2. ruff format                    │
│     → OK ou modifie le fichier     │
└────────────────────────────────────┘
        │
        ▼  (si fichiers modifiés → commit bloqué, re-stager)
        │
┌─ stage commit-msg ─────────────────┐
│  3. conventional-pre-commit        │
│     → valide le message            │
└────────────────────────────────────┘
        │
        ▼
   Commit créé ✓
```

Si un hook modifie un fichier, voici ce qui se passe concrètement :

```bash
$ git commit -m "feat(ingestion): add GCS upload helper"
ruff.....................................................Failed
- hook id: ruff
- files were modified by this hook

# Que faire :
$ git diff                    # voir ce que ruff a changé
$ git add -u                  # re-stager les fichiers modifiés
$ git commit -m "feat(ingestion): add GCS upload helper"   # recommit
```

---

## Environnement isolé — Point clé

Pre-commit **n'utilise pas le ruff de votre `.venv/`**. Il gère ses propres environnements dans `~/.cache/pre-commit/` :

1. Clone le repo du hook au tag spécifié (`rev:` dans le YAML)
2. Crée un environnement isolé
3. Installe l'outil dedans
4. Lance l'outil depuis cet environnement

Conséquence : il y a deux versions de ruff en jeu.

| Contexte | Version | Fichier source |
|----------|---------|----------------|
| Pre-commit | `rev: v0.11.6` | `.pre-commit-config.yaml` |
| IDE / terminal | `ruff>=0.11` | `ingestion/pyproject.toml` |

Lors d'un bump de version, mettre à jour les deux dans le même commit.

---

## Commandes utiles

```bash
# Lancer tous les hooks sur tous les fichiers (sans commit)
pre-commit run --all-files

# Lancer un hook spécifique
pre-commit run ruff --all-files
pre-commit run ruff-format --all-files

# Mettre à jour les versions des hooks
pre-commit autoupdate

# Bypasser les hooks (urgence uniquement — à éviter)
git commit --no-verify -m "hotfix: ..."
```

---

## Dépannage

| Symptôme | Cause probable | Solution |
|----------|---------------|----------|
| Le message de commit n'est jamais validé | `pre-commit install --hook-type commit-msg` manquant | Relancer la commande |
| `ruff` hook introuvable | Première exécution, cache vide | `pre-commit install` puis réessayer (le téléchargement est automatique) |
| Hook passe en local mais échoue en CI | Versions divergentes | Vérifier que CI utilise les mêmes `rev:` que le YAML |
| Fichier modifié par ruff à chaque commit | Code non conforme aux règles | Configurer l'IDE pour utiliser ruff en format-on-save |
