from __future__ import annotations

from pathlib import Path

import requests

from pipeline.acquisition.auth import get_access_token


class ProductDownloadError(RuntimeError):
    """Raised when a CDSE product download fails."""


def download_product(
    product_url: str,
    output_path: str | Path,
    *,
    timeout: int = 300,
) -> Path:
    output_path = Path(output_path)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    temporary_path = output_path.with_suffix(
        output_path.suffix + ".part"
    )

    token = get_access_token()

    headers = {
        "Authorization": f"Bearer {token}"
    }

    try:
        with requests.get(
            product_url,
            headers=headers,
            stream=True,
            timeout=timeout,
        ) as response:

            if not response.ok:
                raise ProductDownloadError(
                    f"Product download failed "
                    f"(HTTP {response.status_code}): "
                    f"{response.text[:500]}"
                )

            total_size = response.headers.get("Content-Length")

            if total_size:
                total_size = int(total_size)
                print(
                    f"Expected download size: "
                    f"{total_size / (1024 ** 3):.2f} GB"
                )

            downloaded = 0

            with temporary_path.open("wb") as file:
                for chunk in response.iter_content(
                    chunk_size=8 * 1024 * 1024
                ):
                    if not chunk:
                        continue

                    file.write(chunk)
                    downloaded += len(chunk)

                    if total_size:
                        percent = (
                            downloaded / total_size
                        ) * 100

                        print(
                            f"\rDownloaded: "
                            f"{downloaded / (1024 ** 3):.2f} GB "
                            f"({percent:.1f}%)",
                            end="",
                            flush=True,
                        )

        print()

    except requests.RequestException as exc:
        if temporary_path.exists():
            temporary_path.unlink()

        raise ProductDownloadError(
            f"Could not download product: {exc}"
        ) from exc

    except Exception:
        if temporary_path.exists():
            temporary_path.unlink()

        raise

    temporary_path.replace(output_path)

    return output_path
