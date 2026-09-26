from __future__ import annotations

from typing import Any

import requests


class CDSEError(RuntimeError):
    """Raised when the Copernicus Data Space API request fails."""


class CDSEClient:
    """Client for the Copernicus Data Space STAC API."""

    def __init__(
        self,
        base_url: str = "https://stac.dataspace.copernicus.eu/v1",
        timeout: int = 60,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def search(
        self,
        collection: str,
        bbox: list[float],
        start: str,
        end: str,
        limit: int = 100,
        cloud_cover: float | None = None,
    ) -> dict[str, Any]:

        payload: dict[str, Any] = {
            "collections": [collection],
            "bbox": bbox,
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
            "limit": limit,
        }

        if cloud_cover is not None:
            payload["query"] = {
                "eo:cloud_cover": {
                    "lt": cloud_cover
                }
            }

        url = f"{self.base_url}/search"

        try:
            response = requests.post(
                url,
                json=payload,
                timeout=self.timeout,
            )
        except requests.RequestException as exc:
            raise CDSEError(
                f"Could not connect to Copernicus Data Space: {exc}"
            ) from exc

        if not response.ok:
            raise CDSEError(
                f"STAC request failed with HTTP "
                f"{response.status_code}: {response.text[:500]}"
            )

        try:
            return response.json()
        except ValueError as exc:
            raise CDSEError(
                "Copernicus returned a response that was not valid JSON."
            ) from exc