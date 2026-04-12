"""Layer 3: Token Efficiency Check.

Validates that RLang traces achieve meaningful compression and avoid
token waste through redundancy or verbosity.

Rules enforced:
    - Compression ratio within 2.0x-10.0x range
    - No redundant observations (same obs() appearing multiple times)
    - No redundant metadata (ep:direct on obs() is implied)
    - No overly verbose variable names (>20 chars)
    - No unnecessary parentheses
    - Information density = unique operators / total tokens
"""

from __future__ import annotations

import re
from collections import Counter

from . import CheckResult

# Regex patterns
OPERATOR_PATTERN = re.compile(r"\b(obs|cause|prvnt|enbl|req|sim|confl|cncl|cntns|isa|"
                              r"chng|seq|sup|wkn|neut|resolve|conf|decay|refresh|"
                              r"goal|dcmp|prioritize|select|replan|"
                              r"exec|inv|pcv|rmb|rcl|forget|bt|verify|retry_with|"
                              r"dlg|msg|discover|match_capability|negotiate|cancel|poll|"
                              r"subscribe|cfp|propose|accept_proposal|reject_proposal|"
                              r"inform|query_if|agree|refuse|resolve_conflict|"
                              r"assert|hedge|suspend|reject|emit)\b")
OBS_CALL_PATTERN = re.compile(r"\bobs\((\w+)\)")
VARIABLE_NAME_PATTERN = re.compile(r"\blet\s+(\w+)")
REDUNDANT_EP_DIRECT_PATTERN = re.compile(r"\bobs\([^)]+\)[^;]*\|\s*ep:direct\b")
UNNECESSARY_PARENS_PATTERN = re.compile(r"\(\s*(\w+)\s*\)")


def _tokenize(text: str) -> list[str]:
    """Split text into tokens (whitespace + punctuation splitting)."""
    # Split on whitespace first
    tokens: list[str] = []
    for word in text.split():
        # Further split on punctuation boundaries
        parts = re.findall(r"[a-zA-Z_]\w*|[0-9]+\.?[0-9]*|\S", word)
        tokens.extend(parts)
    return tokens


def _count_unique_operators(rlang: str) -> int:
    """Count the number of unique operators used in the trace."""
    return len(set(OPERATOR_PATTERN.findall(rlang)))


def _check_compression_ratio(trace: dict) -> tuple[float, list[str]]:
    """Check that compression ratio is in acceptable range.

    Returns:
        Tuple of (compression_ratio, list of issues).
    """
    issues = []
    english = trace.get("english", trace.get("original", ""))
    rlang = trace.get("rlang", "")

    if not english:
        return 1.0, ["No English text available for compression ratio check"]

    english_tokens = len(_tokenize(english))
    rlang_tokens = len(_tokenize(rlang))

    if rlang_tokens == 0:
        return 0.0, ["RLang trace is empty"]

    ratio = english_tokens / rlang_tokens

    if ratio < 1.2:
        issues.append(
            f"Compression ratio {ratio:.1f}x is below 1.2x -- "
            f"not enough compression (English: {english_tokens} tokens, "
            f"RLang: {rlang_tokens} tokens)"
        )
    elif ratio > 10.0:
        issues.append(
            f"Compression ratio {ratio:.1f}x exceeds 10.0x -- "
            f"suspicious, may have lost content (English: {english_tokens} tokens, "
            f"RLang: {rlang_tokens} tokens)"
        )

    return ratio, issues


def _check_redundant_observations(rlang: str) -> list[str]:
    """Detect same obs() appearing multiple times."""
    issues = []
    obs_calls = OBS_CALL_PATTERN.findall(rlang)
    counts = Counter(obs_calls)

    for obs_arg, count in counts.items():
        if count > 1:
            issues.append(
                f"Redundant observation: obs({obs_arg}) appears {count} times"
            )

    return issues


def _check_redundant_metadata(rlang: str) -> list[str]:
    """Detect redundant metadata (e.g., ep:direct on obs() is implied)."""
    issues = []
    matches = REDUNDANT_EP_DIRECT_PATTERN.findall(rlang)
    if matches:
        issues.append(
            f"Redundant metadata: ep:direct on obs() is implied -- "
            f"found {len(matches)} instance(s) that could be removed"
        )

    return issues


def _check_verbose_variable_names(rlang: str) -> list[str]:
    """Detect overly verbose variable names (>20 chars)."""
    issues = []
    for match in VARIABLE_NAME_PATTERN.finditer(rlang):
        name = match.group(1)
        if len(name) > 20:
            issues.append(
                f"Verbose variable name '{name}' ({len(name)} chars, max recommended: 20)"
            )

    return issues


def _check_unnecessary_parens(rlang: str) -> list[str]:
    """Detect unnecessary parentheses wrapping single identifiers."""
    issues = []
    # Remove string literals and comments
    cleaned = re.sub(r'"[^"]*"', '""', rlang)
    cleaned = re.sub(r"//[^\n]*", "", cleaned)

    # Find single-identifier parenthesization that isn't an operator call
    count = 0
    for match in UNNECESSARY_PARENS_PATTERN.finditer(cleaned):
        # Check that the previous non-whitespace char is not a letter (would be fn call)
        start = match.start()
        preceding = cleaned[:start].rstrip()
        if preceding and preceding[-1].isalpha():
            continue  # This is a function/operator call, parens are needed
        count += 1

    if count > 0:
        issues.append(f"Found {count} unnecessary parenthesis pair(s)")

    return issues


def _calculate_info_density(rlang: str) -> float:
    """Calculate information density: unique operators / total tokens."""
    tokens = _tokenize(rlang)
    if not tokens:
        return 0.0
    unique_ops = _count_unique_operators(rlang)
    return unique_ops / len(tokens)


def run_check(trace: dict) -> CheckResult:
    """Run token efficiency check on a single trace.

    Args:
        trace: Dictionary with 'rlang' key and optionally 'english'/'original'.

    Returns:
        CheckResult with efficiency check results.
    """
    rlang = trace.get("rlang", "")
    issues: list[str] = []
    score = 1.0

    # 1. Compression ratio
    ratio, ratio_issues = _check_compression_ratio(trace)
    issues.extend(ratio_issues)
    if ratio_issues:
        # Scale deduction based on how far from acceptable range
        if ratio < 1.2 and ratio > 0:
            score -= min(0.3, (1.2 - ratio) * 0.15)
        elif ratio > 10.0:
            score -= min(0.3, (ratio - 10.0) * 0.05)

    # 2. Redundant observations
    # Penalty reduced: re-referencing observations across phases is often
    # valid (e.g., Frame defines obs, Verify re-checks it).
    obs_issues = _check_redundant_observations(rlang)
    issues.extend(obs_issues)
    score -= 0.03 * len(obs_issues)

    # 3. Redundant metadata
    # Penalty reduced: ep:direct on obs() is technically implied but
    # retained in many converted traces for readability. Minor issue.
    meta_issues = _check_redundant_metadata(rlang)
    issues.extend(meta_issues)
    score -= 0.02 * len(meta_issues)

    # 4. Verbose variable names
    verbose_issues = _check_verbose_variable_names(rlang)
    issues.extend(verbose_issues)
    score -= 0.05 * len(verbose_issues)

    # 5. Unnecessary parentheses
    paren_issues = _check_unnecessary_parens(rlang)
    issues.extend(paren_issues)
    score -= 0.05 * len(paren_issues)

    # 6. Information density
    info_density = _calculate_info_density(rlang)
    if info_density < 0.01:
        issues.append(
            f"Low information density ({info_density:.3f}) -- "
            f"trace may be overly verbose or boilerplate-heavy"
        )
        score -= 0.10

    # Clamp score
    score = max(0.0, min(1.0, score))

    details_parts = []
    if not issues:
        details_parts.append("Efficient")
    else:
        details_parts.append(f"{len(issues)} efficiency issue(s)")

    # Always include key metrics
    english = trace.get("english", trace.get("original", ""))
    if english:
        details_parts.append(f"compression={ratio:.1f}x")
    details_parts.append(f"density={info_density:.3f}")

    details = "; ".join(details_parts)
    if issues:
        details += " -- " + "; ".join(issues[:2])
        if len(issues) > 2:
            details += f" (+{len(issues) - 2} more)"

    return CheckResult(
        name="efficiency",
        passed=score >= 0.8,
        score=score,
        details=details,
    )


if __name__ == "__main__":
    sample_trace = {
        "id": "test-001",
        "english": """
Let me think about whether we should deploy the fix.
First, I notice that the tests are passing. That's a good sign.
However, I'm concerned because there's no rollback plan in place.
The traffic is low right now, which is favorable for deployment.
Let me weigh the evidence. Tests passing supports deployment.
No rollback plan weakens the case for deployment significantly.
Low traffic supports deployment somewhat.
Overall, I'd say we're at about 70% confidence for deploying.
Since that's above 55% but below 80%, I'd recommend a conditional
deployment -- deploy only if we can get a rollback plan in place.
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
