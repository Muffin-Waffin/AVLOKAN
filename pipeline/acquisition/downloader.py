from __future__ import annotations

from pathlib import Path

import requests


class DownloadError(RuntimeError):
    """Raised when an asset download fails."""


def download_asset(
    url: str,
    output_path: str | Path,
    *,
    timeout: int = 120,
    headers: dict[str, str] | None = None,
) -> Path:

    output_path = Path(output_path)

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".part"
    )

    request_headers = headers or {}

    try:

        with requests.get(
            url,
            headers=request_headers,
            stream=True,
            timeout=timeout,
        ) as response:

            if not response.ok:
                raise DownloadError(
                    f"Asset download failed "
                    f"(HTTP {response.status_code}): "
                    f"{response.text[:500]}"
                )

            with temporary_path.open("wb") as file:

                for chunk in response.iter_content(
                    chunk_size=1024 * 1024
                ):

                    if chunk:
                        file.write(chunk)

    except requests.RequestException as exc:

        if temporary_path.exists():
            temporary_path.unlink()

        raise DownloadError(
            f"Could not download asset: {exc}"
        ) from exc

    except Exception:

        if temporary_path.exists():
            temporary_path.unlink()

        raise

    temporary_path.replace(output_path)

    return output_path
