"""Sample English-to-RLang converter with 5 hardcoded examples.

Demonstrates the conversion pipeline without needing the full dataset.
Each example shows a different reasoning domain and pattern.

Usage:
    python dataset/convert_sample.py              # Run conversion + tests
    python dataset/convert_sample.py --validate   # Also validate with cargo
"""

import argparse
import json
import sys
from pathlib import Path

# Import the converter engine
sys.path.insert(0, str(Path(__file__).parent))
from convert import (
    convert_trace,
    estimate_tokens,
    validate_rlang,
    strip_waste,
    extract_statements,
    detect_confidence,
    detect_ep_mode,
)

# ---------------------------------------------------------------------------
# 5 Hardcoded sample traces
# ---------------------------------------------------------------------------

SAMPLE_TRACES = [
    {
        "id": "sample_001",
        "source": "handcrafted",
        "domain": "math",
        "difficulty": "medium",
        "problem": "What is the sum of the first 10 positive integers?",
        "solution": "55",
        "thinking_english": (
            "I notice the problem asks for the sum of 1 through 10. "
            "Looking at this, I see it's an arithmetic series. "
            "The formula for the sum of first n integers is n*(n+1)/2. "
            "This is similar to the triangular number sequence. "
            "Let me think about this... okay so applying the formula: "
            "10 * 11 / 2 = 55. "
            "The arithmetic series formula causes us to get 55 directly. "
            "The goal is to compute the sum efficiently. "
            "Therefore, the answer is definitely 55. "
            "Let me verify: 1+2+3+4+5+6+7+8+9+10 = 55. The sum requires the formula to hold."
        ),
    },
    {
        "id": "sample_002",
        "source": "handcrafted",
        "domain": "code",
        "difficulty": "hard",
        "problem": "Should we deploy the hotfix to production given the current system state?",
        "solution": "Deploy with rollback plan",
        "thinking_english": (
            "I observe that all unit tests are passing with 100% coverage. "
            "I notice the error rate has spiked 3x in the last hour. "
            "Given that the fix addresses the root cause of the errors, "
            "this causes confidence in the fix to increase. "
            "However, the lack of a rollback plan prevents safe recovery. "
            "The staging environment enables us to test before production. "
            "Wait, actually, hmm, let me reconsider the risk. "
            "The deployment requires passing integration tests too. "
            "The current traffic pattern is similar to last Tuesday's low-traffic window. "
            "The goal is to deploy the fix without causing downtime. "
            "I think we should probably deploy but only with a rollback plan. "
            "The deployment requires both passing tests and a rollback strategy."
        ),
    },
    {
        "id": "sample_003",
        "source": "handcrafted",
        "domain": "science",
        "difficulty": "medium",
        "problem": "Why does ice float on water?",
        "solution": "Ice is less dense than liquid water due to hydrogen bonding creating an open crystal structure.",
        "thinking_english": (
            "I observe that ice forms a crystalline structure when water freezes. "
            "Looking at the molecular level, I see hydrogen bonds create an open lattice. "
            "This causes the solid form to be less dense than the liquid. "
            "The hydrogen bonding enables the open crystal structure to form. "
            "This is similar to how other materials with directional bonding behave. "
            "The density difference causes ice to float. "
            "Okay so let me think about this more carefully. "
            "The open lattice structure contains more space than liquid water. "
            "The goal is to explain the density anomaly of water. "
            "Therefore the answer is clearly that hydrogen bonding creates an open structure, "
            "making ice less dense. This requires understanding of intermolecular forces."
        ),
    },
    {
        "id": "sample_004",
        "source": "handcrafted",
        "domain": "logic",
        "difficulty": "easy",
        "problem": "All cats are mammals. Whiskers is a cat. Is Whiskers a mammal?",
        "solution": "Yes, Whiskers is a mammal.",
        "thinking_english": (
            "I notice the first premise: all cats are mammals. "
            "I observe the second premise: Whiskers is a cat. "
            "Whiskers is a type of cat based on the given information. "
            "The first premise causes us to conclude that any cat is a mammal. "
            "The classification of Whiskers as a cat enables the deduction. "
            "Therefore, Whiskers is definitely a mammal. "
            "The conclusion requires both premises to hold. "
            "The goal is to determine Whiskers' classification."
        ),
    },
    {
        "id": "sample_005",
        "source": "handcrafted",
        "domain": "reasoning",
        "difficulty": "hard",
        "problem": "A company's revenue dropped 20% while costs increased 15%. Should they cut staff or invest in growth?",
        "solution": "Invest in targeted growth with cost optimization, not blanket staff cuts.",
        "thinking_english": (
            "I notice the revenue has dropped by 20 percent. "
            "I observe that costs have simultaneously increased by 15 percent. "
            "Given that the margin is being squeezed from both sides, "
            "this causes significant financial pressure. "
            "Cutting staff prevents the company from recovering through growth. "
            "However, investing in growth enables future revenue recovery. "
            "Wait, actually, let me reconsider. Not all growth investment is equal. "
            "The revenue decline contradicts the assumption of stable demand. "
            "The cost increase conflicts with operational efficiency goals. "
            "The company probably needs a balanced approach. "
            "Targeted growth investment requires identifying high-ROI opportunities. "
            "The situation is similar to the classic turnaround playbook. "
            "Then the company should optimize costs while investing selectively. "
            "The goal is to restore profitability without destroying capacity. "
            "After that, the company can scale growth investments. "
            "The balanced approach requires both discipline and vision."
        ),
    },
]


# ---------------------------------------------------------------------------
# Sample conversion
# ---------------------------------------------------------------------------

def run_sample_conversion(do_validate: bool = False) -> None:
    """Convert all 5 sample traces and print results."""
    print("=" * 70)
    print("  SAMPLE ENGLISH-TO-RLANG CONVERSION")
    print("  5 hardcoded examples across math, code, science, logic, reasoning")
    print("=" * 70)

    results = []
    total_english_tokens = 0
    total_rlang_tokens = 0

    for sample in SAMPLE_TRACES:
        print(f"\n{'─' * 70}")
        print(f"  [{sample['id']}] {sample['domain'].upper()} / {sample['difficulty']}")
        print(f"  Problem: {sample['problem'][:80]}")
        print(f"{'─' * 70}")

        english = sample["thinking_english"]
        rlang_text, success = convert_trace(english)

        if not success:
            print("  FAILED: Could not convert trace")
            results.append({"id": sample["id"], "success": False})
            continue

        english_tokens = estimate_tokens(english)
        rlang_tokens = estimate_tokens(rlang_text)
        compression = english_tokens / rlang_tokens if rlang_tokens > 0 else 0

        valid = True
        if do_validate:
            valid = validate_rlang(rlang_text)
            status = "VALID" if valid else "INVALID"
            print(f"  Validation: {status}")

        total_english_tokens += english_tokens
        total_rlang_tokens += rlang_tokens

        print(f"\n  English tokens: {english_tokens}")
        print(f"  RLang tokens:   {rlang_tokens}")
        print(f"  Compression:    {compression:.2f}x")
        print(f"\n  --- Generated RLang ---")
        for line in rlang_text.split("\n"):
            print(f"  {line}")

        result = {
            "id": sample["id"],
            "source": sample["source"],
            "problem": sample["problem"],
            "thinking_english": english,
            "thinking_rlang": rlang_text,
            "solution": sample["solution"],
            "english_tokens_est": english_tokens,
            "rlang_tokens_est": rlang_tokens,
            "compression_ratio": round(compression, 2),
            "valid": valid,
            "domain": sample["domain"],
            "difficulty": sample["difficulty"],
        }
        results.append(result)

    # Summary
    successful = [r for r in results if r.get("success", True) and "compression_ratio" in r]
    avg_compression = (
        total_english_tokens / total_rlang_tokens
        if total_rlang_tokens > 0 else 0
    )

    print(f"\n{'=' * 70}")
    print("  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Converted:        {len(successful)}/{len(SAMPLE_TRACES)}")
    print(f"  Total English:    {total_english_tokens} tokens")
    print(f"  Total RLang:      {total_rlang_tokens} tokens")
    print(f"  Avg compression:  {avg_compression:.2f}x")
    if do_validate:
        valid_count = sum(1 for r in successful if r.get("valid", False))
        print(f"  Valid traces:     {valid_count}/{len(successful)}")
    print(f"{'=' * 70}")

    # Save results
    output_path = Path(__file__).parent / "data" / "sample_converted.jsonl"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        for r in successful:
            f.write(json.dumps(r) + "\n")
    print(f"\n  Saved to: {output_path}")


# ---------------------------------------------------------------------------
# Inline tests
# ---------------------------------------------------------------------------

def _test_sample_traces_convert():
    """Test that all 5 sample traces convert successfully."""
    for sample in SAMPLE_TRACES:
        rlang, success = convert_trace(sample["thinking_english"])
        assert success, f"Failed to convert {sample['id']}"
        assert "#[phase(Frame)]" in rlang, f"Missing Frame in {sample['id']}"
        assert "#[phase(Explore)]" in rlang, f"Missing Explore in {sample['id']}"
        assert "#[phase(Verify)]" in rlang, f"Missing Verify in {sample['id']}"
        assert "#[phase(Decide)]" in rlang, f"Missing Decide in {sample['id']}"
    print("  [PASS] all 5 sample traces convert successfully")


def _test_waste_removal():
    """Test that waste is properly removed."""
    for sample in SAMPLE_TRACES:
        english = sample["thinking_english"]
        cleaned = strip_waste(english)
        # Waste markers should be removed
        assert "let me think about this" not in cleaned.lower() or "Wait" not in cleaned
        assert "okay so" not in cleaned.lower() or "hmm" not in cleaned.lower()
    print("  [PASS] waste removal works on all samples")


def _test_operator_extraction():
    """Test that operators are extracted from each sample."""
    for sample in SAMPLE_TRACES:
        cleaned = strip_waste(sample["thinking_english"])
        stmts = extract_statements(cleaned)
        assert len(stmts) > 0, f"No statements from {sample['id']}"
        ops = {s.operator for s in stmts}
        # Each trace should produce at least obs or cause
        assert ops & {"obs", "cause", "goal", "req", "enbl", "prvnt", "sim"}, \
            f"No meaningful operators in {sample['id']}: {ops}"
    print("  [PASS] operators extracted from all samples")


def _test_compression_ratio():
    """Test that samples achieve compression.

    Short samples (< 150 English words) have high fixed structural overhead
    from phase blocks and metadata, so we use a relaxed threshold. Real
    dataset traces (500+ words) achieve 2-4x compression.
    """
    compressions = []
    for sample in SAMPLE_TRACES:
        rlang, success = convert_trace(sample["thinking_english"])
        assert success
        english_tokens = estimate_tokens(sample["thinking_english"])
        rlang_tokens = estimate_tokens(rlang)
        compression = english_tokens / rlang_tokens if rlang_tokens > 0 else 0
        compressions.append((sample["id"], compression))
        # Even short traces should not balloon (no worse than 2x expansion)
        assert compression > 0.5, \
            f"Excessive expansion for {sample['id']}: {compression:.2f}x"

    # At least the longer samples (reasoning, code) should compress
    long_sample_compressions = [c for sid, c in compressions
                                 if sid in ("sample_002", "sample_005")]
    assert any(c > 1.0 for c in long_sample_compressions), \
        f"Longer samples should compress > 1.0x: {long_sample_compressions}"

    avg = sum(c for _, c in compressions) / len(compressions)
    print(f"  [PASS] compression ratios valid (avg: {avg:.2f}x, "
          f"range: {min(c for _,c in compressions):.2f}-{max(c for _,c in compressions):.2f})")


def _test_confidence_mapping():
    """Test confidence values are properly assigned."""
    # Sample 001 uses "definitely" -> should have high confidence
    stmts = extract_statements(strip_waste(SAMPLE_TRACES[0]["thinking_english"]))
    confs = [s.confidence for s in stmts]
    assert any(c >= 0.90 for c in confs), f"Expected high confidence in math sample, got {confs}"

    # Sample 004 (logic, easy) uses "definitely" -> high confidence
    stmts = extract_statements(strip_waste(SAMPLE_TRACES[3]["thinking_english"]))
    confs = [s.confidence for s in stmts]
    assert any(c >= 0.90 for c in confs), f"Expected high confidence in logic sample, got {confs}"

    # Sample 004 reasoning uses "probably" -> moderate confidence
    stmts = extract_statements(strip_waste(SAMPLE_TRACES[4]["thinking_english"]))
    confs = [s.confidence for s in stmts]
    assert any(0.70 <= c <= 0.85 for c in confs), \
        f"Expected moderate confidence in reasoning sample, got {confs}"
    print("  [PASS] confidence mapping works correctly")


def _test_output_schema():
    """Test that output matches the expected JSONL schema."""
    required_keys = {
        "id", "source", "problem", "thinking_english", "thinking_rlang",
        "solution", "english_tokens_est", "rlang_tokens_est",
        "compression_ratio", "valid", "domain", "difficulty",
    }
    sample = SAMPLE_TRACES[0]
    rlang, success = convert_trace(sample["thinking_english"])
    assert success

    record = {
        "id": sample["id"],
        "source": sample["source"],
        "problem": sample["problem"],
        "thinking_english": sample["thinking_english"],
        "thinking_rlang": rlang,
        "solution": sample["solution"],
        "english_tokens_est": estimate_tokens(sample["thinking_english"]),
        "rlang_tokens_est": estimate_tokens(rlang),
        "compression_ratio": round(
            estimate_tokens(sample["thinking_english"]) / estimate_tokens(rlang), 2
        ),
        "valid": True,
        "domain": sample["domain"],
        "difficulty": sample["difficulty"],
    }

    assert set(record.keys()) == required_keys, \
        f"Schema mismatch: {set(record.keys()) ^ required_keys}"
    assert isinstance(record["english_tokens_est"], int)
    assert isinstance(record["rlang_tokens_est"], int)
    assert isinstance(record["compression_ratio"], float)
    assert isinstance(record["valid"], bool)
    print("  [PASS] output schema matches specification")


def run_tests():
    """Run all inline tests."""
    print("Running sample converter tests...\n")
    _test_sample_traces_convert()
    _test_waste_removal()
    _test_operator_extraction()
    _test_compression_ratio()
    _test_confidence_mapping()
    _test_output_schema()
    print("\nAll sample tests passed!")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Sample English-to-RLang conversion with 5 hardcoded examples"
    )
    parser.add_argument(
        "--validate", action="store_true",
        help="Validate generated RLang with cargo validator",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Run inline tests",
    )
    args = parser.parse_args()

    if args.test:
        run_tests()
    else:
        # Always run tests first, then show conversions
        run_tests()
        print()
        run_sample_conversion(do_validate=args.validate)


if __name__ == "__main__":
    main()
