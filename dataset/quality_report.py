#!/usr/bin/env python3
"""Generate a comprehensive quality report for the optimized RLang dataset.

Reads rlang_optimized.jsonl and produces QUALITY_REPORT.md with statistics
on compression, operator usage, phase distribution, confidence, and more.
"""

import json
import re
import sys
from collections import Counter
from pathlib import Path

from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"

INPUT_PATH = DATA_DIR / "rlang_optimized.jsonl"
REJECTED_PATH = DATA_DIR / "rlang_rejected.jsonl"
REPORT_PATH = SCRIPT_DIR / "QUALITY_REPORT.md"

# ---------------------------------------------------------------------------
# RLang operator patterns
# ---------------------------------------------------------------------------
RLANG_OPERATORS = [
    "obs", "cause", "req", "verify", "conf", "sup", "wkn", "neut",
    "resolve", "assert", "hedge", "suspend", "reject", "emit",
    "enbl", "exec", "plan", "goal", "seq", "par", "alt",
    "dep", "del", "revise", "chng", "ctx", "mem", "retr",
]

PHASE_NAMES = ["Frame", "Explore", "Verify", "Decide"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count: word_count * 1.3."""
    if not text:
        return 0
    return int(len(text.split()) * 1.3)


def count_operators(rlang_text: str) -> Counter:
    """Count occurrences of RLang operators in a trace."""
    counts: Counter = Counter()
    if not rlang_text:
        return counts
    for op in RLANG_OPERATORS:
        # Match operator calls like op(...)
        pattern = r'\b' + re.escape(op) + r'\s*\('
        matches = len(re.findall(pattern, rlang_text))
        if matches > 0:
            counts[op] = matches
    return counts


def count_phases(rlang_text: str) -> dict[str, int]:
    """Count lines (statements) per phase."""
    phase_lines: dict[str, int] = {p: 0 for p in PHASE_NAMES}
    if not rlang_text:
        return phase_lines

    current_phase = None
    brace_depth = 0

    for line in rlang_text.split("\n"):
        stripped = line.strip()

        # Detect phase start
        for phase in PHASE_NAMES:
            if f"#[phase({phase})]" in stripped:
                current_phase = phase
                break

        # Track braces
        brace_depth += stripped.count("{") - stripped.count("}")

        # Count non-empty lines inside phases as statements
        if current_phase and stripped and not stripped.startswith("//"):
            if stripped not in ("{", "}") and not stripped.startswith("#[phase"):
                if not stripped.startswith("impl "):
                    phase_lines[current_phase] += 1

    return phase_lines


def extract_confidence_values(rlang_text: str) -> list[float]:
    """Extract confidence values from metadata (p:X.XX) and type annotations (blf<X.XX>)."""
    values = []
    if not rlang_text:
        return values

    # Match p:0.XX metadata
    for m in re.finditer(r'\bp:(\d+\.\d+)', rlang_text):
        try:
            values.append(float(m.group(1)))
        except ValueError:
            pass

    # Match blf<0.XX> type annotations
    for m in re.finditer(r'blf<(\d+\.\d+)>', rlang_text):
        try:
            values.append(float(m.group(1)))
        except ValueError:
            pass

    return values


def histogram_buckets(values: list[float], buckets: list[tuple[float, float, str]]) -> list[tuple[str, int]]:
    """Create histogram from a list of values and bucket definitions."""
    result = []
    for lo, hi, label in buckets:
        count = sum(1 for v in values if lo <= v <= hi)
        result.append((label, count))
    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    # -----------------------------------------------------------------------
    # Pre-flight
    # -----------------------------------------------------------------------
    if not INPUT_PATH.exists():
        print(f"Error: Input file not found: {INPUT_PATH}")
        print("Run optimize_traces.py first to generate rlang_optimized.jsonl.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Load traces
    # -----------------------------------------------------------------------
    print(f"Reading optimized traces from {INPUT_PATH} ...")
    traces = []
    with open(INPUT_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError:
                pass

    total = len(traces)
    print(f"  Loaded {total} traces.")

    # Load rejected count
    rejected_count = 0
    if REJECTED_PATH.exists():
        with open(REJECTED_PATH) as f:
            rejected_count = sum(1 for line in f if line.strip())

    if total == 0:
        print("No traces to analyze.")
        sys.exit(0)

    # -----------------------------------------------------------------------
    # Compute metrics
    # -----------------------------------------------------------------------
    english_tokens_list = []
    rlang_tokens_list = []
    compression_ratios = []
    all_operators: Counter = Counter()
    all_phase_lines: dict[str, list[int]] = {p: [] for p in PHASE_NAMES}
    all_confidence_values: list[float] = []
    domain_compression: dict[str, list[float]] = {}
    difficulty_compression: dict[str, list[float]] = {}

    for trace in tqdm(traces, desc="Analyzing traces"):
        rlang_text = trace.get("thinking_rlang", "")
        english_text = trace.get("thinking_english", "")
        domain = trace.get("domain", "unknown")
        difficulty = trace.get("difficulty", "unknown")

        # Token counts
        eng_tokens = trace.get("thinking_tokens_est", estimate_tokens(english_text))
        rl_tokens = trace.get("rlang_tokens_est", estimate_tokens(rlang_text))
        english_tokens_list.append(eng_tokens)
        rlang_tokens_list.append(rl_tokens)

        # Compression ratio
        ratio = eng_tokens / rl_tokens if rl_tokens > 0 else 1.0
        compression_ratios.append(ratio)

        # Per-domain compression
        if domain not in domain_compression:
            domain_compression[domain] = []
        domain_compression[domain].append(ratio)

        # Per-difficulty compression
        if difficulty not in difficulty_compression:
            difficulty_compression[difficulty] = []
        difficulty_compression[difficulty].append(ratio)

        # Operator usage
        op_counts = count_operators(rlang_text)
        all_operators.update(op_counts)

        # Phase distribution
        phase_lines = count_phases(rlang_text)
        for phase, count in phase_lines.items():
            all_phase_lines[phase].append(count)

        # Confidence values
        conf_values = extract_confidence_values(rlang_text)
        all_confidence_values.extend(conf_values)

    # -----------------------------------------------------------------------
    # Build report
    # -----------------------------------------------------------------------
    report = []
    report.append("# RLang Dataset Quality Report")
    report.append("")

    # Summary
    report.append("## Summary")
    report.append("")
    report.append(f"- **Total optimized traces:** {total}")
    report.append(f"- **Rejected traces:** {rejected_count}")
    report.append(f"- **Validation pass rate:** {total / (total + rejected_count) * 100:.1f}%" if (total + rejected_count) > 0 else "- **Validation pass rate:** N/A")
    report.append("")

    # Compression ratios
    avg_ratio = sum(compression_ratios) / len(compression_ratios) if compression_ratios else 0
    median_ratio = sorted(compression_ratios)[len(compression_ratios) // 2] if compression_ratios else 0
    min_ratio = min(compression_ratios) if compression_ratios else 0
    max_ratio = max(compression_ratios) if compression_ratios else 0

    report.append("## Compression Ratios (English tokens / RLang tokens)")
    report.append("")
    report.append(f"- **Average:** {avg_ratio:.2f}x")
    report.append(f"- **Median:** {median_ratio:.2f}x")
    report.append(f"- **Min:** {min_ratio:.2f}x")
    report.append(f"- **Max:** {max_ratio:.2f}x")
    report.append("")

    # Compression ratio distribution
    ratio_buckets = [
        (0.0, 1.0, "<1x (expansion)"),
        (1.0, 2.0, "1-2x"),
        (2.0, 3.0, "2-3x"),
        (3.0, 5.0, "3-5x"),
        (5.0, 10.0, "5-10x"),
        (10.0, float("inf"), "10x+"),
    ]

    report.append("### Compression Ratio Distribution")
    report.append("")
    report.append("| Bucket | Count | % |")
    report.append("|--------|------:|---:|")
    for label, count in histogram_buckets(compression_ratios, ratio_buckets):
        pct = count / total * 100 if total > 0 else 0
        report.append(f"| {label} | {count} | {pct:.1f}% |")
    report.append("")

    # Per-domain compression
    report.append("## Compression by Domain")
    report.append("")
    report.append("| Domain | Traces | Avg Compression |")
    report.append("|--------|-------:|----------------:|")
    for domain in sorted(domain_compression.keys()):
        ratios = domain_compression[domain]
        avg = sum(ratios) / len(ratios) if ratios else 0
        report.append(f"| {domain} | {len(ratios)} | {avg:.2f}x |")
    report.append("")

    # Per-difficulty compression
    diff_order = ["easy", "medium", "hard", "phd"]
    report.append("## Compression by Difficulty")
    report.append("")
    report.append("| Difficulty | Traces | Avg Compression |")
    report.append("|------------|-------:|----------------:|")
    for diff in diff_order:
        if diff in difficulty_compression:
            ratios = difficulty_compression[diff]
            avg = sum(ratios) / len(ratios) if ratios else 0
            report.append(f"| {diff} | {len(ratios)} | {avg:.2f}x |")
    # Also add any difficulties not in the standard order
    for diff in sorted(difficulty_compression.keys()):
        if diff not in diff_order:
            ratios = difficulty_compression[diff]
            avg = sum(ratios) / len(ratios) if ratios else 0
            report.append(f"| {diff} | {len(ratios)} | {avg:.2f}x |")
    report.append("")

    # Top 10 operators
    report.append("## Top 10 Most Common RLang Operators")
    report.append("")
    report.append("| Rank | Operator | Occurrences |")
    report.append("|-----:|----------|------------:|")
    for rank, (op, count) in enumerate(all_operators.most_common(10), 1):
        report.append(f"| {rank} | `{op}()` | {count:,} |")
    report.append("")

    # Phase distribution
    report.append("## Average Phase Distribution")
    report.append("")
    report.append("| Phase | Avg Statements | % of Trace |")
    report.append("|-------|---------------:|-----------:|")
    total_avg_stmts = sum(
        sum(counts) / len(counts) if counts else 0
        for counts in all_phase_lines.values()
    )
    for phase in PHASE_NAMES:
        counts = all_phase_lines[phase]
        avg = sum(counts) / len(counts) if counts else 0
        pct = (avg / total_avg_stmts * 100) if total_avg_stmts > 0 else 0
        report.append(f"| {phase} | {avg:.1f} | {pct:.1f}% |")
    report.append("")

    # Confidence values
    if all_confidence_values:
        avg_conf = sum(all_confidence_values) / len(all_confidence_values)
        median_conf = sorted(all_confidence_values)[len(all_confidence_values) // 2]
        min_conf = min(all_confidence_values)
        max_conf = max(all_confidence_values)

        report.append("## Confidence Value Statistics")
        report.append("")
        report.append(f"- **Total confidence annotations:** {len(all_confidence_values)}")
        report.append(f"- **Average:** {avg_conf:.3f}")
        report.append(f"- **Median:** {median_conf:.3f}")
        report.append(f"- **Min:** {min_conf:.3f}")
        report.append(f"- **Max:** {max_conf:.3f}")
        report.append("")

        conf_buckets = [
            (0.0, 0.5, "0.0-0.5 (low)"),
            (0.5, 0.7, "0.5-0.7 (moderate)"),
            (0.7, 0.85, "0.7-0.85 (high)"),
            (0.85, 0.95, "0.85-0.95 (very high)"),
            (0.95, 1.0, "0.95-1.0 (near certain)"),
        ]
        report.append("### Confidence Distribution")
        report.append("")
        report.append("| Range | Count | % |")
        report.append("|-------|------:|---:|")
        for label, count in histogram_buckets(all_confidence_values, conf_buckets):
            pct = count / len(all_confidence_values) * 100 if all_confidence_values else 0
            report.append(f"| {label} | {count} | {pct:.1f}% |")
        report.append("")

    # Token count distribution
    report.append("## RLang Token Count Distribution")
    report.append("")
    token_buckets = [
        (0, 50, "0-50"),
        (51, 100, "51-100"),
        (101, 200, "101-200"),
        (201, 500, "201-500"),
        (501, 1000, "501-1K"),
        (1001, float("inf"), "1K+"),
    ]
    report.append("| Bucket | Count | % |")
    report.append("|--------|------:|---:|")
    rl_token_floats = [float(t) for t in rlang_tokens_list]
    for label, count in histogram_buckets(rl_token_floats, token_buckets):
        pct = count / total * 100 if total > 0 else 0
        report.append(f"| {label} | {count} | {pct:.1f}% |")
    report.append("")

    # English token count distribution
    report.append("## English Token Count Distribution")
    report.append("")
    eng_token_buckets = [
        (0, 100, "0-100"),
        (101, 500, "101-500"),
        (501, 1000, "501-1K"),
        (1001, 2000, "1K-2K"),
        (2001, 5000, "2K-5K"),
        (5001, float("inf"), "5K+"),
    ]
    report.append("| Bucket | Count | % |")
    report.append("|--------|------:|---:|")
    eng_token_floats = [float(t) for t in english_tokens_list]
    for label, count in histogram_buckets(eng_token_floats, eng_token_buckets):
        pct = count / total * 100 if total > 0 else 0
        report.append(f"| {label} | {count} | {pct:.1f}% |")
    report.append("")

    # -----------------------------------------------------------------------
    # Write report
    # -----------------------------------------------------------------------
    full_report = "\n".join(report)
    print(full_report)

    REPORT_PATH.write_text(full_report)
    print(f"\nReport saved to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
