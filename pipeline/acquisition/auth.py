from __future__ import annotations

import os

import requests
from dotenv import load_dotenv


CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu"
    "/auth/realms/CDSE/protocol/openid-connect/token"
)


class CDSEAuthError(RuntimeError):
    """Raised when CDSE authentication fails."""


def get_access_token() -> str:
    """
    Authenticate against Copernicus Data Space Ecosystem
    and return an access token.
    """

    load_dotenv()

    username = os.getenv("CDSE_USERNAME")
    password = os.getenv("CDSE_PASSWORD")

    if not username:
        raise CDSEAuthError(
            "CDSE_USERNAME is not set in the environment."
        )

    if not password:
        raise CDSEAuthError(
            "CDSE_PASSWORD is not set in the environment."
        )

    payload = {
        "client_id": "cdse-public",
        "grant_type": "password",
        "username": username,
        "password": password,
    }

    try:
        response = requests.post(
            CDSE_TOKEN_URL,
            data=payload,
            timeout=30,
        )
    except requests.RequestException as exc:
        raise CDSEAuthError(
            f"Could not connect to CDSE authentication service: {exc}"
        ) from exc

    if not response.ok:
        try:
            error_data = response.json()
        except ValueError:
            error_data = response.text[:500]

        raise CDSEAuthError(
            f"CDSE authentication failed "
            f"(HTTP {response.status_code}): {error_data}"
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise CDSEAuthError(
            "CDSE authentication returned invalid JSON."
        ) from exc

    access_token = data.get("access_token")

    if not access_token:
        raise CDSEAuthError(
            "CDSE authentication succeeded but no access token was returned."
        )

    return access_token