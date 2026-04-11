use serde::{Deserialize, Serialize};

use super::common::{Span, Statement};

/// The top-level AST node: a complete reasoning trace
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Trace {
    pub phases: Vec<PhaseBlock>,
    pub span: Option<Span>,
}

/// Which reasoning phase this block represents
#[derive(Debug, Clone, Copy, PartialEq, Eq, PartialOrd, Ord, Serialize, Deserialize)]
pub enum Phase {
    Frame   = 0,
    Explore = 1,
    Verify  = 2,
    Decide  = 3,
}

/// A phase block: #[phase(X)] { statements... }
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PhaseBlock {
    pub phase: Phase,
    pub impl_mode: Option<ReasoningMode>,
    pub statements: Vec<Statement>,
    pub span: Option<Span>,
}

/// Reasoning mode declared via impl
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ReasoningMode {
    Deductive,
    Abductive,
    Analogical,
}
