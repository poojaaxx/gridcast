"""Real electricity load provider.

Wraps a generic hourly-demand REST API (e.g. EIA's "electricity/rto/region-data"
endpoint). Requires an API key. If the key is missing or the request fails for
any reason, callers should fall back to ``SyntheticElectricityProvider`` -
see ``app.ingestion.pipeline.get_electricity_provider``.
"""
from __future__ import annotations

import datetime as dt

import requests

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.base import LoadRecord

logger = get_logger(__name__)


class RealElectricityProvider:
    """Fetches real hourly load data from a configured HTTP API.

    This is intentionally generic: the exact upstream API used in production
    can vary by region/utility. GridCast ships with an EIA-compatible client;
    swap the ``_parse_response``/request params if you point it elsewhere.
    """

    name = "real"

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or settings.eia_api_key
        self.base_url = base_url or settings.eia_api_base_url
        if not self.api_key:
            raise ValueError("RealElectricityProvider requires an API key (EIA_API_KEY).")

    def fetch_load(
        self,
        *,
        latitude: float,
        longitude: float,
        start: dt.datetime,
        end: dt.datetime,
    ) -> list[LoadRecord]:
        params = {
            "api_key": self.api_key,
            "frequency": "hourly",
            "data[0]": "value",
            "start": start.strftime("%Y-%m-%dT%H"),
            "end": end.strftime("%Y-%m-%dT%H"),
        }
        url = f"{self.base_url}/electricity/rto/region-data/data/"
        try:
            response = requests.get(url, params=params, timeout=20)
            response.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Real electricity API request failed: %s", exc)
            raise

        payload = response.json()
        rows = payload.get("response", {}).get("data", [])
        records: list[LoadRecord] = []
        for row in rows:
            try:
                ts = dt.datetime.fromisoformat(row["period"]).replace(tzinfo=dt.timezone.utc)
                load_mw = float(row["value"])
            except (KeyError, ValueError, TypeError):
                continue
            records.append(LoadRecord(timestamp=ts, load_mw=load_mw, source=self.name))
        return records
