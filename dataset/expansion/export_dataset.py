"""export_dataset.py

Merges new expansion traces with the existing HuggingFace dataset and
produces two clean export files.

Outputs:
    output/rlang_v2_full.jsonl      — existing + new (deduplicated)
    output/rlang_v2_new_only.jsonl  — new rows only (deduplicated against existing)

Usage:
    python export_dataset.py
    python export_dataset.py --no-hf          # skip HF download, use local cache only
    python export_dataset.py --input-dir path  # override expansion output dir
    python export_dataset.py --dry-run         # stats only, no files written
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
OUTPUT_DIR = HERE / "output"
FULL_OUTPUT = OUTPUT_DIR / "rlang_v2_full.jsonl"
NEW_ONLY_OUTPUT = OUTPUT_DIR / "rlang_v2_new_only.jsonl"

HF_DATASET_REPO = "Michael-Kozu/rlang-reasoning-traces"

# Required top-level fields for a valid ShareGPT-style entry
REQUIRED_SHAREGPT_FIELDS = {"conversations"}
# Each conversation turn must have these keys
REQUIRED_TURN_KEYS = {"from", "value"}


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------

def _prompt_hash(record: dict) -> str:
    """Stable hash over the user prompt for deduplication.

    Tries, in order: the first 'human' turn in 'conversations', then
    'problem', then 'thinking_english', then the full record JSON.
    """
    conversations = record.get("conversations", [])
    for turn in conversations:
        if isinstance(turn, dict) and turn.get("from") == "human":
            key = turn.get("value", "")
            if key:
                return hashlib.sha256(key.encode("utf-8")).hexdigest()

    for field in ("problem", "thinking_english"):
        val = record.get(field, "")
        if val:
            return hashlib.sha256(str(val).encode("utf-8")).hexdigest()

    # Fallback: hash the whole record
    raw = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def _is_valid_sharegpt(record: dict) -> tuple[bool, str]:
    """Check that a record has the required ShareGPT structure.

    Returns (ok, reason).
    """
    if not isinstance(record, dict):
        return False, "record is not a dict"

    for field in REQUIRED_SHAREGPT_FIELDS:
        if field not in record:
            return False, f"missing required field '{field}'"

    conversations = record.get("conversations")
    if not isinstance(conversations, list) or len(conversations) == 0:
        return False, "'conversations' must be a non-empty list"

    for i, turn in enumerate(conversations):
        if not isinstance(turn, dict):
            return False, f"conversations[{i}] is not a dict"
        for key in REQUIRED_TURN_KEYS:
            if key not in turn:
                return False, f"conversations[{i}] missing key '{key}'"

    return True, ""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _load_hf_dataset(repo: str) -> list[dict]:
    """Download dataset from HuggingFace Hub and return records as dicts."""
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("  [WARN] 'datasets' package not installed — skipping HF load.")
        print("         Install with: pip install datasets")
        return []

    print(f"  Loading existing dataset from HuggingFace: {repo} ...")
    try:
        ds = load_dataset(repo, split="train")
        records = [dict(row) for row in ds]
        print(f"  Loaded {len(records):,} rows from HF.")
        return records
    except Exception as exc:
        print(f"  [WARN] Could not load HF dataset: {exc}")
        return []


def _load_jsonl_files(input_dir: Path) -> list[dict]:
    """Load all *.jsonl files from the given directory."""
    records: list[dict] = []
    files = sorted(input_dir.glob("*.jsonl"))
    if not files:
        print(f"  [WARN] No .jsonl files found in {input_dir}")
        return records

    for fpath in files:
        count_before = len(records)
        with fpath.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    print(f"  [WARN] {fpath.name}:{lineno} — JSON parse error: {exc}")
        added = len(records) - count_before
        print(f"  {fpath.name}: {added:,} rows")

    return records


# ---------------------------------------------------------------------------
# Feature coverage stats
# ---------------------------------------------------------------------------

_OPERATOR_NAMES = [
    "obs", "cause", "corr", "enbl", "prvnt", "req", "resolve", "sup", "wkn",
    "neut", "decay", "refresh", "conf", "goal", "desire", "intent", "dcmp",
    "prioritize", "select", "replan", "assert", "hedge", "suspend", "reject",
    "exec", "inv", "rmb", "rcl", "bt", "retry_with", "emit", "dlg",
    "discover", "match_capability", "poll", "subscribe",
]

_CONNECTIVE_NAMES = ["|>", "->", "||>", "<|", "~>", "!>", "?>", "@>", "<@"]


def _feature_coverage(records: list[dict]) -> dict:
    """Count how many records use each RLang operator/connective."""
    op_counts: dict[str, int] = {op: 0 for op in _OPERATOR_NAMES}
    conn_counts: dict[str, int] = {c: 0 for c in _CONNECTIVE_NAMES}

    for rec in records:
        rlang = rec.get("thinking_rlang", "") or ""
        # Collect operator presence per record (not total occurrences)
        for op in _OPERATOR_NAMES:
            if f"{op}(" in rlang:
                op_counts[op] += 1
        for conn in _CONNECTIVE_NAMES:
            if conn in rlang:
                conn_counts[conn] += 1

    return {"operators": op_counts, "connectives": conn_counts}


# ---------------------------------------------------------------------------
# Stats printing
# ---------------------------------------------------------------------------

def _print_stats(
    existing: list[dict],
    new_rows: list[dict],
    full: list[dict],
    skipped_invalid: int,
    skipped_dup: int,
) -> None:
    print("\n" + "=" * 60)
    print("EXPORT STATS")
    print("=" * 60)
    print(f"  Existing rows (HF):          {len(existing):>8,}")
    print(f"  New rows loaded:             {len(new_rows):>8,}")
    print(f"  Skipped — invalid ShareGPT:  {skipped_invalid:>8,}")
    print(f"  Skipped — duplicates:        {skipped_dup:>8,}")
    print(f"  New rows added:              {len(new_rows) - skipped_invalid - skipped_dup:>8,}")
    print(f"  Full combined total:         {len(full):>8,}")

    # By category / domain
    from collections import Counter
    domain_counter: Counter = Counter()
    source_counter: Counter = Counter()
    for rec in full:
        domain_counter[rec.get("domain", "unknown")] += 1
        source_counter[rec.get("source", "unknown")] += 1

    print("\n  By domain:")
    for domain, count in domain_counter.most_common():
        print(f"    {domain:<30} {count:>6,}")

    print("\n  By source:")
    for source, count in source_counter.most_common():
        print(f"    {source:<30} {count:>6,}")

    # Feature coverage on new rows only
    if new_rows:
        net_new = [r for r in full if r.get("_is_new")]
        if net_new:
            coverage = _feature_coverage(net_new)
            print("\n  Operator coverage (new rows, top 10):")
            top_ops = sorted(
                coverage["operators"].items(), key=lambda x: -x[1]
            )[:10]
            for op, cnt in top_ops:
                pct = 100 * cnt / len(net_new)
                print(f"    {op:<20} {cnt:>5,}  ({pct:.1f}%)")

            print("\n  Connective coverage (new rows):")
            for conn, cnt in sorted(coverage["connectives"].items()):
                pct = 100 * cnt / len(net_new) if net_new else 0
                print(f"    {conn:<6} {cnt:>5,}  ({pct:.1f}%)")

    print("=" * 60)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(
    input_dir: Path = OUTPUT_DIR,
    load_hf: bool = True,
    dry_run: bool = False,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # --- Load existing dataset ---
    existing: list[dict] = []
    if load_hf:
        existing = _load_hf_dataset(HF_DATASET_REPO)
    else:
        print("  Skipping HF download (--no-hf flag set).")

    existing_hashes: set[str] = {_prompt_hash(r) for r in existing}
    print(f"  Existing prompt hashes indexed: {len(existing_hashes):,}")

    # --- Load new expansion rows ---
    print(f"\n  Loading new rows from: {input_dir}")
    raw_new = _load_jsonl_files(input_dir)
    print(f"  Total new rows loaded: {len(raw_new):,}")

    # --- Validate and deduplicate ---
    skipped_invalid = 0
    skipped_dup = 0
    accepted_new: list[dict] = []
    seen_new_hashes: set[str] = set()

    for rec in raw_new:
        ok, reason = _is_valid_sharegpt(rec)
        if not ok:
            skipped_invalid += 1
            continue

        h = _prompt_hash(rec)
        if h in existing_hashes:
            skipped_dup += 1
            continue
        if h in seen_new_hashes:
            skipped_dup += 1
            continue

        seen_new_hashes.add(h)
        rec["_is_new"] = True
        accepted_new.append(rec)

    # Combine
    full = list(existing) + accepted_new

    # Print stats before writing
    _print_stats(existing, raw_new, full, skipped_invalid, skipped_dup)

    if dry_run:
        print("\n  [DRY RUN] No files written.")
        return

    # --- Write outputs ---
    print(f"\n  Writing {len(full):,} rows to {FULL_OUTPUT} ...")
    with FULL_OUTPUT.open("w", encoding="utf-8") as fh:
        for rec in full:
            # Strip internal bookkeeping key before export
            export_rec = {k: v for k, v in rec.items() if k != "_is_new"}
            fh.write(json.dumps(export_rec, ensure_ascii=False) + "\n")

    print(f"  Writing {len(accepted_new):,} rows to {NEW_ONLY_OUTPUT} ...")
    with NEW_ONLY_OUTPUT.open("w", encoding="utf-8") as fh:
        for rec in accepted_new:
            export_rec = {k: v for k, v in rec.items() if k != "_is_new"}
            fh.write(json.dumps(export_rec, ensure_ascii=False) + "\n")

    print(f"\n  Done.")
    print(f"    Full:     {FULL_OUTPUT}")
    print(f"    New only: {NEW_ONLY_OUTPUT}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Merge expansion traces with HF dataset and export"
    )
    parser.add_argument(
        "--input-dir", type=Path, default=OUTPUT_DIR,
        help=f"Directory containing new *.jsonl files (default: {OUTPUT_DIR})"
    )
    parser.add_argument(
        "--no-hf", action="store_true",
        help="Skip HuggingFace download (useful offline / testing)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Print stats but do not write any files"
    )
    args = parser.parse_args()

    run(
        input_dir=args.input_dir,
        load_hf=not args.no_hf,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
