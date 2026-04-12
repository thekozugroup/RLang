"""Download and standardize Opus 4.6 Reasoning + Harmonic Reasoning datasets."""

import json
import os
from collections import Counter
from pathlib import Path

import pandas as pd
from datasets import load_dataset
from tqdm import tqdm

# Output directory
DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# Domain normalization mapping
DOMAIN_MAP = {
    "math": "math",
    "mathematics": "math",
    "algebra": "math",
    "geometry": "math",
    "calculus": "math",
    "number_theory": "math",
    "combinatorics": "math",
    "probability": "math",
    "statistics": "math",
    "code": "code",
    "coding": "code",
    "programming": "code",
    "computer_science": "code",
    "algorithms": "code",
    "science": "science",
    "physics": "science",
    "chemistry": "science",
    "biology": "science",
    "logic": "logic",
    "logical_reasoning": "logic",
    "reasoning": "reasoning",
    "general": "reasoning",
    "puzzle": "reasoning",
    "riddle": "reasoning",
    "critical_thinking": "reasoning",
}

# Difficulty normalization
DIFFICULTY_MAP = {
    "easy": "easy",
    "simple": "easy",
    "basic": "easy",
    "medium": "medium",
    "moderate": "medium",
    "intermediate": "medium",
    "hard": "hard",
    "difficult": "hard",
    "advanced": "hard",
    "challenging": "hard",
    "phd": "phd",
    "expert": "phd",
    "research": "phd",
}


def normalize_domain(domain: str | None) -> str:
    """Normalize domain to one of: math, code, science, logic, reasoning."""
    if not domain:
        return "reasoning"
    key = domain.lower().strip().replace(" ", "_")
    return DOMAIN_MAP.get(key, "reasoning")


def normalize_difficulty(difficulty: str | None) -> str:
    """Normalize difficulty to one of: easy, medium, hard, phd."""
    if not difficulty:
        return "medium"
    key = difficulty.lower().strip().replace(" ", "_")
    return DIFFICULTY_MAP.get(key, "medium")


def estimate_tokens(text: str | None) -> int:
    """Estimate token count: word_count * 1.3."""
    if not text:
        return 0
    word_count = len(text.split())
    return int(word_count * 1.3)


def process_opus(ds) -> list[dict]:
    """Process Opus 4.6 Reasoning dataset into standardized format."""
    records = []
    for i, row in enumerate(tqdm(ds, desc="Processing Opus 4.6 Reasoning")):
        record = {
            "id": f"opus_{row.get('id', i)}",
            "source": "opus-4.6-reasoning",
            "problem": row.get("problem", ""),
            "thinking_english": row.get("thinking", ""),
            "solution": row.get("solution", ""),
            "domain": normalize_domain(row.get("category")),
            "category": row.get("category", ""),
            "difficulty": normalize_difficulty(row.get("difficulty")),
            "thinking_tokens_est": estimate_tokens(row.get("thinking", "")),
            "metadata": json.dumps({
                "timestamp": row.get("timestamp", ""),
                "hash": row.get("hash", ""),
                "original_difficulty": row.get("difficulty", ""),
                "original_category": row.get("category", ""),
            }),
        }
        records.append(record)
    return records


def process_harmonic(ds) -> list[dict]:
    """Process Harmonic Reasoning dataset into standardized format."""
    records = []
    for i, row in enumerate(tqdm(ds, desc="Processing Harmonic Reasoning")):
        record = {
            "id": f"harmonic_{row.get('id', i)}",
            "source": "harmonic-reasoning-v1",
            "problem": row.get("problem", ""),
            "thinking_english": row.get("thinking", ""),
            "solution": row.get("solution", ""),
            "domain": normalize_domain(row.get("domain")),
            "category": row.get("category", ""),
            "difficulty": normalize_difficulty(row.get("difficulty")),
            "thinking_tokens_est": estimate_tokens(row.get("thinking", "")),
            "metadata": json.dumps({
                "signal_score": row.get("signal_score"),
                "reasoning_style": row.get("reasoning_style", ""),
                "thinking_depth": row.get("thinking_depth"),
                "thinking_words": row.get("thinking_words"),
                "self_corrections": row.get("self_corrections"),
                "verifications": row.get("verifications"),
                "explorations": row.get("explorations"),
                "coherence": row.get("coherence"),
                "original_domain": row.get("domain", ""),
                "original_difficulty": row.get("difficulty", ""),
                "conversations": row.get("conversations", ""),
            }),
        }
        records.append(record)
    return records


def print_summary(df: pd.DataFrame, name: str) -> None:
    """Print summary statistics for a dataframe."""
    print(f"\n{'=' * 60}")
    print(f"  {name}")
    print(f"{'=' * 60}")
    print(f"  Total rows: {len(df)}")
    print(f"  Avg thinking length (chars): {df['thinking_english'].str.len().mean():.0f}")
    print(f"  Avg thinking tokens (est): {df['thinking_tokens_est'].mean():.0f}")
    print(f"  Median thinking tokens (est): {df['thinking_tokens_est'].median():.0f}")
    print()
    print("  Domain distribution:")
    for domain, count in df["domain"].value_counts().items():
        pct = count / len(df) * 100
        print(f"    {domain:>12s}: {count:>5d} ({pct:5.1f}%)")
    print()
    print("  Difficulty distribution:")
    for diff, count in df["difficulty"].value_counts().items():
        pct = count / len(df) * 100
        print(f"    {diff:>12s}: {count:>5d} ({pct:5.1f}%)")


def main():
    print("Downloading Opus 4.6 Reasoning dataset...")
    opus_ds = load_dataset("Crownelius/Opus-4.6-Reasoning-3300x", split="train")
    print(f"  Downloaded {len(opus_ds)} rows")

    print("\nDownloading Harmonic Reasoning dataset...")
    harmonic_ds = load_dataset("DJLougen/harmonic-reasoning-v1", split="train")
    print(f"  Downloaded {len(harmonic_ds)} rows")

    # Process into standardized format
    opus_records = process_opus(opus_ds)
    harmonic_records = process_harmonic(harmonic_ds)

    # Create DataFrames
    opus_df = pd.DataFrame(opus_records)
    harmonic_df = pd.DataFrame(harmonic_records)
    combined_df = pd.concat([opus_df, harmonic_df], ignore_index=True)

    # Save parquet files
    opus_path = DATA_DIR / "opus_standardized.parquet"
    harmonic_path = DATA_DIR / "harmonic_standardized.parquet"
    combined_path = DATA_DIR / "standardized.parquet"

    opus_df.to_parquet(opus_path, index=False)
    print(f"\nSaved: {opus_path} ({len(opus_df)} rows)")

    harmonic_df.to_parquet(harmonic_path, index=False)
    print(f"Saved: {harmonic_path} ({len(harmonic_df)} rows)")

    combined_df.to_parquet(combined_path, index=False)
    print(f"Saved: {combined_path} ({len(combined_df)} rows)")

    # Print summaries
    print_summary(opus_df, "Opus 4.6 Reasoning")
    print_summary(harmonic_df, "Harmonic Reasoning v1")
    print_summary(combined_df, "Combined Dataset")


if __name__ == "__main__":
    main()
