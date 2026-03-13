# v5 (fix #1 + #2 + #4 + #5 + #6 + #7 + #10 + #12)

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
    url = f"{BASE_URL}/{resource}"
    params = {"fields": RESOURCES[resource]}
    # --- [7] kwargs structlog au lieu de f-string.
    #     Les variables passées en kwargs sont exploitables
    #     dans les sinks (CloudWatch, BigQuery, etc.).
    logger.info("api_call", url=url, resource=resource)
    response = httpx.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def run():
    # --- [10] log début de run() avec liste des resources.
    logger.info("ingestion_start", source="geo", resources=list(RESOURCES.keys()))

    for resource in RESOURCES:
        try:
            data = fetch_geo_data(resource)

            local_path = f"/tmp/geo_{resource}.json"
            jsonl_data = "\n".join(json.dumps(row) for row in data)

            with open(local_path, "w", encoding="utf-8") as f:
                f.write(jsonl_data)
            # --- [7] log écriture locale.
            logger.info("local_file_written", path=local_path, rows=len(data))

            gcs_uri = upload_to_gcs(local_path, "geo")
            # --- [7] log upload GCS.
            logger.info("gcs_upload_ok", gcs_uri=gcs_uri)

            table_id = f"geo_{resource}"

            load_gcs_to_bq(gcs_uri, "raw", table_id)
            # --- [7] log load BQ.
            logger.info("bq_load_ok", table=f"raw.{table_id}")

            if os.path.exists(local_path):
                os.remove(local_path)

        except Exception as e:
            # --- [7] log erreur structuré.
            logger.error("ingestion_error", resource=resource, error=str(e), exc_info=True)

    # --- [10] log fin de run().
    logger.info("ingestion_end", source="geo")


if __name__ == "__main__":
    run()
```

## `config.py`

```python
BASE_URL = "https://geo.api.gouv.fr"

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
6. **`RESOURCES` dict `{resource: fields}`** — champs utiles explicités par endpoint.
7. **Logging structuré** — tous les `logger.*` utilisent des kwargs au lieu de f-strings. Événements nommés : `api_call`, `local_file_written`, `gcs_upload_ok`, `bq_load_ok`, `ingestion_error`.
10. **Logs début/fin** — `ingestion_start` et `ingestion_end` encadrent `run()`.
12. **`httpx` remplace `requests`**.