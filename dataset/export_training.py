#!/usr/bin/env python3
"""Export the final optimized RLang dataset in multiple training formats.

Reads rlang_optimized.jsonl and exports:
  1. Flat JSONL for general use
  2. ShareGPT format with system/user/assistant turns
  3. Paired input/thinking/output format
"""

import json
import sys
import uuid
from pathlib import Path

from tqdm import tqdm

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
DATA_DIR = SCRIPT_DIR / "data"
OUTPUT_DIR = SCRIPT_DIR / "output"

INPUT_PATH = DATA_DIR / "rlang_optimized.jsonl"
FLAT_PATH = OUTPUT_DIR / "rlang_training.jsonl"
SHAREGPT_PATH = OUTPUT_DIR / "rlang_training_sharegpt.jsonl"
PAIRS_PATH = OUTPUT_DIR / "rlang_training_pairs.jsonl"

# ---------------------------------------------------------------------------
# System prompt for ShareGPT format
# ---------------------------------------------------------------------------
RLANG_SYSTEM_PROMPT = """\
You are a reasoning assistant that thinks in RLang, a Rust-inspired structured \
reasoning language. When solving problems, you first produce an RLang trace that \
formalizes your reasoning into four phases:

1. **Frame** - Observe evidence and establish beliefs with confidence levels \
(using obs(), blf types, and epistemic metadata like p:, ep:, src:, scope:, t:).
2. **Explore** - Weigh evidence for and against hypotheses using sup()/wkn()/neut() \
evidence items, then resolve() to update beliefs.
3. **Verify** - Check requirements against observations using req() |> verify() \
pipe chains.
4. **Decide** - Match on confidence levels using conf() and emit final judgments \
with assert()/hedge()/suspend()/reject().

After the RLang trace, provide a clear English conclusion.\
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    """Estimate token count: word_count * 1.3."""
    if not text:
        return 0
    return int(len(text.split()) * 1.3)


def load_traces() -> list[dict]:
    """Load optimized traces from JSONL."""
    if not INPUT_PATH.exists():
        print(f"Error: Input file not found: {INPUT_PATH}")
        print("Run optimize_traces.py first to generate rlang_optimized.jsonl.")
        sys.exit(1)

    traces = []
    with open(INPUT_PATH) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                traces.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  Warning: skipping malformed JSON on line {line_num}: {e}")

    return traces


# ---------------------------------------------------------------------------
# Export: Flat JSONL
# ---------------------------------------------------------------------------

def export_flat(traces: list[dict]) -> int:
    """Export flat JSONL format for general use.

    Each row contains all fields plus metadata.
    """
    count = 0
    with open(FLAT_PATH, "w") as f:
        for trace in tqdm(traces, desc="Exporting flat JSONL"):
            row = {
                "id": trace.get("id", str(uuid.uuid4())),
                "problem": trace.get("problem", ""),
                "thinking_english": trace.get("thinking_english", ""),
                "thinking_rlang": trace.get("thinking_rlang", ""),
                "solution": trace.get("solution", ""),
                "domain": trace.get("domain", "unknown"),
                "difficulty": trace.get("difficulty", "medium"),
                "source": trace.get("source", ""),
                "english_tokens_est": trace.get(
                    "thinking_tokens_est",
                    estimate_tokens(trace.get("thinking_english", "")),
                ),
                "rlang_tokens_est": trace.get(
                    "rlang_tokens_est",
                    estimate_tokens(trace.get("thinking_rlang", "")),
                ),
                "compression_ratio": trace.get("compression_ratio", 0.0),
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# ---------------------------------------------------------------------------
# Export: ShareGPT
# ---------------------------------------------------------------------------

def export_sharegpt(traces: list[dict]) -> int:
    """Export ShareGPT format with system prompt, user message, and assistant response.

    The assistant response includes <think> RLang trace </think> followed by
    an English conclusion.
    """
    count = 0
    with open(SHAREGPT_PATH, "w") as f:
        for trace in tqdm(traces, desc="Exporting ShareGPT"):
            problem = trace.get("problem", "")
            rlang_trace = trace.get("thinking_rlang", "")
            solution = trace.get("solution", "")

            if not problem or not rlang_trace:
                continue

            # Build assistant response with <think> block
            assistant_content = f"<think>\n{rlang_trace}\n</think>\n\n{solution}"

            row = {
                "id": trace.get("id", str(uuid.uuid4())),
                "conversations": [
                    {"from": "system", "value": RLANG_SYSTEM_PROMPT},
                    {"from": "human", "value": problem},
                    {"from": "gpt", "value": assistant_content},
                ],
                "metadata": {
                    "domain": trace.get("domain", "unknown"),
                    "difficulty": trace.get("difficulty", "medium"),
                    "source": trace.get("source", ""),
                    "compression_ratio": trace.get("compression_ratio", 0.0),
                    "rlang_tokens_est": trace.get(
                        "rlang_tokens_est",
                        estimate_tokens(rlang_trace),
                    ),
                },
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# ---------------------------------------------------------------------------
# Export: Paired format
# ---------------------------------------------------------------------------

def export_pairs(traces: list[dict]) -> int:
    """Export paired input/thinking/output format.

    Each row is: {input, thinking, output} plus metadata.
    """
    count = 0
    with open(PAIRS_PATH, "w") as f:
        for trace in tqdm(traces, desc="Exporting pairs"):
            problem = trace.get("problem", "")
            rlang_trace = trace.get("thinking_rlang", "")
            solution = trace.get("solution", "")

            if not problem or not rlang_trace:
                continue

            row = {
                "input": problem,
                "thinking": rlang_trace,
                "output": solution,
                "metadata": {
                    "id": trace.get("id", str(uuid.uuid4())),
                    "domain": trace.get("domain", "unknown"),
                    "difficulty": trace.get("difficulty", "medium"),
                    "source": trace.get("source", ""),
                    "compression_ratio": trace.get("compression_ratio", 0.0),
                    "english_tokens_est": trace.get(
                        "thinking_tokens_est",
                        estimate_tokens(trace.get("thinking_english", "")),
                    ),
                    "rlang_tokens_est": trace.get(
                        "rlang_tokens_est",
                        estimate_tokens(rlang_trace),
                    ),
                },
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            count += 1
    return count


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Loading optimized traces ...")
    traces = load_traces()
    total = len(traces)
    print(f"  Loaded {total} traces.\n")

    if total == 0:
        print("No traces to export.")
        sys.exit(0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Export all three formats
    flat_count = export_flat(traces)
    sharegpt_count = export_sharegpt(traces)
    pairs_count = export_pairs(traces)

    # Report
    print("\n" + "=" * 60)
    print("  EXPORT REPORT")
    print("=" * 60)
    print(f"  Input traces:    {total}")
    print()
    print(f"  Flat JSONL:      {flat_count} rows  -> {FLAT_PATH}")
    print(f"  ShareGPT:        {sharegpt_count} rows  -> {SHAREGPT_PATH}")
    print(f"  Pairs:           {pairs_count} rows  -> {PAIRS_PATH}")
    print()

    # Quick size report
    for path in [FLAT_PATH, SHAREGPT_PATH, PAIRS_PATH]:
        if path.exists():
            size_mb = path.stat().st_size / (1024 * 1024)
            print(f"  {path.name:<35s}  {size_mb:.2f} MB")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
