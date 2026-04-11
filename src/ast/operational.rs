use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MemType {
    Episodic,
    Semantic,
    Procedural,
    Working,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum DiagnosisKind {
    WrongApproach,
    MissingInfo,
    ConstraintViolation,
    ToolFailure,
    InsufficientEvidence,
    ConflictingEvidence,
}
