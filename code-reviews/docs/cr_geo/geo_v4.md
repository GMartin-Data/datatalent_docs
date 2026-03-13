# v4 (fix #1 + #2 + #4 + #5 + #6 + #12)

## `ingest.py`

```python
import json
import os

import httpx
from geo.config import BASE_URL, RESOURCES
from shared.bigquery import load_gcs_to_bq
from shared.gcs import upload_to_gcs
from shared.logging import get_logger
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = get_logger(__name__)


@retry(
    retry=retry_if_exception_type((httpx.TransportError, httpx.HTTPStatusError)),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    stop=stop_after_attempt(3),
    reraise=True,
)
def fetch_geo_data(resource):
    # --- [6] RESOURCES est maintenant un dict {resource: fields}.
    #     On passe ?fields=... à l'API pour ne récupérer que les
    #     champs utiles au projet. Sans ça, /communes retourne
    #     tous les champs dont contour (~34 Mo de polygones inutiles).
    url = f"{BASE_URL}/{resource}"
    params = {"fields": RESOURCES[resource]}
    logger.info(f"Appel API : {url}")
    response = httpx.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def run():
    for resource in RESOURCES:
        try:
            data = fetch_geo_data(resource)

            local_path = f"/tmp/geo_{resource}.json"
            jsonl_data = "\n".join(json.dumps(row) for row in data)

            with open(local_path, "w", encoding="utf-8") as f:
                f.write(jsonl_data)

            gcs_uri = upload_to_gcs(local_path, "geo")
            logger.info(f"Fichier GCS mis à jour : {gcs_uri}")

            table_id = f"geo_{resource}"

            load_gcs_to_bq(gcs_uri, "raw", table_id)
            logger.info(f"Table BQ mise à jour : raw.{table_id}")

            if os.path.exists(local_path):
                os.remove(local_path)

        except Exception as e:
            logger.error(f"Erreur ingestion {resource}: {e}", exc_info=True)


if __name__ == "__main__":
    run()
```

## `config.py`

```python
BASE_URL = "https://geo.api.gouv.fr"

# --- [6] RESOURCES passe de liste à dict {resource: fields}.
#     Clé = endpoint API, valeur = CSV des champs utiles au projet.
#     Seuls les champs documentés dans ingestion-geo.md sont listés —
#     ça évite de télécharger contour, siren, codeEpci, etc.
RESOURCES = {
    "regions": "code,nom,zone",
    "departements": "code,nom,codeRegion,zone",
    "communes": "code,nom,codesPostaux,codeDepartement,codeRegion,population,centre,surface",
}
```

## Corrections appliquées (cumulées)

1. **`upload_to_gcs(local_path, "geo")`** — signature contrat `shared/`.
2. **`load_gcs_to_bq(gcs_uri, "raw", table_id)`** — dataset `"raw"` au lieu du project ID.
4. **`@retry` tenacity sur `fetch_geo_data`** — 3 tentatives, backoff exponentiel, `reraise=True`.
5. **`BUCKET_NAME` et `DATASET_ID` supprimés** de `config.py` et de l'import.
6. **`RESOURCES` devient un dict `{resource: fields}`** — champs utiles explicités par endpoint, passés via `params={"fields": ...}` dans le GET.
12. **`httpx` remplace `requests`**.