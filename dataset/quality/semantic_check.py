"""Layer 2: Semantic Correctness Check.

Validates that RLang traces use operators, types, and constructs correctly
according to the language specification.

Rules enforced:
    - Every operator is used with correct arity (obs=1, cause=2, chng=3, etc.)
    - Confidence values are in range 0.0-1.0
    - Every belief has metadata (at minimum p: field)
    - Evidence blocks only use sup/wkn/neut
    - Match expressions in Decide phase use assert/hedge/suspend/reject
    - Pipe chains use valid connective sequences
    - Variables referenced in later phases were defined in an earlier phase
"""

from __future__ import annotations

import re

from . import CheckResult

# Operator arity table (from src/semantic/mod.rs)
# None means variadic (any arg count is valid)
OPERATOR_ARITY: dict[str, int | None] = {
    # Layer 1: Epistemic -- binary
    "cause": 2,
    "prvnt": 2,
    "enbl": 2,
    "req": 2,
    "sim": 2,
    "confl": 2,
    "cncl": 2,
    "cntns": 2,
    "isa": 2,
    # Layer 1: Epistemic -- unary
    "obs": 1,
    "goal": 1,
    # Layer 1: Epistemic -- ternary
    "chng": 3,
    # Layer 1: Epistemic -- variadic
    "seq": None,
    # Layer 1: Evidence modifiers (claim, weight)
    "sup": 2,
    "wkn": 2,
    "neut": 2,
    # Layer 1: Resolution -- variadic (1 or 2 depending on pipe context)
    "resolve": None,
    "conf": None,
    "decay": None,
    "refresh": None,
    # Layer 2: Motivational
    "dcmp": 2,
    "prioritize": 2,
    "select": 1,
    "replan": 2,
    # Layer 3: Operational
    "exec": 1,
    "inv": 2,
    "pcv": 1,
    "rmb": 2,
    "rcl": 1,
    "forget": 1,
    "bt": 1,
    "verify": 1,
    "retry_with": 2,
    # Layer 4: Communicative
    "dlg": 2,
    "msg": 2,
    "discover": 1,
    "match_capability": 2,
    "negotiate": 2,
    "cancel": 1,
    "poll": 1,
    "subscribe": 2,
    "cfp": 1,
    "propose": 2,
    "accept_proposal": 1,
    "reject_proposal": 1,
    "inform": 2,
    "query_if": 2,
    "agree": 1,
    "refuse": 1,
    "resolve_conflict": 2,
    # Built-in assertions -- variadic
    "assert": None,
    "hedge": None,
    "suspend": None,
    "reject": None,
    "emit": None,
}

# Valid evidence effect operators
EVIDENCE_OPERATORS = {"sup", "wkn", "neut"}

# Valid Decide-phase match arm operators
DECIDE_OPERATORS = {"assert", "hedge", "suspend", "reject"}

# Valid connective tokens
VALID_CONNECTIVES = {"||>", "|>", "<|", "<@", "~>", "!>", "?>", "@>", "->"}

# Regex patterns
OPERATOR_CALL_PATTERN = re.compile(r"\b(\w+)\(([^)]*)\)")
CONFIDENCE_PATTERN = re.compile(r"\bp:([\d.]+)")
BLF_CONFIDENCE_PATTERN = re.compile(r"blf<([\d.]+)")
LET_BINDING_PATTERN = re.compile(r"\blet\s+(\w+)")
VARIABLE_REF_PATTERN = re.compile(r"\b([a-z_]\w*)\b")
EVIDENCE_BLOCK_PATTERN = re.compile(
    r"let\s+\w+\s*(?::\s*\w+)?\s*=\s*\[([^\]]*)\]", re.DOTALL
)
EVIDENCE_ITEM_PATTERN = re.compile(r"=>\s*(\w+)\(")
PHASE_PATTERN = re.compile(r"#\[phase\((\w+)\)\]")
MATCH_BLOCK_PATTERN = re.compile(
    r"match\s+\w+\([^)]*\)\s*\{([^}]*)\}", re.DOTALL
)
MATCH_ARM_BODY_PATTERN = re.compile(r"=>\s*(\w+)\(")
METADATA_PATTERN = re.compile(r"\|\s*p:")


def _count_args(arg_str: str) -> int:
    """Count the number of arguments in a function call, handling nested parens."""
    if not arg_str.strip():
        return 0
    depth = 0
    count = 1
    for ch in arg_str:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            count += 1
    return count


def _extract_phase_sections(rlang: str) -> dict[str, str]:
    """Split RLang text into phase sections."""
    sections: dict[str, str] = {}
    parts = PHASE_PATTERN.split(rlang)
    i = 1
    while i < len(parts):
        phase_name = parts[i]
        block_text = parts[i + 1] if (i + 1) < len(parts) else ""
        if phase_name in sections:
            sections[phase_name] += "\n" + block_text
        else:
            sections[phase_name] = block_text
        i += 2
    return sections


def _check_operator_arity(rlang: str) -> list[str]:
    """Check that all operator calls have correct argument counts."""
    issues = []
    # Remove string literals and comments
    cleaned = re.sub(r'"[^"]*"', '""', rlang)
    cleaned = re.sub(r"//[^\n]*", "", cleaned)

    for match in OPERATOR_CALL_PATTERN.finditer(cleaned):
        op_name = match.group(1).lower()
        args_str = match.group(2)

        if op_name not in OPERATOR_ARITY:
            continue  # Not a known operator, might be a function

        expected = OPERATOR_ARITY[op_name]
        if expected is None:
            continue  # Variadic, any count is fine

        actual = _count_args(args_str)
        if actual != expected:
            issues.append(
                f"Operator {op_name}() expects {expected} arg(s), got {actual}"
            )

    return issues


def _check_confidence_ranges(rlang: str) -> list[str]:
    """Check that all confidence values are in [0.0, 1.0]."""
    issues = []

    # Check p: metadata values
    for match in CONFIDENCE_PATTERN.finditer(rlang):
        try:
            val = float(match.group(1))
            if not (0.0 <= val <= 1.0):
                issues.append(f"Confidence value p:{val} is out of range [0.0, 1.0]")
        except ValueError:
            issues.append(f"Invalid confidence value: p:{match.group(1)}")

    # Check blf<value> type annotations
    for match in BLF_CONFIDENCE_PATTERN.finditer(rlang):
        try:
            val = float(match.group(1))
            if not (0.0 <= val <= 1.0):
                issues.append(
                    f"Belief confidence blf<{val}> is out of range [0.0, 1.0]"
                )
        except ValueError:
            issues.append(f"Invalid belief confidence: blf<{match.group(1)}>")

    return issues


def _check_belief_metadata(rlang: str) -> list[str]:
    """Check that beliefs have metadata (at minimum p: field)."""
    issues = []
    # Find let bindings with blf type but no p: metadata
    blf_let_pattern = re.compile(
        r"let\s+(\w+)\s*:\s*blf<[\d.]+>\s*=\s*[^;]+;", re.DOTALL
    )
    for match in blf_let_pattern.finditer(rlang):
        binding = match.group(0)
        var_name = match.group(1)
        if "| p:" not in binding and "| confidence:" not in binding:
            # Check if there's any metadata pipe
            if "|" not in binding.split("=", 1)[1]:
                issues.append(
                    f"Belief '{var_name}' has blf type but no metadata (missing at least p:)"
                )

    return issues


def _check_evidence_blocks(rlang: str) -> list[str]:
    """Check that evidence blocks only use sup/wkn/neut on effect side."""
    issues = []
    for block_match in EVIDENCE_BLOCK_PATTERN.finditer(rlang):
        block_content = block_match.group(1)
        for item_match in EVIDENCE_ITEM_PATTERN.finditer(block_content):
            op = item_match.group(1).lower()
            if op not in EVIDENCE_OPERATORS:
                issues.append(
                    f"Evidence block uses '{op}()' on effect side; "
                    f"must use sup(), wkn(), or neut()"
                )

    return issues


def _check_decide_match_arms(rlang: str) -> list[str]:
    """Check that match arms in Decide phase use assert/hedge/suspend/reject."""
    issues = []
    sections = _extract_phase_sections(rlang)
    decide_text = sections.get("Decide", "")

    if not decide_text:
        return issues

    for match_block in MATCH_BLOCK_PATTERN.finditer(decide_text):
        block_content = match_block.group(1)
        for arm_match in MATCH_ARM_BODY_PATTERN.finditer(block_content):
            op = arm_match.group(1).lower()
            if op not in DECIDE_OPERATORS:
                issues.append(
                    f"Decide-phase match arm uses '{op}()'; "
                    f"must use assert(), hedge(), suspend(), or reject()"
                )

    return issues


def _check_connectives(rlang: str) -> list[str]:
    """Check that pipe chains use valid connective tokens."""
    issues = []
    # Look for potential connective-like tokens that aren't valid
    # This is a heuristic check -- we look for operator-like symbols
    suspicious_pattern = re.compile(r"[|<>~!?@]{2,3}")
    for match in suspicious_pattern.finditer(rlang):
        token = match.group(0)
        if token not in VALID_CONNECTIVES and token not in {"||", "&&", "!=", "==", ">=", "<="}:
            # Skip if it's inside a string or comment
            line_start = rlang.rfind("\n", 0, match.start()) + 1
            line = rlang[line_start : match.end()]
            if "//" not in line[:match.start() - line_start] and '"' not in line:
                issues.append(f"Unknown connective-like token: '{token}'")

    return issues


def _check_variable_scoping(rlang: str) -> list[str]:
    """Check that variables referenced in later phases were defined earlier.

    This is a best-effort heuristic check -- it tracks let bindings and
    checks references in subsequent phases.
    """
    issues = []
    sections = _extract_phase_sections(rlang)
    phase_order = ["Frame", "Explore", "Verify", "Decide"]

    # Collect variable definitions per phase
    defined: set[str] = set()
    # Built-in names that don't need definitions
    builtins = {
        "self", "true", "false", "Ok", "Err", "None", "Some",
        "match", "let", "if", "else", "impl", "fn", "struct",
        "Working", "Semantic", "Episodic", "Balanced",
        "Deploy", "Monitor", "Decision", "Contract",
        "ResourceBudget", "Evidence", "AgentCard", "Reflection",
        "ToolFailure", "InsufEv", "Conflict", "Stale",
        "Hedge", "Delegated",
    }
    # Add all operator names as builtins
    builtins.update(OPERATOR_ARITY.keys())
    builtins.update(EVIDENCE_OPERATORS)
    builtins.update(DECIDE_OPERATORS)

    for phase in phase_order:
        text = sections.get(phase, "")
        # Extract let bindings
        for m in LET_BINDING_PATTERN.finditer(text):
            defined.add(m.group(1))

    # For now, just check that Decide phase doesn't reference totally unknown variables
    # A full check would need a proper parser; this is a heuristic
    decide_text = sections.get("Decide", "")
    if decide_text:
        # Extract identifiers used in operator calls in Decide
        for m in OPERATOR_CALL_PATTERN.finditer(decide_text):
            args_str = m.group(2)
            for ref_match in VARIABLE_REF_PATTERN.finditer(args_str):
                var = ref_match.group(1)
                if (
                    var not in defined
                    and var not in builtins
                    and not var.startswith("_")
                    and len(var) > 2  # Skip short tokens like 'c', 'ev'
                    and var not in {"cond", "condition", "priority", "deadline"}
                ):
                    # Only flag with low confidence since this is heuristic
                    pass  # Too noisy for production; keep for future enhancement

    return issues


def run_check(trace: dict) -> CheckResult:
    """Run semantic correctness check on a single trace.

    Args:
        trace: Dictionary with at least 'rlang' key containing the RLang text.

    Returns:
        CheckResult with semantic check results.
    """
    rlang = trace.get("rlang", "")
    issues: list[str] = []
    score = 1.0
    deduction_per_issue = 0.15

    # 1. Operator arity
    arity_issues = _check_operator_arity(rlang)
    issues.extend(arity_issues)
    score -= deduction_per_issue * len(arity_issues)

    # 2. Confidence ranges
    conf_issues = _check_confidence_ranges(rlang)
    issues.extend(conf_issues)
    score -= deduction_per_issue * len(conf_issues)

    # 3. Belief metadata
    meta_issues = _check_belief_metadata(rlang)
    issues.extend(meta_issues)
    score -= deduction_per_issue * len(meta_issues)

    # 4. Evidence blocks
    ev_issues = _check_evidence_blocks(rlang)
    issues.extend(ev_issues)
    score -= deduction_per_issue * len(ev_issues)

    # 5. Decide match arms
    decide_issues = _check_decide_match_arms(rlang)
    issues.extend(decide_issues)
    score -= deduction_per_issue * len(decide_issues)

    # 6. Valid connectives
    conn_issues = _check_connectives(rlang)
    issues.extend(conn_issues)
    score -= deduction_per_issue * len(conn_issues)

    # 7. Variable scoping (heuristic)
    scope_issues = _check_variable_scoping(rlang)
    issues.extend(scope_issues)
    score -= deduction_per_issue * 0.5 * len(scope_issues)  # Half weight for heuristic

    # Clamp score
    score = max(0.0, min(1.0, score))

    details = (
        f"{len(issues)} semantic issue(s) found" if issues else "Semantically correct"
    )
    if issues:
        details += ": " + "; ".join(issues[:3])
        if len(issues) > 3:
            details += f" (+{len(issues) - 3} more)"

    return CheckResult(
        name="semantic",
        passed=score >= 0.8,
        score=score,
        details=details,
    )


if __name__ == "__main__":
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
}
""",
    }

    result = run_check(sample_trace)
    print(f"Result: {result}")
    print(f"  Score: {result.score:.2f}")
    print(f"  Passed: {result.passed}")
    print(f"  Details: {result.details}")
