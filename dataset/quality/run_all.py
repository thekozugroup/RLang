"""Master quality runner for the 6-layer quality checking system.

Reads RLang traces from dataset/data/rlang_converted.jsonl (or a given input),
runs all 6 quality checks on each trace, computes composite scores, and
classifies traces into PASS/REVIEW/REJECT buckets.

Outputs:
    dataset/data/quality_results.jsonl  -- per-trace quality scores and details
    dataset/data/quality_passed.jsonl   -- traces that passed (score >= 0.85)
    dataset/data/quality_review.jsonl   -- traces needing review (0.60-0.84)
    dataset/data/quality_rejected.jsonl -- traces that failed (score < 0.60)

Usage:
    python -m dataset.quality.run_all
    python -m dataset.quality.run_all --input path/to/traces.jsonl
    python -m dataset.quality.run_all --input path/to/traces.jsonl --output-dir path/to/output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dataset.quality import (
    PASS_THRESHOLD,
    REVIEW_THRESHOLD,
    WEIGHTS,
    CheckResult,
    QualityResult,
)
from dataset.quality import structural_check
from dataset.quality import semantic_check
from dataset.quality import efficiency_check
from dataset.quality import signal_check
from dataset.quality import self_correction_check
from dataset.quality import consistency_check
from dataset.quality.consistency_check import CorpusStats


def run_all_checks(
    trace: dict,
    corpus_stats: CorpusStats | None = None,
) -> QualityResult:
    """Run all 6 quality checks on a single trace.

    Args:
        trace: Dictionary with at least 'rlang' key.
        corpus_stats: Pre-computed corpus statistics for consistency check.

    Returns:
        QualityResult with composite score and all individual check results.
    """
    trace_id = trace.get("id", trace.get("trace_id", "unknown"))

    # Run each check
    checks: dict[str, CheckResult] = {}
    checks["structural"] = structural_check.run_check(trace)
    checks["semantic"] = semantic_check.run_check(trace)
    checks["efficiency"] = efficiency_check.run_check(trace)
    checks["signal"] = signal_check.run_check(trace)
    checks["self_correction"] = self_correction_check.run_check(trace)
    checks["consistency"] = consistency_check.run_check(trace, corpus_stats)

    # Compute composite score (weighted average)
    composite_score = sum(
        checks[name].score * weight
        for name, weight in WEIGHTS.items()
        if name in checks
    )

    # Collect all issues
    issues: list[str] = []
    suggestions: list[str] = []

    for name, cr in checks.items():
        if not cr.passed:
            issues.append(f"[{name}] {cr.details}")

    # Generate suggestions based on failed checks
    if checks["structural"].score < 0.8:
        suggestions.append("Review phase structure -- ensure all 4 phases present in order")
    if checks["semantic"].score < 0.8:
        suggestions.append("Check operator arity and evidence block syntax")
    if checks["efficiency"].score < 0.8:
        suggestions.append("Optimize token usage -- remove redundant observations and metadata")
    if checks["signal"].score < 0.8:
        suggestions.append("Verify reasoning signal -- ensure RLang captures English reasoning faithfully")
    if checks["self_correction"].score < 0.8:
        suggestions.append("Review self-correction handling -- productive corrections -> bt(), wasteful -> strip")
    if checks["consistency"].score < 0.8:
        suggestions.append("Check consistency with corpus norms for operator usage and confidence calibration")

    passed = composite_score >= PASS_THRESHOLD

    return QualityResult(
        trace_id=trace_id,
        passed=passed,
        score=composite_score,
        checks=checks,
        issues=issues,
        suggestions=suggestions,
    )


def _result_to_dict(result: QualityResult) -> dict:
    """Convert a QualityResult to a JSON-serializable dictionary."""
    return {
        "trace_id": result.trace_id,
        "passed": result.passed,
        "score": round(result.score, 4),
        "classification": result.classification,
        "checks": {
            name: {
                "name": cr.name,
                "passed": cr.passed,
                "score": round(cr.score, 4),
                "details": cr.details,
            }
            for name, cr in result.checks.items()
        },
        "issues": result.issues,
        "suggestions": result.suggestions,
    }


def _load_traces(input_path: str) -> list[dict]:
    """Load traces from a JSONL file."""
    traces: list[dict] = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                trace = json.loads(line)
                if "id" not in trace and "trace_id" not in trace:
                    trace["id"] = f"trace-{line_num:04d}"
                traces.append(trace)
            except json.JSONDecodeError as e:
                print(f"WARNING: Skipping line {line_num} -- invalid JSON: {e}")
    return traces


def _print_summary(
    results: list[QualityResult],
    elapsed: float,
) -> None:
    """Print a summary of quality check results."""
    total = len(results)
    if total == 0:
        print("No traces processed.")
        return

    passed = sum(1 for r in results if r.classification == "PASS")
    review = sum(1 for r in results if r.classification == "REVIEW")
    rejected = sum(1 for r in results if r.classification == "REJECT")

    scores = [r.score for r in results]
    avg_score = sum(scores) / len(scores)
    min_score = min(scores)
    max_score = max(scores)

    # Score distribution
    buckets = Counter()
    for s in scores:
        bucket = f"{int(s * 10) / 10:.1f}"
        buckets[bucket] += 1

    # Most common issues
    all_issues: list[str] = []
    for r in results:
        all_issues.extend(r.issues)
    issue_counts = Counter(all_issues)

    print("\n" + "=" * 72)
    print("  QUALITY CHECK SUMMARY")
    print("=" * 72)
    print(f"\n  Total traces:  {total}")
    print(f"  Time elapsed:  {elapsed:.1f}s ({elapsed / total:.3f}s per trace)")
    print()
    print(f"  PASS   (>= 0.85):  {passed:5d}  ({passed / total:.1%})")
    print(f"  REVIEW (0.60-0.84): {review:5d}  ({review / total:.1%})")
    print(f"  REJECT (< 0.60):    {rejected:5d}  ({rejected / total:.1%})")
    print()
    print(f"  Score statistics:")
    print(f"    Mean:  {avg_score:.3f}")
    print(f"    Min:   {min_score:.3f}")
    print(f"    Max:   {max_score:.3f}")
    print()
    print(f"  Score distribution:")
    for bucket in sorted(buckets.keys()):
        count = buckets[bucket]
        bar = "#" * min(count, 50)
        print(f"    {bucket}: {bar} ({count})")

    if issue_counts:
        print(f"\n  Most common issues:")
        for issue, count in issue_counts.most_common(10):
            truncated = issue[:70] + "..." if len(issue) > 70 else issue
            print(f"    {count:3d}x  {truncated}")

    # Per-layer average scores
    print(f"\n  Per-layer average scores:")
    for layer_name in WEIGHTS:
        layer_scores = [
            r.checks[layer_name].score
            for r in results
            if layer_name in r.checks
        ]
        if layer_scores:
            avg = sum(layer_scores) / len(layer_scores)
            weight = WEIGHTS[layer_name]
            print(f"    {layer_name:20s}  avg={avg:.3f}  weight={weight:.0%}")

    print("\n" + "=" * 72)


def main() -> None:
    """Main entry point for the quality check runner."""
    parser = argparse.ArgumentParser(
        description="Run 6-layer quality checks on RLang training traces"
    )
    parser.add_argument(
        "--input",
        default=str(PROJECT_ROOT / "dataset" / "data" / "rlang_converted.jsonl"),
        help="Input JSONL file with traces (default: dataset/data/rlang_converted.jsonl)",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "dataset" / "data"),
        help="Output directory for results (default: dataset/data/)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Process only first N traces (0 = all)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-trace results",
    )

    args = parser.parse_args()

    # Validate input file
    if not os.path.exists(args.input):
        print(f"ERROR: Input file not found: {args.input}")
        print("Expected a JSONL file with traces containing at least an 'rlang' field.")
        print("Generate it with the conversion pipeline first.")
        sys.exit(1)

    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)

    # Load traces
    print(f"Loading traces from: {args.input}")
    traces = _load_traces(args.input)
    if args.limit > 0:
        traces = traces[: args.limit]
    print(f"Loaded {len(traces)} trace(s)")

    if not traces:
        print("No traces to process.")
        sys.exit(0)

    # Phase 1: Build corpus stats (first pass)
    print("Phase 1: Building corpus statistics...")
    corpus_stats = CorpusStats()
    for trace in traces:
        corpus_stats.update(trace)
    print(f"  Corpus stats built from {corpus_stats.trace_count} traces")
    if corpus_stats.compression_ratios:
        print(f"  Mean compression: {corpus_stats.mean_compression:.1f}x")
        print(f"  Std compression:  {corpus_stats.std_compression:.1f}x")

    # Phase 2: Run quality checks (second pass)
    print(f"\nPhase 2: Running 6-layer quality checks...")
    start_time = time.time()

    results: list[QualityResult] = []
    for i, trace in enumerate(traces):
        result = run_all_checks(trace, corpus_stats)
        results.append(result)

        if args.verbose:
            print(result.summary())
            print()

        # Progress indicator
        if (i + 1) % 100 == 0:
            elapsed = time.time() - start_time
            rate = (i + 1) / elapsed
            print(f"  Processed {i + 1}/{len(traces)} ({rate:.0f} traces/sec)")

    elapsed = time.time() - start_time

    # Phase 3: Write output files
    print(f"\nPhase 3: Writing output files...")

    output_dir = Path(args.output_dir)

    # All results
    results_path = output_dir / "quality_results.jsonl"
    with open(results_path, "w", encoding="utf-8") as f:
        for result in results:
            f.write(json.dumps(_result_to_dict(result)) + "\n")
    print(f"  All results:     {results_path} ({len(results)} traces)")

    # Passed traces
    passed_path = output_dir / "quality_passed.jsonl"
    passed_traces = [
        {**traces[i], **_result_to_dict(results[i])}
        for i in range(len(results))
        if results[i].classification == "PASS"
    ]
    with open(passed_path, "w", encoding="utf-8") as f:
        for trace in passed_traces:
            f.write(json.dumps(trace) + "\n")
    print(f"  Passed traces:   {passed_path} ({len(passed_traces)} traces)")

    # Review traces
    review_path = output_dir / "quality_review.jsonl"
    review_traces = [
        {**traces[i], **_result_to_dict(results[i])}
        for i in range(len(results))
        if results[i].classification == "REVIEW"
    ]
    with open(review_path, "w", encoding="utf-8") as f:
        for trace in review_traces:
            f.write(json.dumps(trace) + "\n")
    print(f"  Review traces:   {review_path} ({len(review_traces)} traces)")

    # Rejected traces
    rejected_path = output_dir / "quality_rejected.jsonl"
    rejected_traces = [
        {**traces[i], **_result_to_dict(results[i])}
        for i in range(len(results))
        if results[i].classification == "REJECT"
    ]
    with open(rejected_path, "w", encoding="utf-8") as f:
        for trace in rejected_traces:
            f.write(json.dumps(trace) + "\n")
    print(f"  Rejected traces: {rejected_path} ({len(rejected_traces)} traces)")

    # Print summary
    _print_summary(results, elapsed)


if __name__ == "__main__":
    main()
