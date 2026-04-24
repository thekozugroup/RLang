#!/usr/bin/env python3
"""run_pipeline.py

End-to-end pipeline runner for the RLang v2 dataset expansion.

Steps:
  1. Scan all batch_NNN_output.jsonl + output/synthetic_traces.jsonl
  2. Validate each RLang trace (phase structure, operators, connectives)
  3. Deduplicate against existing HF dataset (Michael-Kozu/rlang-reasoning-traces)
  4. Write output/rlang_v2_full.jsonl  (existing + new)
     Write output/rlang_v2_new_only.jsonl  (new rows only)
  5. Print detailed stats

Usage:
    python run_pipeline.py                    # full run (downloads HF data)
    python run_pipeline.py --no-hf            # skip HF download
    python run_pipeline.py --dry-run          # validate + stats, no files written
    python run_pipeline.py --batch-dir PATH   # override batches directory
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

HERE = Path(__file__).resolve().parent
BATCHES_DIR = HERE / "batches"
OUTPUT_DIR = HERE / "output"
SYNTHETIC_FILE = OUTPUT_DIR / "synthetic_traces.jsonl"

FULL_OUT = OUTPUT_DIR / "rlang_v2_full.jsonl"
NEW_ONLY_OUT = OUTPUT_DIR / "rlang_v2_new_only.jsonl"
REPORT_OUT = OUTPUT_DIR / "pipeline_report.json"

HF_DATASET_REPO = "Michael-Kozu/rlang-reasoning-traces"
HF_V2_REPO = "Michael-Kozu/rlang-reasoning-traces-v2"

# ---------------------------------------------------------------------------
# RLang validation (inline — mirrors verify.py logic)
# ---------------------------------------------------------------------------

PHASES = ["Frame", "Explore", "Verify", "Decide"]
PHASE_RE = re.compile(r"#\[phase\((\w+)\)\]")
BLF_RE = re.compile(r"\bblf\s*<\s*([0-9]*\.?[0-9]+)")
THINK_RE = re.compile(r"<think>(.*?)</think>", re.DOTALL)

ALL_OPERATORS = {
    "obs", "cause", "corr", "enbl", "prvnt", "req", "blf",
    "resolve", "sup", "wkn", "neut", "decay", "refresh", "conf",
    "goal", "desire", "intent", "dcmp", "prioritize", "select",
    "replan", "assert", "hedge", "suspend", "reject",
    "exec", "inv", "rmb", "rcl", "bt", "retry_with", "emit",
    "dlg", "discover", "match_capability", "poll", "subscribe",
}
ALL_CONNECTIVES = {"|>", "->", "||>", "<|", "~>", "!>", "?>", "@>", "<@"}

MIN_OPS = 6
MIN_CONN = 2
MIN_CHARS = 150


def _extract_rlang(gpt_value: str) -> str:
    """Pull RLang text from inside <think>...</think>."""
    m = THINK_RE.search(gpt_value)
    return m.group(1).strip() if m else ""


def _validate_rlang(text: str) -> tuple[bool, list[str]]:
    """Return (valid, issues). Quick structural check."""
    if not text or len(text) < MIN_CHARS:
        return False, [f"Trace too short ({len(text)} chars)"]

    issues: list[str] = []

    # Phase presence and order
    found_phases = PHASE_RE.findall(text)
    missing = [p for p in PHASES if p not in found_phases]
    if missing:
        issues.append(f"Missing phases: {', '.join(missing)}")
    else:
        positions = {p: text.index(f"#[phase({p})]") for p in PHASES}
        ordered = sorted(PHASES, key=lambda p: positions[p])
        if ordered != PHASES:
            issues.append(f"Phases out of order: {' -> '.join(ordered)}")

    # Operator count
    found_ops = {op for op in ALL_OPERATORS if re.search(r"\b" + re.escape(op) + r"\s*\(", text)}
    if len(found_ops) < MIN_OPS:
        issues.append(f"Too few operators: {len(found_ops)} (need {MIN_OPS})")

    # Connective count
    found_conn = {c for c in ALL_CONNECTIVES if c in text}
    if len(found_conn) < MIN_CONN:
        issues.append(f"Too few connectives: {len(found_conn)} (need {MIN_CONN})")

    # blf range
    for m in BLF_RE.finditer(text):
        try:
            v = float(m.group(1))
            if v < 0.0 or v >= 1.0:
                issues.append(f"blf value out of range: {v}")
                break
        except ValueError:
            pass

    return len(issues) == 0, issues


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------

def _prompt_hash(record: dict) -> str:
    for turn in record.get("conversations", []):
        if isinstance(turn, dict) and turn.get("from") == "human":
            val = turn.get("value", "")
            if val:
                return hashlib.sha256(val.encode()).hexdigest()
    raw = json.dumps(record, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _load_jsonl(path: Path, label: str = "") -> list[dict]:
    records: list[dict] = []
    if not path.exists():
        print(f"  [SKIP] {label or path.name} not found")
        return records
    with path.open(encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                print(f"  [WARN] {path.name}:{lineno} parse error: {exc}")
    return records


def _load_all_batch_outputs(batches_dir: Path) -> list[tuple[str, dict]]:
    """Load all batch_NNN_output.jsonl files. Returns (filename, record) pairs."""
    pairs: list[tuple[str, dict]] = []
    output_files = sorted(batches_dir.glob("batch_*_output.jsonl"))
    if not output_files:
        print(f"  [WARN] No batch_*_output.jsonl files found in {batches_dir}")
        return pairs
    for fpath in output_files:
        recs = _load_jsonl(fpath, fpath.name)
        for r in recs:
            pairs.append((fpath.name, r))
        print(f"  {fpath.name}: {len(recs)} rows")
    return pairs


def _load_hf_dataset(repo: str) -> list[dict]:
    try:
        from datasets import load_dataset  # type: ignore
    except ImportError:
        print("  [WARN] 'datasets' not installed — skipping HF load")
        return []
    print(f"  Downloading existing dataset: {repo} ...")
    try:
        ds = load_dataset(repo, split="train")
        rows = [dict(r) for r in ds]
        print(f"  Loaded {len(rows):,} existing rows from HF")
        return rows
    except Exception as exc:
        print(f"  [WARN] Could not load HF dataset: {exc}")
        return []


# ---------------------------------------------------------------------------
# Feature coverage (works with ShareGPT format)
# ---------------------------------------------------------------------------

_OP_LIST = sorted(ALL_OPERATORS)
_CONN_LIST = sorted(ALL_CONNECTIVES)


def _feature_coverage(records: list[dict]) -> dict:
    op_counts: dict[str, int] = {op: 0 for op in _OP_LIST}
    conn_counts: dict[str, int] = {c: 0 for c in _CONN_LIST}

    for rec in records:
        # Extract RLang text from ShareGPT gpt turn
        rlang = ""
        for turn in rec.get("conversations", []):
            if isinstance(turn, dict) and turn.get("from") == "gpt":
                rlang = _extract_rlang(turn.get("value", ""))
                break

        for op in _OP_LIST:
            if re.search(r"\b" + re.escape(op) + r"\s*\(", rlang):
                op_counts[op] += 1
        for conn in _CONN_LIST:
            if conn in rlang:
                conn_counts[conn] += 1

    return {"operators": op_counts, "connectives": conn_counts}


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(
    batches_dir: Path = BATCHES_DIR,
    load_hf: bool = True,
    dry_run: bool = False,
) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("\n" + "=" * 60)
    print("STEP 1 — Load existing HF dataset")
    print("=" * 60)
    existing: list[dict] = []
    if load_hf:
        existing = _load_hf_dataset(HF_DATASET_REPO)
    existing_hashes: set[str] = {_prompt_hash(r) for r in existing}
    print(f"  Existing prompt hashes indexed: {len(existing_hashes):,}")

    print("\n" + "=" * 60)
    print("STEP 2 — Load new rows")
    print("=" * 60)
    batch_pairs = _load_all_batch_outputs(batches_dir)
    print(f"\n  Batch outputs total: {len(batch_pairs):,} rows")

    synthetic_recs = _load_jsonl(SYNTHETIC_FILE, "synthetic_traces.jsonl")
    print(f"  Synthetic gold traces: {len(synthetic_recs):,} rows")

    all_new_pairs: list[tuple[str, dict]] = batch_pairs + [
        ("synthetic_traces.jsonl", r) for r in synthetic_recs
    ]
    print(f"  Total candidate rows: {len(all_new_pairs):,}")

    print("\n" + "=" * 60)
    print("STEP 3 — Validate + deduplicate")
    print("=" * 60)

    n_invalid = 0
    n_dup = 0
    n_too_short_rlang = 0
    invalid_detail: list[dict] = []
    accepted: list[dict] = []
    seen_new: set[str] = set()

    for fname, rec in all_new_pairs:
        # Must have conversations field
        convs = rec.get("conversations")
        if not isinstance(convs, list) or len(convs) == 0:
            n_invalid += 1
            invalid_detail.append({"file": fname, "id": rec.get("id"), "reason": "no conversations"})
            continue

        # Extract and validate RLang trace
        rlang_text = ""
        for turn in convs:
            if isinstance(turn, dict) and turn.get("from") == "gpt":
                rlang_text = _extract_rlang(turn.get("value", ""))
                break

        if not rlang_text:
            n_too_short_rlang += 1
            invalid_detail.append({"file": fname, "id": rec.get("id"), "reason": "no <think> block"})
            continue

        valid, issues = _validate_rlang(rlang_text)
        if not valid:
            n_invalid += 1
            invalid_detail.append({"file": fname, "id": rec.get("id"), "reason": "; ".join(issues)})
            continue

        # Dedup against HF and within new batch
        h = _prompt_hash(rec)
        if h in existing_hashes:
            n_dup += 1
            continue
        if h in seen_new:
            n_dup += 1
            continue

        seen_new.add(h)
        rec_out = dict(rec)
        rec_out.pop("_is_new", None)
        accepted.append(rec_out)

    print(f"  Accepted:        {len(accepted):>6,}")
    print(f"  Invalid:         {n_invalid:>6,}")
    print(f"  No think block:  {n_too_short_rlang:>6,}")
    print(f"  Duplicates:      {n_dup:>6,}")

    if invalid_detail:
        print(f"\n  Invalid row sample (first 10):")
        for d in invalid_detail[:10]:
            print(f"    [{d['file']}] id={d['id']} — {d['reason']}")

    # Combined dataset
    full = list(existing) + accepted

    print("\n" + "=" * 60)
    print("STEP 4 — Stats")
    print("=" * 60)

    cat_counter: Counter = Counter()
    src_counter: Counter = Counter()
    quality_counter: Counter = Counter()
    for rec in accepted:
        meta = rec.get("metadata") or {}
        cat_counter[meta.get("category", "unknown")] += 1
        src_counter[meta.get("source", "unknown")] += 1
        quality_counter[meta.get("quality", "unknown")] += 1

    print(f"\n  Total rows in v2 dataset:    {len(full):,}")
    print(f"  Existing rows (from v1 HF):  {len(existing):,}")
    print(f"  Net new rows added:          {len(accepted):,}")

    print("\n  New rows by category:")
    for cat, cnt in cat_counter.most_common():
        print(f"    {cat:<30} {cnt:>6,}")

    print("\n  New rows by source:")
    for src, cnt in src_counter.most_common():
        print(f"    {src:<50} {cnt:>6,}")

    print("\n  New rows by quality:")
    for q, cnt in quality_counter.most_common():
        print(f"    {q:<20} {cnt:>6,}")

    if accepted:
        cov = _feature_coverage(accepted)
        total = len(accepted)
        print(f"\n  Operator coverage (new rows, {total:,} total):")
        for op, cnt in sorted(cov["operators"].items(), key=lambda x: -x[1]):
            if cnt > 0:
                pct = 100 * cnt / total
                bar = "█" * int(pct / 5)
                print(f"    {op:<20} {cnt:>5,} ({pct:5.1f}%) {bar}")

        print(f"\n  Connective coverage (new rows):")
        for conn, cnt in sorted(cov["connectives"].items(), key=lambda x: -x[1]):
            pct = 100 * cnt / total if total else 0
            bar = "█" * int(pct / 5)
            print(f"    {conn:<6} {cnt:>5,} ({pct:5.1f}%) {bar}")

    if dry_run:
        print("\n  [DRY RUN] No files written.")
        return

    print("\n" + "=" * 60)
    print("STEP 5 — Write outputs")
    print("=" * 60)

    print(f"  Writing {len(full):,} rows → {FULL_OUT} ...")
    with FULL_OUT.open("w", encoding="utf-8") as fh:
        for rec in full:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"  Writing {len(accepted):,} rows → {NEW_ONLY_OUT} ...")
    with NEW_ONLY_OUT.open("w", encoding="utf-8") as fh:
        for rec in accepted:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # Pipeline report
    report = {
        "existing_rows": len(existing),
        "candidate_new_rows": len(all_new_pairs),
        "invalid_rows": n_invalid,
        "no_think_block": n_too_short_rlang,
        "duplicate_rows": n_dup,
        "accepted_new_rows": len(accepted),
        "full_dataset_rows": len(full),
        "categories": dict(cat_counter),
        "invalid_samples": invalid_detail[:20],
    }
    REPORT_OUT.write_text(json.dumps(report, indent=2, ensure_ascii=False))

    print(f"\n  Done.")
    print(f"    Full:     {FULL_OUT}")
    print(f"    New only: {NEW_ONLY_OUT}")
    print(f"    Report:   {REPORT_OUT}")

    print("\n" + "=" * 60)
    print("NEXT STEP")
    print("=" * 60)
    print(f"  To publish to HuggingFace:")
    print(f"    export HF_TOKEN=hf_...")
    print(f"    python push_to_hub.py --source {NEW_ONLY_OUT} --repo {HF_V2_REPO}")
    print(f"  Or full dataset:")
    print(f"    python push_to_hub.py --source {FULL_OUT} --repo {HF_V2_REPO}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full RLang v2 dataset pipeline")
    parser.add_argument("--batch-dir", type=Path, default=BATCHES_DIR,
                        help=f"Batch outputs directory (default: {BATCHES_DIR})")
    parser.add_argument("--no-hf", action="store_true",
                        help="Skip HuggingFace download (use when offline or testing)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and print stats but do not write any files")
    args = parser.parse_args()

    run(
        batches_dir=args.batch_dir,
        load_hf=not args.no_hf,
        dry_run=args.dry_run,
    )


if __name__ == "__main__":
    main()
