#!/usr/bin/env python3
"""Optimization pass for validated RLang traces.

Reads rlang_validated.jsonl, applies token-saving transformations,
re-validates after optimization, and outputs rlang_optimized.jsonl.
"""

import json
import os
import re
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

INPUT_PATH = DATA_DIR / "rlang_validated.jsonl"
OUTPUT_PATH = DATA_DIR / "rlang_optimized.jsonl"

CARGO_RELEASE = PROJECT_ROOT / "target" / "release" / "rlang"
CARGO_DEBUG = PROJECT_ROOT / "target" / "debug" / "rlang"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count using word_count * 1.3."""
    if not text:
        return 0
    return int(len(text.split()) * 1.3)


def find_binary() -> str:
    """Locate a pre-built rlang binary."""
    if CARGO_RELEASE.exists():
        return str(CARGO_RELEASE)
    if CARGO_DEBUG.exists():
        return str(CARGO_DEBUG)
    return ""


def validate_rlang(text: str, binary: str) -> bool:
    """Quick validation check — returns True if the trace parses and validates."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".rl", delete=False
    ) as tmp:
        tmp.write(text)
        tmp_path = tmp.name

    try:
        if binary:
            cmd = [binary, tmp_path, "--validate-only", "--quiet"]
        else:
            cmd = ["cargo", "run", "--", tmp_path, "--validate-only", "--quiet"]

        result = subprocess.run(
            cmd,
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False
    finally:
        os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# Optimization rules
# ---------------------------------------------------------------------------

# Rule (a): Merge consecutive observations in the same phase
# Detects patterns like:
#   let x: blf<0.9> = obs(a) | p:0.9 | ...;
#   let y: blf<0.8> = obs(b) | p:0.8 | ...;
# These are already concise in RLang; merging means removing redundant
# whitespace/comments between consecutive let bindings in Frame phase.

def optimize_merge_observations(text: str) -> tuple[str, int]:
    """Merge consecutive observation let-bindings by removing blank lines between them.

    Returns (optimized_text, count_of_merges).
    """
    # Remove blank lines between consecutive let statements in Frame phase
    lines = text.split("\n")
    result = []
    merges = 0
    in_frame = False
    prev_was_let = False

    for line in lines:
        stripped = line.strip()

        if "#[phase(Frame)]" in stripped:
            in_frame = True
        elif "#[phase(" in stripped and "Frame" not in stripped:
            in_frame = False

        if in_frame:
            is_let = stripped.startswith("let ") and "=" in stripped
            if prev_was_let and stripped == "":
                # Skip blank line between consecutive lets
                merges += 1
                continue
            prev_was_let = is_let
        else:
            prev_was_let = False

        result.append(line)

    return "\n".join(result), merges


# Rule (b): Abbreviate identifiers where unambiguous
# Common abbreviation map for longer identifiers
ABBREVIATION_MAP = {
    "tests_pass": "tst_pass",
    "tests_passing": "tst_pass",
    "no_rollback": "no_rback",
    "low_traffic": "lo_traf",
    "high_traffic": "hi_traf",
    "deploy_blf": "dep_blf",
    "deploy_ready": "dep_rdy",
    "confidence": "conf",
    "observation": "obs_val",
    "threshold": "thresh",
    "monitoring": "mon",
    "pipeline": "pipe",
    "rollback": "rback",
    "evidence": "ev",
    "confirmed": "cfm",
    "resolved": "rslv",
    "approved": "apvd",
    "rejected": "rjct",
    "response": "resp",
    "request": "req_val",
    "available": "avail",
    "performance": "perf",
    "temperature": "temp",
    "probability": "prob",
    "information": "info",
    "environment": "env",
    "configuration": "config",
    "infrastructure": "infra",
    "verification": "verif",
    "assessment": "asmt",
    "evaluation": "eval",
}


def optimize_abbreviate_identifiers(text: str) -> tuple[str, int]:
    """Abbreviate long identifiers where unambiguous.

    Returns (optimized_text, count_of_abbreviations).
    """
    count = 0
    result = text

    for long_name, short_name in ABBREVIATION_MAP.items():
        # Only replace if the identifier appears as a standalone word
        # (not inside a string literal or operator name)
        pattern = r'\b' + re.escape(long_name) + r'\b'
        matches = len(re.findall(pattern, result))
        if matches > 0:
            result = re.sub(pattern, short_name, result)
            count += matches

    return result, count


# Rule (c): Collapse trivial verify phases
# If verify phase is just: req(x, obs(y)) |> verify(x) -> Ok(());
# Keep it minimal (single line, no extra whitespace)

def optimize_collapse_verify(text: str) -> tuple[str, int]:
    """Collapse trivial verify phases to minimal form.

    Returns (optimized_text, count_of_collapses).
    """
    # Pattern: #[phase(Verify)] block with a single pipe-chain statement
    verify_pattern = re.compile(
        r'(#\[phase\(Verify\)\]\s*\{)\s*\n'
        r'(\s*req\([^)]+\)\s*\|>\s*verify\([^)]+\)\s*->\s*Ok\(\(\)\);)\s*\n'
        r'(\s*\})',
        re.MULTILINE,
    )

    def collapse_match(m):
        return f"{m.group(1)} {m.group(2).strip()} {m.group(3).strip()}"

    result, count = verify_pattern.subn(collapse_match, text)
    return result, count


# Rule (d): Remove redundant metadata
# If ep:direct is the default for obs() calls, we can omit it

def optimize_remove_redundant_metadata(text: str) -> tuple[str, int]:
    """Remove truly redundant metadata (scope:loc, t:fresh) but PRESERVE ep:.

    QAQC requires ep: on every blf<> binding, so we must never strip it.
    Only strip scope:loc (always local) and t:fresh (always fresh) which
    are genuinely redundant defaults.

    Returns (optimized_text, count_of_removals).
    """
    result = text
    count = 0

    # Remove | scope:loc (always implied for local bindings)
    scope_pattern = re.compile(r'\s*\|\s*scope:loc')
    new_result, n = scope_pattern.subn('', result)
    count += n
    result = new_result

    # Remove | t:fresh (always implied for new beliefs)
    fresh_pattern = re.compile(r'\s*\|\s*t:fresh')
    new_result, n = fresh_pattern.subn('', result)
    count += n
    result = new_result

    return result, count


# Rule (e): Simplify evidence blocks
# If all evidence items are sup(), merge into single sup() with summed delta

def optimize_simplify_evidence(text: str) -> tuple[str, int]:
    """Merge all-sup evidence blocks into a single sup() with summed delta.

    Returns (optimized_text, count_of_simplifications).
    """
    # Find evidence blocks where ALL items are sup()
    ev_block_pattern = re.compile(
        r'let\s+\w+\s*=\s*\[\s*\n((?:\s*\w+\s*=>\s*sup\([^)]*\),?\s*\n)+)\s*\];',
        re.MULTILINE,
    )

    count = 0

    def try_merge(m):
        nonlocal count
        block_text = m.group(1)
        # Parse individual sup() items
        item_pattern = re.compile(
            r'(\w+)\s*=>\s*sup\((\w+),\s*([+-]?\d+\.\d+)\)'
        )
        items = item_pattern.findall(block_text)

        if len(items) < 2:
            return m.group(0)  # Don't merge single items

        # Check all items target the same belief
        targets = set(item[1] for item in items)
        if len(targets) != 1:
            return m.group(0)  # Different targets, can't merge

        target = items[0][1]
        total_delta = sum(float(item[2]) for item in items)
        sign = "+" if total_delta >= 0 else ""
        sources = ", ".join(item[0] for item in items)

        count += 1
        # Use combined form
        return f"let ev = [{sources} => sup({target}, {sign}{total_delta:.2f})];"

    result = ev_block_pattern.sub(try_merge, text)
    return result, count


# ---------------------------------------------------------------------------
# Main optimization pipeline
# ---------------------------------------------------------------------------

ALL_RULES = [
    ("merge_observations", optimize_merge_observations),
    ("abbreviate_identifiers", optimize_abbreviate_identifiers),
    ("collapse_verify", optimize_collapse_verify),
    ("remove_redundant_metadata", optimize_remove_redundant_metadata),
    ("simplify_evidence", optimize_simplify_evidence),
]


def optimize_trace(rlang_text: str) -> tuple[str, dict[str, int]]:
    """Apply all optimization rules to a single trace.

    Returns (optimized_text, {rule_name: count_applied}).
    """
    result = rlang_text
    rule_counts: dict[str, int] = {}

    for rule_name, rule_fn in ALL_RULES:
        result, count = rule_fn(result)
        rule_counts[rule_name] = count

    return result, rule_counts


def main():
    # -----------------------------------------------------------------------
    # Pre-flight
    # -----------------------------------------------------------------------
    if not INPUT_PATH.exists():
        print(f"Error: Input file not found: {INPUT_PATH}")
        print("Run validate_traces.py first to generate rlang_validated.jsonl.")
        sys.exit(1)

    binary = find_binary()
    if binary:
        print(f"Using binary: {binary}")
    else:
        print("No binary found; using `cargo run` for re-validation (slower).")

    # -----------------------------------------------------------------------
    # Load traces
    # -----------------------------------------------------------------------
    print(f"\nReading validated traces from {INPUT_PATH} ...")
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
        print("No traces to optimize.")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Optimize and re-validate
    # -----------------------------------------------------------------------
    optimized_traces = []
    failed_revalidation = 0
    total_rule_counts: Counter = Counter()
    total_tokens_before = 0
    total_tokens_after = 0

    for trace in tqdm(traces, desc="Optimizing traces"):
        rlang_text = trace.get("thinking_rlang", "")
        if not rlang_text:
            optimized_traces.append(trace)
            continue

        tokens_before = estimate_tokens(rlang_text)
        total_tokens_before += tokens_before

        # Apply optimizations
        optimized_text, rule_counts = optimize_trace(rlang_text)
        tokens_after = estimate_tokens(optimized_text)

        # Accumulate rule counts
        for rule, count in rule_counts.items():
            total_rule_counts[rule] += count

        # Re-validate
        if optimized_text != rlang_text:
            if validate_rlang(optimized_text, binary):
                # Optimization succeeded and still valid
                total_tokens_after += tokens_after
                compression_ratio = (
                    tokens_before / tokens_after if tokens_after > 0 else 1.0
                )
                optimized_traces.append({
                    **trace,
                    "thinking_rlang": optimized_text,
                    "rlang_tokens_est": tokens_after,
                    "rlang_tokens_pre_opt": tokens_before,
                    "compression_ratio": round(compression_ratio, 3),
                    "optimizations_applied": {
                        k: v for k, v in rule_counts.items() if v > 0
                    },
                })
            else:
                # Re-validation failed — keep original
                failed_revalidation += 1
                total_tokens_after += tokens_before
                optimized_traces.append(trace)
        else:
            # No changes made
            total_tokens_after += tokens_before
            optimized_traces.append(trace)

    # -----------------------------------------------------------------------
    # Post-optimization compression filter
    # Drop traces where RLang >= English (character-based ratio < 1.0)
    # -----------------------------------------------------------------------
    filtered_traces = []
    dropped_compression = 0
    for trace in optimized_traces:
        english_text = trace.get("thinking_english", "")
        rlang_text = trace.get("thinking_rlang", "")
        if english_text and rlang_text:
            rlang_stripped = re.sub(r'//[^\n]*', '', rlang_text).strip()
            char_ratio = len(english_text) / max(len(rlang_stripped), 1)
            if char_ratio < 1.0:
                dropped_compression += 1
                continue
            # Update stored metrics
            trace["rlang_tokens_est"] = estimate_tokens(rlang_text)
            trace["compression_ratio"] = round(char_ratio, 2)
        filtered_traces.append(trace)

    if dropped_compression > 0:
        print(f"\n  Dropped {dropped_compression} traces with RLang >= English (compression < 1.0)")

    # -----------------------------------------------------------------------
    # Write output
    # -----------------------------------------------------------------------
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT_PATH, "w") as f:
        for trace in filtered_traces:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")
    print(f"\nOptimized traces written to: {OUTPUT_PATH}")

    # -----------------------------------------------------------------------
    # Report
    # -----------------------------------------------------------------------
    tokens_saved = total_tokens_before - total_tokens_after
    avg_saved_pct = (
        (tokens_saved / total_tokens_before * 100) if total_tokens_before > 0 else 0.0
    )

    print("\n" + "=" * 60)
    print("  OPTIMIZATION REPORT")
    print("=" * 60)
    print(f"  Total traces:            {total}")
    print(f"  Output traces:           {len(filtered_traces)}")
    print(f"  Dropped (compression):   {dropped_compression}")
    print(f"  Failed re-validation:    {failed_revalidation}")
    print()
    print(f"  Tokens before:           {total_tokens_before:,}")
    print(f"  Tokens after:            {total_tokens_after:,}")
    print(f"  Tokens saved:            {tokens_saved:,}  ({avg_saved_pct:.1f}%)")
    print()

    if total > 0 and total_tokens_before > 0:
        avg_before = total_tokens_before / total
        avg_after = total_tokens_after / total
        print(f"  Avg tokens/trace before: {avg_before:.0f}")
        print(f"  Avg tokens/trace after:  {avg_after:.0f}")
        print(f"  Avg saved/trace:         {(avg_before - avg_after):.0f}")
        print()

    print("  Optimization Breakdown by Rule:")
    print("  " + "-" * 50)
    for rule, count in total_rule_counts.most_common():
        print(f"    {rule:<35s}  {count:>5d} applications")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
