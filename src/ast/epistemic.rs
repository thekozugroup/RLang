use serde::{Deserialize, Serialize};

/// Epistemic mode — how a belief was formed
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum EpMode {
    Direct,
    Infer,
    Anl,
    Recv,
}

/// Information freshness lifetime
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Freshness {
    Fresh,
    Stale,
    Unk,
}

/// Scope of a claim
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Scope {
    All,
    Some,
    None,
    Cond,
    Gen,
    Loc,
}

/// Source of a belief
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Src {
    Obs(String),
    Chain(Vec<String>),
    Agent(String),
    Mem(String),
    Given,
}
