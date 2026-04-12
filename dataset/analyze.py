"""Analyze the standardized reasoning dataset and print a markdown report."""

import json
import re
from collections import Counter
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).parent / "data"
PARQUET_PATH = DATA_DIR / "standardized.parquet"

# Self-correction / self-reflection markers
SELF_CORRECTION_MARKERS = [
    r"\bwait\b",
    r"\bactually\b",
    r"\bhmm\b",
    r"\bno,",
    r"\blet me reconsider\b",
]


def count_markers(text: str) -> dict[str, int]:
    """Count occurrences of self-correction markers in text."""
    if not text:
        return {m: 0 for m in SELF_CORRECTION_MARKERS}
    counts = {}
    text_lower = text.lower()
    for marker in SELF_CORRECTION_MARKERS:
        counts[marker] = len(re.findall(marker, text_lower))
    return counts


def token_histogram(tokens: pd.Series) -> list[tuple[str, int]]:
    """Create histogram buckets for token counts."""
    buckets = [
        (0, 100, "0-100"),
        (101, 500, "101-500"),
        (501, 1000, "501-1K"),
        (1001, 2000, "1K-2K"),
        (2001, 5000, "2K-5K"),
        (5001, 10000, "5K-10K"),
        (10001, float("inf"), "10K+"),
    ]
    result = []
    for lo, hi, label in buckets:
        count = ((tokens >= lo) & (tokens <= hi)).sum()
        result.append((label, count))
    return result


def main():
    if not PARQUET_PATH.exists():
        print(f"Error: {PARQUET_PATH} not found. Run download.py first.")
        return

    df = pd.read_parquet(PARQUET_PATH)
    total_rows = len(df)

    # Count markers across all traces
    all_marker_counts = Counter()
    total_marker_instances = 0
    rows_with_markers = 0

    for _, row in df.iterrows():
        text = row.get("thinking_english", "")
        if not text:
            continue
        counts = count_markers(text)
        row_total = sum(counts.values())
        if row_total > 0:
            rows_with_markers += 1
        total_marker_instances += row_total
        for marker, count in counts.items():
            all_marker_counts[marker] += count

    # Estimate self-reflection token overhead
    # Each marker occurrence ~ 5 words of surrounding reflection context (conservative)
    REFLECTION_CONTEXT_WORDS = 15
    reflection_tokens_est = total_marker_instances * REFLECTION_CONTEXT_WORDS * 1.3
    total_thinking_tokens = df["thinking_tokens_est"].sum()
    reflection_pct = (
        (reflection_tokens_est / total_thinking_tokens * 100)
        if total_thinking_tokens > 0
        else 0
    )

    # Build report
    report = []
    report.append("# Reasoning Dataset Analysis Report")
    report.append("")
    report.append(f"**Total samples:** {total_rows}")
    report.append(
        f"**Sources:** Opus 4.6 Reasoning ({len(df[df['source'] == 'opus-4.6-reasoning'])}), "
        f"Harmonic Reasoning ({len(df[df['source'] == 'harmonic-reasoning-v1'])})"
    )
    report.append("")

    # Token distribution histogram
    report.append("## Token Count Distribution (Estimated)")
    report.append("")
    report.append("| Bucket | Count | % |")
    report.append("|--------|------:|---:|")
    hist = token_histogram(df["thinking_tokens_est"])
    for label, count in hist:
        pct = count / total_rows * 100
        report.append(f"| {label} | {count} | {pct:.1f}% |")
    report.append("")

    # Average thinking length per domain
    report.append("## Average Thinking Length by Domain")
    report.append("")
    report.append("| Domain | Samples | Avg Tokens (est) | Avg Chars |")
    report.append("|--------|--------:|------------------:|----------:|")
    domain_stats = (
        df.groupby("domain")
        .agg(
            samples=("id", "count"),
            avg_tokens=("thinking_tokens_est", "mean"),
            avg_chars=("thinking_english", lambda x: x.str.len().mean()),
        )
        .sort_values("avg_tokens", ascending=False)
    )
    for domain, row in domain_stats.iterrows():
        report.append(
            f"| {domain} | {row['samples']} | {row['avg_tokens']:.0f} | {row['avg_chars']:.0f} |"
        )
    report.append("")

    # Average thinking length per difficulty
    report.append("## Average Thinking Length by Difficulty")
    report.append("")
    report.append("| Difficulty | Samples | Avg Tokens (est) | Avg Chars |")
    report.append("|------------|--------:|------------------:|----------:|")
    diff_order = ["easy", "medium", "hard", "phd"]
    diff_stats = (
        df.groupby("difficulty")
        .agg(
            samples=("id", "count"),
            avg_tokens=("thinking_tokens_est", "mean"),
            avg_chars=("thinking_english", lambda x: x.str.len().mean()),
        )
    )
    for diff in diff_order:
        if diff in diff_stats.index:
            row = diff_stats.loc[diff]
            report.append(
                f"| {diff} | {row['samples']} | {row['avg_tokens']:.0f} | {row['avg_chars']:.0f} |"
            )
    report.append("")

    # Self-correction markers
    report.append("## Self-Correction Markers in English Traces")
    report.append("")
    report.append(f"**Rows with at least one marker:** {rows_with_markers} / {total_rows} ({rows_with_markers / total_rows * 100:.1f}%)")
    report.append(f"**Total marker instances:** {total_marker_instances}")
    report.append("")
    report.append("| Marker | Count |")
    report.append("|--------|------:|")
    # Pretty-print marker names
    marker_labels = {
        r"\bwait\b": '"wait"',
        r"\bactually\b": '"actually"',
        r"\bhmm\b": '"hmm"',
        r"\bno,": '"no,"',
        r"\blet me reconsider\b": '"let me reconsider"',
    }
    for marker in SELF_CORRECTION_MARKERS:
        label = marker_labels.get(marker, marker)
        report.append(f"| {label} | {all_marker_counts[marker]} |")
    report.append("")

    # Self-reflection overhead estimate
    report.append("## Self-Reflection Overhead Estimate")
    report.append("")
    report.append(f"- Total estimated thinking tokens: **{total_thinking_tokens:,.0f}**")
    report.append(f"- Estimated self-reflection tokens: **{reflection_tokens_est:,.0f}**")
    report.append(f"- Self-reflection overhead: **{reflection_pct:.1f}%** of thinking tokens")
    report.append("")
    report.append(
        "*Note: Overhead is estimated by assuming ~15 words of reflection context "
        "around each self-correction marker occurrence.*"
    )

    # Print report
    full_report = "\n".join(report)
    print(full_report)

    # Also save to file
    report_path = DATA_DIR / "analysis_report.md"
    report_path.write_text(full_report)
    print(f"\n\nReport saved to: {report_path}")


if __name__ == "__main__":
    main()
