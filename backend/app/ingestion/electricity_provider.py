"""Real electricity load provider - U.S. Energy Information Administration (EIA).

Wraps EIA's "electricity/rto/region-data" v2 endpoint (Form EIA-930, Hourly
Electric Grid Monitor), filtered to a single balancing authority
(``settings.eia_respondent_code``) and a single metric (``type=D``, actual
Demand - not the "DF" day-ahead demand *forecast* series, which the
unfiltered endpoint also returns and which would corrupt a load history if
left unfiltered). Confirmed via the endpoint's own metadata that
``frequency=hourly`` timestamps are UTC-labeled ("hourly (UTC)"), so no
timezone conversion is applied here beyond attaching the UTC tzinfo.

See README "Data Sources" for why EIA (a U.S. source) was selected: an
Indian source could not be verified as a stable, machine-readable API within
this project's research, and the project's own instructions designate EIA as
the documented fallback in that case rather than fabricating or scraping an
alternative.

Requires an API key (``EIA_API_KEY``). If the key is missing or the request
fails for any reason, this raises - callers decide whether/when a fallback to
synthetic data is acceptable (see ``app.ingestion.pipeline``, which only ever
falls back to synthetic when the app is *not* configured for live mode; a
live-mode failure is surfaced as a failure, never silently masked).
"""
from __future__ import annotations

import datetime as dt

import requests

from app.core.config import settings
from app.core.logging import get_logger
from app.ingestion.base import LoadRecord

logger = get_logger(__name__)

# EIA's JSON API caps rows per request; paginate with offset for longer ranges.
PAGE_SIZE = 5000
# Hard ceiling on pages per call, purely as a runaway-loop safeguard - at
# PAGE_SIZE=5000 this covers ~28 years of hourly data in one fetch_load call.
MAX_PAGES = 50


class RealElectricityProvider:
    """Fetches real hourly actual-demand data for one EIA balancing authority."""

    name = "eia"

    def __init__(self, api_key: str | None = None, base_url: str | None = None, respondent_code: str | None = None):
        self.api_key = api_key or settings.eia_api_key
        self.base_url = base_url or settings.eia_api_base_url
        self.respondent_code = respondent_code or settings.eia_respondent_code
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
        """Fetch actual hourly demand for ``self.respondent_code`` in [start, end).

        ``latitude``/``longitude`` are accepted (per the shared provider
        Protocol used for weather colocation) but intentionally unused here:
        EIA identifies regions by balancing-authority code, not geographic
        coordinates, so the respondent is chosen via configuration rather
        than the lat/long GridCast otherwise uses for weather lookups.
        """
        url = f"{self.base_url}/electricity/rto/region-data/data/"
        records: list[LoadRecord] = []
        rejected = 0
        offset = 0

        for _ in range(MAX_PAGES):
            params = [
                ("api_key", self.api_key),
                ("frequency", "hourly"),
                ("data[0]", "value"),
                ("facets[respondent][]", self.respondent_code),
                ("facets[type][]", "D"),
                ("start", start.strftime("%Y-%m-%dT%H")),
                ("end", end.strftime("%Y-%m-%dT%H")),
                ("sort[0][column]", "period"),
                ("sort[0][direction]", "asc"),
                ("offset", str(offset)),
                ("length", str(PAGE_SIZE)),
            ]
            try:
                response = requests.get(url, params=params, timeout=20)
                response.raise_for_status()
            except requests.RequestException as exc:
                logger.error("EIA API request failed (respondent=%s): %s", self.respondent_code, exc)
                raise

            payload = response.json()
            api_response = payload.get("response", {})
            rows = api_response.get("data", [])
            if not rows:
                break

            for row in rows:
                parsed = self._parse_row(row)
                if parsed is None:
                    rejected += 1
                    continue
                records.append(parsed)

            offset += len(rows)
            total = int(api_response.get("total", 0) or 0)
            if offset >= total or len(rows) < PAGE_SIZE:
                break

        if rejected:
            logger.warning(
                "EIA provider: rejected %d malformed/invalid rows for respondent=%s", rejected, self.respondent_code,
            )
        return records

    def _parse_row(self, row: dict) -> LoadRecord | None:
        try:
            ts = dt.datetime.fromisoformat(row["period"]).replace(tzinfo=dt.timezone.utc)
            raw_value = row["value"]
            if raw_value is None:
                return None
            load_mw = float(raw_value)
        except (KeyError, ValueError, TypeError):
            return None

        # Real demand is never negative; EIA occasionally publishes null or
        # placeholder rows for very recent/unsettled hours - reject rather
        # than silently treating them as zero-demand observations.
        if load_mw < 0:
            return None

        return LoadRecord(timestamp=ts, load_mw=load_mw, source=self.name)
