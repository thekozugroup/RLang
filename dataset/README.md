# RLang Dataset Pipeline

Download and standardize HuggingFace reasoning datasets for the RLang project.

## Datasets

| Dataset | Rows | Description |
|---------|-----:|-------------|
| [Crownelius/Opus-4.6-Reasoning-3300x](https://huggingface.co/datasets/Crownelius/Opus-4.6-Reasoning-3300x) | ~2,160 | Opus 4.6 model reasoning traces across math, code, science, and logic domains |
| [DJLougen/harmonic-reasoning-v1](https://huggingface.co/datasets/DJLougen/harmonic-reasoning-v1) | ~799 | Curated reasoning with rich metadata (signal scores, self-corrections, coherence) |

Both datasets are licensed under **Apache 2.0**.

## Quick Start

```bash
cd dataset/
pip install -r requirements.txt
python download.py
python analyze.py
```

## Pipeline

1. **`download.py`** - Downloads both datasets from HuggingFace, standardizes them into a common schema, and saves as Parquet files.
2. **`analyze.py`** - Reads the standardized dataset and generates a markdown analysis report with token distributions, domain/difficulty breakdowns, and self-correction marker analysis.

## Output Files

```
data/
  standardized.parquet           # Combined dataset (all sources)
  opus_standardized.parquet      # Opus 4.6 Reasoning only
  harmonic_standardized.parquet  # Harmonic Reasoning only
  analysis_report.md             # Generated analysis report
```

## Standardized Schema

All records conform to this schema:

| Field | Type | Description |
|-------|------|-------------|
| `id` | str | Unique ID prefixed with source (`opus_` or `harmonic_`) |
| `source` | str | `"opus-4.6-reasoning"` or `"harmonic-reasoning-v1"` |
| `problem` | str | The input question or problem statement |
| `thinking_english` | str | Original English reasoning trace |
| `solution` | str | Final answer or solution |
| `domain` | str | Normalized domain: `math`, `code`, `science`, `logic`, `reasoning` |
| `category` | str | Subcategory from the original dataset |
| `difficulty` | str | Normalized: `easy`, `medium`, `hard`, `phd` |
| `thinking_tokens_est` | int | Estimated token count (`word_count * 1.3`) |
| `metadata` | str (JSON) | Source-specific metadata (signal_score, reasoning_style, etc.) |

## License

The pipeline code is part of the RLang project. The downloaded datasets are licensed under Apache 2.0 by their respective authors.
