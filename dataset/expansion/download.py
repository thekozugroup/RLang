#!/usr/bin/env python3
"""
Download and standardize source datasets for RLang expansion.
Targets 5 priority datasets covering missing categories.
"""
import os
import json
import random
import pandas as pd
from pathlib import Path
from datasets import load_dataset

SEED = 42
random.seed(SEED)

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)

# Priority datasets: (hf_id, config, split, reasoning_col, prompt_col, category, sample_n)
SOURCES = [
    {
        "id": "nvidia/OpenCodeReasoning",
        "config": "split_0",
        "split": "split_0",           # actual split name IS the config
        "reasoning_col": "solution",
        "prompt_col": "question",
        "category": "code",
        "sample_n": 600,
        "quality": "xhigh",
    },
    {
        "id": "open-r1/Mixture-of-Thoughts",
        "config": "science",
        "split": "train",
        "reasoning_col": "messages",   # actual col: messages (conversation list)
        "prompt_col": "messages",      # extract from same field
        "category": "science",
        "sample_n": 400,
        "quality": "high",
    },
    {
        "id": "FreedomIntelligence/medical-o1-reasoning-SFT",
        "config": "en",
        "split": "train",
        "reasoning_col": "Complex_CoT",  # actual column name
        "prompt_col": "Question",        # actual column name
        "category": "medical",
        "sample_n": 300,
        "quality": "high",
    },
    {
        "id": "open-thoughts/OpenThoughts-114k",
        "config": "default",
        "split": "train",
        "reasoning_col": "conversations",
        "prompt_col": "conversations",
        "category": "logic",           # has logic/puzzle subset
        "sample_n": 300,
        "quality": "high",
    },
    {
        "id": "allenai/big-reasoning-traces",
        "config": "DeepSeek",          # required: DeepSeek or DeepSeek_debug
        "split": "train",
        "reasoning_col": "reasoning_trace",
        "prompt_col": "prompt",
        "category": "general",
        "sample_n": 400,
        "quality": "xhigh",
    },
]

def extract_text(value):
    """Extract plain text from various field formats."""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        # Conversation format: find assistant turn
        for msg in reversed(value):
            if isinstance(msg, dict):
                role = msg.get("role") or msg.get("from", "")
                if role in ("assistant", "gpt"):
                    return (msg.get("content") or msg.get("value") or "").strip()
        # Fallback: join all
        return " ".join(
            (m.get("content") or m.get("value") or "") if isinstance(m, dict) else str(m)
            for m in value
        ).strip()
    if isinstance(value, dict):
        return str(value.get("text") or value.get("content") or value).strip()
    return str(value).strip()

def download_source(source: dict) -> list[dict]:
    print(f"\n{'='*60}")
    print(f"Downloading: {source['id']} [{source['category']}]")

    # Use streaming to avoid downloading full dataset — much faster
    try:
        kwargs = dict(split=source["split"], streaming=True)
        if source["config"]:
            kwargs["name"] = source["config"]
        ds = load_dataset(source["id"], **kwargs)
    except Exception as e:
        print(f"  ERROR loading {source['id']}: {e}")
        return []

    # Peek at first row to discover column names
    first = None
    for row in ds:
        first = row
        break
    if first is None:
        print(f"  ERROR: empty dataset")
        return []

    cols = list(first.keys())
    print(f"  Columns: {cols}")

    # Resolve column names
    r_col = source["reasoning_col"]
    p_col = source["prompt_col"]
    if r_col not in cols:
        for alt in ["solution", "output", "thinking", "response", "answer",
                    "reasoning_trace", "generated_solution", "conversations", "text"]:
            if alt in cols:
                r_col = alt
                break
    if p_col not in cols:
        for alt in ["question", "problem", "input", "prompt", "instruction", "query"]:
            if alt in cols:
                p_col = alt
                break

    if r_col not in cols or p_col not in cols:
        print(f"  WARN: Could not resolve columns. r={r_col}, p={p_col}, have={cols}")
        return []

    print(f"  Using: prompt='{p_col}', reasoning='{r_col}'")

    # Stream sample_n rows with reservoir sampling (handles infinite/huge datasets)
    target = source["sample_n"]
    reservoir = []
    count = 0
    for row in ds:
        count += 1
        if len(reservoir) < target:
            reservoir.append(row)
        else:
            j = random.randint(0, count - 1)
            if j < target:
                reservoir[j] = row
        if count >= target * 5:  # scan 5x to get diversity, then stop
            break

    print(f"  Scanned {count} rows, reservoir {len(reservoir)}")

    rows = []
    for row in reservoir:
        # Special case: when prompt and reasoning share the same messages column
        if p_col == r_col and p_col in ("messages", "conversations"):
            msgs = row.get(p_col, [])
            prompt = ""
            reasoning = ""
            for m in msgs if isinstance(msgs, list) else []:
                role = (m.get("role") or m.get("from") or "").lower()
                content = (m.get("content") or m.get("value") or "")
                if isinstance(content, list):
                    content = " ".join(c.get("text", "") for c in content if isinstance(c, dict))
                if role == "user" and not prompt:
                    prompt = content.strip()
                elif role in ("assistant", "gpt") and not reasoning:
                    reasoning = content.strip()
        else:
            prompt = extract_text(row.get(p_col, ""))
            reasoning = extract_text(row.get(r_col, ""))

        if not prompt or not reasoning or len(reasoning) < 200:
            continue
        rows.append({
            "source": source["id"],
            "category": source["category"],
            "quality": source["quality"],
            "prompt": prompt,
            "english_reasoning": reasoning,
            "rlang_trace": None,
        })

    print(f"  Collected {len(rows)} usable rows")
    return rows

def main():
    all_rows = []
    for source in SOURCES:
        rows = download_source(source)
        all_rows.extend(rows)
        # Save per-category
        cat_file = DATA_DIR / f"{source['category']}_raw.jsonl"
        with open(cat_file, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"  Saved {len(rows)} → {cat_file}")

    # Save combined
    out = DATA_DIR / "combined_raw.jsonl"
    with open(out, "w") as f:
        for r in all_rows:
            f.write(json.dumps(r) + "\n")
    print(f"\nTotal: {len(all_rows)} rows → {out}")

    # Stats
    by_cat = {}
    for r in all_rows:
        by_cat[r["category"]] = by_cat.get(r["category"], 0) + 1
    print("\nBy category:", json.dumps(by_cat, indent=2))

if __name__ == "__main__":
    main()
