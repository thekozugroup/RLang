"""Layer 4: Reasoning Signal Quality Check.

Validates that the RLang trace actually captures the REASONING from the
English chain-of-thought, not just surface patterns.

Rules enforced:
    - Evidence blocks have logical connection to claims they support/weaken
    - Confidence values correlate with hedging in the English
    - Final decision matches the English conclusion
    - No "empty reasoning" (structure without logical content)
    - No "lost reasoning" (important English steps missing from RLang)
    - Reasoning coverage: ratio of mapped English steps to total
"""

from __future__ import annotations

import re
from collections import Counter

from . import CheckResult

# Hedging indicators in English text (sorted by strength: weak -> strong)
WEAK_HEDGES = {
    "might", "maybe", "perhaps", "possibly", "could", "somewhat",
    "slightly", "a bit", "sort of", "kind of", "not sure",
}
MODERATE_HEDGES = {
    "likely", "probably", "seems", "appears", "tend to",
    "I think", "I believe", "it looks like", "suggests",
}
STRONG_ASSERTIONS = {
    "definitely", "certainly", "clearly", "obviously", "absolutely",
    "without doubt", "must be", "I'm confident", "I'm sure",
    "no question",
}

# English conclusion patterns
ENGLISH_ASSERT_PATTERNS = re.compile(
    r"\b(should|must|will|recommend|conclude|therefore|thus|"
    r"the answer is|I(?:'m| am) (?:confident|sure|certain))\b",
    re.IGNORECASE,
)
ENGLISH_HEDGE_PATTERNS = re.compile(
    r"\b(might|could|possibly|perhaps|maybe|if|only if|"
    r"conditional(?:ly)?|provided that|assuming)\b",
    re.IGNORECASE,
)
ENGLISH_REJECT_PATTERNS = re.compile(
    r"\b(should not|shouldn't|must not|cannot|don't|"
    r"not recommended|reject|refuse|against)\b",
    re.IGNORECASE,
)
ENGLISH_SUSPEND_PATTERNS = re.compile(
    r"\b(not enough|insufficient|more (?:data|info|evidence)|"
    r"unclear|uncertain|can't (?:tell|say|determine)|need more)\b",
    re.IGNORECASE,
)

# RLang decision patterns
RLANG_ASSERT_PATTERN = re.compile(r"\bassert\(")
RLANG_HEDGE_PATTERN = re.compile(r"\bhedge\(")
RLANG_REJECT_PATTERN = re.compile(r"\breject\(")
RLANG_SUSPEND_PATTERN = re.compile(r"\bsuspend\(")

# English reasoning step indicators
REASONING_STEP_PATTERNS = [
    re.compile(r"\b(?:first|second|third|next|then|also|additionally|moreover|furthermore)\b", re.I),
    re.compile(r"\b(?:because|since|therefore|thus|hence|so|consequently)\b", re.I),
    re.compile(r"\b(?:however|but|although|despite|nevertheless|on the other hand)\b", re.I),
    re.compile(r"\b(?:I notice|I see|I observe|looking at|examining)\b", re.I),
    re.compile(r"\b(?:this means|this suggests|this implies|this indicates)\b", re.I),
    re.compile(r"\b(?:the evidence|the data|the results|the findings)\b", re.I),
    re.compile(r"\b(?:weighing|considering|evaluating|comparing|analyzing)\b", re.I),
    re.compile(r"\b(?:let me|I'll|I need to|I should)\b", re.I),
]

# RLang operator patterns that map to reasoning steps
RLANG_REASONING_PATTERNS = [
    re.compile(r"\bobs\("),
    re.compile(r"\bcause\("),
    re.compile(r"\benbl\("),
    re.compile(r"\bprvnt\("),
    re.compile(r"\bsup\("),
    re.compile(r"\bwkn\("),
    re.compile(r"\bresolve\("),
    re.compile(r"\bconf\("),
    re.compile(r"\breq\("),
    re.compile(r"\bverify\("),
    re.compile(r"\bchng\("),
    re.compile(r"\bsim\("),
    re.compile(r"\bconfl\("),
]


def _count_english_reasoning_steps(english: str) -> int:
    """Count the approximate number of reasoning steps in English text."""
    if not english:
        return 0
    # Split into sentences
    sentences = re.split(r"[.!?]+", english)
    step_count = 0
    for sentence in sentences:
        sentence = sentence.strip()
        if len(sentence) < 10:
            continue
        # Count sentences that contain reasoning indicators
        for pattern in REASONING_STEP_PATTERNS:
            if pattern.search(sentence):
                step_count += 1
                break
    return max(step_count, 1)  # At least 1 step


def _count_rlang_reasoning_steps(rlang: str) -> int:
    """Count the number of reasoning operators in RLang."""
    count = 0
    for pattern in RLANG_REASONING_PATTERNS:
        count += len(pattern.findall(rlang))
    return count


def _detect_hedging_level(english: str) -> str:
    """Detect the hedging level in English text.

    Returns:
        'strong_assert' -- high confidence language
        'moderate' -- typical assertion with some hedging
        'hedged' -- significant hedging
        'uncertain' -- very uncertain/suspended
    """
    if not english:
        return "moderate"

    english_lower = english.lower()
    strong_count = sum(1 for h in STRONG_ASSERTIONS if h.lower() in english_lower)
    weak_count = sum(1 for h in WEAK_HEDGES if h.lower() in english_lower)
    moderate_count = sum(1 for h in MODERATE_HEDGES if h.lower() in english_lower)

    if ENGLISH_SUSPEND_PATTERNS.search(english):
        return "uncertain"
    if strong_count > weak_count + moderate_count:
        return "strong_assert"
    if weak_count > strong_count:
        return "hedged"
    return "moderate"


def _detect_english_conclusion(english: str) -> str:
    """Detect what kind of conclusion the English text reaches.

    Returns one of: 'assert', 'hedge', 'reject', 'suspend', 'unknown'
    """
    if not english:
        return "unknown"

    # Look at the last third of the text (where conclusions usually are)
    conclusion_section = english[len(english) * 2 // 3 :]

    if ENGLISH_REJECT_PATTERNS.search(conclusion_section):
        return "reject"
    if ENGLISH_SUSPEND_PATTERNS.search(conclusion_section):
        return "suspend"
    if ENGLISH_HEDGE_PATTERNS.search(conclusion_section):
        return "hedge"
    if ENGLISH_ASSERT_PATTERNS.search(conclusion_section):
        return "assert"

    return "unknown"


def _detect_rlang_decision(rlang: str) -> str:
    """Detect the final decision in the RLang Decide phase.

    Returns one of: 'assert', 'hedge', 'reject', 'suspend', 'unknown'
    """
    # Look at just the Decide phase
    decide_match = re.search(r"#\[phase\(Decide\)\](.+)", rlang, re.DOTALL)
    if not decide_match:
        return "unknown"

    decide_text = decide_match.group(1)

    # Check what appears in match arms or standalone
    if RLANG_ASSERT_PATTERN.search(decide_text):
        if RLANG_HEDGE_PATTERN.search(decide_text):
            return "hedge"  # Has both assert and hedge -> likely hedged
        return "assert"
    if RLANG_HEDGE_PATTERN.search(decide_text):
        return "hedge"
    if RLANG_REJECT_PATTERN.search(decide_text):
        return "reject"
    if RLANG_SUSPEND_PATTERN.search(decide_text):
        return "suspend"

    return "unknown"


def _check_empty_reasoning(rlang: str) -> bool:
    """Detect if the trace has structure but no real logical content.

    Returns True if reasoning appears empty.
    """
    # Check: does Explore phase have evidence blocks or causal operators?
    explore_match = re.search(
        r"#\[phase\(Explore\)\](.+?)#\[phase\(Verify\)\]", rlang, re.DOTALL
    )
    if not explore_match:
        return True

    explore_text = explore_match.group(1)

    # Must have at least one evidence-building or reasoning operator
    has_evidence = bool(re.search(r"\b(sup|wkn|neut|resolve|cause|enbl|prvnt)\(", explore_text))
    has_variable = bool(re.search(r"\blet\s+\w+", explore_text))

    return not (has_evidence or has_variable)


def _check_confidence_hedging_correlation(trace: dict) -> list[str]:
    """Cross-reference English hedging with RLang confidence values."""
    issues = []
    english = trace.get("english", trace.get("original", ""))
    rlang = trace.get("rlang", "")

    if not english:
        return issues

    hedging_level = _detect_hedging_level(english)

    # Extract final confidence from RLang
    conf_matches = re.findall(r"blf<([\d.]+)>", rlang)
    if not conf_matches:
        return issues

    # Use the last resolved confidence (usually the one used in Decide)
    final_conf = float(conf_matches[-1])

    # Check correlation
    if hedging_level == "strong_assert" and final_conf < 0.70:
        issues.append(
            f"English expresses strong assertion but RLang confidence is {final_conf:.2f} "
            f"(expected >= 0.70 for strong assertions)"
        )
    elif hedging_level == "uncertain" and final_conf > 0.60:
        issues.append(
            f"English expresses uncertainty but RLang confidence is {final_conf:.2f} "
            f"(expected <= 0.60 for uncertain language)"
        )
    elif hedging_level == "hedged" and final_conf > 0.85:
        issues.append(
            f"English is significantly hedged but RLang confidence is {final_conf:.2f} "
            f"(expected <= 0.85 for hedged language)"
        )

    return issues


def run_check(trace: dict) -> CheckResult:
    """Run reasoning signal quality check on a single trace.

    Args:
        trace: Dictionary with 'rlang' key and optionally 'english'/'original'.

    Returns:
        CheckResult with signal quality results.
    """
    rlang = trace.get("rlang", "")
    english = trace.get("english", trace.get("original", ""))
    issues: list[str] = []
    score = 1.0

    # 1. Check for empty reasoning
    if _check_empty_reasoning(rlang):
        issues.append("Empty reasoning: trace has structure but no logical content in Explore")
        score -= 0.30

    # 2. Check confidence-hedging correlation
    corr_issues = _check_confidence_hedging_correlation(trace)
    issues.extend(corr_issues)
    score -= 0.15 * len(corr_issues)

    # 3. Check decision alignment
    if english:
        english_conclusion = _detect_english_conclusion(english)
        rlang_decision = _detect_rlang_decision(rlang)

        if english_conclusion != "unknown" and rlang_decision != "unknown":
            if english_conclusion != rlang_decision:
                # Allow hedge/assert mismatch as soft error (common in nuanced reasoning)
                if {english_conclusion, rlang_decision} == {"assert", "hedge"}:
                    issues.append(
                        f"Soft decision mismatch: English concludes '{english_conclusion}' "
                        f"but RLang decides '{rlang_decision}' (assert/hedge overlap is common)"
                    )
                    score -= 0.05
                else:
                    issues.append(
                        f"Decision mismatch: English concludes '{english_conclusion}' "
                        f"but RLang decides '{rlang_decision}'"
                    )
                    score -= 0.20

    # 4. Calculate reasoning coverage
    if english:
        english_steps = _count_english_reasoning_steps(english)
        rlang_steps = _count_rlang_reasoning_steps(rlang)
        coverage = min(1.0, rlang_steps / max(english_steps, 1))

        if coverage < 0.3:
            issues.append(
                f"Low reasoning coverage ({coverage:.0%}): "
                f"English has ~{english_steps} reasoning steps, "
                f"RLang captures ~{rlang_steps}"
            )
            score -= 0.25
        elif coverage < 0.5:
            issues.append(
                f"Moderate reasoning coverage ({coverage:.0%}): "
                f"some English reasoning steps may be lost"
            )
            score -= 0.10

    # 5. Check for lost reasoning (key English concepts not in RLang)
    if english:
        # Extract key nouns/concepts from English (simple heuristic)
        english_words = set(re.findall(r"\b[a-z]{4,}\b", english.lower()))
        rlang_words = set(re.findall(r"\b[a-z]{4,}\b", rlang.lower()))

        # Key reasoning words that should probably appear in RLang
        reasoning_words = {
            w for w in english_words
            if w in {"tests", "deploy", "risk", "traffic", "rollback",
                     "evidence", "confidence", "monitor", "verify",
                     "failure", "success", "plan", "requirement"}
        }
        lost_words = reasoning_words - rlang_words
        if lost_words and len(lost_words) > len(reasoning_words) * 0.5:
            issues.append(
                f"Potentially lost concepts: {', '.join(sorted(lost_words)[:5])}"
            )
            score -= 0.10

    # Clamp score
    score = max(0.0, min(1.0, score))

    details = (
        f"{len(issues)} signal issue(s) found" if issues else "Strong reasoning signal"
    )
    if issues:
        details += ": " + "; ".join(issues[:2])
        if len(issues) > 2:
            details += f" (+{len(issues) - 2} more)"

    return CheckResult(
        name="signal",
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
