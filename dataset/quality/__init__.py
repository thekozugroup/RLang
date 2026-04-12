"""Multi-layer quality checking system for RLang training data.

This module provides a 6-layer quality checking pipeline for validating
RLang reasoning traces converted from English chain-of-thought:

    Layer 1: Structural Integrity  (structural_check)
    Layer 2: Semantic Correctness  (semantic_check)
    Layer 3: Token Efficiency      (efficiency_check)
    Layer 4: Reasoning Signal      (signal_check)
    Layer 5: Self-Correction       (self_correction_check)
    Layer 6: Cross-Trace Consistency (consistency_check)

Each layer produces a CheckResult; the composite QualityResult aggregates
all layers into a single pass/fail decision with a 0.0-1.0 score.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class CheckResult:
    """Result from a single quality check layer."""

    name: str
    passed: bool
    score: float  # 0.0-1.0
    details: str

    def __repr__(self) -> str:
        status = "PASS" if self.passed else "FAIL"
        return f"CheckResult({self.name}: {status} score={self.score:.2f})"


@dataclass
class QualityResult:
    """Composite quality result aggregating all check layers."""

    trace_id: str
    passed: bool
    score: float  # 0.0-1.0 composite quality score
    checks: dict[str, CheckResult] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)  # human-readable issue descriptions
    suggestions: list[str] = field(default_factory=list)  # optimization suggestions

    @property
    def classification(self) -> str:
        """Classify trace based on composite score.

        Returns:
            'PASS'   -- score >= 0.85, include in training set
            'REVIEW' -- score 0.60-0.84, needs manual review
            'REJECT' -- score < 0.60, exclude from training set
        """
        if self.score >= 0.85:
            return "PASS"
        elif self.score >= 0.60:
            return "REVIEW"
        else:
            return "REJECT"

    def summary(self) -> str:
        """Return a human-readable summary."""
        lines = [
            f"Trace {self.trace_id}: {self.classification} (score={self.score:.3f})",
        ]
        for name, cr in self.checks.items():
            status = "PASS" if cr.passed else "FAIL"
            lines.append(f"  [{status}] {name}: {cr.score:.2f} -- {cr.details}")
        if self.issues:
            lines.append("  Issues:")
            for issue in self.issues:
                lines.append(f"    - {issue}")
        if self.suggestions:
            lines.append("  Suggestions:")
            for s in self.suggestions:
                lines.append(f"    - {s}")
        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"QualityResult({self.trace_id}: {self.classification} score={self.score:.3f})"


# Classification thresholds
PASS_THRESHOLD = 0.85
REVIEW_THRESHOLD = 0.60

# Composite score weights
WEIGHTS = {
    "structural": 0.25,
    "semantic": 0.25,
    "efficiency": 0.15,
    "signal": 0.20,
    "self_correction": 0.10,
    "consistency": 0.05,
}
