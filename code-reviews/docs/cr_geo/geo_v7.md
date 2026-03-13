# v7 (fix #1 + #2 + #4 + #5 + #6 + #7 + #8 + #9 + #10 + #12)

## `ingest.py`

```python
"""Ingestion source Géo — snapshots des référentiels géographiques français.

Récupère régions, départements et communes depuis l'API Géo (geo.api.gouv.fr),
dépose les fichiers JSON dans GCS et charge les tables raw dans BigQuery.
"""

import json
import os
from typing import Any

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
def fetch_geo_data(resource: str) -> list[dict[str, Any]]:
    """Fetch geographic reference data from the French government API.

    Args:
        resource: API endpoint name (key of RESOURCES in config.py).

    Returns:
        List of geographic entities as dictionaries.

    Raises:
        httpx.HTTPStatusError: on 4xx/5xx after retries exhausted.
        httpx.TransportError: on network failure after retries exhausted.
    """
    url = f"{BASE_URL}/{resource}"
    params = {"fields": RESOURCES[resource]}
    logger.info("api_call", url=url, resource=resource)
    response = httpx.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()


def run() -> None:
    """Ingest all geographic resources into BigQuery raw layer.

    Fetches regions, départements, and communes from the API Géo,
    uploads JSON snapshots to GCS, and loads them into BigQuery.

    Raises:
        RuntimeError: if at least one resource failed ingestion.
    """
    logger.info("ingestion_start", source="geo", resources=list(RESOURCES.keys()))

    errors: list[str] = []

    for resource in RESOURCES:
        try:
            data = fetch_geo_data(resource)

            local_path = f"/tmp/geo_{resource}.json"
            jsonl_data = "\n".join(json.dumps(row) for row in data)

            with open(local_path, "w", encoding="utf-8") as f:
                f.write(jsonl_data)
            logger.info("local_file_written", path=local_path, rows=len(data))

            gcs_uri = upload_to_gcs(local_path, "geo")
            logger.info("gcs_upload_ok", gcs_uri=gcs_uri)

            table_id = f"geo_{resource}"

            load_gcs_to_bq(gcs_uri, "raw", table_id)
            logger.info("bq_load_ok", table=f"raw.{table_id}")

            if os.path.exists(local_path):
                os.remove(local_path)

        except Exception as e:
            logger.error("ingestion_error", resource=resource, error=str(e), exc_info=True)
            errors.append(resource)

    if errors:
        logger.error("ingestion_partial_failure", failed=errors)
        raise RuntimeError(f"Ingestion failed for: {', '.join(errors)}")

    logger.info("ingestion_end", source="geo")


if __name__ == "__main__":
    run()
```

## `config.py`

```python
"""Configuration de la source Géo — endpoints et champs utiles."""

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
7. **Logging structuré** — kwargs structlog, événements nommés.
8. **Type hints + docstrings Google** — fonctions annotées, module docstrings ajoutées aux deux fichiers.
9. **Échecs partiels remontés** — `RuntimeError` en fin de `run()` si erreur.
10. **Logs début/fin** — `ingestion_start` et `ingestion_end` encadrent `run()`.
12. **`httpx` remplace `requests`**.