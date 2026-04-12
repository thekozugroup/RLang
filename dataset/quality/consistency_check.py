"""Layer 6: Cross-Trace Consistency Check.

Validates that a trace is consistent with corpus-wide norms for operator
usage, confidence calibration, and compression ratios.

Rules enforced:
    - Similar problems get similar RLang structures
    - Operator usage is consistent across domains
    - Confidence calibration is consistent (similar hedging -> similar p: values)
    - Flag outlier traces (compression ratio >2 std devs from mean)
    - Flag traces with unusual operator distributions
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field

from . import CheckResult

# Regex patterns
OPERATOR_PATTERN = re.compile(
    r"\b(obs|cause|prvnt|enbl|req|sim|confl|cncl|cntns|isa|"
    r"chng|seq|sup|wkn|neut|resolve|conf|decay|refresh|"
    r"goal|dcmp|prioritize|select|replan|"
    r"exec|inv|pcv|rmb|rcl|forget|bt|verify|retry_with|"
    r"dlg|msg|discover|match_capability|negotiate|cancel|poll|"
    r"subscribe|cfp|propose|accept_proposal|reject_proposal|"
    r"inform|query_if|agree|refuse|resolve_conflict|"
    r"assert|hedge|suspend|reject|emit)\b"
)
CONFIDENCE_PATTERN = re.compile(r"\bp:([\d.]+)")
BLF_CONFIDENCE_PATTERN = re.compile(r"blf<([\d.]+)")
PHASE_PATTERN = re.compile(r"#\[phase\((\w+)\)\]")


@dataclass
class CorpusStats:
    """Accumulated statistics across the entire corpus.

    Build this incrementally by calling update() for each trace,
    then use it in run_check() for consistency evaluation.
    """

    # Compression ratios
    compression_ratios: list[float] = field(default_factory=list)

    # Operator frequency distributions per trace
    operator_distributions: list[Counter] = field(default_factory=list)

    # Confidence values seen in corpus
    confidence_values: list[float] = field(default_factory=list)

    # Phase proportion distributions
    phase_proportions: list[dict[str, float]] = field(default_factory=list)

    # Number of traces processed
    trace_count: int = 0

    def update(self, trace: dict) -> None:
        """Update corpus stats with a new trace."""
        rlang = trace.get("rlang", "")
        english = trace.get("english", trace.get("original", ""))

        self.trace_count += 1

        # Compression ratio
        if english and rlang:
            eng_tokens = len(english.split())
            rl_tokens = len(rlang.split())
            if rl_tokens > 0:
                self.compression_ratios.append(eng_tokens / rl_tokens)

        # Operator distribution
        ops = Counter(OPERATOR_PATTERN.findall(rlang))
        self.operator_distributions.append(ops)

        # Confidence values
        for m in CONFIDENCE_PATTERN.finditer(rlang):
            try:
                self.confidence_values.append(float(m.group(1)))
            except ValueError:
                pass
        for m in BLF_CONFIDENCE_PATTERN.finditer(rlang):
            try:
                self.confidence_values.append(float(m.group(1)))
            except ValueError:
                pass

        # Phase proportions
        sections = PHASE_PATTERN.split(rlang)
        phase_lens: dict[str, int] = {}
        i = 1
        while i < len(sections):
            phase_name = sections[i]
            block_text = sections[i + 1] if (i + 1) < len(sections) else ""
            phase_lens[phase_name] = phase_lens.get(phase_name, 0) + len(block_text)
            i += 2
        total = sum(phase_lens.values())
        if total > 0:
            props = {p: l / total for p, l in phase_lens.items()}
            self.phase_proportions.append(props)

    @property
    def mean_compression(self) -> float:
        if not self.compression_ratios:
            return 3.5  # Default expected ratio
        return sum(self.compression_ratios) / len(self.compression_ratios)

    @property
    def std_compression(self) -> float:
        if len(self.compression_ratios) < 2:
            return 1.5  # Default std dev
        mean = self.mean_compression
        variance = sum((x - mean) ** 2 for x in self.compression_ratios) / (
            len(self.compression_ratios) - 1
        )
        return math.sqrt(variance)

    @property
    def mean_confidence(self) -> float:
        if not self.confidence_values:
            return 0.75
        return sum(self.confidence_values) / len(self.confidence_values)

    @property
    def corpus_operator_dist(self) -> Counter:
        """Aggregate operator distribution across all traces."""
        total: Counter = Counter()
        for dist in self.operator_distributions:
            total.update(dist)
        return total

    def operator_frequency(self, op: str) -> float:
        """Get the average frequency of an operator across traces."""
        if not self.operator_distributions:
            return 0.0
        counts = [d.get(op, 0) for d in self.operator_distributions]
        return sum(counts) / len(counts)


# Global corpus stats instance (built up during run_all)
_corpus_stats: CorpusStats | None = None


def set_corpus_stats(stats: CorpusStats) -> None:
    """Set the corpus stats to use for consistency checks."""
    global _corpus_stats
    _corpus_stats = stats


def get_corpus_stats() -> CorpusStats:
    """Get the current corpus stats, creating a default if needed."""
    global _corpus_stats
    if _corpus_stats is None:
        _corpus_stats = CorpusStats()
    return _corpus_stats


def _check_compression_outlier(trace: dict, stats: CorpusStats) -> list[str]:
    """Check if the trace's compression ratio is an outlier."""
    issues = []
    english = trace.get("english", trace.get("original", ""))
    rlang = trace.get("rlang", "")

    if not english or not rlang:
        return issues

    eng_tokens = len(english.split())
    rl_tokens = len(rlang.split())
    if rl_tokens == 0:
        return ["RLang trace is empty"]

    ratio = eng_tokens / rl_tokens
    mean = stats.mean_compression
    std = stats.std_compression

    if std > 0 and abs(ratio - mean) > 2 * std:
        direction = "above" if ratio > mean else "below"
        z_score = (ratio - mean) / std
        issues.append(
            f"Compression ratio {ratio:.1f}x is an outlier "
            f"({direction} mean {mean:.1f}x, z-score={z_score:.1f})"
        )

    return issues


def _check_operator_consistency(rlang: str, stats: CorpusStats) -> list[str]:
    """Check that operator usage is consistent with corpus norms."""
    issues = []
    trace_ops = Counter(OPERATOR_PATTERN.findall(rlang))

    if not trace_ops or stats.trace_count < 5:
        return issues  # Not enough data for comparison

    # Check for operators that are unusually frequent or absent
    corpus_dist = stats.corpus_operator_dist
    total_corpus_ops = sum(corpus_dist.values())
    total_trace_ops = sum(trace_ops.values())

    if total_corpus_ops == 0 or total_trace_ops == 0:
        return issues

    # Flag operators used much more than corpus average
    for op, count in trace_ops.items():
        trace_freq = count / total_trace_ops
        corpus_freq = corpus_dist.get(op, 0) / total_corpus_ops

        if corpus_freq > 0 and trace_freq > corpus_freq * 5:
            issues.append(
                f"Operator '{op}' is used {trace_freq:.1%} of the time "
                f"(corpus average: {corpus_freq:.1%}) -- unusually frequent"
            )

    # Check for expected operators that are completely missing
    expected_ops = {"obs", "resolve", "verify"}
    for op in expected_ops:
        if op not in trace_ops and corpus_dist.get(op, 0) > stats.trace_count * 0.5:
            issues.append(
                f"Expected operator '{op}' is missing "
                f"(used in {corpus_dist.get(op, 0) / stats.trace_count:.0%} of traces)"
            )

    return issues


def _check_confidence_calibration(trace: dict, stats: CorpusStats) -> list[str]:
    """Check that confidence values are calibrated consistently with corpus."""
    issues = []
    rlang = trace.get("rlang", "")

    # Extract confidence values from this trace
    trace_confs = []
    for m in CONFIDENCE_PATTERN.finditer(rlang):
        try:
            trace_confs.append(float(m.group(1)))
        except ValueError:
            pass
    for m in BLF_CONFIDENCE_PATTERN.finditer(rlang):
        try:
            trace_confs.append(float(m.group(1)))
        except ValueError:
            pass

    if not trace_confs or stats.trace_count < 5:
        return issues

    # Check if trace's average confidence is far from corpus mean
    trace_mean = sum(trace_confs) / len(trace_confs)
    corpus_mean = stats.mean_confidence

    if abs(trace_mean - corpus_mean) > 0.25:
        direction = "higher" if trace_mean > corpus_mean else "lower"
        issues.append(
            f"Average confidence {trace_mean:.2f} is significantly {direction} "
            f"than corpus mean {corpus_mean:.2f}"
        )

    # Check for suspiciously uniform confidence values
    if len(trace_confs) >= 3:
        unique_confs = set(round(c, 2) for c in trace_confs)
        if len(unique_confs) == 1:
            issues.append(
                f"All {len(trace_confs)} confidence values are identical ({trace_confs[0]:.2f}) "
                f"-- may indicate confidence theater"
            )

    return issues


def _check_structural_consistency(trace: dict, stats: CorpusStats) -> list[str]:
    """Check that the trace's structure is consistent with corpus norms."""
    issues = []
    rlang = trace.get("rlang", "")

    if stats.trace_count < 5:
        return issues

    # Extract phase proportions for this trace
    sections = PHASE_PATTERN.split(rlang)
    phase_lens: dict[str, int] = {}
    i = 1
    while i < len(sections):
        phase_name = sections[i]
        block_text = sections[i + 1] if (i + 1) < len(sections) else ""
        phase_lens[phase_name] = phase_lens.get(phase_name, 0) + len(block_text)
        i += 2

    total = sum(phase_lens.values())
    if total == 0:
        return issues

    trace_props = {p: l / total for p, l in phase_lens.items()}

    # Calculate corpus average proportions
    if stats.phase_proportions:
        corpus_avg: dict[str, float] = {}
        for phase in ["Frame", "Explore", "Verify", "Decide"]:
            vals = [p.get(phase, 0.0) for p in stats.phase_proportions]
            corpus_avg[phase] = sum(vals) / len(vals) if vals else 0.0

        # Flag phases that are very different from corpus average
        for phase in ["Frame", "Explore", "Verify", "Decide"]:
            trace_prop = trace_props.get(phase, 0.0)
            corp_prop = corpus_avg.get(phase, 0.0)
            if corp_prop > 0 and abs(trace_prop - corp_prop) > 0.20:
                issues.append(
                    f"Phase {phase} proportion {trace_prop:.1%} differs from "
                    f"corpus average {corp_prop:.1%} by {abs(trace_prop - corp_prop):.1%}"
                )

    return issues


def run_check(trace: dict, corpus_stats: CorpusStats | None = None) -> CheckResult:
    """Run cross-trace consistency check on a single trace.

    Args:
        trace: Dictionary with 'rlang' key and optionally 'english'/'original'.
        corpus_stats: Pre-computed corpus statistics. If None, uses global stats.

    Returns:
        CheckResult with consistency check results.
    """
    stats = corpus_stats or get_corpus_stats()
    rlang = trace.get("rlang", "")
    issues: list[str] = []
    score = 1.0

    # If we don't have enough corpus data, give a neutral score
    if stats.trace_count < 5:
        return CheckResult(
            name="consistency",
            passed=True,
            score=0.90,
            details=f"Insufficient corpus data ({stats.trace_count} traces) for consistency check",
        )

    # 1. Compression ratio outlier
    comp_issues = _check_compression_outlier(trace, stats)
    issues.extend(comp_issues)
    score -= 0.15 * len(comp_issues)

    # 2. Operator distribution consistency
    op_issues = _check_operator_consistency(rlang, stats)
    issues.extend(op_issues)
    score -= 0.10 * len(op_issues)

    # 3. Confidence calibration
    conf_issues = _check_confidence_calibration(trace, stats)
    issues.extend(conf_issues)
    score -= 0.15 * len(conf_issues)

    # 4. Structural consistency
    struct_issues = _check_structural_consistency(trace, stats)
    issues.extend(struct_issues)
    score -= 0.10 * len(struct_issues)

    # Clamp score
    score = max(0.0, min(1.0, score))

    details = (
        f"{len(issues)} consistency issue(s) found"
        if issues
        else f"Consistent with corpus ({stats.trace_count} traces)"
    )
    if issues:
        details += ": " + "; ".join(issues[:2])
        if len(issues) > 2:
            details += f" (+{len(issues) - 2} more)"

    return CheckResult(
        name="consistency",
        passed=score >= 0.8,
        score=score,
        details=details,
    )


if __name__ == "__main__":
    # Build some fake corpus stats for testing
    stats = CorpusStats()
    for _ in range(10):
        stats.update({
            "english": "This is a test English trace with some reasoning steps. "
                       "First we observe something. Then we analyze it. "
                       "The evidence supports the conclusion.",
            "rlang": """
#[phase(Frame)]
impl Deductive {
    let x: blf<0.90> = obs(test) | p:0.90 | ep:direct;
}
#[phase(Explore)]
{
    let ev = [x => sup(goal, +0.15)];
    let r = resolve(ev) -> Ok(blf<0.80>);
}
#[phase(Verify)]
{
    req(goal, obs(test)) |> verify(test) -> Ok(());
}
#[phase(Decide)]
{
    match conf(r) {
        c if c > 0.55 => assert(goal),
        _ => reject(goal),
    }
}
""",
        })

    sample_trace = {
        "id": "test-001",
        "english": "Some reasoning about deployment decisions.",
        "rlang": """
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct;
}
#[phase(Explore)]
{
    let ev = [tests => sup(deploy, +0.15)];
    let deploy_blf = resolve(ev) -> Ok(blf<0.80>);
}
#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}
#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        _ => reject(deploy),
    }
}
""",
    }

    result = run_check(sample_trace, stats)
    print(f"Result: {result}")
    print(f"  Score: {result.score:.2f}")
    print(f"  Passed: {result.passed}")
    print(f"  Details: {result.details}")
