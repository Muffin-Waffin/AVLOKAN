from pipeline.acquisition.cdse import CDSEClient


def test_cdse_client_url():
    client = CDSEClient(
        base_url="https://example.com/v1"
    )

    assert client.base_url == "https://example.com/v1"


def test_cdse_client_strips_trailing_slash():
    client = CDSEClient(
        base_url="https://example.com/v1/"
    )

    assert client.base_url == "https://example.com/v1"