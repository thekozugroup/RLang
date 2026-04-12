use serde::{Deserialize, Serialize};

use super::common::{Expr, Ident};
use super::motivational::PlanExpr;

// ── MemType ─────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum MemType {
    Episodic,
    Semantic,
    Procedural,
    Working,
}

// ── ActionExpr ──────────────────────────────────────────────────────────────

/// An action the agent can take in the world.
/// Actions are not beliefs — they change state rather than describing it.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ActionExpr {
    /// Invoke an external tool
    Invoke {
        tool: Ident,
        args: Expr,
        expected: Option<f64>,
    },
    /// Execute a primitive operation
    Exec {
        op: Ident,
        args: Expr,
    },
    /// Delegate to another agent (bridges to Layer 4)
    Delegate {
        to: Ident,
        task: Expr,
        contract: Expr,
    },
    /// Store to memory
    Remember {
        key: Ident,
        value: Expr,
        mem_type: MemType,
    },
    /// Retrieve from memory
    Recall {
        query: Expr,
        mem_type: MemType,
    },
    /// Emit output to user/consumer
    Emit {
        content: Expr,
        format: Option<Ident>,
    },
}

// ── ActionResultExpr ────────────────────────────────────────────────────────

/// Result of executing an action — always typed.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ActionResultExpr {
    Ok(Expr),
    Err(String),
    Partial(Expr, Vec<Expr>),
    Timeout,
    Blocked(String),
}

// ── ObsFeedExpr ─────────────────────────────────────────────────────────────

/// Environmental feedback received after an action.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ObsFeedExpr {
    pub data: Expr,
    pub source: FeedSource,
    pub timestamp: String,
    pub relevance: f64,
}

// ── FeedSource ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum FeedSource {
    Env,
    Tool(Ident),
    Agent(Ident),
    User,
}

// ── ReflectionExpr ──────────────────────────────────────────────────────────

/// A structured reflection on a failed attempt.
/// NOT free-form text — typed diagnosis with specific fields.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ReflectionExpr {
    pub attempt: Ident,
    pub outcome: ActionResultExpr,
    pub diagnosis: DiagnosisKind,
    pub revision: Option<PlanExpr>,
}

// ── DiagnosisKind ───────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum DiagnosisKind {
    WrongApproach(String),
    MissingInfo(Vec<Expr>),
    ConstraintViolation(String),
    ToolFailure(Ident, String),
    InsufficientEvidence,
    ConflictingEvidence(Ident),
}
