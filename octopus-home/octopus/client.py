"""Octopus Energy Agile tariff REST API client."""
import logging
from datetime import datetime, timezone

import httpx

from core.config import settings

logger = logging.getLogger(__name__)

OCTOPUS_BASE = "https://api.octopus.energy/v1"


class OctopusClient:
    """Async client for the Octopus Energy API."""

    def __init__(self) -> None:
        # API key used as Basic Auth username; password is blank
        auth = (settings.octopus_api_key, "") if settings.octopus_api_key else None
        self._client = httpx.AsyncClient(
            base_url=OCTOPUS_BASE,
            auth=auth,
            timeout=30.0,
        )

    async def get_agile_unit_rates(
        self,
        period_from: datetime | None = None,
        period_to: datetime | None = None,
        page_size: int = 100,
    ) -> list[dict]:
        """Fetch half-hourly unit rates for the configured Agile tariff.

        Returns a list of dicts with keys: valid_from, valid_to, value_inc_vat.
        Results are sorted ascending by valid_from.
        """
        url = (
            f"/products/{settings.octopus_product_code}"
            f"/electricity-tariffs/{settings.octopus_tariff_code}"
            f"/standard-unit-rates/"
        )
        params: dict = {"page_size": page_size}
        if period_from:
            params["period_from"] = period_from.isoformat()
        if period_to:
            params["period_to"] = period_to.isoformat()

        all_results: list[dict] = []
        next_url: str | None = url

        while next_url:
            if next_url == url:
                response = await self._client.get(next_url, params=params)
            else:
                # Subsequent pages include full URL
                response = await self._client.get(next_url)

            response.raise_for_status()
            data = response.json()
            all_results.extend(data.get("results", []))
            next_url = data.get("next")

        # Sort ascending by valid_from
        all_results.sort(key=lambda r: r["valid_from"])
        logger.info("Fetched %d Agile price slots from Octopus API", len(all_results))
        return all_results

    async def close(self) -> None:
        await self._client.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.close()


def parse_dt(s: str) -> datetime:
    """Parse ISO 8601 string from Octopus API to an aware UTC datetime."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    return dt.astimezone(timezone.utc)
