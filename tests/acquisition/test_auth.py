import pytest

from pipeline.acquisition.auth import (
    CDSEAuthError,
    get_access_token,
)


def test_missing_credentials(monkeypatch):
    monkeypatch.setenv("CDSE_USERNAME", "")
    monkeypatch.setenv("CDSE_PASSWORD", "")

    with pytest.raises(CDSEAuthError):
        get_access_token()