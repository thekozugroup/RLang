use serde::{Deserialize, Serialize};

use super::common::{Expr, Ident};

// ── Priority ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Priority {
    Critical,
    High,
    Normal,
    Low,
    Background,
}

// ── Deadline ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Deadline {
    Urgent,
    By(String),
    Within(String),
    Flexible,
    None,
}

// ── GoalStatus ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum GoalStatus {
    Pending,
    Active,
    Achieved,
    Failed(String),
    Abandoned(String),
    Blocked(Vec<Ident>),
}

// ── GoalExpr ────────────────────────────────────────────────────────────────

/// A desire that has been evaluated and selected for pursuit.
/// Has a defined target, success criteria, and resource bounds.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GoalExpr {
    pub target: Expr,
    pub priority: Priority,
    pub deadline: Deadline,
    pub success: Expr,
    pub status: GoalStatus,
    pub parent: Option<Ident>,
}

// ── IntentExpr ──────────────────────────────────────────────────────────────

/// A goal the agent has committed to, with an attached plan.
/// Intent = Goal + Plan + Resource Commitment.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct IntentExpr {
    pub goal: GoalExpr,
    pub plan: PlanExpr,
    pub resources: ResourceBudget,
    pub progress: usize,
}

// ── PlanExpr ────────────────────────────────────────────────────────────────

/// An ordered sequence of steps to achieve a goal.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct PlanExpr {
    pub steps: Vec<StepKind>,
    pub dependencies: Vec<(usize, usize)>,
    pub status: PlanStatus,
}

// ── StepKind ────────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum StepKind {
    /// Think about something (epistemic reasoning)
    Reason(Expr),
    /// Do something in the world (operational action)
    Act(Expr),
    /// Hand off to another agent (communicative)
    Delegate(Expr),
    /// Check a result
    Verify(Expr),
    /// Conditional branching
    Branch(Expr),
    /// Nested plan (recursive decomposition)
    SubPlan(Box<PlanExpr>),
}

// ── PlanStatus ──────────────────────────────────────────────────────────────

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum PlanStatus {
    Draft,
    Ready,
    InProgress,
    Completed,
    Failed(usize, String),
    Replanned,
}

// ── ResourceBudget ──────────────────────────────────────────────────────────

/// Resource constraints for an intent. Delegation must satisfy
/// conservation laws: child budgets sum to <= parent budget.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ResourceBudget {
    pub tokens: u64,
    pub api_calls: u32,
    pub wall_time: String,
    pub delegations: u8,
    pub cost: Option<f64>,
}
