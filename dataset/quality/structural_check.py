"""Layer 1: Structural Integrity Check.

Validates that RLang traces have correct phase structure, ordering,
proportions, reasoning modes, and balanced syntax elements.

Rules enforced:
    - All 4 phases present in correct order: Frame -> Explore -> Verify -> Decide
    - No phase is empty (at least 1 statement per phase)
    - Rebloom count <= 3
    - Phase proportions are reasonable
    - impl blocks use valid reasoning modes (Deductive, Abductive, Analogical)
    - Balanced braces, brackets, semicolons
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from . import CheckResult

# Phase ordering constants
PHASES = ["Frame", "Explore", "Verify", "Decide"]
VALID_REASONING_MODES = {"Deductive", "Abductive", "Analogical"}

# Phase proportion bounds (min%, max%)
# Widened to accommodate converted traces where short reasoning steps
# naturally produce different proportions than hand-crafted examples.
PHASE_PROPORTIONS = {
    "Frame": (0.05, 0.35),
    "Explore": (0.20, 0.60),
    "Verify": (0.05, 0.30),
    "Decide": (0.05, 0.30),
}

# Regex patterns
PHASE_PATTERN = re.compile(r"#\[phase\((\w+)\)\]")
IMPL_PATTERN = re.compile(r"impl\s+(\w+)")
REBLOOM_PATTERN = re.compile(
    r"#\[phase\(Verify\)\].*?#\[phase\(Explore\)\]", re.DOTALL
)


def _extract_phases(rlang: str) -> list[str]:
    """Extract the ordered list of phase names from an RLang trace."""
    return PHASE_PATTERN.findall(rlang)


def _extract_phase_blocks(rlang: str) -> dict[str, list[str]]:
    """Extract content blocks for each phase.

    Returns a dict mapping phase name to a list of block contents
    (a phase can appear multiple times due to reblooms).
    """
    blocks: dict[str, list[str]] = {p: [] for p in PHASES}
    parts = PHASE_PATTERN.split(rlang)
    # parts alternates between: text_before, phase_name, block_text, ...
    i = 1
    while i < len(parts):
        phase_name = parts[i]
        block_text = parts[i + 1] if (i + 1) < len(parts) else ""
        if phase_name in blocks:
            blocks[phase_name].append(block_text)
        i += 2
    return blocks


def _count_statements(block_text: str) -> int:
    """Estimate the number of statements in a block by counting semicolons
    and closing braces that end statements."""
    # Count lines that look like statements (have a semicolon or are non-empty code lines)
    lines = [line.strip() for line in block_text.splitlines() if line.strip()]
    # Filter out pure comments and empty lines
    code_lines = [
        line
        for line in lines
        if not line.startswith("//") and line not in ("{", "}")
    ]
    # Count semicolons as statement terminators
    semicolons = block_text.count(";")
    # Use max of code lines and semicolons as statement estimate
    return max(semicolons, len(code_lines))


def _check_balanced(rlang: str) -> list[str]:
    """Check for balanced braces, brackets, and parentheses."""
    issues = []
    pairs = {"(": ")", "[": "]", "{": "}"}
    stack: list[str] = []

    # Strip string literals and comments to avoid false positives
    cleaned = re.sub(r'"[^"]*"', '""', rlang)
    cleaned = re.sub(r"//[^\n]*", "", cleaned)

    for ch in cleaned:
        if ch in pairs:
            stack.append(pairs[ch])
        elif ch in pairs.values():
            if not stack:
                issues.append(f"Unmatched closing '{ch}'")
            elif stack[-1] != ch:
                issues.append(f"Mismatched bracket: expected '{stack[-1]}', got '{ch}'")
                stack.pop()
            else:
                stack.pop()

    for remaining in stack:
        opener = {v: k for k, v in pairs.items()}.get(remaining, "?")
        issues.append(f"Unclosed '{opener}'")

    return issues


def _check_reasoning_modes(rlang: str) -> list[str]:
    """Check that impl blocks use valid reasoning modes."""
    issues = []
    for match in IMPL_PATTERN.finditer(rlang):
        mode = match.group(1)
        if mode not in VALID_REASONING_MODES:
            issues.append(
                f"Invalid reasoning mode '{mode}' in impl block; "
                f"valid modes: {', '.join(sorted(VALID_REASONING_MODES))}"
            )
    return issues


def run_check(trace: dict) -> CheckResult:
    """Run structural integrity check on a single trace.

    Args:
        trace: Dictionary with at least 'rlang' key containing the RLang text.
               May also have 'id' for identification.

    Returns:
        CheckResult with structural check results.
    """
    rlang = trace.get("rlang", "")
    issues: list[str] = []
    score = 1.0
    deduction_per_issue = 0.2

    # 1. Check all 4 phases present in correct order
    phase_names = _extract_phases(rlang)
    # Deduplicate while preserving order for forward-pass check
    seen_forward: list[str] = []
    for p in phase_names:
        if p not in seen_forward:
            seen_forward.append(p)

    missing_phases = [p for p in PHASES if p not in seen_forward]
    if missing_phases:
        issues.append(f"Missing phases: {', '.join(missing_phases)}")
        score -= deduction_per_issue * len(missing_phases)

    # Check ordering: the first occurrence of each phase should be in PHASES order
    phase_indices = {p: i for i, p in enumerate(PHASES)}
    forward_indices = [phase_indices.get(p, -1) for p in seen_forward if p in phase_indices]
    if forward_indices != sorted(forward_indices):
        issues.append("Phases are out of order (expected Frame -> Explore -> Verify -> Decide)")
        score -= deduction_per_issue

    # 2. Check no phase is empty
    phase_blocks = _extract_phase_blocks(rlang)
    for phase in PHASES:
        blocks = phase_blocks.get(phase, [])
        if not blocks:
            continue  # Already caught by missing phases check
        total_stmts = sum(_count_statements(b) for b in blocks)
        if total_stmts == 0:
            issues.append(f"Phase {phase} is empty (no statements)")
            score -= deduction_per_issue

    # 3. Check rebloom count <= 3
    # Count Verify->Explore transitions (reblooms)
    rebloom_count = 0
    for i in range(len(phase_names) - 1):
        if phase_names[i] == "Verify" and phase_names[i + 1] == "Explore":
            rebloom_count += 1
    if rebloom_count > 3:
        issues.append(f"Rebloom count {rebloom_count} exceeds maximum of 3")
        score -= deduction_per_issue

    # 4. Check phase proportions
    total_chars = sum(
        sum(len(b) for b in blocks) for blocks in phase_blocks.values()
    )
    if total_chars > 0 and not missing_phases:
        for phase, (min_pct, max_pct) in PHASE_PROPORTIONS.items():
            phase_chars = sum(len(b) for b in phase_blocks.get(phase, []))
            proportion = phase_chars / total_chars
            if proportion < min_pct * 0.5:  # Allow some slack (half the minimum)
                issues.append(
                    f"Phase {phase} is underrepresented "
                    f"({proportion:.1%} vs expected {min_pct:.0%}-{max_pct:.0%})"
                )
                score -= deduction_per_issue * 0.5  # Half deduction for proportions
            elif proportion > max_pct * 1.5:  # Allow some slack (1.5x the maximum)
                issues.append(
                    f"Phase {phase} is overrepresented "
                    f"({proportion:.1%} vs expected {min_pct:.0%}-{max_pct:.0%})"
                )
                score -= deduction_per_issue * 0.5

    # 5. Check reasoning modes
    mode_issues = _check_reasoning_modes(rlang)
    issues.extend(mode_issues)
    score -= deduction_per_issue * len(mode_issues)

    # 6. Check balanced syntax
    balance_issues = _check_balanced(rlang)
    issues.extend(balance_issues)
    score -= deduction_per_issue * len(balance_issues)

    # Clamp score
    score = max(0.0, min(1.0, score))

    details = f"{len(issues)} structural issue(s) found" if issues else "Perfect structure"
    if issues:
        details += ": " + "; ".join(issues[:3])
        if len(issues) > 3:
            details += f" (+{len(issues) - 3} more)"

    return CheckResult(
        name="structural",
        passed=score >= 0.8,
        score=score,
        details=details,
    )


if __name__ == "__main__":
    # Test with a minimal well-formed trace
    sample_trace = {
        "id": "test-001",
        "rlang": """
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass)
        | p:0.99 | ep:direct | src:ci_pipeline | t:fresh;
    let risk: blf<0.85> = obs(no_rollback)
        | p:0.85 | ep:direct | src:obs(infra) | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests => sup(deploy, +0.15),
        risk  => wkn(deploy, -0.25),
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
    emit(Decision { deploy: true });
}
""",
    }

    result = run_check(sample_trace)
    print(f"Result: {result}")
    print(f"  Score: {result.score:.2f}")
    print(f"  Passed: {result.passed}")
    print(f"  Details: {result.details}")
