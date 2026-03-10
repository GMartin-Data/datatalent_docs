# Onboarding — Configuration Ruff

**Fichier :** `ruff.toml` (racine du repo)
**Rôle :** Convention de linting et formatting Python pour toute l'équipe.

---

## Pourquoi `ruff.toml` à la racine (et pas dans `ingestion/pyproject.toml`) ?

Ruff cherche sa config en remontant l'arborescence depuis le fichier linté. Avec `ruff.toml` à la racine :

- Tout fichier `.py` du repo est couvert, quel que soit son sous-dossier
- `ingestion/pyproject.toml` reste dédié aux dépendances Python → autonome pour Docker
- Pre-commit lance ruff depuis la racine → il trouve `ruff.toml` automatiquement

Voir `docs/decision-pyproject-ruff.md` pour le détail de cette décision.

---

## Paramètres expliqués

### `target-version = "py312"`

Ruff adapte ses règles à la version Python cible. Exemple concret : avec `py312`, la règle `UP` (pyupgrade) suggérera d'utiliser `type X = ...` (PEP 695) au lieu de `TypeAlias`. Doit rester cohérent avec `.python-version` à la racine.

### `line-length = 88`

La longueur max de ligne. Trois conventions courantes :

| Valeur | Origine | Usage |
|--------|---------|-------|
| 79 | PEP 8 strict | Trop agressif sur du code moderne (f-strings, type hints longs) |
| 88 | Black / Ruff (défaut) | Consensus actuel de l'écosystème Python |
| 120 | Google style | Trop permissif, lisibilité dégradée en split-screen |

On suit le défaut de l'écosystème. Pas de raison de diverger.

### `[lint] select`

Les rulesets activés. Chaque lettre correspond à un ensemble de règles :

| Code | Source | Ce que ça attrape |
|------|--------|-------------------|
| `E` | pycodestyle | Erreurs de style : espaces, indentation, lignes trop longues |
| `F` | pyflakes | Bugs probables : imports inutilisés, variables non définies, `except` trop large |
| `I` | isort | Tri et groupement automatique des imports — plus de débats en review |
| `UP` | pyupgrade | Syntaxe obsolète → suggestion de syntaxe moderne Python 3.12 |

C'est un point de départ conservateur. Rulesets à considérer plus tard :

- `B` (flake8-bugbear) — Patterns Python dangereux mais techniquement valides
- `SIM` (flake8-simplify) — Simplifications de code
- `PTH` (flake8-use-pathlib) — `pathlib.Path` au lieu de `os.path`

Pour ajouter un ruleset : modifier `select` dans `ruff.toml`, commit, et toute l'équipe l'a au prochain `git pull`.

### `[format] quote-style = "double"`

Le formatter Ruff (équivalent de Black) reformate automatiquement les guillemets. Convention explicite : doubles guillemets partout. Ça évite les discussions en review et garantit la cohérence.

---

## Qui lance ruff et quand ?

| Contexte | Qui lance ruff | Quelle version |
|----------|---------------|----------------|
| Pre-commit (à chaque `git commit`) | L'environnement isolé de pre-commit (`~/.cache/pre-commit/`) | Celle déclarée dans `.pre-commit-config.yaml` (`rev:`) |
| IDE / linting manuel | Le ruff installé dans `ingestion/.venv/` | Celle déclarée dans `ingestion/pyproject.toml` (`[dependency-groups] dev`) |

**Ces deux versions sont indépendantes.** Il faut les garder synchronisées manuellement. Lors d'un bump de version ruff, mettre à jour les deux fichiers dans le même commit.

---

## Commandes utiles

```bash
# Linting (depuis la racine)
ruff check .

# Linting + auto-fix
ruff check --fix .

# Formatting
ruff format .

# Vérifier sans modifier (CI)
ruff format --check .
```
