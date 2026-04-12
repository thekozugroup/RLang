#!/usr/bin/env python3
"""Batch validator for converted RLang traces.

Reads rlang_converted.jsonl, validates each trace through the Rust parser/validator,
and splits into validated vs rejected outputs with a detailed error report.
"""

import json
import os
import subprocess
import sys
import tempfile
from collections import Counter
from pathlib import Path

from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
DATA_DIR = SCRIPT_DIR / "data"

INPUT_PATH = DATA_DIR / "rlang_converted.jsonl"
VALID_PATH = DATA_DIR / "rlang_validated.jsonl"
REJECTED_PATH = DATA_DIR / "rlang_rejected.jsonl"

# The rlang binary — try release first, then debug
CARGO_RELEASE = PROJECT_ROOT / "target" / "release" / "rlang"
CARGO_DEBUG = PROJECT_ROOT / "target" / "debug" / "rlang"


def find_rlang_binary() -> str:
    """Locate a pre-built rlang binary or fall back to `cargo run`."""
    if CARGO_RELEASE.exists():
        return str(CARGO_RELEASE)
    if CARGO_DEBUG.exists():
        return str(CARGO_DEBUG)
    # Fall back — caller will use cargo run instead
    return ""


def build_project() -> bool:
    """Attempt to build the project so we have a fast binary."""
    print("Building rlang project (release) ...")
    result = subprocess.run(
        ["cargo", "build", "--release"],
        cwd=str(PROJECT_ROOT),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"  Release build failed, trying debug build ...")
        result = subprocess.run(
            ["cargo", "build"],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  Debug build also failed: {result.stderr[:500]}")
            return False
    print("  Build succeeded.")
    return True


def categorize_error(stderr: str) -> str:
    """Categorize an error based on stderr output from the rlang validator."""
    lower = stderr.lower()
    if "parse error" in lower or "syntax" in lower:
        return "parse_error"
    if "phase error" in lower or "phase" in lower and "error" in lower:
        return "phase_error"
    if "metadata error" in lower or "metadata" in lower and "error" in lower:
        return "metadata_error"
    if "semantic error" in lower or "semantic" in lower:
        return "semantic_error"
    if "bounds error" in lower:
        return "bounds_error"
    if "type error" in lower:
        return "type_error"
    if "resource error" in lower:
        return "resource_error"
    if "validation error" in lower:
        return "validation_error"
    if "could not read" in lower:
        return "io_error"
    return "unknown_error"


def extract_error_message(stderr: str) -> str:
    """Extract a concise error message from stderr."""
    lines = [l.strip() for l in stderr.strip().splitlines() if l.strip()]
    # Filter ANSI escape codes
    import re
    ansi_escape = re.compile(r'\x1b\[[0-9;]*m')
    cleaned = [ansi_escape.sub('', l) for l in lines]
    # Return first meaningful error line(s), up to 3
    error_lines = [l for l in cleaned if l and not l.startswith("Usage:")]
    return "\n".join(error_lines[:3])


def validate_trace(rlang_text: str, binary: str) -> tuple[bool, str, str]:
    """Validate a single RLang trace by writing to a temp file and running the parser.

    Returns: (is_valid, error_category, error_message)
    """
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".rl", delete=False
    ) as tmp:
        tmp.write(rlang_text)
        tmp_path = tmp.name

    try:
        if binary:
            cmd = [binary, tmp_path, "--validate-only", "--quiet"]
        else:
            cmd = [
                "cargo", "run", "--", tmp_path, "--validate-only", "--quiet",
            ]

        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            return True, "", ""
        else:
            stderr = result.stderr
            category = categorize_error(stderr)
            message = extract_error_message(stderr)
            return False, category, message

    except subprocess.TimeoutExpired:
        return False, "timeout", "Validation timed out after 30s"
    except Exception as e:
        return False, "execution_error", str(e)
    finally:
        os.unlink(tmp_path)


def main():
    # -----------------------------------------------------------------------
    # Pre-flight checks
    # -----------------------------------------------------------------------
    if not INPUT_PATH.exists():
        print(f"Error: Input file not found: {INPUT_PATH}")
        print("Run convert_to_rlang.py first to generate rlang_converted.jsonl.")
        sys.exit(1)

    # Build project for speed
    build_project()
    binary = find_rlang_binary()
    if binary:
        print(f"Using binary: {binary}")
    else:
        print("No binary found; using `cargo run` (slower).")

    # -----------------------------------------------------------------------
    # Load traces
    # -----------------------------------------------------------------------
    print(f"\nReading traces from {INPUT_PATH} ...")
    traces = []
    with open(INPUT_PATH) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Warning: skipping malformed JSON on line {line_num}: {e}")

    total = len(traces)
    print(f"  Loaded {total} traces.")

    if total == 0:
        print("No traces to validate.")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Validate each trace
    # -----------------------------------------------------------------------
    valid_traces = []
    rejected_traces = []
    error_counter: Counter = Counter()
    error_examples: dict[str, list[str]] = {}

    for trace in tqdm(traces, desc="Validating traces"):
        rlang_text = trace.get("thinking_rlang", "")
        if not rlang_text:
            rejected_traces.append({
                **trace,
                "rejection_reason": "empty_rlang",
                "error_category": "empty_rlang",
                "error_message": "No RLang trace present",
            })
            error_counter["empty_rlang"] += 1
            continue

        is_valid, error_cat, error_msg = validate_trace(rlang_text, binary)

        if is_valid:
            valid_traces.append(trace)
        else:
            rejected_traces.append({
                **trace,
                "rejection_reason": error_cat,
                "error_category": error_cat,
                "error_message": error_msg,
            })
            error_counter[error_cat] += 1
            # Keep first 3 examples per category
            if error_cat not in error_examples:
                error_examples[error_cat] = []
            if len(error_examples[error_cat]) < 3:
                error_examples[error_cat].append(
                    error_msg[:200] if error_msg else "(no message)"
                )

    # -----------------------------------------------------------------------
    # Write outputs
    # -----------------------------------------------------------------------
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(VALID_PATH, "w") as f:
        for trace in valid_traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    print(f"\nValid traces written to:    {VALID_PATH}")

    with open(REJECTED_PATH, "w") as f:
        for trace in rejected_traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    print(f"Rejected traces written to: {REJECTED_PATH}")

    # -----------------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------------
    passed = len(valid_traces)
    failed = len(rejected_traces)
    pass_rate = (passed / total * 100) if total > 0 else 0.0

    print("\n" + "=" * 60)
    print("  VALIDATION REPORT")
    print("=" * 60)
    print(f"  Total traces:    {total}")
    print(f"  Passed:          {passed}  ({pass_rate:.1f}%)")
    print(f"  Rejected:        {failed}  ({100 - pass_rate:.1f}%)")
    print()

    if error_counter:
        print("  Error Distribution:")
        print("  " + "-" * 50)
        for category, count in error_counter.most_common():
            pct = count / total * 100
            print(f"    {category:<25s}  {count:>5d}  ({pct:5.1f}%)")

        print()
        print("  Example Errors (first per category):")
        print("  " + "-" * 50)
        for category, examples in sorted(error_examples.items()):
            print(f"  [{category}]")
            for ex in examples[:1]:
                for line in ex.splitlines():
                    print(f"    {line}")
            print()

    print("=" * 60)


if __name__ == "__main__":
    main()
