"""Layer 5: Self-Correction Quality Check.

Validates how self-correction moments from the English reasoning trace are
handled in the RLang conversion.

Distinguishes between:
    a. Productive corrections: model catches a real error -> should be bt() + DiagnosisKind
    b. Wasteful rumination: model second-guesses without new info -> should be stripped
    c. Verification steps: checking work once -> should be in Verify phase
    d. Over-verification: checking same thing repeatedly -> should be stripped

Based on anti-patterns #2 (infinite reflection), #5 (over-verification),
and #6 (rumination) from the RLang specification.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import CheckResult

# Self-correction markers in English text
PRODUCTIVE_CORRECTION_PATTERNS = [
    re.compile(r"\bwait\b.*\b(?:actually|I was wrong|that's (?:wrong|incorrect)|mistake)\b", re.I | re.DOTALL),
    re.compile(r"\b(?:actually|no),?\s+(?:that's|I was|it's)\s+(?:wrong|incorrect|not right)\b", re.I),
    re.compile(r"\bI (?:made|had) (?:a|an) (?:error|mistake)\b", re.I),
    re.compile(r"\b(?:correction|correcting|let me (?:fix|correct))\b", re.I),
    re.compile(r"\b(?:on second thought|upon reflection|looking (?:more )?carefully)\b", re.I),
]

WASTEFUL_RUMINATION_PATTERNS = [
    re.compile(r"\bwait\b.*\blet me (?:reconsider|think again)\b", re.I | re.DOTALL),
    re.compile(r"\b(?:hmm|hm+)\b.*\b(?:but|maybe|perhaps)\b", re.I | re.DOTALL),
    re.compile(r"\b(?:actually|well)\b.*\b(?:I(?:'m| am) not sure|maybe)\b", re.I | re.DOTALL),
    re.compile(r"\blet me (?:reconsider|rethink|think about this again)\b", re.I),
    re.compile(r"\bI keep going back and forth\b", re.I),
]

VERIFICATION_STEP_PATTERNS = [
    re.compile(r"\blet me (?:check|verify|confirm|validate|double.?check)\b", re.I),
    re.compile(r"\b(?:checking|verifying|confirming|validating)\b", re.I),
    re.compile(r"\b(?:does this|is this|let's see if)\s+(?:hold|work|make sense|check out)\b", re.I),
]

OVER_VERIFICATION_PATTERNS = [
    re.compile(r"\b(?:one more time|once more|let me check again|let me verify again)\b", re.I),
    re.compile(r"\b(?:just to be (?:sure|safe|certain)|to be absolutely sure)\b", re.I),
    re.compile(r"\b(?:triple.?check|re.?verify|re.?check|check(?:ing)? once more)\b", re.I),
]

# RLang backtrack/correction patterns
BT_PATTERN = re.compile(r"\bbt\(")
REFLECTION_PATTERN = re.compile(r"\bReflection\b")
DIAGNOSIS_PATTERN = re.compile(r"\bDiagnosisKind|ToolFailure|LogicError|InsufficientEvidence\b")
REVISION_PATTERN = re.compile(r"\brevision\b", re.I)


@dataclass
class CorrectionInstance:
    """A detected self-correction moment in the English text."""

    kind: str  # 'productive', 'wasteful', 'verification', 'over_verification'
    text_snippet: str  # The matching text
    start_pos: int


def _find_corrections(english: str) -> list[CorrectionInstance]:
    """Find all self-correction moments in English text."""
    corrections: list[CorrectionInstance] = []

    if not english:
        return corrections

    # Split into sentences for context
    sentences = re.split(r"(?<=[.!?])\s+", english)

    for i, sentence in enumerate(sentences):
        # Check each pattern category
        for pattern in PRODUCTIVE_CORRECTION_PATTERNS:
            if pattern.search(sentence):
                corrections.append(CorrectionInstance(
                    kind="productive",
                    text_snippet=sentence[:80].strip(),
                    start_pos=english.find(sentence),
                ))
                break

        for pattern in WASTEFUL_RUMINATION_PATTERNS:
            if pattern.search(sentence):
                # Only count as wasteful if not already classified as productive
                already_productive = any(
                    c.text_snippet == sentence[:80].strip() and c.kind == "productive"
                    for c in corrections
                )
                if not already_productive:
                    corrections.append(CorrectionInstance(
                        kind="wasteful",
                        text_snippet=sentence[:80].strip(),
                        start_pos=english.find(sentence),
                    ))
                    break

        for pattern in OVER_VERIFICATION_PATTERNS:
            if pattern.search(sentence):
                corrections.append(CorrectionInstance(
                    kind="over_verification",
                    text_snippet=sentence[:80].strip(),
                    start_pos=english.find(sentence),
                ))
                break

        for pattern in VERIFICATION_STEP_PATTERNS:
            if pattern.search(sentence):
                # Only count if not already categorized
                already_found = any(
                    c.text_snippet == sentence[:80].strip()
                    for c in corrections
                )
                if not already_found:
                    corrections.append(CorrectionInstance(
                        kind="verification",
                        text_snippet=sentence[:80].strip(),
                        start_pos=english.find(sentence),
                    ))
                    break

    return corrections


def _count_bt_operators(rlang: str) -> int:
    """Count the number of bt() (backtrack) operators in RLang."""
    return len(BT_PATTERN.findall(rlang))


def _has_diagnosis(rlang: str) -> bool:
    """Check if the RLang trace includes DiagnosisKind in backtracks."""
    return bool(DIAGNOSIS_PATTERN.search(rlang))


def _has_revision(rlang: str) -> bool:
    """Check if the RLang trace includes revision plans in backtracks."""
    return bool(REVISION_PATTERN.search(rlang))


def _check_productive_preserved(
    corrections: list[CorrectionInstance], rlang: str
) -> list[str]:
    """Check that productive corrections are preserved as bt() operators."""
    issues = []
    productive = [c for c in corrections if c.kind == "productive"]
    bt_count = _count_bt_operators(rlang)

    if productive and bt_count == 0:
        issues.append(
            f"Found {len(productive)} productive self-correction(s) in English "
            f"but no bt() operators in RLang -- corrections should be preserved"
        )

    # If there are bt() operators, check they have proper structure
    if bt_count > 0:
        if not _has_diagnosis(rlang):
            issues.append(
                "bt() operators present but missing DiagnosisKind -- "
                "backtracks should have typed diagnosis (anti-pattern #6)"
            )
        if not _has_revision(rlang):
            issues.append(
                "bt() operators present but missing revision plan -- "
                "backtracks should include novel revision (anti-pattern #6)"
            )

    return issues


def _check_wasteful_stripped(
    corrections: list[CorrectionInstance], rlang: str
) -> list[str]:
    """Check that wasteful rumination was properly stripped."""
    issues = []
    wasteful = [c for c in corrections if c.kind == "wasteful"]

    if not wasteful:
        return issues

    # Check if rumination artifacts appear in RLang
    rumination_artifacts = [
        re.compile(r"\b(?:reconsider|rethink)\b", re.I),
        re.compile(r"\b(?:not sure|uncertain)\b", re.I),
        re.compile(r"\b(?:going back|back and forth)\b", re.I),
    ]

    for pattern in rumination_artifacts:
        if pattern.search(rlang):
            issues.append(
                f"Wasteful rumination artifact detected in RLang: "
                f"'{pattern.pattern}' should have been stripped"
            )

    return issues


def _check_verification_placed(
    corrections: list[CorrectionInstance], rlang: str
) -> list[str]:
    """Check that verification steps are in the Verify phase."""
    issues = []
    verifications = [c for c in corrections if c.kind == "verification"]

    if not verifications:
        return issues

    # Check that Verify phase has content
    verify_match = re.search(
        r"#\[phase\(Verify\)\](.+?)(?:#\[phase\(Decide\)\]|$)", rlang, re.DOTALL
    )
    if verify_match:
        verify_text = verify_match.group(1)
        has_verification_ops = bool(
            re.search(r"\b(verify|req|check|assert)\(", verify_text)
        )
        if not has_verification_ops:
            issues.append(
                f"English has {len(verifications)} verification step(s) "
                f"but Verify phase lacks verification operators"
            )

    return issues


def _check_over_verification_stripped(
    corrections: list[CorrectionInstance], rlang: str
) -> list[str]:
    """Check that over-verification was properly eliminated."""
    issues = []
    over_verifications = [c for c in corrections if c.kind == "over_verification"]

    if not over_verifications:
        return issues

    # Count how many times verify() appears in the Verify phase
    verify_match = re.search(
        r"#\[phase\(Verify\)\](.+?)(?:#\[phase\(Decide\)\]|$)", rlang, re.DOTALL
    )
    if verify_match:
        verify_text = verify_match.group(1)
        verify_calls = len(re.findall(r"\bverify\(", verify_text))
        # Check for redundant verify calls on the same thing
        verify_args = re.findall(r"\bverify\((\w+)\)", verify_text)
        from collections import Counter
        arg_counts = Counter(verify_args)
        for arg, count in arg_counts.items():
            if count > 1:
                issues.append(
                    f"Over-verification: verify({arg}) called {count} times -- "
                    f"should verify each thing once (anti-pattern #5)"
                )

    return issues


def run_check(trace: dict) -> CheckResult:
    """Run self-correction quality check on a single trace.

    Args:
        trace: Dictionary with 'rlang' key and optionally 'english'/'original'.

    Returns:
        CheckResult with self-correction quality results.
    """
    rlang = trace.get("rlang", "")
    english = trace.get("english", trace.get("original", ""))
    issues: list[str] = []
    score = 1.0

    if not english:
        # Without English text, we can only do limited checking
        return CheckResult(
            name="self_correction",
            passed=True,
            score=0.90,  # Slight penalty for missing English reference
            details="No English text available for self-correction analysis",
        )

    # 1. Find all correction instances in English
    corrections = _find_corrections(english)

    if not corrections:
        # No self-corrections detected -- this is fine, not all traces have them
        return CheckResult(
            name="self_correction",
            passed=True,
            score=1.0,
            details="No self-correction moments detected in English trace",
        )

    # 2. Check productive corrections are preserved
    productive_issues = _check_productive_preserved(corrections, rlang)
    issues.extend(productive_issues)
    score -= 0.20 * len(productive_issues)

    # 3. Check wasteful rumination is stripped
    wasteful_issues = _check_wasteful_stripped(corrections, rlang)
    issues.extend(wasteful_issues)
    score -= 0.15 * len(wasteful_issues)

    # 4. Check verification steps are in Verify phase
    verify_issues = _check_verification_placed(corrections, rlang)
    issues.extend(verify_issues)
    score -= 0.10 * len(verify_issues)

    # 5. Check over-verification is stripped
    over_issues = _check_over_verification_stripped(corrections, rlang)
    issues.extend(over_issues)
    score -= 0.15 * len(over_issues)

    # Clamp score
    score = max(0.0, min(1.0, score))

    # Build summary
    kind_counts = {}
    for c in corrections:
        kind_counts[c.kind] = kind_counts.get(c.kind, 0) + 1

    summary_parts = [f"{v} {k}" for k, v in sorted(kind_counts.items())]
    correction_summary = ", ".join(summary_parts)

    details = f"Found {len(corrections)} correction(s) ({correction_summary})"
    if issues:
        details += f"; {len(issues)} issue(s): " + "; ".join(issues[:2])
        if len(issues) > 2:
            details += f" (+{len(issues) - 2} more)"
    else:
        details += "; all well-handled"

    return CheckResult(
        name="self_correction",
        passed=score >= 0.8,
        score=score,
        details=details,
    )


if __name__ == "__main__":
    # Test with English that has self-corrections
    sample_trace = {
        "id": "test-001",
        "english": """
Let me think about deploying the fix.
The tests pass, so we should deploy immediately.
Wait, actually, I forgot about the rollback plan.
There's no rollback plan in place, which is risky.
Let me reconsider -- we need to weigh this more carefully.
Hmm, but maybe the low traffic makes it safe enough?
Actually no, I think we should be cautious.
Let me verify that the tests really pass... yes, confirmed.
Let me double-check the test results one more time... still passing.
Just to be absolutely sure, let me check once more... yes.
So my conclusion is: deploy conditionally, only with a rollback plan.
""",
        "rlang": """
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass)
        | p:0.99 | ep:direct | src:ci_pipeline | t:fresh;
    let risk: blf<0.85> = obs(no_rollback)
        | p:0.85 | ep:direct | src:obs(infra) | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic)
        | p:0.90 | ep:direct | src:obs(metrics) | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests   => sup(deploy, +0.15),
        risk    => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];
    let deploy_blf = resolve(ev) -> Ok(blf<0.70>);
}

#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy),
        _ => reject(deploy),
    }
}
""",
    }

    result = run_check(sample_trace)
    print(f"Result: {result}")
    print(f"  Score: {result.score:.2f}")
    print(f"  Passed: {result.passed}")
    print(f"  Details: {result.details}")
