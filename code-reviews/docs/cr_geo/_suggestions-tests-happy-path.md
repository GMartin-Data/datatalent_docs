# Tests happy path — `ingestion-geo`

## `run()` — flux complet

1. **Les 3 resources sont ingérées** — `upload_to_gcs` et `load_gcs_to_bq` appelés 3 fois chacun (regions, departements, communes). C'est le test fondamental : il prouve que la boucle traverse tout.

2. **`upload_to_gcs` reçoit les bons arguments** — `(local_path, "geo")` pour chaque resource. Vérifie le respect du contrat `shared/`.

3. **`load_gcs_to_bq` reçoit les bons arguments** — `(gcs_uri, "raw", "geo_{resource}")` pour chaque resource. Même logique.

4. **Le fichier local est supprimé** après chaque resource — `os.path.exists` retourne `False` en fin de boucle.

5. **Le fichier local est au format JSONL** — contenu écrit = une ligne JSON par entrée, pas un tableau JSON. Vérifie que `"\n".join(json.dumps(row) ...)` produit le bon format.

## `fetch_geo_data()` — appel API isolé

6. **Retourne la liste désérialisée** — mock `httpx.get`, vérifie que le retour est bien `response.json()`.

7. **Passe le paramètre `fields` correct** — vérifie que `httpx.get` est appelé avec `params={"fields": RESOURCES[resource]}` pour chaque resource.

## Logging

8. **Événements clés loggés** — `ingestion_start`, `api_call` ×3, `local_file_written` ×3, `gcs_upload_ok` ×3, `bq_load_ok` ×3, `ingestion_end`. Moins critique que les 7 précédents, mais prouve que le monitoring fonctionne.

---

## Stratégie de mock

- **Mock `shared/`** (`upload_to_gcs`, `load_gcs_to_bq`) — c'est le contrat, pas l'implémentation.
- **Mock `httpx.get`** — on ne tape pas l'API réelle en test unitaire.
- **Ne pas mocker** `json.dumps`, `os.remove`, le filesystem `/tmp` — ce sont des détails internes, pas des frontières.