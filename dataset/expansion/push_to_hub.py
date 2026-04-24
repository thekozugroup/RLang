"""push_to_hub.py

Pushes the final merged dataset to HuggingFace Hub as a new v2 repository.

Prerequisites:
    pip install datasets huggingface_hub
    export HF_TOKEN=hf_...

Source file:
    output/rlang_v2_full.jsonl   (produced by export_dataset.py)

Target repo:
    Michael-Kozu/rlang-reasoning-traces-v2   (created if it does not exist)

Usage:
    python push_to_hub.py
    python push_to_hub.py --source output/rlang_v2_full.jsonl
    python push_to_hub.py --repo MyOrg/my-dataset-v2
    python push_to_hub.py --private          # create as private repo
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
DEFAULT_SOURCE = HERE / "output" / "rlang_v2_full.jsonl"
DEFAULT_REPO = "Michael-Kozu/rlang-reasoning-traces-v2"
HF_TOKEN_ENV = "HF_TOKEN"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_token() -> str:
    """Read HF token from env; exit with a clear message if missing."""
    token = os.environ.get(HF_TOKEN_ENV, "").strip()
    if not token:
        print(f"Error: environment variable {HF_TOKEN_ENV!r} is not set.")
        print("Obtain a token at https://huggingface.co/settings/tokens")
        print(f"Then run:  export {HF_TOKEN_ENV}=hf_...")
        sys.exit(1)
    return token


def _load_jsonl(path: Path) -> list[dict]:
    """Load records from a JSONL file."""
    if not path.exists():
        print(f"Error: source file not found: {path}")
        print("Run export_dataset.py first to generate it.")
        sys.exit(1)

    records: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"  [WARN] line {lineno}: JSON parse error — {exc}")
    return records


def _build_dataset(records: list[dict]):
    """Convert a list of dicts to a datasets.Dataset object."""
    try:
        from datasets import Dataset  # type: ignore
    except ImportError:
        print("Error: 'datasets' package is not installed.")
        print("Install with:  pip install datasets")
        sys.exit(1)

    return Dataset.from_list(records)


def _ensure_repo_exists(repo_id: str, token: str, private: bool) -> None:
    """Create the HF dataset repo if it does not already exist."""
    try:
        from huggingface_hub import HfApi  # type: ignore
    except ImportError:
        print("Error: 'huggingface_hub' package is not installed.")
        print("Install with:  pip install huggingface_hub")
        sys.exit(1)

    api = HfApi(token=token)
    try:
        api.repo_info(repo_id=repo_id, repo_type="dataset")
        print(f"  Repository already exists: https://huggingface.co/datasets/{repo_id}")
    except Exception:
        print(f"  Creating new dataset repository: {repo_id} (private={private}) ...")
        api.create_repo(
            repo_id=repo_id,
            repo_type="dataset",
            private=private,
            exist_ok=True,
        )
        print(f"  Repository created.")


# ---------------------------------------------------------------------------
# Main push routine
# ---------------------------------------------------------------------------

def push(
    source: Path = DEFAULT_SOURCE,
    repo_id: str = DEFAULT_REPO,
    private: bool = False,
) -> str:
    """Load JSONL, build Dataset, push to Hub. Returns the dataset URL."""
    token = _require_token()

    # --- Load ---
    print(f"Loading records from {source} ...")
    records = _load_jsonl(source)
    if not records:
        print("Error: no records found in source file.")
        sys.exit(1)
    print(f"  {len(records):,} records loaded.")

    # --- Build ---
    print("Building datasets.Dataset object ...")
    ds = _build_dataset(records)
    print(f"  Dataset: {ds}")

    # --- Ensure repo exists ---
    _ensure_repo_exists(repo_id, token, private)

    # --- Push ---
    print(f"\nPushing to HuggingFace Hub: {repo_id} ...")
    ds.push_to_hub(
        repo_id=repo_id,
        token=token,
        private=private,
    )

    url = f"https://huggingface.co/datasets/{repo_id}"
    print(f"\nDataset pushed successfully.")
    print(f"  URL: {url}")
    print(f"  Rows: {len(records):,}")
    return url


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push rlang_v2_full.jsonl to HuggingFace Hub"
    )
    parser.add_argument(
        "--source", type=Path, default=DEFAULT_SOURCE,
        help=f"Path to the full merged JSONL (default: {DEFAULT_SOURCE})"
    )
    parser.add_argument(
        "--repo", type=str, default=DEFAULT_REPO,
        help=f"HuggingFace dataset repo ID (default: {DEFAULT_REPO})"
    )
    parser.add_argument(
        "--private", action="store_true",
        help="Create / keep the repo private"
    )
    args = parser.parse_args()

    url = push(
        source=args.source,
        repo_id=args.repo,
        private=args.private,
    )
    print(f"\nConfirmation URL: {url}")


if __name__ == "__main__":
    main()
