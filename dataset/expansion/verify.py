"""verify.py

Pure-Python validation of a single RLang trace.  No cargo invocation.

Returns a structured result so callers can gate on score, display issues,
or feed a feedback loop.

Usage:
    from verify import verify_trace

    result = verify_trace(rlang_text)
    if result["valid"]:
        print(f"Score: {result['score']:.2f}")
    else:
        for issue in result["issues"]:
            print(f"  - {issue}")

CLI:
    python verify.py trace.rl
    python verify.py --text '#[phase(Frame)] ...'
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Mandatory phases in required order
PHASES = ["Frame", "Explore", "Verify", "Decide"]

# Distinct operators the spec defines across all 4 layers.
# We check for presence of at least MIN_DISTINCT_OPERATORS of these.
ALL_OPERATORS = {
    # Layer 1 — Epistemic
    "obs", "cause", "corr", "enbl", "prvnt", "req", "blf",
    "resolve", "sup", "wkn", "neut", "decay", "refresh", "conf",
    # Layer 2 — Motivational
    "goal", "desire", "intent", "dcmp", "prioritize", "select",
    "replan", "assert", "hedge", "suspend", "reject",
    # Layer 3 — Operational
    "exec", "inv", "rmb", "rcl", "bt", "retry_with", "emit",
    # Layer 4 — Communicative
    "dlg", "discover", "match_capability", "poll", "subscribe",
}

MIN_DISTINCT_OPERATORS = 6

# Connectives defined in the spec
ALL_CONNECTIVES = {"|>", "->", "||>", "<|", "~>", "!>", "?>", "@>", "<@"}
MIN_DISTINCT_CONNECTIVES = 3

# Character-level length bounds (rough token proxy: ~4 chars/token)
MIN_CHARS = 150   # ~37 tokens
MAX_CHARS = 12000 # ~3000 tokens

# Forbidden patterns
FORBIDDEN_BLF_CERTAINTY = re.compile(r"\bblf\s*<\s*1\.0\s*>")

# blf confidence value extractor: blf<0.85> or blf<0.85, 'stale>
BLF_VALUE_RE = re.compile(r"\bblf\s*<\s*([0-9]*\.?[0-9]+)")

# Phase header pattern
PHASE_HEADER_RE = re.compile(r"#\[phase\((\w+)\)\]")

# Phase body: text that follows a phase header up to the next header (or EOF)
# We use this to check for empty phases.
PHASE_BODY_RE = re.compile(
    r"#\[phase\(\w+\)\]\s*(?:impl\s+\w+\s*)?\{([^}]*(?:\{[^}]*\}[^}]*)*)\}",
    re.DOTALL,
)

# Scoring weights (must sum to 1.0)
WEIGHTS = {
    "phases_present":    0.25,
    "phase_order":       0.15,
    "operator_count":    0.20,
    "confidence_range":  0.15,
    "no_forbidden":      0.10,
    "connective_density":0.10,
    "length":            0.05,
}


# ---------------------------------------------------------------------------
# Core checks
# ---------------------------------------------------------------------------

def _check_phases(text: str) -> tuple[bool, bool, list[str]]:
    """Return (all_present, correct_order, issues)."""
    issues: list[str] = []
    found = PHASE_HEADER_RE.findall(text)

    missing = [p for p in PHASES if p not in found]
    if missing:
        issues.append(f"Missing phases: {', '.join(missing)}")
        return False, False, issues

    # Check order: the position of the first occurrence of each phase
    positions = {p: text.index(f"#[phase({p})]") for p in PHASES}
    ordered = sorted(PHASES, key=lambda p: positions[p])
    if ordered != PHASES:
        issues.append(
            f"Phases out of order: found {' -> '.join(ordered)}, "
            f"expected {' -> '.join(PHASES)}"
        )
        return True, False, issues

    return True, True, issues


def _check_empty_phases(text: str) -> list[str]:
    """Return issues for any phase whose body contains no operator calls."""
    issues: list[str] = []
    bodies = PHASE_BODY_RE.findall(text)
    # Pair bodies with phase names by matching order
    headers = PHASE_HEADER_RE.findall(text)
    for phase_name, body in zip(headers, bodies):
        stripped = body.strip()
        # A non-empty phase must have at least one operator call (word followed by '(')
        if not re.search(r"\w+\s*\(", stripped):
            issues.append(f"Phase '{phase_name}' appears empty (no operator calls found)")
    return issues


def _check_operators(text: str) -> tuple[int, list[str]]:
    """Return (distinct_operator_count, issues)."""
    found = set()
    for op in ALL_OPERATORS:
        # Match operator followed by '(' — avoids false positives in comments/strings
        if re.search(r"\b" + re.escape(op) + r"\s*\(", text):
            found.add(op)
    issues: list[str] = []
    if len(found) < MIN_DISTINCT_OPERATORS:
        issues.append(
            f"Too few distinct operators: {len(found)} (need >= {MIN_DISTINCT_OPERATORS}). "
            f"Found: {', '.join(sorted(found))}"
        )
    return len(found), issues


def _check_confidence_range(text: str) -> list[str]:
    """All blf<X> values must be in [0.0, 1.0) — 1.0 is forbidden by certainty rule."""
    issues: list[str] = []
    for m in BLF_VALUE_RE.finditer(text):
        try:
            val = float(m.group(1))
        except ValueError:
            continue
        if val < 0.0 or val > 1.0:
            issues.append(f"blf confidence out of range: {val} (must be 0.0-1.0)")
    return issues


def _check_no_forbidden(text: str) -> list[str]:
    """Check for forbidden patterns."""
    issues: list[str] = []
    if FORBIDDEN_BLF_CERTAINTY.search(text):
        issues.append(
            "Forbidden pattern: blf<1.0> (absolute certainty is disallowed; use blf<0.99> or hedge)"
        )
    return issues


def _check_connectives(text: str) -> tuple[int, list[str]]:
    """Return (distinct_connective_count, issues)."""
    found = {c for c in ALL_CONNECTIVES if c in text}
    issues: list[str] = []
    if len(found) < MIN_DISTINCT_CONNECTIVES:
        issues.append(
            f"Too few distinct connectives: {len(found)} (need >= {MIN_DISTINCT_CONNECTIVES}). "
            f"Found: {', '.join(sorted(found)) or 'none'}"
        )
    return len(found), issues


def _check_length(text: str) -> list[str]:
    """Rough length check using character count as a token proxy."""
    n = len(text)
    issues: list[str] = []
    if n < MIN_CHARS:
        issues.append(f"Trace too short: {n} chars (minimum {MIN_CHARS})")
    elif n > MAX_CHARS:
        issues.append(f"Trace too long: {n} chars (maximum {MAX_CHARS})")
    return issues


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def _compute_score(checks: dict) -> float:
    """Compute a weighted score in [0.0, 1.0].

    checks keys (bool): phases_present, phase_order, operator_ok,
                        confidence_ok, forbidden_ok, connective_ok, length_ok
    """
    raw = {
        "phases_present":     1.0 if checks["phases_present"] else 0.0,
        "phase_order":        1.0 if checks["phase_order"] else 0.0,
        "operator_count":     min(1.0, checks["operator_count"] / MIN_DISTINCT_OPERATORS),
        "confidence_range":   1.0 if checks["confidence_ok"] else 0.0,
        "no_forbidden":       1.0 if checks["forbidden_ok"] else 0.0,
        "connective_density": min(1.0, checks["connective_count"] / MIN_DISTINCT_CONNECTIVES),
        "length":             1.0 if checks["length_ok"] else 0.0,
    }
    return round(sum(WEIGHTS[k] * v for k, v in raw.items()), 4)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_trace(rlang_text: str) -> dict:
    """Validate a single RLang trace without invoking cargo.

    Returns:
        {
            "valid": bool,          # True iff all required checks pass
            "score": float,         # 0.0-1.0 quality score
            "issues": list[str],    # human-readable failure descriptions
        }
    """
    if not rlang_text or not rlang_text.strip():
        return {"valid": False, "score": 0.0, "issues": ["Empty trace"]}

    all_issues: list[str] = []

    # --- Phase presence & order ---
    phases_present, phase_order, phase_issues = _check_phases(rlang_text)
    all_issues.extend(phase_issues)

    # --- Empty phase bodies ---
    all_issues.extend(_check_empty_phases(rlang_text))

    # --- Operator count ---
    op_count, op_issues = _check_operators(rlang_text)
    all_issues.extend(op_issues)

    # --- Confidence range ---
    conf_issues = _check_confidence_range(rlang_text)
    all_issues.extend(conf_issues)

    # --- Forbidden patterns ---
    forbidden_issues = _check_no_forbidden(rlang_text)
    all_issues.extend(forbidden_issues)

    # --- Connective density ---
    conn_count, conn_issues = _check_connectives(rlang_text)
    all_issues.extend(conn_issues)

    # --- Length ---
    len_issues = _check_length(rlang_text)
    all_issues.extend(len_issues)

    checks = {
        "phases_present":  phases_present,
        "phase_order":     phase_order,
        "operator_count":  op_count,
        "confidence_ok":   len(conf_issues) == 0,
        "forbidden_ok":    len(forbidden_issues) == 0,
        "connective_count": conn_count,
        "length_ok":       len(len_issues) == 0,
    }
    score = _compute_score(checks)

    # A trace is valid only when all hard requirements pass
    valid = (
        phases_present
        and phase_order
        and op_count >= MIN_DISTINCT_OPERATORS
        and len(conf_issues) == 0
        and len(forbidden_issues) == 0
        and conn_count >= MIN_DISTINCT_CONNECTIVES
        and len(len_issues) == 0
        and len([i for i in all_issues if "empty" in i.lower()]) == 0
    )

    return {"valid": valid, "score": score, "issues": all_issues}


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cli() -> None:
    import argparse, json as _json

    parser = argparse.ArgumentParser(
        description="Validate a single RLang trace (pure Python, no cargo)"
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs="?", type=Path, help="Path to .rl file")
    group.add_argument("--text", type=str, help="RLang trace as a string argument")
    parser.add_argument("--json", action="store_true", help="Output result as JSON")
    args = parser.parse_args()

    if args.text:
        trace = args.text
    else:
        trace = args.file.read_text(encoding="utf-8")

    result = verify_trace(trace)

    if args.json:
        print(_json.dumps(result, indent=2))
    else:
        status = "VALID" if result["valid"] else "INVALID"
        print(f"[{status}] score={result['score']:.4f}")
        if result["issues"]:
            print("Issues:")
            for issue in result["issues"]:
                print(f"  - {issue}")
        else:
            print("No issues found.")

    sys.exit(0 if result["valid"] else 1)


if __name__ == "__main__":
    _cli()
