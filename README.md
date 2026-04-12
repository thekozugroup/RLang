RLang is a Rust-inspired synthetic reasoning language that replaces verbose English chain-of-thought traces with typed, compressed, verifiable reasoning. Trained on analysis of 6M+ reasoning traces across 15 public datasets, it achieves 6.3x average token compression while preventing the seven most common reasoning failure modes through grammar-level enforcement.

## Screenshots

![RLang reasoning trace parsed and validated in a terminal](./docs/screenshot.png)

## How it works

Every RLang trace passes through four mandatory phases — Frame, Explore, Verify, Decide — enforced by a PEG parser. Skipping a phase or looping without bounds is a structural error caught at parse time, not a runtime surprise. This mirrors the four-phase reasoning model identified across DeepSeek R1, OpenAI o1, and Claude Opus traces in published research.

The language organizes reasoning into four composable layers: Epistemic (beliefs with typed confidence and evidence provenance), Motivational (goals with deadlines and resource budgets), Operational (observe-think-act loops with bounded self-correction), and Communicative (FIPA-ACL speech acts and A2A protocol alignment for multi-agent coordination).

Confidence values are computed from evidence chains, never asserted through prose. Beliefs carry temporal freshness markers (`t:fresh`/`t:stale`) inspired by Rust's ownership model, preventing stale-data reasoning. Anti-pattern mechanisms block circular reasoning, infinite reflection loops, constraint forgetting, and five other failure modes at the grammar and type-system level.

The training pipeline downloads real reasoning traces from HuggingFace, converts them to RLang, validates every trace through a Rust parser, optimizes for density, and runs six-layer quality checks. The final dataset of 6,049 verified traces ships in ShareGPT format for fine-tuning with Unsloth or similar frameworks.

## Stack

- Rust (Pest PEG parser, AST, validator)
- Python (dataset pipeline: download, convert, validate, optimize, QAQC, export)
- HuggingFace Datasets (Opus 4.6 Reasoning, Harmonic Reasoning, Hermes Agent Traces)
- ShareGPT format for SFT training data

## Status

In progress
