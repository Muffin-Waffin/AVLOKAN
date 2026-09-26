from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

from huggingface_hub import hf_hub_download

from pipeline.embeddings.remoteclip import CHECKPOINT_NAME, CHECKPOINT_SHA256, HF_REPO


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the pinned official RemoteCLIP checkpoint.")
    parser.add_argument("--output-dir", default="models/remoteclip")
    args = parser.parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    path = Path(hf_hub_download(
        repo_id=HF_REPO,
        filename=CHECKPOINT_NAME,
        revision="main",
        local_dir=output_dir,
    ))
    actual = sha256(path)
    if actual != CHECKPOINT_SHA256:
        path.unlink(missing_ok=True)
        raise RuntimeError(f"Checkpoint SHA-256 mismatch: {actual}")
    print(f"Verified checkpoint: {path}\nSHA-256: {actual}")


if __name__ == "__main__":
    main()
