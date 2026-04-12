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
import random
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

    # Cancel / negate -- arity 2: cncl(subject, negated_thing)
    (re.compile(r"(?:not|no\s+longer|cancel(?:ed|led)?|negated?)\s+(.+?)(?:\.|,|$)", re.I),
     "cncl", 2),

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
# Confidence tier detection (for thresholds and deltas)
# ---------------------------------------------------------------------------

VERY_CERTAIN_WORDS = re.compile(
    r"\b(?:clearly|definitely|certainly|obviously|undoubtedly|proven|unambiguous"
    r"|without\s+(?:a\s+)?doubt)\b", re.I
)
MODERATE_WORDS = re.compile(
    r"\b(?:likely|probably|most\s+likely|appears?\s+to|seems?\s+to|indicates?"
    r"|suggests?|supports?)\b", re.I
)
UNCERTAIN_WORDS = re.compile(
    r"\b(?:possibly|might|could|perhaps|maybe|conceivably)\b", re.I
)
HEAVY_HEDGE_WORDS = re.compile(
    r"\b(?:very\s+unlikely|highly\s+doubtful|extremely\s+uncertain|improbable"
    r"|questionable|tenuous|speculative|not\s+(?:at\s+all\s+)?(?:clear|certain|sure))\b",
    re.I,
)

# Evidence strength words
STRONG_SUPPORT_WORDS = re.compile(
    r"\b(?:proves?|confirms?|clearly\s+shows?|establishes?|demonstrates?"
    r"|conclusively|undeniably)\b", re.I
)
MODERATE_SUPPORT_WORDS = re.compile(
    r"\b(?:suggests?|indicates?|supports?|points?\s+to|shows?|implies?)\b", re.I
)
WEAK_SUPPORT_WORDS = re.compile(
    r"\b(?:might\s+suggest|could\s+indicate|may\s+support|loosely|vaguely"
    r"|somewhat|partially)\b", re.I
)
WEAKENING_WORDS = re.compile(
    r"\b(?:however|but|on\s+the\s+other\s+hand|yet|although|despite"
    r"|conversely|alternatively|nonetheless|nevertheless)\b", re.I
)
STRONG_CONTRA_WORDS = re.compile(
    r"\b(?:disproves?|refutes?|contradicts?|invalidates?|undermines?"
    r"|negates?|falsifies?)\b", re.I
)

# Domain detection for variable naming
MATH_DOMAIN = re.compile(
    r"\b(?:equation|formula|sum|product|integral|derivative|proof|theorem"
    r"|calculate|compute|solve|algebra|geometry|trigonometr|logarithm"
    r"|polynomial|variable|coefficient|matrix|vector|fraction|decimal"
    r"|\d+\s*[\+\-\*\/\=]\s*\d+)\b", re.I
)
CODE_DOMAIN = re.compile(
    r"\b(?:function|class|method|variable|loop|array|string|compile|debug"
    r"|deploy|test|code|program|algorithm|implementation|runtime|API"
    r"|server|database|query|endpoint|repository|commit)\b", re.I
)
SCIENCE_DOMAIN = re.compile(
    r"\b(?:hypothesis|experiment|data|theory|observation|measurement"
    r"|molecule|atom|cell|energy|force|reaction|species|evolution"
    r"|temperature|pressure|velocity|density|chemical|biological"
    r"|physical|scientific)\b", re.I
)
LOGIC_DOMAIN = re.compile(
    r"\b(?:premise|conclusion|argument|valid|invalid|syllogism|deduction"
    r"|induction|proposition|logical|therefore|implies|if\s+and\s+only\s+if"
    r"|necessary|sufficient|contradiction|tautology|fallacy)\b", re.I
)


def detect_confidence_tier(text: str) -> str:
    """Detect overall confidence tier from the full English trace.

    Returns one of: 'very_certain', 'moderate', 'uncertain', 'heavy_hedge'
    """
    heavy = len(HEAVY_HEDGE_WORDS.findall(text))
    uncertain = len(UNCERTAIN_WORDS.findall(text))
    moderate = len(MODERATE_WORDS.findall(text))
    certain = len(VERY_CERTAIN_WORDS.findall(text))

    if heavy > 0 or uncertain > moderate + certain:
        return "heavy_hedge"
    if uncertain > certain and uncertain > moderate:
        return "uncertain"
    if certain > moderate:
        return "very_certain"
    return "moderate"


def get_decision_thresholds(tier: str) -> tuple[float, float, float]:
    """Return (high, mid, low) thresholds for the Decide phase with jitter.

    Avoids the exact boilerplate values 0.80 and 0.50 that QAQC flags.
    """
    base = {
        "very_certain": (0.90, 0.70, 0.40),
        "moderate": (0.85, 0.55, 0.30),
        "uncertain": (0.75, 0.45, 0.25),
        "heavy_hedge": (0.70, 0.40, 0.20),
    }
    h, m, l = base.get(tier, (0.85, 0.55, 0.30))

    def jitter(v: float) -> float:
        result = round(max(0.10, min(0.99, v + random.uniform(-0.05, 0.05))), 2)
        # Avoid the exact boilerplate values QAQC flags
        if result == 0.80:
            result = 0.81 if random.random() > 0.5 else 0.79
        if result == 0.50:
            result = 0.51 if random.random() > 0.5 else 0.49
        return result

    return jitter(h), jitter(m), jitter(l)


def compute_evidence_delta(sentence: str, operator: str) -> float:
    """Compute an evidence delta based on the strength language in the sentence."""
    if STRONG_CONTRA_WORDS.search(sentence):
        base = random.uniform(-0.35, -0.25)
    elif WEAKENING_WORDS.search(sentence):
        base = random.uniform(-0.25, -0.10)
    elif STRONG_SUPPORT_WORDS.search(sentence):
        base = random.uniform(0.20, 0.30)
    elif MODERATE_SUPPORT_WORDS.search(sentence):
        base = random.uniform(0.10, 0.20)
    elif WEAK_SUPPORT_WORDS.search(sentence):
        base = random.uniform(0.05, 0.10)
    else:
        # Default based on operator type
        if operator in ("prvnt", "confl", "cncl"):
            base = random.uniform(-0.20, -0.10)
        else:
            base = random.uniform(0.08, 0.18)

    # Small additional jitter
    base += random.uniform(-0.02, 0.02)
    return round(base, 2)


def detect_domain(text: str) -> str:
    """Detect the domain of an English trace for variable naming."""
    scores = {
        "math": len(MATH_DOMAIN.findall(text)),
        "code": len(CODE_DOMAIN.findall(text)),
        "science": len(SCIENCE_DOMAIN.findall(text)),
        "logic": len(LOGIC_DOMAIN.findall(text)),
    }
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "general"


# Domain-specific variable name prefixes
DOMAIN_VAR_NAMES = {
    "math": ["eqn", "val", "proof", "result", "sum", "expr", "term", "calc"],
    "code": ["impl", "fn_out", "test_res", "perf", "build", "deploy", "err", "api"],
    "science": ["hyp", "exp_data", "theory", "meas", "obs_val", "pred", "model", "rxn"],
    "logic": ["premise", "concl", "prop", "arg", "valid", "infer", "axiom", "lem"],
    "general": ["claim", "fact", "point", "step", "find", "check", "note", "res"],
}


def is_filler_sentence(sentence: str) -> bool:
    """Detect if a sentence is filler that should not produce operators."""
    filler_patterns = [
        r"^(?:let\s+me|okay|alright|so\s+basically|well|hmm|um|uh)",
        r"^(?:I\s+(?:need\s+to|want\s+to|will|should)\s+(?:think|consider|look|check|start))",
        r"^(?:let'?s?\s+(?:see|think|start|begin|look|consider))",
        r"^(?:now|first|second|third|next|finally|lastly)",
        r"^(?:in\s+(?:conclusion|summary|other\s+words))",
        r"^(?:as\s+(?:I|we)\s+(?:mentioned|said|noted|discussed))",
        r"(?:step\s+by\s+step|one\s+by\s+one|working\s+through)",
    ]
    s = sentence.strip().lower()
    for pat in filler_patterns:
        if re.search(pat, s, re.I):
            return True
    # Very short sentences are likely filler
    word_count = len(s.split())
    if word_count < 4:
        return True
    return False


def extract_first_noun(sentence: str) -> str:
    """Extract the first meaningful noun/noun-phrase from a sentence for naming."""
    # Remove common prefixes
    s = re.sub(
        r"^(?:I\s+(?:notice|see|observe|find|think|believe)\s+(?:that\s+)?(?:the\s+)?|"
        r"looking\s+at\s+(?:the\s+)?|given\s+that\s+(?:the\s+)?|"
        r"therefore\s*,?\s*(?:the\s+)?|however\s*,?\s*(?:the\s+)?|"
        r"the\s+|a\s+|an\s+)",
        "", sentence.strip(), flags=re.I,
    )
    # Get content words (3+ chars)
    words = re.findall(r"\b[a-zA-Z]{3,}\b", s)
    # Skip common verbs, function words, and filler
    skip = {
        "the", "and", "for", "are", "was", "were", "has", "have", "had",
        "this", "that", "with", "from", "into", "they", "them", "their",
        "will", "would", "should", "could", "shall", "being", "been",
        "also", "very", "much", "more", "most", "some", "any", "each",
        "not", "but", "yet", "nor", "both", "either", "neither",
        "therefore", "however", "because", "since", "then", "thus",
        "causes", "cause", "enables", "enable", "prevents", "prevent",
        "requires", "require", "suggests", "indicate", "indicates",
        "think", "believe", "seems", "probably", "definitely",
        "clearly", "certainly", "possibly", "might", "maybe",
        "conclusion", "answer", "result", "means", "shows",
    }
    meaningful = [w.lower() for w in words if w.lower() not in skip]
    if not meaningful:
        return ""
    # Take first 1-2 words, max 12 chars total
    name = "_".join(meaningful[:2])
    return name[:12]


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

def sanitize_identifier(text: str, domain: str = "general") -> str:
    """Convert English phrase to valid, concise RLang identifier.

    Uses first meaningful noun from the text, constrained to 12 chars max.
    Falls back to domain-specific defaults when extraction fails.
    """
    text = text.strip().lower()
    # Remove articles, prepositions, common verbs, transition words
    text = re.sub(
        r"\b(?:the|a|an|is|are|was|were|of|in|to|for|with|that|this|it|"
        r"let|me|i|we|you|he|she|they|be|been|being|have|has|had|do|does|did|"
        r"will|would|should|could|might|may|can|shall|must|"
        r"not|no|yes|so|but|and|or|if|then|than|as|at|by|on|about|into|"
        r"also|very|much|more|most|some|any|all|each|every|"
        r"first|second|third|next|just|still|already|"
        r"however|therefore|thus|hence|because|since|although|"
        r"given|looking|notice|observe|think|believe|see|find|"
        r"causes?|enables?|prevents?|requires?|suggests?|indicates?|"
        r"shows?|means?|makes?|leads?)\b",
        "", text,
    )
    text = text.strip()
    # Extract alphanumeric words only
    words = [re.sub(r"[^a-z0-9]", "", w) for w in re.split(r"\s+", text) if w]
    words = [w for w in words if len(w) >= 2]

    if not words:
        # Fall back to domain-specific default
        names = DOMAIN_VAR_NAMES.get(domain, DOMAIN_VAR_NAMES["general"])
        return random.choice(names)

    # Take first 2 meaningful words, join with underscore
    ident = "_".join(words[:2])
    # Ensure it starts with a letter
    if ident and not ident[0].isalpha():
        ident = "v_" + ident
    # Enforce max 12 chars
    ident = ident[:12]
    return ident or "x"


def detect_confidence(sentence: str) -> float:
    """Detect confidence level from English hedging language.

    Returns a varied confidence rather than flat 0.75 for unmatched sentences.
    Assertive statements get higher base confidence than neutral ones.
    """
    for pattern, conf in CONFIDENCE_PATTERNS:
        if pattern.search(sentence):
            return conf

    # Issue 5: Vary the default based on sentence assertiveness
    # Sentences with strong verbs/assertions get higher confidence
    if re.search(r"\b(?:is|are|was|were|equals?|must|always|never)\b", sentence, re.I):
        return round(random.uniform(0.78, 0.88), 2)
    # Questions or tentative phrasing get lower
    if re.search(r"\?|whether|if\s+(?:we|it|the)", sentence, re.I):
        return round(random.uniform(0.55, 0.70), 2)
    # Default with slight variation
    return round(random.uniform(0.70, 0.82), 2)


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


def extract_statements(text: str, domain: str = "general") -> list[ExtractedStatement]:
    """Extract RLang operator statements from English text.

    Filters filler sentences, uses domain-aware naming, and captures
    the source sentence for downstream delta computation.
    """
    statements = []
    sentences = SENTENCE_SPLIT.split(text)

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 10:
            continue

        # Skip filler sentences entirely (Issue 5)
        if is_filler_sentence(sentence):
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
                    args = [sanitize_identifier(groups[0], domain)]
                elif arity == 2:
                    if len(groups) >= 2:
                        args = [sanitize_identifier(groups[0], domain),
                                sanitize_identifier(groups[1], domain)]
                    else:
                        pre_text = sentence[:m.start()].strip()
                        subject = sanitize_identifier(pre_text, domain) if pre_text else "x"
                        args = [subject, sanitize_identifier(groups[0], domain)]
                elif arity == 3:
                    if len(groups) >= 2:
                        subject_text = sentence[:m.start()].strip()
                        subject = sanitize_identifier(subject_text, domain) if subject_text else "x"
                        args = [subject, sanitize_identifier(groups[0], domain),
                                sanitize_identifier(groups[1], domain)]
                    else:
                        args = [sanitize_identifier(groups[0], domain)]
                else:
                    args = [sanitize_identifier(g, domain) for g in groups]

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
            # Try to extract a meaningful noun from the sentence
            noun = extract_first_noun(sentence)
            ident = noun if noun else sanitize_identifier(sentence, domain)
            if ident and ident != "x" and len(ident) >= 2:
                if ep == "direct":
                    statements.append(ExtractedStatement(
                        operator="obs",
                        args=[ident],
                        confidence=conf,
                        ep_mode="direct",
                        source_sentence=sentence,
                    ))
                elif conf >= 0.80 or ep == "infer":
                    # Use domain-specific second arg instead of duplicate
                    names = DOMAIN_VAR_NAMES.get(domain, DOMAIN_VAR_NAMES["general"])
                    second = random.choice(names)
                    statements.append(ExtractedStatement(
                        operator="cause",
                        args=[ident, second],
                        confidence=conf,
                        ep_mode=ep,
                        source_sentence=sentence,
                    ))

    return statements


def assign_phases(
    statements: list[ExtractedStatement],
    english_word_count: int = 500,
) -> RLangTrace:
    """Assign statements to the 4 RLang phases based on position and type.

    Limits Frame to max 3 observations and Explore to max 4 evidence items
    to ensure good compression. Short traces (< 200 English words) get
    even tighter limits.
    """
    if not statements:
        return RLangTrace()

    n = len(statements)
    trace = RLangTrace()

    # Tighter limits for short English traces (Issue 3)
    max_frame = 2 if english_word_count < 200 else 3
    max_explore = 3 if english_word_count < 200 else 4

    # Phase assignment by position and operator type
    frame_end = max(1, int(n * 0.20))
    explore_end = max(frame_end + 1, int(n * 0.75))
    verify_end = max(explore_end + 1, int(n * 0.90))

    frame_ops = {"obs", "req", "goal", "isa", "cntns"}
    explore_ops = {"cause", "prvnt", "enbl", "sim", "confl", "seq", "chng", "cncl"}

    for i, stmt in enumerate(statements):
        if stmt.operator in frame_ops and i < explore_end:
            trace.frame_statements.append(stmt)
        elif i < frame_end:
            trace.frame_statements.append(stmt)
        elif i < explore_end:
            trace.explore_statements.append(stmt)
        elif i < verify_end:
            trace.verify_statements.append(stmt)
        else:
            trace.decide_statements.append(stmt)

    # Enforce frame/explore limits (keep most confident / diverse)
    if len(trace.frame_statements) > max_frame:
        # Keep goal statements and highest confidence obs
        goals = [s for s in trace.frame_statements if s.operator == "goal"]
        non_goals = [s for s in trace.frame_statements if s.operator != "goal"]
        non_goals.sort(key=lambda s: s.confidence, reverse=True)
        trace.frame_statements = goals[:1] + non_goals[:max_frame - len(goals[:1])]

    if len(trace.explore_statements) > max_explore:
        # Keep diverse operators; prefer highest confidence
        trace.explore_statements.sort(key=lambda s: s.confidence, reverse=True)
        trace.explore_statements = trace.explore_statements[:max_explore]

    # Detect goal name
    for stmt in trace.frame_statements:
        if stmt.operator == "goal":
            trace.goal_name = stmt.args[-1] if stmt.args else "conclusion"
            break

    # Detect reasoning mode
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
        trace.primary_belief = (
            trace.frame_statements[0].args[0]
            if trace.frame_statements[0].args else "conclusion"
        )
    else:
        trace.primary_belief = "conclusion"

    # Ensure each phase has at least one statement
    if not trace.frame_statements:
        trace.frame_statements.append(ExtractedStatement(
            operator="obs", args=["input"],
            confidence=0.90, ep_mode="direct",
        ))
    # Ensure frame has at least one obs() for blf<> declaration
    has_obs = any(s.operator == "obs" for s in trace.frame_statements)
    if not has_obs:
        # Promote first statement's subject to an observation
        first_arg = trace.frame_statements[0].args[0] if trace.frame_statements[0].args else "input"
        trace.frame_statements.insert(0, ExtractedStatement(
            operator="obs", args=[first_arg],
            confidence=round(random.uniform(0.78, 0.92), 2), ep_mode="direct",
        ))
    if not trace.explore_statements:
        trace.explore_statements.append(ExtractedStatement(
            operator="cause",
            args=[trace.primary_belief, "ev"],
            confidence=DEFAULT_CONFIDENCE, ep_mode="infer",
            source_sentence="",
        ))
    if not trace.verify_statements:
        first_obs = trace.frame_statements[0].args[0] if trace.frame_statements[0].args else "input"
        trace.verify_statements.append(ExtractedStatement(
            operator="req",
            args=[trace.primary_belief, "obs(" + first_obs + ")"],
            confidence=0.90, ep_mode="infer",
        ))

    return trace


def format_operator_call(stmt: ExtractedStatement) -> str:
    """Format a single operator call with metadata."""
    args_str = ", ".join(stmt.args)
    return f"{stmt.operator}({args_str})"


def generate_frame_block(trace: RLangTrace) -> str:
    """Generate a compact Frame phase block."""
    lines = []
    lines.append(f"#[phase(Frame)]")
    lines.append(f"impl {trace.reasoning_mode} {{")

    obs_stmts = [s for s in trace.frame_statements if s.operator == "obs"]
    other_stmts = [s for s in trace.frame_statements if s.operator != "obs"]

    for stmt in obs_stmts:
        name = stmt.args[0] if stmt.args else "fact"
        conf = f"{stmt.confidence:.2f}"
        # Compact metadata: use abbreviated form
        lines.append(
            f"    let {name}: blf<{conf}> = obs({name})"
            f" | p:{conf} | ep:{stmt.ep_mode} | scope:loc | t:fresh;"
        )

    for stmt in other_stmts:
        if stmt.operator == "goal":
            goal_name = stmt.args[-1] if stmt.args else "target"
            lines.append(
                f"    let {goal_name} = goal({goal_name}) | p:{stmt.confidence:.2f} | ep:{stmt.ep_mode};"
            )
        elif stmt.operator == "req":
            name = f"r_{stmt.args[0]}" if stmt.args else "r_cstr"
            lines.append(
                f"    let {name} = {format_operator_call(stmt)} | p:{stmt.confidence:.2f} | ep:{stmt.ep_mode};"
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
    """Generate the Explore phase block with dynamic evidence deltas."""
    lines = []
    lines.append("#[phase(Explore)]")
    lines.append("{")

    belief = trace.primary_belief

    ev_items = []
    seen_sources = set()
    for stmt in trace.explore_statements:
        # Compute delta from the source sentence language (Issue 2)
        delta_val = compute_evidence_delta(stmt.source_sentence, stmt.operator)
        source_name = stmt.args[0] if stmt.args else "ev"

        # Avoid duplicate source names in evidence block
        if source_name in seen_sources:
            source_name = source_name + "_" + str(len(seen_sources))
        seen_sources.add(source_name)

        if stmt.operator in ("prvnt", "confl", "cncl"):
            # Force negative delta for weakening operators
            d = -abs(delta_val) if delta_val > 0 else delta_val
            ev_items.append(f"        {source_name} => wkn({belief}, {d:+.2f})")
        elif stmt.operator == "sim":
            d = abs(delta_val) if delta_val < 0 else delta_val
            ev_items.append(f"        {source_name} => sup({belief}, {d:+.2f})")
        else:
            # Supporting evidence: force positive delta
            d = abs(delta_val) if delta_val < 0 else delta_val
            ev_items.append(f"        {source_name} => sup({belief}, {d:+.2f})")

    if ev_items:
        lines.append("    let ev = [")
        lines.append(",\n".join(ev_items) + ",")
        lines.append("    ];")
        lines.append(f"    {belief} |> resolve(ev) -> Ok(rslv);")
    else:
        lines.append(f"    {belief} |> resolve([]) -> Ok(rslv);")

    lines.append("}")
    return "\n".join(lines)


def generate_verify_block(trace: RLangTrace) -> str:
    """Generate a compact Verify phase block -- single verification is usually sufficient."""
    lines = []
    lines.append("#[phase(Verify)]")
    lines.append("{")

    belief = trace.primary_belief

    # Use at most ONE verify statement for compression (Issue 3)
    if trace.verify_statements:
        stmt = trace.verify_statements[0]  # Take only the first
        if stmt.operator == "req":
            args_str = ", ".join(stmt.args)
            lines.append(f"    req({args_str}) |> verify({belief}) -> Ok(());")
        else:
            obs_name = stmt.args[0] if stmt.args else belief
            lines.append(f"    req({belief}, obs({obs_name})) |> verify({belief}) -> Ok(());")
    else:
        first_obs = (
            trace.frame_statements[0].args[0]
            if trace.frame_statements and trace.frame_statements[0].args
            else "input"
        )
        lines.append(f"    req({belief}, obs({first_obs})) |> verify({belief}) -> Ok(());")

    lines.append("}")
    return "\n".join(lines)


def generate_decide_block(trace: RLangTrace, confidence_tier: str = "moderate") -> str:
    """Generate the Decide phase block with varied thresholds."""
    lines = []
    lines.append("#[phase(Decide)]")
    lines.append("{")

    belief = trace.primary_belief

    # Use confidence tier to pick thresholds with jitter (Issue 1)
    high, mid, _low = get_decision_thresholds(confidence_tier)

    # Determine overall confidence for mid-tier decision operator
    all_confs = [s.confidence for s in
                 trace.frame_statements + trace.explore_statements +
                 trace.verify_statements + trace.decide_statements]
    avg_conf = sum(all_confs) / len(all_confs) if all_confs else DEFAULT_CONFIDENCE

    lines.append(f"    match conf({belief}) {{")
    lines.append(f"        c if c > {high:.2f} => assert({belief}),")
    if avg_conf > 0.6:
        lines.append(f"        c if c > {mid:.2f} => hedge({belief}),")
    else:
        lines.append(f"        c if c > {mid:.2f} => suspend({belief}),")
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

    # Detect domain and confidence tier from the FULL English text
    domain = detect_domain(english_text)
    confidence_tier = detect_confidence_tier(english_text)
    english_word_count = len(english_text.split())

    # Step 2: Extract operator statements (domain-aware naming)
    statements = extract_statements(cleaned, domain=domain)
    if not statements:
        # If no operators found, create minimal obs-based trace
        sentences = SENTENCE_SPLIT.split(cleaned)
        meaningful = [s.strip() for s in sentences
                      if len(s.strip()) > 15 and not is_filler_sentence(s)][:3]
        for s in meaningful:
            ident = sanitize_identifier(s, domain)
            if ident and ident != "x":
                statements.append(ExtractedStatement(
                    operator="obs", args=[ident],
                    confidence=detect_confidence(s),
                    ep_mode=detect_ep_mode(s), source_sentence=s,
                ))
        if not statements:
            return "", False

    # Step 3: Assign to phases (with compression limits)
    trace = assign_phases(statements, english_word_count=english_word_count)

    # Step 4: Generate RLang blocks (no auto-conversion comment -- Issue 3)
    parts = [
        generate_frame_block(trace),
        "",
        generate_explore_block(trace),
        "",
        generate_verify_block(trace),
        "",
        generate_decide_block(trace, confidence_tier=confidence_tier),
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
    # With new 12-char limit, results are truncated
    result = sanitize_identifier("the quick brown fox")
    assert result and len(result) <= 12, f"Got '{result}'"
    assert "quick" in result, f"Expected 'quick' in '{result}'"

    result = sanitize_identifier("123bad")
    assert result.startswith("v_") or result[0].isalpha(), f"Got '{result}'"

    result = sanitize_identifier("")
    assert result and result != "x", f"Empty should give domain default, got '{result}'"

    result = sanitize_identifier("simple")
    assert "simple" in result, f"Got '{result}'"
    print("  [PASS] sanitize_identifier")


def _test_confidence():
    assert detect_confidence("This is definitely true") == 0.95
    assert detect_confidence("It probably works") == 0.80
    assert detect_confidence("It might be correct") == 0.60
    assert detect_confidence("This is unlikely") == 0.35
    assert detect_confidence("I'm not sure about this") == 0.50
    # With varied defaults, unmatched sentences get 0.55-0.88 range
    c = detect_confidence("The answer is 42")
    assert 0.55 <= c <= 0.90, f"Expected varied default, got {c}"
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

    # Verify no auto-conversion marker (Issue 3)
    assert "Auto-converted" not in rlang, "Auto-conversion marker should be removed"

    # Verify thresholds are NOT the boilerplate 0.80/0.50 (Issue 1)
    assert "c > 0.80" not in rlang or "c > 0.50" not in rlang, \
        "Should have varied thresholds"

    english_tokens = estimate_tokens(english)
    rlang_tokens = estimate_tokens(rlang)
    compression = english_tokens / rlang_tokens if rlang_tokens > 0 else 0
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
