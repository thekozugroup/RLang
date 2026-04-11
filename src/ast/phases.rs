use serde::{Deserialize, Serialize};

use super::common::Span;

/// The top-level AST node: a complete reasoning trace
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trace {
    pub phases: Vec<PhaseBlock>,
    pub span: Option<Span>,
}

/// Which reasoning phase this block represents
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Phase {
    Frame,
    Explore,
    Verify,
    Decide,
}

/// A phase block: #[phase(X)] { statements... }
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseBlock {
    pub phase: Phase,
    pub impl_mode: Option<ReasoningMode>,
    pub statements: Vec<super::common::Ident>, // Placeholder — will be Statement enum
    pub span: Option<Span>,
}

/// Reasoning mode declared via impl
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReasoningMode {
    Deductive,
    Abductive,
    Analogical,
}
