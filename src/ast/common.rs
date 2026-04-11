use serde::{Deserialize, Serialize};

/// Source span for error reporting
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Span {
    pub start: usize,
    pub end: usize,
    pub line: usize,
    pub col: usize,
}

/// Any identifier in the language
#[derive(Debug, Clone, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub struct Ident(pub String);

/// Numeric literal
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Literal {
    Float(f64),
    Int(i64),
    Str(String),
    Bool(bool),
}

/// All operators in RLang — flat enum for the 13 core + extensions
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Operator {
    // Layer 1: Epistemic — 13 core
    Cause, Prvnt, Enbl, Req, Obs, Sim, Confl,
    Chng, Cncl, Cntns, Isa, Seq, Goal,
    // Layer 1: Evidence modifiers
    Sup, Wkn, Neut,
    // Layer 1: Resolution
    Resolve, Conf, Decay, Refresh,
    // Layer 2: Motivational
    Dcmp, Prioritize, Select, Replan,
    // Layer 3: Operational
    Exec, Inv, Pcv, Rmb, Rcl, Forget,
    Bt, Verify, RetryWith,
    // Layer 4: Communicative
    Dlg, Msg, Discover, MatchCapability,
    Negotiate, Cancel, Poll, Subscribe,
    Cfp, Propose, AcceptProposal, RejectProposal,
    Inform, QueryIf, Agree, Refuse,
    ResolveConflict,
    // Built-in assertions (also usable as operators)
    Assert, Hedge, Suspend, Reject, Emit,
}

/// Metadata attached to any expression via | pipes
#[derive(Debug, Clone, Default, Serialize, Deserialize)]
pub struct Metadata {
    pub confidence: Option<f64>,
    pub ep_mode: Option<super::epistemic::EpMode>,
    pub source: Option<super::epistemic::Src>,
    pub scope: Option<super::epistemic::Scope>,
    pub freshness: Option<super::epistemic::Freshness>,
    pub extra: Vec<MetaField>,
}

/// A single metadata field for extension fields (priority, deadline, etc.)
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MetaField {
    pub key: String,
    pub value: MetaValue,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum MetaValue {
    Float(f64),
    Ident(String),
    Str(String),
    Call(String, Vec<Expr>),
}

/// The core expression enum — every node in the AST
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Expr {
    /// Operator call: cause(a, b), obs(x), dlg(agent, task)
    OperatorCall {
        name: Operator,
        args: Vec<Expr>,
        span: Option<Span>,
    },
    /// Generic function call (user-defined or unrecognized)
    FnCall {
        name: Ident,
        args: Vec<Expr>,
        span: Option<Span>,
    },
    /// Pipe chain: a |> b -> c
    PipeChain {
        steps: Vec<(super::connectives::Connective, Expr)>,
        span: Option<Span>,
    },
    /// Match expression
    Match {
        scrutinee: Box<Expr>,
        arms: Vec<MatchArm>,
        span: Option<Span>,
    },
    /// Result variant: Ok(x), Err(e), Some(v), None
    ResultExpr {
        variant: ResultVariant,
        inner: Option<Box<Expr>>,
        span: Option<Span>,
    },
    /// Evidence block: [obs(x) => sup(claim, +0.2), ...]
    EvidenceBlock {
        items: Vec<EvidenceItem>,
        span: Option<Span>,
    },
    /// Array literal: [a, b, c]
    Array {
        elements: Vec<Expr>,
        span: Option<Span>,
    },
    /// Struct literal: Name { field: value, ... }
    Struct {
        name: Ident,
        fields: Vec<(Ident, Expr)>,
        span: Option<Span>,
    },
    /// Literal value
    Literal(Literal),
    /// Identifier reference
    Ident(Ident),
    /// Expression with metadata: expr | p:0.7 | ep:infer
    WithMetadata {
        expr: Box<Expr>,
        metadata: Metadata,
        span: Option<Span>,
    },
}

/// A match arm: pattern => expr
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct MatchArm {
    pub pattern: Pattern,
    pub body: Expr,
    pub span: Option<Span>,
}

/// Pattern in a match expression
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Pattern {
    Wildcard,
    Ident(Ident),
    Literal(Literal),
    Guard { binding: Ident, condition: GuardCondition },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct GuardCondition {
    pub left: Ident,
    pub op: ComparisonOp,
    pub right: Expr,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ComparisonOp {
    Gt, Lt, Gte, Lte, Eq, Neq,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ResultVariant {
    Ok, Err, Some, None,
}

/// A single evidence item: expr => expr
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct EvidenceItem {
    pub observation: Expr,
    pub effect: Expr,
}

/// A statement in a phase block
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Statement {
    Let {
        name: Ident,
        type_ann: Option<TypeAnnotation>,
        value: Expr,
        metadata: Option<Metadata>,
        span: Option<Span>,
    },
    ExprStatement {
        expr: Expr,
        span: Option<Span>,
    },
    Assertion {
        kind: AssertionKind,
        args: Vec<Expr>,
        metadata: Option<Metadata>,
        span: Option<Span>,
    },
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum AssertionKind {
    Assert, Hedge, Suspend, Reject, Emit,
}

/// Type annotation: blf<0.7, 'fresh>, goal<Deploy>, etc.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TypeAnnotation {
    Simple(String),
    Generic {
        base: String,
        params: Vec<TypeParam>,
    },
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum TypeParam {
    Float(f64),
    Lifetime(String),
    Type(Box<TypeAnnotation>),
    Ident(String),
}
