"""English-to-RLang converter: pattern recognition, phase structuring, waste removal.

Converts English reasoning traces into valid, optimized RLang traces.
Reads from dataset/data/standardized.parquet or JSONL input.
Outputs to dataset/data/rlang_converted.jsonl.

Usage:
    python dataset/convert.py                          # Convert from parquet
    python dataset/convert.py --input traces.jsonl     # Convert from JSONL
    python dataset/convert.py --limit 100              # Convert first N rows
    python dataset/convert.py --no-validate            # Skip cargo validation
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_INPUT = DATA_DIR / "standardized.parquet"
DEFAULT_OUTPUT = DATA_DIR / "rlang_converted.jsonl"
VALIDATOR_CMD = ["cargo", "run", "--quiet", "--", "--validate-only"]

# ---------------------------------------------------------------------------
# Pattern definitions
# ---------------------------------------------------------------------------

# Operator mapping: (regex_pattern, operator_template)
# Each tuple is (compiled_regex, operator_name, arity)
# We extract noun phrases from the surrounding context.

OPERATOR_PATTERNS = [
    # Causal operators
    (re.compile(r"(?:because|causes?|leads?\s+to|results?\s+in)\s+(.+?)(?:\.|,|$)", re.I),
     "cause", 2),
    (re.compile(r"(?:prevents?|blocks?|stops?)\s+(.+?)(?:\.|,|$)", re.I),
     "prvnt", 2),
    (re.compile(r"(?:enables?|allows?|makes?\s+possible)\s+(.+?)(?:\.|,|$)", re.I),
     "enbl", 2),
    (re.compile(r"(?:requires?|needs?|depends?\s+on|must\s+have)\s+(.+?)(?:\.|,|$)", re.I),
     "req", 2),

    # Observation
    (re.compile(r"(?:I\s+notice|I\s+see|I\s+observe|looking\s+at|given\s+that)\s+(.+?)(?:\.|,|$)", re.I),
     "obs", 1),

    # Similarity / analogy
    (re.compile(r"(?:similar\s+to|like|analogous\s+to|reminds?\s+me\s+of)\s+(.+?)(?:\.|,|$)", re.I),
     "sim", 2),

    # Conflict
    (re.compile(r"(?:contradicts?|conflicts?\s+with|inconsistent\s+with?)\s+(.+?)(?:\.|,|$)", re.I),
     "confl", 2),

    # Change
    (re.compile(r"(?:changes?\s+from|went\s+from|transformed?)\s+(.+?)(?:\s+to\s+)(.+?)(?:\.|,|$)", re.I),
     "chng", 3),

    # Cancel / negate
    (re.compile(r"(?:not|no\s+longer|cancel(?:ed|led)?|negated?)\s+(.+?)(?:\.|,|$)", re.I),
     "cncl", 1),

    # Contains
    (re.compile(r"(?:contains?|includes?|has)\s+(.+?)(?:\.|,|$)", re.I),
     "cntns", 2),

    # Taxonomy
    (re.compile(r"(?:is\s+a\s+type\s+of|is\s+a\s+kind\s+of|categorized\s+as)\s+(.+?)(?:\.|,|$)", re.I),
     "isa", 2),

    # Sequence
    (re.compile(r"(?:then|next|followed\s+by|after\s+that)\s*[,:]?\s*(.+?)(?:\.|,|$)", re.I),
     "seq", 2),

    # Goal
    (re.compile(r"(?:goal\s+is|want\s+to|need\s+to\s+achieve|objective\s+is)\s+(.+?)(?:\.|,|$)", re.I),
     "goal", 2),
]

# Confidence mapping from English hedging language
CONFIDENCE_PATTERNS = [
    (re.compile(r"\b(?:definitely|certainly|clearly|obviously|undoubtedly)\b", re.I), 0.95),
    (re.compile(r"\b(?:likely|probably|most\s+likely)\b", re.I), 0.80),
    (re.compile(r"\b(?:possibly|might|could|perhaps|maybe)\b", re.I), 0.60),
    (re.compile(r"\b(?:unlikely|doubtful|improbable)\b", re.I), 0.35),
    (re.compile(r"\b(?:I'?m\s+not\s+sure|uncertain|unclear|unsure)\b", re.I), 0.50),
]
DEFAULT_CONFIDENCE = 0.75

# Epistemic mode detection
EP_DIRECT_PATTERNS = re.compile(
    r"\b(?:I\s+(?:see|notice|observe|find)|looking\s+at|given\s+that|the\s+data\s+shows?)\b", re.I
)
EP_INFER_PATTERNS = re.compile(
    r"\b(?:therefore|thus|so\s+(?:that|we)|hence|implies?|deduc|infer|conclude|it\s+follows|must\s+be|logically)\b", re.I
)
EP_ANL_PATTERNS = re.compile(
    r"\b(?:similar\s+to|like|analogous|analogy|reminds?\s+me|compare|just\s+as|same\s+way)\b", re.I
)

# Waste patterns to strip
SELF_REFLECTION = re.compile(
    r"(?:^|\.\s*)"
    r"(?:wait|actually|hmm+|let\s+me\s+reconsider|let\s+me\s+re-?think|"
    r"hold\s+on|on\s+second\s+thought|no\s+wait|scratch\s+that|"
    r"let\s+me\s+start\s+over|actually\s+wait)"
    r"[^.]*\.?",
    re.I | re.MULTILINE,
)

FILLER = re.compile(
    r"(?:^|\.\s*)"
    r"(?:let\s+me\s+think\s+about\s+this|"
    r"okay\s+so|alright|so\s+basically|"
    r"let\s+me\s+work\s+through\s+this|"
    r"let's\s+see|let\s+me\s+break\s+this\s+down|"
    r"I\s+need\s+to\s+think\s+about|"
    r"hmm\s+let\s+me|well\s+let\s+me)"
    r"[^.]*\.?",
    re.I | re.MULTILINE,
)

PROBLEM_RESTATEMENT = re.compile(
    r"(?:^|\.\s*)"
    r"(?:the\s+(?:problem|question)\s+(?:is|asks?|states?|says?)|"
    r"we\s+(?:are|need\s+to)\s+(?:asked|given|told)|"
    r"so\s+the\s+question\s+is|"
    r"I\s+need\s+to\s+(?:find|determine|figure\s+out|solve))"
    r"[^.]*\.?",
    re.I | re.MULTILINE,
)

REDUNDANT_HEDGING = re.compile(
    r"\b(?:I\s+think\s+that|I\s+believe\s+that|it\s+seems?\s+(?:like|that)|"
    r"in\s+my\s+opinion|as\s+far\s+as\s+I\s+can\s+tell)\b",
    re.I,
)

# Sentence splitter (simple)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class ExtractedStatement:
    """A single RLang statement extracted from English."""
    operator: str
    args: list[str]
    confidence: float = DEFAULT_CONFIDENCE
    ep_mode: str = "infer"
    source_sentence: str = ""
    phase_hint: str = ""  # frame, explore, verify, decide


@dataclass
class RLangTrace:
    """A complete RLang trace with all 4 phases."""
    frame_statements: list[ExtractedStatement] = field(default_factory=list)
    explore_statements: list[ExtractedStatement] = field(default_factory=list)
    verify_statements: list[ExtractedStatement] = field(default_factory=list)
    decide_statements: list[ExtractedStatement] = field(default_factory=list)
    reasoning_mode: str = "Deductive"
    primary_belief: str = "conclusion"
    goal_name: Optional[str] = None


# ---------------------------------------------------------------------------
# Core conversion logic
# ---------------------------------------------------------------------------

def sanitize_identifier(text: str) -> str:
    """Convert English phrase to valid RLang identifier."""
    # Take first few meaningful words
    text = text.strip().lower()
    # Remove articles and prepositions
    text = re.sub(r"\b(?:the|a|an|is|are|was|were|of|in|to|for|with|that|this|it)\b", "", text)
    text = text.strip()
    # Take first 3 words max
    words = re.split(r"\s+", text)[:3]
    words = [re.sub(r"[^a-z0-9]", "", w) for w in words if w]
    if not words:
        return "x"
    ident = "_".join(words)
    # Ensure it starts with a letter
    if ident and not ident[0].isalpha():
        ident = "v_" + ident
    return ident[:30] or "x"


def detect_confidence(sentence: str) -> float:
    """Detect confidence level from English hedging language."""
    for pattern, conf in CONFIDENCE_PATTERNS:
        if pattern.search(sentence):
            return conf
    return DEFAULT_CONFIDENCE


def detect_ep_mode(sentence: str) -> str:
    """Detect epistemic mode from sentence language."""
    if EP_DIRECT_PATTERNS.search(sentence):
        return "direct"
    if EP_ANL_PATTERNS.search(sentence):
        return "anl"
    if EP_INFER_PATTERNS.search(sentence):
        return "infer"
    return "infer"


def strip_waste(text: str) -> str:
    """Remove self-reflection, filler, problem restatement, redundant hedging."""
    text = SELF_REFLECTION.sub("", text)
    text = FILLER.sub("", text)
    text = PROBLEM_RESTATEMENT.sub("", text)
    text = REDUNDANT_HEDGING.sub("", text)
    # Clean up whitespace
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_statements(text: str) -> list[ExtractedStatement]:
    """Extract RLang operator statements from English text."""
    statements = []
    sentences = SENTENCE_SPLIT.split(text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue

        conf = detect_confidence(sentence)
        ep = detect_ep_mode(sentence)

        matched = False
        for pattern, op_name, arity in OPERATOR_PATTERNS:
            m = pattern.search(sentence)
            if m:
                groups = [g.strip() for g in m.groups() if g and g.strip()]
                if not groups:
                    continue

                if arity == 1:
                    args = [sanitize_identifier(groups[0])]
                elif arity == 2:
                    if len(groups) >= 2:
                        args = [sanitize_identifier(groups[0]), sanitize_identifier(groups[1])]
                    else:
                        # For binary ops, try to extract subject from before the match
                        pre_text = sentence[:m.start()].strip()
                        subject = sanitize_identifier(pre_text) if pre_text else "x"
                        args = [subject, sanitize_identifier(groups[0])]
                elif arity == 3:
                    if len(groups) >= 2:
                        subject_text = sentence[:m.start()].strip()
                        subject = sanitize_identifier(subject_text) if subject_text else "x"
                        args = [subject, sanitize_identifier(groups[0]), sanitize_identifier(groups[1])]
                    else:
                        args = [sanitize_identifier(groups[0])]
                else:
                    args = [sanitize_identifier(g) for g in groups]

                stmt = ExtractedStatement(
                    operator=op_name,
                    args=args,
                    confidence=conf,
                    ep_mode=ep,
                    source_sentence=sentence,
                )
                statements.append(stmt)
                matched = True
                break  # One operator per sentence

        # If no operator matched, capture factual or conclusive statements
        if not matched:
            ident = sanitize_identifier(sentence)
            if ident and ident != "x":
                if ep == "direct":
                    # Direct observations
                    statements.append(ExtractedStatement(
                        operator="obs",
                        args=[ident],
                        confidence=conf,
                        ep_mode="direct",
                        source_sentence=sentence,
                    ))
                elif conf >= 0.80 or ep == "infer":
                    # High-confidence conclusions or inferences -- capture as
                    # evidence that will flow into the Explore phase
                    statements.append(ExtractedStatement(
                        operator="cause",
                        args=["analysis", ident],
                        confidence=conf,
                        ep_mode=ep,
                        source_sentence=sentence,
                    ))

    return statements


def assign_phases(statements: list[ExtractedStatement]) -> RLangTrace:
    """Assign statements to the 4 RLang phases based on position and type."""
    if not statements:
        return RLangTrace()

    n = len(statements)
    trace = RLangTrace()

    # Phase assignment by position and operator type
    # Frame: first 10-20% -- obs(), req(), goal()
    # Explore: middle 40-60% -- evidence, causal reasoning
    # Verify: next 15-25% -- req() checks, verify()
    # Decide: final 10-15% -- match conf()

    frame_end = max(1, int(n * 0.20))
    explore_end = max(frame_end + 1, int(n * 0.75))
    verify_end = max(explore_end + 1, int(n * 0.90))

    # Observation and requirement operators always go to Frame
    frame_ops = {"obs", "req", "goal", "isa", "cntns"}
    # Evidence modifiers go to Explore
    explore_ops = {"cause", "prvnt", "enbl", "sim", "confl", "seq", "chng", "cncl"}

    for i, stmt in enumerate(statements):
        if stmt.operator in frame_ops and i < explore_end:
            # obs/req/goal statements go to Frame even if in explore range
            trace.frame_statements.append(stmt)
        elif i < frame_end:
            trace.frame_statements.append(stmt)
        elif i < explore_end:
            trace.explore_statements.append(stmt)
        elif i < verify_end:
            trace.verify_statements.append(stmt)
        else:
            trace.decide_statements.append(stmt)

    # Detect goal name from any goal() statement
    for stmt in trace.frame_statements:
        if stmt.operator == "goal":
            trace.goal_name = stmt.args[-1] if stmt.args else "conclusion"
            break

    # Detect reasoning mode from statement types
    has_analogy = any(s.operator == "sim" for s in statements)
    has_obs = any(s.ep_mode == "direct" for s in statements)
    if has_analogy:
        trace.reasoning_mode = "Analogical"
    elif has_obs and not any(s.operator in explore_ops for s in statements):
        trace.reasoning_mode = "Abductive"
    else:
        trace.reasoning_mode = "Deductive"

    # Determine primary belief name
    if trace.goal_name:
        trace.primary_belief = trace.goal_name
    elif trace.frame_statements:
        trace.primary_belief = trace.frame_statements[0].args[0] if trace.frame_statements[0].args else "conclusion"
    else:
        trace.primary_belief = "conclusion"

    # Ensure each phase has at least one statement (generate minimal defaults)
    if not trace.frame_statements:
        trace.frame_statements.append(ExtractedStatement(
            operator="obs", args=["input"], confidence=0.90, ep_mode="direct"
        ))
    if not trace.explore_statements:
        # Promote last frame statements or create default
        trace.explore_statements.append(ExtractedStatement(
            operator="cause", args=["analysis", trace.primary_belief],
            confidence=DEFAULT_CONFIDENCE, ep_mode="infer"
        ))
    if not trace.verify_statements:
        trace.verify_statements.append(ExtractedStatement(
            operator="req", args=[trace.primary_belief, "obs(" + trace.frame_statements[0].args[0] + ")"],
            confidence=0.90, ep_mode="infer"
        ))

    return trace


def format_operator_call(stmt: ExtractedStatement) -> str:
    """Format a single operator call with metadata."""
    args_str = ", ".join(stmt.args)
    return f"{stmt.operator}({args_str})"


def generate_frame_block(trace: RLangTrace) -> str:
    """Generate the Frame phase block."""
    lines = []
    lines.append(f"#[phase(Frame)]")
    lines.append(f"impl {trace.reasoning_mode} {{")

    # Merge consecutive obs() statements efficiently
    obs_stmts = [s for s in trace.frame_statements if s.operator == "obs"]
    other_stmts = [s for s in trace.frame_statements if s.operator != "obs"]

    for stmt in obs_stmts:
        name = stmt.args[0] if stmt.args else "fact"
        conf = f"{stmt.confidence:.2f}"
        lines.append(
            f"    let {name}: blf<{conf}> = obs({name})"
            f" | p:{conf} | ep:{stmt.ep_mode} | src:obs(input) | scope:loc | t:fresh;"
        )

    for stmt in other_stmts:
        if stmt.operator == "goal":
            goal_name = stmt.args[-1] if stmt.args else "target"
            lines.append(
                f"    let {goal_name}_goal = goal({goal_name})"
                f" | p:{stmt.confidence:.2f} | ep:{stmt.ep_mode};"
            )
        elif stmt.operator == "req":
            # req() must be in a let binding or pipe chain, not standalone
            name = f"r_{stmt.args[0]}" if stmt.args else "r_constraint"
            lines.append(
                f"    let {name} = {format_operator_call(stmt)}"
                f" | p:{stmt.confidence:.2f} | ep:{stmt.ep_mode};"
            )
        else:
            name = stmt.args[0] if stmt.args else "fact"
            conf = f"{stmt.confidence:.2f}"
            lines.append(
                f"    let {name}: blf<{conf}> = {format_operator_call(stmt)}"
                f" | p:{conf} | ep:{stmt.ep_mode} | scope:loc | t:fresh;"
            )

    lines.append("}")
    return "\n".join(lines)


def generate_explore_block(trace: RLangTrace) -> str:
    """Generate the Explore phase block."""
    lines = []
    lines.append("#[phase(Explore)]")
    lines.append("{")

    belief = trace.primary_belief

    # Build evidence block from explore statements
    ev_items = []
    for stmt in trace.explore_statements:
        if stmt.operator in ("cause", "enbl"):
            # Supporting evidence
            delta = f"+{(stmt.confidence - 0.5) * 0.5:.2f}" if stmt.confidence > 0.5 else f"{(stmt.confidence - 0.5) * 0.5:.2f}"
            source_name = stmt.args[0] if stmt.args else "evidence"
            ev_items.append(f"        {source_name} => sup({belief}, {delta})")
        elif stmt.operator in ("prvnt", "confl", "cncl"):
            # Weakening evidence
            delta = f"-{(1.0 - stmt.confidence) * 0.5:.2f}"
            source_name = stmt.args[0] if stmt.args else "counter_ev"
            ev_items.append(f"        {source_name} => wkn({belief}, {delta})")
        elif stmt.operator == "sim":
            # Neutral/analogical evidence
            source_name = stmt.args[0] if stmt.args else "analogy"
            ev_items.append(f"        {source_name} => sup({belief}, +0.10)")
        else:
            # Default to supporting
            source_name = stmt.args[0] if stmt.args else "ev"
            delta = f"+{(stmt.confidence - 0.5) * 0.3:.2f}" if stmt.confidence > 0.5 else "+0.05"
            ev_items.append(f"        {source_name} => sup({belief}, {delta})")

    if ev_items:
        lines.append("    let ev = [")
        lines.append(",\n".join(ev_items) + ",")
        lines.append("    ];")
        lines.append(f"    {belief} |> resolve(ev) -> Ok(resolved);")
    else:
        lines.append(f"    {belief} |> resolve([]) -> Ok(resolved);")

    lines.append("}")
    return "\n".join(lines)


def generate_verify_block(trace: RLangTrace) -> str:
    """Generate the Verify phase block."""
    lines = []
    lines.append("#[phase(Verify)]")
    lines.append("{")

    belief = trace.primary_belief

    # Use verify statements or generate from frame observations
    if trace.verify_statements:
        for stmt in trace.verify_statements:
            if stmt.operator == "req":
                args_str = ", ".join(stmt.args)
                lines.append(f"    req({args_str}) |> verify({belief}) -> Ok(());")
            else:
                obs_name = stmt.args[0] if stmt.args else belief
                lines.append(f"    req({belief}, obs({obs_name})) |> verify({obs_name}) -> Ok(());")
    else:
        # Default: verify the primary belief against first observation
        first_obs = trace.frame_statements[0].args[0] if trace.frame_statements and trace.frame_statements[0].args else "input"
        lines.append(f"    req({belief}, obs({first_obs})) |> verify({first_obs}) -> Ok(());")

    lines.append("}")
    return "\n".join(lines)


def generate_decide_block(trace: RLangTrace) -> str:
    """Generate the Decide phase block."""
    lines = []
    lines.append("#[phase(Decide)]")
    lines.append("{")

    belief = trace.primary_belief

    # Determine overall confidence for thresholds
    all_confs = [s.confidence for s in
                 trace.frame_statements + trace.explore_statements +
                 trace.verify_statements + trace.decide_statements]
    avg_conf = sum(all_confs) / len(all_confs) if all_confs else DEFAULT_CONFIDENCE

    # Generate match expression
    lines.append(f"    match conf({belief}) {{")
    lines.append(f"        c if c > 0.80 => assert({belief}),")
    if avg_conf > 0.6:
        lines.append(f"        c if c > 0.50 => hedge({belief}),")
    else:
        lines.append(f"        c if c > 0.50 => suspend({belief}),")
    lines.append(f"        _ => reject({belief}),")
    lines.append("    }")

    lines.append("}")
    return "\n".join(lines)


def convert_trace(english_text: str) -> tuple[str, bool]:
    """Convert a single English reasoning trace to RLang.

    Returns: (rlang_text, success_bool)
    """
    if not english_text or not english_text.strip():
        return "", False

    # Step 1: Strip waste
    cleaned = strip_waste(english_text)
    if not cleaned or len(cleaned) < 20:
        return "", False

    # Step 2: Extract operator statements
    statements = extract_statements(cleaned)
    if not statements:
        # If no operators found, create minimal obs-based trace
        sentences = SENTENCE_SPLIT.split(cleaned)
        meaningful = [s.strip() for s in sentences if len(s.strip()) > 15][:5]
        for s in meaningful:
            ident = sanitize_identifier(s)
            if ident and ident != "x":
                statements.append(ExtractedStatement(
                    operator="obs", args=[ident], confidence=detect_confidence(s),
                    ep_mode=detect_ep_mode(s), source_sentence=s,
                ))
        if not statements:
            return "", False

    # Step 3: Assign to phases
    trace = assign_phases(statements)

    # Step 4: Generate RLang blocks
    parts = [
        f"// Auto-converted from English reasoning trace",
        "",
        generate_frame_block(trace),
        "",
        generate_explore_block(trace),
        "",
        generate_verify_block(trace),
        "",
        generate_decide_block(trace),
    ]

    rlang_text = "\n".join(parts)
    return rlang_text, True


def estimate_tokens(text: str) -> int:
    """Estimate token count: word_count * 1.3."""
    if not text:
        return 0
    return int(len(text.split()) * 1.3)


def validate_rlang(rlang_text: str) -> bool:
    """Validate an RLang trace by calling the cargo validator."""
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".rl", dir=str(PROJECT_ROOT), delete=False
        ) as f:
            f.write(rlang_text)
            f.flush()
            tmp_path = f.name

        result = subprocess.run(
            VALIDATOR_CMD + [tmp_path],
            cwd=str(PROJECT_ROOT),
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return False
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# Batch processing
# ---------------------------------------------------------------------------

def process_record(record: dict, do_validate: bool = True) -> Optional[dict]:
    """Process a single record from the standardized dataset."""
    english = record.get("thinking_english", "")
    if not english:
        return None

    rlang_text, success = convert_trace(english)
    if not success:
        return None

    english_tokens = estimate_tokens(english)
    rlang_tokens = estimate_tokens(rlang_text)

    valid = True
    if do_validate:
        valid = validate_rlang(rlang_text)

    compression = english_tokens / rlang_tokens if rlang_tokens > 0 else 0.0

    return {
        "id": record.get("id", "unknown"),
        "source": record.get("source", "unknown"),
        "problem": record.get("problem", ""),
        "thinking_english": english,
        "thinking_rlang": rlang_text,
        "solution": record.get("solution", ""),
        "english_tokens_est": english_tokens,
        "rlang_tokens_est": rlang_tokens,
        "compression_ratio": round(compression, 2),
        "valid": valid,
        "domain": record.get("domain", "reasoning"),
        "difficulty": record.get("difficulty", "medium"),
    }


def load_input(input_path: Path) -> list[dict]:
    """Load records from parquet or JSONL."""
    if input_path.suffix == ".parquet":
        import pandas as pd
        df = pd.read_parquet(input_path)
        return df.to_dict("records")
    elif input_path.suffix in (".jsonl", ".json"):
        records = []
        with open(input_path) as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        return records
    else:
        raise ValueError(f"Unsupported input format: {input_path.suffix}")


def run_batch(
    input_path: Path = DEFAULT_INPUT,
    output_path: Path = DEFAULT_OUTPUT,
    limit: Optional[int] = None,
    do_validate: bool = True,
) -> dict:
    """Run batch conversion and return statistics."""
    records = load_input(input_path)
    if limit:
        records = records[:limit]

    print(f"Processing {len(records)} records...")
    print(f"  Input:  {input_path}")
    print(f"  Output: {output_path}")
    print(f"  Validation: {'enabled' if do_validate else 'disabled'}")
    print()

    results = []
    successes = 0
    failures = 0
    validation_failures = 0
    total_english_tokens = 0
    total_rlang_tokens = 0
    failure_reasons: Counter = Counter()

    with open(output_path, "w") as out_f:
        for i, record in enumerate(records):
            if (i + 1) % 100 == 0:
                print(f"  [{i + 1}/{len(records)}] "
                      f"success={successes} fail={failures} "
                      f"valid_fail={validation_failures}")

            result = process_record(record, do_validate=do_validate)

            if result is None:
                failures += 1
                english = record.get("thinking_english", "")
                if not english:
                    failure_reasons["empty_trace"] += 1
                elif len(english) < 20:
                    failure_reasons["trace_too_short"] += 1
                else:
                    failure_reasons["no_operators_found"] += 1
                continue

            if not result["valid"]:
                validation_failures += 1
                failure_reasons["validation_failed"] += 1

            results.append(result)
            successes += 1
            total_english_tokens += result["english_tokens_est"]
            total_rlang_tokens += result["rlang_tokens_est"]

            out_f.write(json.dumps(result) + "\n")

    # Compute statistics
    avg_compression = (
        total_english_tokens / total_rlang_tokens
        if total_rlang_tokens > 0 else 0.0
    )
    valid_count = sum(1 for r in results if r["valid"])

    stats = {
        "total_records": len(records),
        "converted": successes,
        "failed": failures,
        "validation_failures": validation_failures,
        "success_rate": successes / len(records) * 100 if records else 0,
        "valid_rate": valid_count / successes * 100 if successes else 0,
        "avg_compression_ratio": round(avg_compression, 2),
        "total_english_tokens": total_english_tokens,
        "total_rlang_tokens": total_rlang_tokens,
        "failure_reasons": dict(failure_reasons),
    }

    return stats


def print_stats(stats: dict) -> None:
    """Pretty-print conversion statistics."""
    print()
    print("=" * 60)
    print("  CONVERSION STATISTICS")
    print("=" * 60)
    print(f"  Total records:       {stats['total_records']}")
    print(f"  Converted:           {stats['converted']}")
    print(f"  Failed:              {stats['failed']}")
    print(f"  Validation failures: {stats['validation_failures']}")
    print(f"  Success rate:        {stats['success_rate']:.1f}%")
    print(f"  Valid rate:          {stats['valid_rate']:.1f}%")
    print(f"  Avg compression:     {stats['avg_compression_ratio']:.2f}x")
    print(f"  English tokens:      {stats['total_english_tokens']:,}")
    print(f"  RLang tokens:        {stats['total_rlang_tokens']:,}")
    if stats["failure_reasons"]:
        print()
        print("  Failure breakdown:")
        for reason, count in sorted(stats["failure_reasons"].items(), key=lambda x: -x[1]):
            print(f"    {reason:>25s}: {count}")
    print("=" * 60)


# ---------------------------------------------------------------------------
# Inline tests
# ---------------------------------------------------------------------------

def _test_sanitize():
    assert sanitize_identifier("the quick brown fox") == "quick_brown_fox"
    assert sanitize_identifier("123bad") == "v_123bad"
    assert sanitize_identifier("") == "x"
    assert sanitize_identifier("simple") == "simple"
    print("  [PASS] sanitize_identifier")


def _test_confidence():
    assert detect_confidence("This is definitely true") == 0.95
    assert detect_confidence("It probably works") == 0.80
    assert detect_confidence("It might be correct") == 0.60
    assert detect_confidence("This is unlikely") == 0.35
    assert detect_confidence("I'm not sure about this") == 0.50
    assert detect_confidence("The answer is 42") == DEFAULT_CONFIDENCE
    print("  [PASS] detect_confidence")


def _test_ep_mode():
    assert detect_ep_mode("I see that the value is 5") == "direct"
    assert detect_ep_mode("Therefore the result must be 10") == "infer"
    assert detect_ep_mode("This is similar to the previous problem") == "anl"
    assert detect_ep_mode("The value equals 5") == "infer"
    print("  [PASS] detect_ep_mode")


def _test_strip_waste():
    text = "Wait, let me reconsider. The answer is 5. Hmm, actually maybe not. It is 5."
    cleaned = strip_waste(text)
    assert "Wait" not in cleaned or "reconsider" not in cleaned
    assert "5" in cleaned
    print("  [PASS] strip_waste")


def _test_extract_statements():
    text = (
        "I notice the tests are passing. "
        "This causes the deployment to succeed. "
        "The lack of rollback prevents safe recovery. "
        "The goal is to deploy the fix."
    )
    stmts = extract_statements(text)
    ops = [s.operator for s in stmts]
    assert "obs" in ops, f"Expected obs in {ops}"
    assert "cause" in ops, f"Expected cause in {ops}"
    assert "prvnt" in ops, f"Expected prvnt in {ops}"
    assert "goal" in ops, f"Expected goal in {ops}"
    print("  [PASS] extract_statements")


def _test_full_conversion():
    english = (
        "Let me think about this carefully. "
        "I notice the tests are all passing with high confidence. "
        "Looking at the metrics, I see low traffic right now. "
        "I observe that the error rate spiked 3x in the last hour. "
        "Given that the fix addresses the root cause, I see it should work. "
        "Okay so the passing tests causes increased confidence in deployment. "
        "This enables us to proceed with the fix safely. "
        "However, the lack of a rollback plan prevents safe recovery if things go wrong. "
        "The staging environment enables us to test before production. "
        "Wait, actually, hmm, let me reconsider the risk here. "
        "The goal is to deploy the fix without causing downtime. "
        "The current traffic pattern is similar to last Tuesday's low-traffic window. "
        "Therefore, I think we should probably deploy but only with conditions. "
        "Alright, let me verify that the requirements hold. "
        "The deployment requires passing tests and a rollback strategy. "
        "The monitoring system requires real-time alerting. "
        "I think the deployment also requires approval from the on-call engineer. "
        "In conclusion, we should deploy with a hedge condition requiring rollback."
    )
    rlang, success = convert_trace(english)
    assert success, "Conversion should succeed"
    assert "#[phase(Frame)]" in rlang
    assert "#[phase(Explore)]" in rlang
    assert "#[phase(Verify)]" in rlang
    assert "#[phase(Decide)]" in rlang
    assert "obs(" in rlang
    assert "match conf(" in rlang
    assert "assert(" in rlang or "hedge(" in rlang

    english_tokens = estimate_tokens(english)
    rlang_tokens = estimate_tokens(rlang)
    compression = english_tokens / rlang_tokens if rlang_tokens > 0 else 0
    # Real traces will have much higher compression; short test traces
    # have fixed structural overhead so we check for > 0.5x minimum
    assert compression > 0.5, f"Expected compression > 0.5, got {compression:.2f}"
    print(f"  [PASS] full_conversion (compression: {compression:.2f}x, "
          f"en={english_tokens} rl={rlang_tokens})")


def _test_empty_trace():
    rlang, success = convert_trace("")
    assert not success
    rlang, success = convert_trace("   ")
    assert not success
    print("  [PASS] empty_trace handling")


def _test_phase_assignment():
    stmts = [
        ExtractedStatement("obs", ["tests_pass"], 0.99, "direct"),
        ExtractedStatement("obs", ["low_traffic"], 0.90, "direct"),
        ExtractedStatement("goal", ["self", "deploy"], 0.80, "infer"),
        ExtractedStatement("cause", ["tests", "confidence"], 0.85, "infer"),
        ExtractedStatement("enbl", ["fix", "deploy"], 0.75, "infer"),
        ExtractedStatement("prvnt", ["no_rollback", "recovery"], 0.60, "infer"),
        ExtractedStatement("req", ["deploy", "tests_pass"], 0.90, "infer"),
    ]
    trace = assign_phases(stmts)
    # obs statements should be in Frame
    frame_ops = [s.operator for s in trace.frame_statements]
    assert "obs" in frame_ops, f"Expected obs in Frame, got {frame_ops}"
    print("  [PASS] phase_assignment")


def run_tests():
    """Run all inline tests."""
    print("Running converter tests...\n")
    _test_sanitize()
    _test_confidence()
    _test_ep_mode()
    _test_strip_waste()
    _test_extract_statements()
    _test_phase_assignment()
    _test_full_conversion()
    _test_empty_trace()
    print("\nAll tests passed!")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Convert English reasoning traces to RLang"
    )
    parser.add_argument(
        "--input", type=Path, default=DEFAULT_INPUT,
        help="Input file (parquet or JSONL)",
    )
    parser.add_argument(
        "--output", type=Path, default=DEFAULT_OUTPUT,
        help="Output JSONL file",
    )
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Process only first N records",
    )
    parser.add_argument(
        "--no-validate", action="store_true",
        help="Skip cargo validation step",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Run inline tests instead of converting",
    )
    args = parser.parse_args()

    if args.test:
        run_tests()
        return

    if not args.input.exists():
        print(f"Error: Input file not found: {args.input}")
        print("Run dataset/download.py first to download the dataset,")
        print("or use --input to specify a JSONL file.")
        sys.exit(1)

    stats = run_batch(
        input_path=args.input,
        output_path=args.output,
        limit=args.limit,
        do_validate=not args.no_validate,
    )
    print_stats(stats)


if __name__ == "__main__":
    main()
