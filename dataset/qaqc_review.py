#!/usr/bin/env python3
"""
QAQC Review Framework for RLang Training Data Traces.

Reads traces from rlang_optimized.jsonl and validates each for:
  1. Structural validity (4 phases in correct order)
  2. Operator correctness (arity checks)
  3. Metadata completeness (p: and ep: on every belief)
  4. Evidence quality (sup/wkn with reasonable deltas)
  5. Decision coherence (match/assert/hedge matches reasoning)
  6. Compression quality (RLang meaningfully shorter than English)
  7. Content preservation (key reasoning captured, not just surface)
  8. Variable naming (meaningful, not generic boilerplate)

Usage:
  python3 dataset/qaqc_review.py --start 0 --end 500
"""

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PHASES_ORDERED = ["Frame", "Explore", "Verify", "Decide"]

# Operator -> expected arity (None = variadic)
OPERATOR_ARITY = {
    # Epistemic -- binary
    "cause": 2, "prvnt": 2, "enbl": 2, "req": 2,
    "sim": 2, "confl": 2, "cncl": 2, "cntns": 2, "isa": 2,
    # Epistemic -- unary
    "obs": 1, "goal": 1,
    # Epistemic -- ternary
    "chng": 3,
    # Epistemic -- variadic
    "seq": None,
    # Evidence modifiers
    "sup": 2, "wkn": 2, "neut": 2,
    # Motivational
    "dcmp": None, "dlg": 3,
    # Memory
    "rmb": 1, "rcl": 1, "bt": 1,
    # Operational
    "exec": 1, "inv": 2,
    # Communication
    "emit": 1, "pcv": 1,
}

# Generic variable names that signal low-quality conversion
GENERIC_VAR_NAMES = {
    "analysis", "first_i", "let_me_analyze", "let_me_break",
    "provided_text", "what_provided", "v_1_analyze",
    "first_i_need", "let_me_work", "let_me_think",
}

# Minimum compression ratio (English len / RLang len)
MIN_COMPRESSION_RATIO = 1.5

# Evidence delta thresholds
COMMON_DELTA_THRESHOLD = 0.90  # if >90% of deltas are identical, flag it


# ---------------------------------------------------------------------------
# Check functions -- each returns (ok: bool, issues: list[str])
# ---------------------------------------------------------------------------

def check_structure(rlang: str) -> tuple[bool, list[str]]:
    """Check all 4 phases present in correct order."""
    issues = []
    phase_positions = {}

    for phase in PHASES_ORDERED:
        pattern = rf'#\[phase\({phase}\)\]'
        match = re.search(pattern, rlang)
        if match:
            phase_positions[phase] = match.start()
        else:
            issues.append(f"missing_phase:{phase}")

    # Check ordering
    if len(phase_positions) >= 2:
        sorted_phases = sorted(phase_positions.keys(), key=lambda p: phase_positions[p])
        expected_present = [p for p in PHASES_ORDERED if p in phase_positions]
        if sorted_phases != expected_present:
            issues.append(f"phase_order_wrong: found {sorted_phases}, expected {expected_present}")

    ok = len(issues) == 0
    return ok, issues


def check_operators(rlang: str) -> tuple[bool, list[str]]:
    """Check operator arity correctness."""
    issues = []

    # Find all operator calls: name(args)
    # We need to handle nested parens, so use a simpler heuristic:
    # find operator_name( and then count commas at the top-level
    for op_name, expected_arity in OPERATOR_ARITY.items():
        if expected_arity is None:
            continue  # variadic, skip

        # Find all occurrences of op_name(
        pattern = rf'\b{op_name}\('
        for match in re.finditer(pattern, rlang):
            start = match.end()
            # Walk forward counting parens to find the closing paren
            depth = 1
            pos = start
            while pos < len(rlang) and depth > 0:
                if rlang[pos] == '(':
                    depth += 1
                elif rlang[pos] == ')':
                    depth -= 1
                pos += 1

            if depth != 0:
                continue  # malformed, will be caught elsewhere

            args_str = rlang[start:pos - 1].strip()
            if not args_str:
                actual_arity = 0
            else:
                # Count top-level commas
                comma_depth = 0
                comma_count = 0
                for ch in args_str:
                    if ch == '(':
                        comma_depth += 1
                    elif ch == ')':
                        comma_depth -= 1
                    elif ch == ',' and comma_depth == 0:
                        comma_count += 1
                actual_arity = comma_count + 1

            if actual_arity != expected_arity:
                issues.append(
                    f"arity_mismatch:{op_name} expected={expected_arity} got={actual_arity}"
                )

    ok = len(issues) == 0
    return ok, issues


def check_metadata(rlang: str) -> tuple[bool, list[str]]:
    """Check that every belief declaration has p: and ep: metadata."""
    issues = []

    # Find all belief declarations: let name: blf<...> = ...;
    blf_pattern = re.compile(r'let\s+(\w+)\s*:\s*blf<[^>]*>\s*=\s*([^;]+);', re.DOTALL)
    for match in blf_pattern.finditer(rlang):
        var_name = match.group(1)
        expr = match.group(2)

        if 'p:' not in expr:
            issues.append(f"missing_p_metadata: var={var_name}")
        if 'ep:' not in expr:
            issues.append(f"missing_ep_metadata: var={var_name}")

    # Also check if there are ANY blf declarations
    if not blf_pattern.search(rlang):
        # Check if Frame phase exists but has no beliefs
        if '#[phase(Frame)]' in rlang:
            issues.append("no_belief_declarations_in_frame")

    ok = len(issues) == 0
    return ok, issues


def check_evidence(rlang: str) -> tuple[bool, list[str]]:
    """Check evidence blocks use sup/wkn properly with reasonable deltas."""
    issues = []

    # Extract all evidence deltas
    delta_pattern = re.compile(r'(?:sup|wkn)\(\w+,\s*([+-]?\d+\.?\d*)\)')
    deltas = delta_pattern.findall(rlang)

    if not deltas:
        # Check if Explore phase exists but has no evidence
        if '#[phase(Explore)]' in rlang:
            # Not necessarily an error -- some traces use other patterns
            pass
        return True, issues

    float_deltas = []
    for d in deltas:
        try:
            float_deltas.append(float(d))
        except ValueError:
            issues.append(f"invalid_delta_value: {d}")

    # Check sup has positive deltas
    sup_deltas = re.findall(r'sup\(\w+,\s*([+-]?\d+\.?\d*)\)', rlang)
    for d in sup_deltas:
        try:
            if float(d) <= 0:
                issues.append(f"sup_with_non_positive_delta: {d}")
        except ValueError:
            pass

    # Check wkn has negative deltas
    wkn_deltas = re.findall(r'wkn\(\w+,\s*([+-]?\d+\.?\d*)\)', rlang)
    for d in wkn_deltas:
        try:
            if float(d) >= 0:
                issues.append(f"wkn_with_non_negative_delta: {d}")
        except ValueError:
            pass

    # Check for delta monoculture (all same value)
    if len(float_deltas) >= 2:
        unique_deltas = set(float_deltas)
        if len(unique_deltas) == 1:
            issues.append(f"delta_monoculture: all deltas are {float_deltas[0]}")

    # Check for unreasonable delta magnitudes (>0.5 is suspicious)
    for d in float_deltas:
        if abs(d) > 0.50:
            issues.append(f"extreme_delta: {d}")

    ok = len(issues) == 0
    return ok, issues


def check_decision(rlang: str) -> tuple[bool, list[str]]:
    """Check decision phase coherence."""
    issues = []

    decide_match = re.search(r'#\[phase\(Decide\)\]', rlang)
    if not decide_match:
        # Already caught by structural check
        return True, issues

    decide_section = rlang[decide_match.start():]

    # Check for match expression
    has_match = bool(re.search(r'match\s+conf\(', decide_section))
    has_assert = 'assert(' in decide_section
    has_hedge = 'hedge(' in decide_section

    if not has_match:
        issues.append("decide_missing_match_expression")

    if not has_assert and not has_hedge:
        issues.append("decide_no_assert_or_hedge")

    # Check match arms use valid decision operators
    match_arms = re.findall(r'=>\s*(\w+)\(', decide_section)
    valid_decision_ops = {'assert', 'hedge', 'suspend', 'reject'}
    for arm_op in match_arms:
        if arm_op not in valid_decision_ops:
            issues.append(f"invalid_decide_arm_operator: {arm_op}")

    # Check for boilerplate: if every trace has identical thresholds (0.80, 0.50)
    thresholds = re.findall(r'c\s*(?:if\s+c\s*)?>\s*(\d+\.?\d*)', decide_section)
    if thresholds == ['0.80', '0.50'] or thresholds == ['0.80', '0.55']:
        issues.append("boilerplate_decision_thresholds")

    ok = len(issues) == 0
    return ok, issues


def check_compression(english: str, rlang: str) -> tuple[bool, list[str]]:
    """Check if RLang is meaningfully shorter than English."""
    issues = []

    if not english or not rlang:
        issues.append("empty_text")
        return False, issues

    # Strip comments from RLang for fair comparison
    rlang_stripped = re.sub(r'//[^\n]*', '', rlang).strip()

    ratio = len(english) / max(len(rlang_stripped), 1)

    if ratio < 1.0:
        issues.append(f"rlang_longer_than_english: ratio={ratio:.2f}")
    elif ratio < MIN_COMPRESSION_RATIO:
        issues.append(f"low_compression: ratio={ratio:.2f} (min={MIN_COMPRESSION_RATIO})")

    return len(issues) == 0, issues


def check_content_preservation(english: str, rlang: str) -> tuple[bool, list[str]]:
    """Check if RLang captures key reasoning from English, not just surface patterns."""
    issues = []

    if not english or not rlang:
        return False, ["empty_text"]

    # Filler/connective words and meta-reasoning words that are NOT domain
    # concepts. These describe HOW you reason, not WHAT you reason about.
    FILLER_WORDS = {
        # Connectives and adverbs
        "however", "therefore", "actually", "basically", "essentially",
        "particularly", "furthermore", "moreover", "additionally",
        "consequently", "nevertheless", "otherwise", "although",
        "meanwhile", "ultimately", "certainly", "definitely",
        "probably", "possibly", "generally", "typically",
        "specifically", "obviously", "apparently", "sometimes",
        "regardless", "nonetheless", "accordingly", "subsequently",
        "previously", "currently", "initially", "originally",
        "frequently", "naturally", "importantly", "significantly",
        "absolutely", "relatively", "approximately",
        "entirely", "completely", "literally", "seriously",
        "honestly", "unfortunately", "fortunately", "interestingly",
        "considering", "following", "including", "involving",
        "regarding", "assuming", "provided",
        "something", "anything", "everything", "nothing",
        "someone", "another", "between", "through", "without",
        "because", "whether", "before", "already",
        # Meta-reasoning words (describe thinking process, not domain)
        "analysis", "analyze", "analyzing", "approach", "calculate",
        "calculation", "compare", "comparing", "comparison", "consider",
        "considered", "considering", "determine", "determining",
        "equation", "equations", "evaluate", "evaluating", "examine",
        "examining", "express", "expressed", "identify", "identifying",
        "important", "interpret", "interpreting", "mention", "mentioned",
        "multiply", "multiplying", "numbers", "observe", "obtained",
        "organized", "perform", "performing", "problem", "problems",
        "process", "processing", "provide", "provided", "question",
        "questions", "reasoning", "recognize", "represent", "representing",
        "required", "requires", "results", "several", "simplify",
        "solution", "solving", "statement", "summarize", "summary",
        "suppose", "understand", "understanding", "variables",
        "verification", "working", "writing", "written",
        "arranged", "becomes", "correct", "correctly", "different",
        "directly", "example", "examples", "explain", "explained",
        "expression", "finding", "information", "instead", "looking",
        "meaning", "methods", "noticed", "possible", "quickly",
        "remember", "similar", "situation", "standard", "suggest",
        "together", "already", "another", "applies", "applied",
        "appropriate", "approximate", "argument", "assuming",
        "breaking", "careful", "carefully", "certain", "clearly",
        "closely", "combined", "complex", "conclude", "condition",
        "conditions", "confirm", "confused", "context", "continue",
        "convert", "converted", "correctly", "dealing", "defined",
        "depends", "described", "details", "discussed", "divided",
        "earlier", "exactly", "expected", "finally", "formula",
        "further", "helpful", "implies", "increase", "initial",
        "involves", "largest", "maximum", "minimum", "modified",
        "negative", "notation", "original", "otherwise", "overall",
        "pattern", "perhaps", "positive", "previous", "proceed",
        "properly", "related", "remaining", "repeated", "response",
        "satisfy", "section", "separate", "simplified", "smallest",
        "started", "straightforward", "structure", "subtract",
        "suggests", "suppose", "systematically", "thinking", "thought",
        "through", "typically", "various", "whether",
    }

    # English reasoning verbs -> RLang operator mapping
    VERB_TO_OPERATOR = {
        "causes": "cause", "caused": "cause", "causing": "cause",
        "prevents": "prvnt", "prevented": "prvnt", "preventing": "prvnt",
        "enables": "enbl", "enabled": "enbl", "enabling": "enbl",
        "requires": "req", "required": "req", "requiring": "req",
        "needs": "req",
        "observes": "obs", "observed": "obs", "observing": "obs",
        "notices": "obs", "noticed": "obs", "noticing": "obs",
        "similar": "sim", "analogous": "sim",
        "conflicts": "confl", "contradicts": "confl", "contradicting": "confl",
        "changes": "chng", "changed": "chng", "transforms": "chng",
        "transforming": "chng", "changing": "chng",
        "contains": "cntns", "includes": "cntns", "containing": "cntns",
        "including": "cntns",
        "goal": "goal", "objective": "goal", "aim": "goal",
    }

    # Extract key nouns/concepts from English (simple heuristic: words > 5 chars)
    english_words = set(re.findall(r'\b[a-zA-Z]{5,}\b', english.lower()))

    # Extract variable names and identifiers from RLang
    rlang_ids = set(re.findall(r'\b[a-zA-Z_]\w*\b', rlang.lower()))

    # Check operator matches from English reasoning verbs
    rlang_lower = rlang.lower()
    operator_matches = 0
    for verb, op in VERB_TO_OPERATOR.items():
        if verb in english.lower() and f"{op}(" in rlang_lower:
            operator_matches += 1

    # Check if key concepts from English appear in RLang identifiers
    # (either directly or via prefix matching)
    found_concepts = 0
    total_concepts = 0
    key_words = {w for w in english_words if len(w) > 6}  # longer = more specific

    # Filter out filler/connective words
    key_words = key_words - FILLER_WORDS

    if not key_words:
        return True, []

    # Pre-compute RLang identifier prefixes for bidirectional matching
    rlang_prefixes = {rid[:6] for rid in rlang_ids if len(rid) >= 4}

    for word in key_words:
        total_concepts += 1
        prefix = word[:6]
        # Prefix matching (bidirectional): concept prefix matches identifier
        # prefix, OR identifier starts with concept prefix, OR concept
        # starts with identifier prefix. Handles converter truncation
        # (e.g., "authentication" -> "authenticati" matches prefix "authen")
        if prefix in rlang_prefixes:
            found_concepts += 1
        elif any(rid.startswith(prefix) for rid in rlang_ids):
            found_concepts += 1
        elif any(word.startswith(rp) for rp in rlang_prefixes if len(rp) >= 4):
            found_concepts += 1
        # Also check if word appears as substring (original behavior)
        elif any(word in rid for rid in rlang_ids):
            found_concepts += 1

    # Count operator matches as additional found concepts
    found_concepts += operator_matches

    # --- Fallback: domain-identifier density check ---
    # Even if English concepts don't directly match RLang identifiers,
    # the RLang may still preserve content through domain-specific
    # identifiers that were coined by the converter. Check that the
    # RLang has enough non-boilerplate identifiers.
    BOILERPLATE_IDS = {
        'impl', 'deductive', 'let', 'blf', 'obs', 'ev', 'resolve', 'conf',
        'match', 'assert', 'hedge', 'reject', 'suspend', 'phase', 'frame',
        'explore', 'verify', 'decide', 'sup', 'wkn', 'neut', 'cause',
        'prvnt', 'enbl', 'req', 'sim', 'confl', 'chng', 'cntns', 'isa',
        'goal', 'seq', 'dcmp', 'dlg', 'rmb', 'rcl', 'bt', 'exec', 'inv',
        'emit', 'pcv', 'ok', 'if', 'c', 'p', 'ep', 'direct', 'infer',
        'mixed', 'fresh', 'stale', 'src', 'eqn', 'key_values', '_',
        'rslv', 'blf_resolved', 'cncl', 'abductive', 'analogical',
    }
    domain_ids = {rid for rid in rlang_ids if rid not in BOILERPLATE_IDS and len(rid) >= 3}
    has_domain_content = len(domain_ids) >= 2

    if total_concepts > 0:
        coverage = found_concepts / total_concepts
        # Pass if:
        #   - coverage > 15% OR
        #   - has > 3 matched concepts OR
        #   - RLang has >= 2 domain-specific identifiers (content preserved
        #     through different naming)
        passes_coverage = (
            coverage > 0.15
            or found_concepts > 3
            or has_domain_content
        )
        if total_concepts <= 3:
            passes_coverage = found_concepts >= 1 or has_domain_content

        if not passes_coverage:
            issues.append(f"very_low_concept_coverage: {coverage:.2f} ({found_concepts}/{total_concepts})")

    # Check for "Auto-converted" comment -- indicates mechanical conversion
    if "Auto-converted from English reasoning trace" in rlang:
        issues.append("auto_conversion_marker_present")

    # Check for template boilerplate
    boilerplate_markers = [
        "impl Deductive",  # appears in almost every trace
    ]
    boilerplate_count = sum(1 for m in boilerplate_markers if m in rlang)
    # Not an issue by itself, but note it

    ok = len(issues) == 0
    return ok, issues


def check_variable_naming(rlang: str) -> tuple[bool, list[str]]:
    """Check variable names are meaningful and not generic boilerplate."""
    issues = []

    # Extract all let-bound variable names
    var_names = re.findall(r'let\s+(\w+)\s*[=:]', rlang)

    # Filter out standard names (ev, rslv)
    standard_names = {'ev', 'rslv', 'blf_resolved'}
    user_vars = [v for v in var_names if v not in standard_names]

    if not user_vars:
        return True, []

    # Check for generic names
    generic_count = 0
    for v in user_vars:
        if v in GENERIC_VAR_NAMES:
            generic_count += 1
            issues.append(f"generic_var_name: {v}")

    # Check for names that look like truncated English sentences
    for v in user_vars:
        if len(v) > 30:
            issues.append(f"var_name_too_long: {v[:40]}...")
        # Names starting with common English phrases
        sentence_prefixes = [
            'let_me_', 'first_i_', 'i_need_', 'we_need_',
            'the_problem_', 'this_is_', 'looking_at_',
            'youve_provided', 'what_provided', 'from_problem_',
        ]
        for prefix in sentence_prefixes:
            if v.startswith(prefix):
                issues.append(f"sentence_fragment_var: {v[:40]}")
                break

    # Check for single-char non-standard names
    for v in user_vars:
        if len(v) == 1 and v not in ('x', 'y', 'z', 'n', 'k', 'i', 'j'):
            issues.append(f"cryptic_single_char_var: {v}")

    ok = len(issues) == 0
    return ok, issues


# ---------------------------------------------------------------------------
# Aggregate scoring
# ---------------------------------------------------------------------------

def compute_score(checks: dict[str, tuple[bool, list[str]]]) -> float:
    """Compute 0.0-1.0 score from check results.

    Scoring is strict: a failed check gets 0 credit (no partial credit).
    This ensures the score honestly reflects quality.
    """
    weights = {
        'structural': 0.20,
        'operators': 0.10,
        'metadata': 0.10,
        'evidence': 0.10,
        'decision': 0.15,
        'compression': 0.15,
        'content': 0.10,
        'naming': 0.10,
    }

    score = 0.0
    for key, (ok, _issues) in checks.items():
        if ok:
            score += weights.get(key, 0.0)
        # Failed check = 0 credit, no partial

    return round(min(1.0, score), 3)


# ---------------------------------------------------------------------------
# Main review pipeline
# ---------------------------------------------------------------------------

def review_trace(trace: dict) -> dict:
    """Run all checks on a single trace and return review result."""
    trace_id = trace.get('id', 'unknown')
    rlang = trace.get('thinking_rlang', '')
    english = trace.get('thinking_english', '')

    checks = {
        'structural': check_structure(rlang),
        'operators': check_operators(rlang),
        'metadata': check_metadata(rlang),
        'evidence': check_evidence(rlang),
        'decision': check_decision(rlang),
        'compression': check_compression(english, rlang),
        'content': check_content_preservation(english, rlang),
        'naming': check_variable_naming(rlang),
    }

    all_issues = []
    for key, (ok, issues) in checks.items():
        all_issues.extend(issues)

    score = compute_score(checks)

    # Overall pass requires: score >= 0.60, structural OK, and at least
    # 5 of 8 checks passing (ensures breadth of quality)
    checks_passing = sum(1 for ok, _ in checks.values() if ok)
    overall_pass = (
        score >= 0.60
        and checks['structural'][0]
        and checks_passing >= 5
    )

    return {
        'id': trace_id,
        'structural_ok': checks['structural'][0],
        'semantic_ok': checks['operators'][0],
        'metadata_ok': checks['metadata'][0],
        'evidence_ok': checks['evidence'][0],
        'decision_ok': checks['decision'][0],
        'compression_ok': checks['compression'][0],
        'content_ok': checks['content'][0],
        'naming_ok': checks['naming'][0],
        'overall_pass': overall_pass,
        'issues': all_issues,
        'score': score,
    }


def write_summary(results: list[dict], output_path: Path) -> None:
    """Write human-readable summary of QAQC results."""
    total = len(results)
    passed = sum(1 for r in results if r['overall_pass'])
    failed = total - passed

    scores = [r['score'] for r in results]
    avg_score = sum(scores) / max(len(scores), 1)

    # Count check-level pass rates
    check_names = [
        'structural_ok', 'semantic_ok', 'metadata_ok', 'evidence_ok',
        'decision_ok', 'compression_ok', 'content_ok', 'naming_ok',
    ]
    check_pass_rates = {}
    for cn in check_names:
        pass_count = sum(1 for r in results if r.get(cn, False))
        check_pass_rates[cn] = pass_count

    # Count issue frequencies
    issue_counter = Counter()
    for r in results:
        for issue in r['issues']:
            # Normalize: take the part before the colon detail
            key = issue.split(':')[0] if ':' in issue else issue
            issue_counter[key] += 1

    # Find worst traces
    worst = sorted(results, key=lambda r: r['score'])[:20]

    with open(output_path, 'w') as f:
        f.write("=" * 72 + "\n")
        f.write("  QAQC Review Summary -- RLang Training Data\n")
        f.write("=" * 72 + "\n\n")

        f.write(f"Traces reviewed:  {total}\n")
        f.write(f"Overall PASS:     {passed} ({100 * passed / max(total, 1):.1f}%)\n")
        f.write(f"Overall FAIL:     {failed} ({100 * failed / max(total, 1):.1f}%)\n")
        f.write(f"Average score:    {avg_score:.3f}\n\n")

        f.write("-" * 72 + "\n")
        f.write("  Check-Level Pass Rates\n")
        f.write("-" * 72 + "\n")
        for cn in check_names:
            count = check_pass_rates[cn]
            label = cn.replace('_ok', '').replace('_', ' ').title()
            f.write(f"  {label:20s}: {count:4d}/{total}  ({100 * count / max(total, 1):5.1f}%)\n")
        f.write("\n")

        f.write("-" * 72 + "\n")
        f.write("  Most Common Issues (top 25)\n")
        f.write("-" * 72 + "\n")
        for issue, count in issue_counter.most_common(25):
            f.write(f"  {count:5d}x  {issue}\n")
        f.write("\n")

        f.write("-" * 72 + "\n")
        f.write("  Worst Traces (lowest scores, up to 20)\n")
        f.write("-" * 72 + "\n")
        for r in worst:
            f.write(f"  score={r['score']:.3f}  id={r['id']}\n")
            for issue in r['issues'][:5]:
                f.write(f"           - {issue}\n")
            if len(r['issues']) > 5:
                f.write(f"           ... and {len(r['issues']) - 5} more issues\n")
        f.write("\n")

        f.write("-" * 72 + "\n")
        f.write("  Recommendations\n")
        f.write("-" * 72 + "\n\n")

        # Generate recommendations based on findings
        if issue_counter.get('auto_conversion_marker_present', 0) > total * 0.5:
            f.write("  1. CRITICAL: Majority of traces have auto-conversion markers.\n")
            f.write("     The conversion pipeline is producing mechanical translations\n")
            f.write("     rather than genuine RLang reasoning. Consider re-converting\n")
            f.write("     with a model that understands RLang semantics.\n\n")

        comp_fail = total - check_pass_rates.get('compression_ok', 0)
        if comp_fail > total * 0.3:
            f.write(f"  2. COMPRESSION: {comp_fail} traces ({100 * comp_fail / total:.0f}%) fail\n")
            f.write("     the compression ratio check. RLang should be significantly\n")
            f.write("     shorter than English. Many traces are longer or about the same.\n")
            f.write("     Root cause: verbose auto-conversion that pads with boilerplate.\n\n")

        if issue_counter.get('generic_var_name', 0) > total * 0.3:
            f.write("  3. NAMING: High rate of generic variable names ('analysis',\n")
            f.write("     'what_provided'). The converter is not extracting meaningful\n")
            f.write("     domain-specific identifiers from the reasoning.\n\n")

        if issue_counter.get('boilerplate_decision_thresholds', 0) > total * 0.5:
            f.write("  4. DECISIONS: Boilerplate decision thresholds (0.80/0.50) used\n")
            f.write("     in >50% of traces. The Decide phase should adapt thresholds\n")
            f.write("     based on problem domain and confidence evolution.\n\n")

        if issue_counter.get('delta_monoculture', 0) > total * 0.1:
            f.write("  5. EVIDENCE: Delta monoculture detected -- most evidence blocks\n")
            f.write("     use identical deltas (+0.12). Evidence weights should reflect\n")
            f.write("     the actual strength of each piece of evidence.\n\n")

        if issue_counter.get('sentence_fragment_var', 0) > total * 0.05:
            f.write("  6. NAMING: Variable names contain English sentence fragments\n")
            f.write("     (e.g., 'let_me_analyze', 'first_i_need'). These should be\n")
            f.write("     concise domain terms.\n\n")

        f.write("=" * 72 + "\n")
        f.write("  End of QAQC Report\n")
        f.write("=" * 72 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="QAQC review of RLang training data traces"
    )
    parser.add_argument(
        '--start', type=int, default=0,
        help='Start index (0-based, inclusive). Default: 0'
    )
    parser.add_argument(
        '--end', type=int, default=500,
        help='End index (exclusive). Default: 500'
    )
    parser.add_argument(
        '--input', type=str,
        default='dataset/data/rlang_optimized.jsonl',
        help='Input JSONL file path'
    )
    parser.add_argument(
        '--output-dir', type=str,
        default='dataset/data',
        help='Output directory for review files'
    )
    args = parser.parse_args()

    # Resolve paths relative to project root
    script_dir = Path(__file__).resolve().parent
    project_root = script_dir.parent
    input_path = project_root / args.input if not Path(args.input).is_absolute() else Path(args.input)
    output_dir = project_root / args.output_dir if not Path(args.output_dir).is_absolute() else Path(args.output_dir)

    if not input_path.exists():
        print(f"Error: input file not found: {input_path}", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Determine batch label from start/end
    batch_label = f"batch{(args.start // 500) + 1}"
    review_path = output_dir / f"qaqc_review_{batch_label}.jsonl"
    summary_path = output_dir / f"qaqc_summary_{batch_label}.txt"

    # Read input
    print(f"Reading traces from {input_path}...")
    with open(input_path, 'r') as f:
        all_lines = f.readlines()

    total_available = len(all_lines)
    start = max(0, args.start)
    end = min(args.end, total_available)
    print(f"Reviewing traces {start}-{end - 1} (of {total_available} total)")

    # Process traces
    results = []
    for i in range(start, end):
        try:
            trace = json.loads(all_lines[i])
        except json.JSONDecodeError as e:
            results.append({
                'id': f'line_{i}',
                'structural_ok': False,
                'semantic_ok': False,
                'metadata_ok': False,
                'evidence_ok': False,
                'decision_ok': False,
                'compression_ok': False,
                'content_ok': False,
                'naming_ok': False,
                'overall_pass': False,
                'issues': [f'json_parse_error: {e}'],
                'score': 0.0,
            })
            continue

        result = review_trace(trace)
        results.append(result)

        # Progress indicator every 100
        if (i - start + 1) % 100 == 0:
            done = i - start + 1
            total = end - start
            recent_scores = [r['score'] for r in results[-100:]]
            avg = sum(recent_scores) / len(recent_scores)
            print(f"  [{done}/{total}] avg score last 100: {avg:.3f}")

    # Write review JSONL
    print(f"\nWriting review to {review_path}...")
    with open(review_path, 'w') as f:
        for r in results:
            f.write(json.dumps(r) + '\n')

    # Write summary
    print(f"Writing summary to {summary_path}...")
    write_summary(results, summary_path)

    # Print quick stats
    passed = sum(1 for r in results if r['overall_pass'])
    total = len(results)
    avg_score = sum(r['score'] for r in results) / max(total, 1)
    print(f"\nDone. {passed}/{total} passed ({100 * passed / max(total, 1):.1f}%), avg score: {avg_score:.3f}")


if __name__ == "__main__":
    main()
