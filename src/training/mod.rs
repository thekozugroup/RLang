//! Training data generator for RLang fine-tuning.
//!
//! Produces paired examples: English prompt -> RLang trace -> English conclusion.
//! Supports 10 diverse template categories and exports in JSONL and ShareGPT formats.

pub mod templates;
pub mod generator;
pub mod export;

// Re-export core types for convenience
pub use templates::{Category, TrainingExample};
pub use generator::{generate_batch, generate_batch_seeded};
pub use export::{to_jsonl, to_sharegpt};
