# RLang Core Parser + Type System — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working RLang parser that takes `.rl` source text and produces a typed AST, with validation for phase ordering and metadata completeness.

**Architecture:** Pest PEG grammar defines the syntax. A Rust AST module defines typed nodes for all four layers. A parser module converts Pest parse pairs into the AST. A validator module checks structural rules (phase ordering, metadata completeness, bounded backtrack, resource conservation). A CLI wraps it all for command-line usage.

**Tech Stack:** Rust, Pest (PEG parser generator), pest_derive, serde (for AST serialization), thiserror (error types), clap (CLI), pretty_assertions + insta (testing)

---

## File Structure

```
rlang/
├── Cargo.toml
├── src/
│   ├── main.rs                    # CLI entry point
│   ├── lib.rs                     # Library root, re-exports
│   ├── grammar/
│   │   ├── mod.rs                 # Grammar module root
│   │   └── rlang.pest             # PEG grammar definition
│   ├── ast/
│   │   ├── mod.rs                 # AST module root, shared types
│   │   ├── common.rs              # Shared types: Identifier, Metadata, Literal
│   │   ├── epistemic.rs           # Layer 1: Blf, EpMode, Src, Scope, Evidence
│   │   ├── motivational.rs        # Layer 2: Goal, Intent, Plan, Step, Priority
│   │   ├── operational.rs         # Layer 3: Action, ActionResult, ObsFeed, Reflection
│   │   ├── communicative.rs       # Layer 4: CommAct, TaskState, Contract, TrustModel
│   │   ├── connectives.rs         # All 8 connective operators
│   │   └── phases.rs              # Phase enum, PhaseBlock, trace structure
│   ├── parser/
│   │   ├── mod.rs                 # Parser module root
│   │   ├── expressions.rs         # Expression parsing (operators, pipes, matches)
│   │   ├── statements.rs          # Statement parsing (let, match, assertions)
│   │   ├── metadata.rs            # Metadata parsing (| p:0.7 | ep:infer ...)
│   │   ├── types.rs               # Type annotation parsing
│   │   └── blocks.rs              # Phase blocks, impl blocks, evidence blocks
│   ├── validator/
│   │   ├── mod.rs                 # Validator module root
│   │   ├── phases.rs              # Phase ordering validation
│   │   ├── metadata.rs            # Metadata completeness checks
│   │   ├── bounds.rs              # Bounded backtrack, max_rebloom checks
│   │   ├── resources.rs           # Resource conservation invariants
│   │   └── types.rs               # Type consistency checks
│   └── errors/
│       ├── mod.rs                 # Error module root
│       └── diagnostic.rs          # Pretty error formatting with source spans
├── tests/
│   ├── grammar_tests.rs           # PEG grammar unit tests
│   ├── parser_tests.rs            # Parser -> AST tests
│   ├── validator_tests.rs         # Validation rule tests
│   ├── integration_tests.rs       # Full trace parse + validate tests
│   └── fixtures/
│       ├── valid/                 # Valid .rl trace files
│       │   ├── simple_belief.rl
│       │   ├── full_deploy_trace.rl
│       │   ├── delegation.rl
│       │   └── multi_layer.rl
│       └── invalid/               # Invalid traces (should fail with specific errors)
│           ├── missing_confidence.rl
│           ├── skip_verify_phase.rl
│           ├── unbounded_backtrack.rl
│           ├── stale_assertion.rl
│           └── resource_violation.rl
└── examples/
    └── deploy_decision.rl         # The full example from the spec
```

---

## Task 1: Project Scaffold + Cargo Setup

**Files:**
- Create: `Cargo.toml`
- Create: `src/main.rs`
- Create: `src/lib.rs`

- [ ] **Step 1: Create Cargo.toml**

```toml
[package]
name = "rlang"
version = "0.2.0"
edition = "2024"
description = "RLang: A Rust-Inspired Agentic Reasoning Language"
license = "Apache-2.0"

[dependencies]
pest = "2.7"
pest_derive = "2.7"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
thiserror = "2"
clap = { version = "4", features = ["derive"] }

[dev-dependencies]
pretty_assertions = "1"
insta = { version = "1", features = ["yaml"] }
```

- [ ] **Step 2: Create src/lib.rs**

```rust
pub mod ast;
pub mod grammar;
pub mod parser;
pub mod validator;
pub mod errors;
```

- [ ] **Step 3: Create src/main.rs**

```rust
use clap::Parser as ClapParser;
use std::fs;
use std::path::PathBuf;
use std::process;

#[derive(ClapParser)]
#[command(name = "rlang", version, about = "RLang reasoning trace parser and validator")]
struct Cli {
    /// Path to .rl file to parse
    file: PathBuf,

    /// Output parsed AST as JSON
    #[arg(long)]
    ast: bool,

    /// Only validate, don't output AST
    #[arg(long)]
    validate_only: bool,

    /// Suppress output on success
    #[arg(short, long)]
    quiet: bool,
}

fn main() {
    let cli = Cli::parse();

    let source = match fs::read_to_string(&cli.file) {
        Ok(s) => s,
        Err(e) => {
            eprintln!("error: could not read {}: {}", cli.file.display(), e);
            process::exit(1);
        }
    };

    match rlang::parser::parse(&source) {
        Ok(trace) => {
            if let Err(errors) = rlang::validator::validate(&trace) {
                for err in &errors {
                    eprintln!("{}", err);
                }
                process::exit(1);
            }

            if !cli.quiet && !cli.validate_only {
                if cli.ast {
                    println!("{}", serde_json::to_string_pretty(&trace).unwrap());
                } else {
                    println!("OK: {} phases, {} statements",
                        trace.phases.len(),
                        trace.phases.iter().map(|p| p.statements.len()).sum::<usize>());
                }
            }
        }
        Err(e) => {
            eprintln!("{}", e);
            process::exit(1);
        }
    }
}
```

- [ ] **Step 4: Create module stub files**

Create empty `mod.rs` files for each module so the project compiles:

`src/grammar/mod.rs`:
```rust
use pest_derive::Parser;

#[derive(Parser)]
#[grammar = "grammar/rlang.pest"]
pub struct RLangParser;
```

`src/ast/mod.rs`:
```rust
pub mod common;
pub mod epistemic;
pub mod motivational;
pub mod operational;
pub mod communicative;
pub mod connectives;
pub mod phases;

pub use common::*;
pub use phases::Trace;
```

`src/parser/mod.rs`:
```rust
pub mod expressions;
pub mod statements;
pub mod metadata;
pub mod types;
pub mod blocks;

use crate::ast::Trace;
use crate::errors::ParseError;

pub fn parse(_source: &str) -> Result<Trace, ParseError> {
    todo!("Parser implementation")
}
```

`src/validator/mod.rs`:
```rust
pub mod phases;
pub mod metadata;
pub mod bounds;
pub mod resources;
pub mod types;

use crate::ast::Trace;
use crate::errors::ValidationError;

pub fn validate(_trace: &Trace) -> Result<(), Vec<ValidationError>> {
    todo!("Validator implementation")
}
```

`src/errors/mod.rs`:
```rust
pub mod diagnostic;

#[derive(Debug, thiserror::Error)]
pub enum ParseError {
    #[error("parse error at {line}:{col}: {message}")]
    Syntax {
        line: usize,
        col: usize,
        message: String,
    },
    #[error("unexpected token: expected {expected}, found {found}")]
    UnexpectedToken {
        expected: String,
        found: String,
    },
}

#[derive(Debug, thiserror::Error)]
pub enum ValidationError {
    #[error("phase error: {message}")]
    Phase { message: String },
    #[error("metadata error: {message}")]
    Metadata { message: String },
    #[error("bounds error: {message}")]
    Bounds { message: String },
    #[error("resource error: {message}")]
    Resource { message: String },
    #[error("type error: {message}")]
    Type { message: String },
}
```

Create stub files for all remaining submodules (empty files that just compile):

`src/ast/common.rs`:
```rust
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
```

`src/ast/phases.rs`:
```rust
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
```

Create remaining stub files with minimal content:

`src/ast/epistemic.rs`:
```rust
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
```

`src/ast/motivational.rs`:
```rust
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Priority {
    Critical,
    High,
    Normal,
    Low,
    Background,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum Deadline {
    Urgent,
    By(String),
    Within(String),
    Flexible,
    None,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum GoalStatus {
    Pending,
    Active,
    Achieved,
    Failed,
    Abandoned,
    Blocked,
}
```

`src/ast/operational.rs`:
```rust
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
```

`src/ast/communicative.rs`:
```rust
use serde::{Deserialize, Serialize};

/// A2A-aligned task state
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskState {
    Submitted,
    Working,
    InputRequired,
    AuthRequired,
    Completed,
    Failed,
    Canceled,
    Rejected,
}

/// Contract mode for delegation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContractMode {
    Urgent,
    Economical,
    Balanced,
}

/// Role in a message exchange
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Role {
    User,
    Agent,
}
```

`src/ast/connectives.rs`:
```rust
use serde::{Deserialize, Serialize};

/// All connective operators in RLang
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Connective {
    Pipe,       // |>  — sequential pipe
    Transform,  // ->  — transform/resolve
    FanOut,     // ||> — parallel fan-out
    Aggregate,  // <|  — merge multiple into one
    Tentative,  // ~>  — exploratory (revertible)
    ErrChannel, // !>  — error routing
    Fallible,   // ?>  — try left, on fail try right
    Store,      // @>  — pipe to memory
    Retrieve,   // <@  — pull from memory
}
```

`src/errors/diagnostic.rs`:
```rust
// Pretty error formatting — will be implemented later
```

`src/parser/expressions.rs`, `src/parser/statements.rs`, `src/parser/metadata.rs`, `src/parser/types.rs`, `src/parser/blocks.rs`, `src/validator/phases.rs`, `src/validator/metadata.rs`, `src/validator/bounds.rs`, `src/validator/resources.rs`, `src/validator/types.rs`:
```rust
// Stub — implementation in later tasks
```

- [ ] **Step 5: Verify the project compiles**

Run: `cargo check`
Expected: Compiles with warnings about unused code and `todo!()` macros, no errors.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: scaffold RLang Rust project with module structure"
```

---

## Task 2: PEG Grammar — Core Expressions and Metadata

**Files:**
- Create: `src/grammar/rlang.pest`
- Create: `tests/grammar_tests.rs`

This is the heart of the language. The grammar defines what valid RLang looks like.

- [ ] **Step 1: Write the grammar test file with test cases for core expressions**

`tests/grammar_tests.rs`:
```rust
use pest::Parser;
use rlang::grammar::RLangParser;
use rlang::grammar::Rule;

#[test]
fn test_float_literal() {
    let result = RLangParser::parse(Rule::float_literal, "0.7");
    assert!(result.is_ok(), "Failed to parse float: {:?}", result.err());
}

#[test]
fn test_float_literal_boundaries() {
    assert!(RLangParser::parse(Rule::float_literal, "0.0").is_ok());
    assert!(RLangParser::parse(Rule::float_literal, "1.0").is_ok());
    assert!(RLangParser::parse(Rule::float_literal, "0.99").is_ok());
}

#[test]
fn test_identifier() {
    assert!(RLangParser::parse(Rule::ident, "storm").is_ok());
    assert!(RLangParser::parse(Rule::ident, "agent_b").is_ok());
    assert!(RLangParser::parse(Rule::ident, "mtg").is_ok());
    assert!(RLangParser::parse(Rule::ident, "health_check_pass").is_ok());
}

#[test]
fn test_operator_call_simple() {
    let result = RLangParser::parse(Rule::operator_call, "obs(rain)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_operator_call_two_args() {
    let result = RLangParser::parse(Rule::operator_call, "cause(storm, cncl(mtg))");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_operator_call_three_args() {
    let result = RLangParser::parse(Rule::operator_call, "chng(state, idle, run)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_metadata_single() {
    let result = RLangParser::parse(Rule::metadata, "| p:0.7");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_metadata_full() {
    let result = RLangParser::parse(Rule::metadata, "| p:0.7 | ep:infer | src:obs(rpt) | scope:loc | t:fresh");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_evidence_item_sup() {
    let result = RLangParser::parse(Rule::evidence_item, "obs(dark_clouds) => sup(claim, +0.20)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_evidence_item_wkn() {
    let result = RLangParser::parse(Rule::evidence_item, "obs(no_notice) => wkn(claim, -0.15)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_evidence_block() {
    let input = r#"[
    obs(dark_clouds) => sup(claim, +0.20),
    obs(no_notice) => wkn(claim, -0.15),
    obs(empty_lot) => sup(claim, +0.10),
]"#;
    let result = RLangParser::parse(Rule::evidence_block, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_let_binding_belief() {
    let input = r#"let claim: blf<0.7> = cause(storm, cncl(mtg)) | p:0.7 | ep:infer | src:obs(rpt) | scope:loc | t:fresh;"#;
    let result = RLangParser::parse(Rule::let_binding, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_pipe_chain() {
    let input = "claim |> resolve(ev) -> Ok(blf_resolved)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_match_expr() {
    let input = r#"match conf(claim) {
    c if c > 0.85 => assert(claim),
    c if c > 0.55 => hedge(claim),
    c if c > 0.30 => suspend(claim),
    _ => reject(claim),
}"#;
    let result = RLangParser::parse(Rule::match_expr, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_phase_attribute() {
    let result = RLangParser::parse(Rule::phase_attr, "#[phase(Frame)]");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_phase_block() {
    let input = r#"#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
}"#;
    let result = RLangParser::parse(Rule::phase_block, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_fanout() {
    let input = "decompose(goal) ||> [delegate(a, t1), delegate(b, t2)] <| synthesize(results)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_tentative() {
    let input = "hypothesis ~> test(hypothesis)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_error_channel() {
    let input = "execute(deploy) !> handle_error(e)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_memory_store() {
    let input = "obs(user_pref) @> remember(prefs, Semantic)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_memory_retrieve() {
    let input = "recall(prefs, Semantic) <@ |> apply_to(response)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_full_trace() {
    let input = r#"#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback) | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests => sup(deploy, +0.15),
        risk  => wkn(deploy, -0.25),
    ];
    let deploy_blf = enbl(fix, resolve(bug)) |> resolve(ev) -> Ok(blf_resolved);
}

#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy),
        _ => reject(deploy),
    }
}"#;
    let result = RLangParser::parse(Rule::trace, input);
    assert!(result.is_ok(), "Failed to parse full trace: {:?}", result.err());
}
```

- [ ] **Step 2: Run tests to verify they fail (grammar not yet written)**

Run: `cargo test --test grammar_tests 2>&1 | head -20`
Expected: Compilation error — `Rule` enum doesn't have the variants yet because the `.pest` file is empty.

- [ ] **Step 3: Write the PEG grammar**

`src/grammar/rlang.pest`:
```pest
// ============================================================
// RLang v0.2 PEG Grammar
// A Rust-Inspired Agentic Reasoning Language
// ============================================================

// Top-level: a trace is one or more phase blocks
trace = { SOI ~ phase_block+ ~ EOI }

// === Phase Structure ===
phase_block = { phase_attr ~ (impl_block | bare_block) }
phase_attr  = { "#[phase(" ~ phase_name ~ ")]" }
phase_name  = { "Frame" | "Explore" | "Verify" | "Decide" }

impl_block  = { "impl" ~ reasoning_mode ~ "{" ~ statement* ~ "}" }
bare_block  = { "{" ~ statement* ~ "}" }

reasoning_mode = { "Deductive" | "Abductive" | "Analogical" }

// === Statements ===
statement = { (let_binding | match_expr | pipe_chain_stmt | assertion | comment) }

let_binding = {
    "let" ~ ident ~ (":" ~ type_annotation)? ~ "=" ~ expr ~ metadata? ~ ";"
}

assertion = {
    assertion_kw ~ "(" ~ expr ~ ("," ~ expr)* ~ ")" ~ metadata? ~ ";"
}
assertion_kw = { "assert" | "hedge" | "suspend" | "reject" | "emit" }

pipe_chain_stmt = { pipe_chain ~ ";" }

// === Expressions ===
expr = { match_expr | pipe_chain | primary_expr }

primary_expr = {
    operator_call
    | result_expr
    | array_literal
    | evidence_block
    | struct_literal
    | literal
    | ident
    | "(" ~ expr ~ ")"
}

// Operator calls: cause(a, b), obs(x), etc.
operator_call = { operator_name ~ "(" ~ arg_list ~ ")" }

operator_name = {
    // Layer 1: Epistemic (13 core operators)
    "cause" | "prvnt" | "enbl" | "req" | "obs" | "sim" | "confl"
    | "chng" | "cncl" | "cntns" | "isa" | "seq" | "goal"
    // Layer 1: Evidence modifiers
    | "sup" | "wkn" | "neut"
    // Layer 1: Resolution
    | "resolve" | "conf" | "decay" | "refresh"
    // Layer 2: Motivational
    | "dcmp" | "prioritize" | "select" | "replan"
    // Layer 3: Operational
    | "exec" | "inv" | "pcv" | "rmb" | "rcl" | "forget"
    | "bt" | "verify" | "retry_with"
    // Layer 4: Communicative
    | "dlg" | "msg" | "discover" | "match_capability"
    | "negotiate" | "cancel" | "poll" | "subscribe"
    | "cfp" | "propose" | "accept_proposal" | "reject_proposal"
    | "inform" | "query_if" | "agree" | "refuse"
    | "resolve_conflict"
    // Assertion-like operators (also usable as expressions)
    | "assert" | "hedge" | "suspend" | "reject" | "emit"
    // Generic function calls
    | ident
}

arg_list = { (arg ~ ("," ~ arg)*)? }
arg = { expr ~ metadata? }

// Result expressions: Ok(...) | Err(...)
result_expr = { result_variant ~ "(" ~ expr ~ ")" }
result_variant = { "Ok" | "Err" | "Some" | "None" }

// === Pipe Chains and Connectives ===
pipe_chain = { primary_expr ~ (connective ~ primary_expr)+ }

connective = {
    "||>" | "|>"   // fan-out before pipe (longer match first)
    | "<|" | "<@"   // aggregate, memory retrieve
    | "~>" | "!>" | "?>" | "@>"  // tentative, error, fallible, memory store
    | "->"          // transform
}

// === Match Expressions ===
match_expr = { "match" ~ primary_expr ~ "{" ~ match_arm+ ~ "}" }
match_arm  = { pattern ~ "=>" ~ expr ~ ","? }
pattern    = { wildcard | guard_pattern | literal | ident }
wildcard   = { "_" }
guard_pattern = { ident ~ "if" ~ guard_condition }
guard_condition = { ident ~ comparison_op ~ primary_expr }
comparison_op  = { ">=" | "<=" | "!=" | ">" | "<" | "==" }

// === Evidence Blocks ===
evidence_block = { "[" ~ evidence_item ~ ("," ~ evidence_item)* ~ ","? ~ "]" }
evidence_item  = { expr ~ "=>" ~ expr }

// === Metadata ===
metadata    = { ("|" ~ meta_field)+ }
meta_field  = { meta_key ~ ":" ~ meta_value }
meta_key    = {
    "p" | "ep" | "src" | "scope" | "t"
    | "priority" | "deadline" | "success" | "mode"
    | "req" | "cond"
}
meta_value  = { operator_call | float_literal | ident | string_literal }

// === Type Annotations ===
type_annotation = {
    generic_type | simple_type
}
generic_type = { simple_type ~ "<" ~ type_params ~ ">" }
type_params  = { type_param ~ ("," ~ type_param)* }
type_param   = { float_literal | lifetime | type_annotation | ident }

simple_type = {
    "blf" | "goal" | "intent" | "action" | "obs_feed" | "reflection"
    | "Contract" | "Evidence" | "Plan" | "Task"
    | "CommAct" | "AgentCard" | "TrustModel"
    | "Result" | "Option" | "Vec" | "HashMap"
    | ident
}

lifetime = { "'" ~ ident }

// === Struct and Array Literals ===
struct_literal = { ident ~ "{" ~ struct_field ~ ("," ~ struct_field)* ~ ","? ~ "}" }
struct_field   = { ident ~ ":" ~ expr }

array_literal = { "[" ~ (expr ~ ("," ~ expr)* ~ ","?)? ~ "]" }

// === Bounded Attribute ===
bounded_attr = { "#[bounded(" ~ bounded_params ~ ")]" }
bounded_params = { ident ~ (":" ~ literal)? ~ ("," ~ ident ~ (":" ~ literal)?)* }

// === Comments ===
comment = { "//" ~ (!NEWLINE ~ ANY)* ~ NEWLINE? }

// === Literals ===
literal = { float_literal | int_literal | string_literal | bool_literal }
float_literal  = @{ ASCII_DIGIT+ ~ "." ~ ASCII_DIGIT+ }
int_literal    = @{ ASCII_DIGIT+ }
string_literal = @{ "\"" ~ (!"\"" ~ ANY)* ~ "\"" }
bool_literal   = { "true" | "false" }

// === Identifiers ===
ident = @{ (ASCII_ALPHA | "_") ~ (ASCII_ALPHANUMERIC | "_")* }

// === Whitespace and Comments (implicit) ===
WHITESPACE = _{ " " | "\t" | "\r" | "\n" }
COMMENT    = _{ "//" ~ (!NEWLINE ~ ANY)* }
NEWLINE    = _{ "\n" | "\r\n" }
```

- [ ] **Step 4: Run grammar tests**

Run: `cargo test --test grammar_tests 2>&1`
Expected: All grammar tests pass. If any fail, fix the grammar rules.

- [ ] **Step 5: Commit**

```bash
git add src/grammar/rlang.pest tests/grammar_tests.rs
git commit -m "feat: PEG grammar for RLang v0.2 — all 4 layers, connectives, phases"
```

---

## Task 3: AST — Complete Type Definitions for All 4 Layers

**Files:**
- Modify: `src/ast/common.rs`
- Modify: `src/ast/epistemic.rs`
- Modify: `src/ast/motivational.rs`
- Modify: `src/ast/operational.rs`
- Modify: `src/ast/communicative.rs`
- Modify: `src/ast/connectives.rs`
- Modify: `src/ast/phases.rs`
- Modify: `src/ast/mod.rs`
- Create: `tests/ast_tests.rs`

- [ ] **Step 1: Write AST serialization tests**

`tests/ast_tests.rs`:
```rust
use rlang::ast::*;
use rlang::ast::epistemic::*;
use rlang::ast::motivational::*;
use rlang::ast::operational::*;
use rlang::ast::communicative::*;
use rlang::ast::connectives::*;
use rlang::ast::phases::*;

#[test]
fn test_blf_serialization() {
    let blf = Expr::OperatorCall {
        name: Operator::Obs,
        args: vec![Expr::Ident(Ident("tests_pass".into()))],
        span: None,
    };
    let json = serde_json::to_string(&blf).unwrap();
    assert!(json.contains("Obs"));
    assert!(json.contains("tests_pass"));
}

#[test]
fn test_metadata_construction() {
    let meta = Metadata {
        confidence: Some(0.85),
        ep_mode: Some(EpMode::Direct),
        source: Some(Src::Obs("ci_pipeline".into())),
        scope: Some(Scope::Loc),
        freshness: Some(Freshness::Fresh),
        extra: vec![],
    };
    assert_eq!(meta.confidence, Some(0.85));
    assert_eq!(meta.ep_mode, Some(EpMode::Direct));
}

#[test]
fn test_phase_ordering() {
    assert!(Phase::Frame < Phase::Explore);
    assert!(Phase::Explore < Phase::Verify);
    assert!(Phase::Verify < Phase::Decide);
}

#[test]
fn test_connective_variants() {
    let conns = vec![
        Connective::Pipe,
        Connective::Transform,
        Connective::FanOut,
        Connective::Aggregate,
        Connective::Tentative,
        Connective::ErrChannel,
        Connective::Fallible,
        Connective::Store,
        Connective::Retrieve,
    ];
    assert_eq!(conns.len(), 9);
}

#[test]
fn test_task_state_terminal() {
    assert!(TaskState::Completed.is_terminal());
    assert!(TaskState::Failed.is_terminal());
    assert!(TaskState::Canceled.is_terminal());
    assert!(TaskState::Rejected.is_terminal());
    assert!(!TaskState::Submitted.is_terminal());
    assert!(!TaskState::Working.is_terminal());
    assert!(!TaskState::InputRequired.is_terminal());
}

#[test]
fn test_trace_construction() {
    let trace = Trace {
        phases: vec![
            PhaseBlock {
                phase: Phase::Frame,
                impl_mode: Some(ReasoningMode::Deductive),
                statements: vec![],
                span: None,
            },
            PhaseBlock {
                phase: Phase::Explore,
                impl_mode: None,
                statements: vec![],
                span: None,
            },
            PhaseBlock {
                phase: Phase::Verify,
                impl_mode: None,
                statements: vec![],
                span: None,
            },
            PhaseBlock {
                phase: Phase::Decide,
                impl_mode: None,
                statements: vec![],
                span: None,
            },
        ],
        span: None,
    };
    assert_eq!(trace.phases.len(), 4);
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cargo test --test ast_tests 2>&1 | head -20`
Expected: Compilation errors — AST types don't match test expectations yet.

- [ ] **Step 3: Implement complete AST types**

Update `src/ast/common.rs`:
```rust
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
```

Update `src/ast/phases.rs`:
```rust
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
```

Update `src/ast/communicative.rs`:
```rust
use serde::{Deserialize, Serialize};

/// A2A-aligned task state
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskState {
    Submitted,
    Working,
    InputRequired,
    AuthRequired,
    Completed,
    Failed,
    Canceled,
    Rejected,
}

impl TaskState {
    pub fn is_terminal(&self) -> bool {
        matches!(self, Self::Completed | Self::Failed | Self::Canceled | Self::Rejected)
    }

    pub fn valid_transitions(&self) -> Vec<TaskState> {
        match self {
            Self::Submitted     => vec![Self::Working, Self::Rejected, Self::Canceled],
            Self::Working       => vec![Self::Completed, Self::Failed, Self::Canceled, Self::InputRequired, Self::AuthRequired],
            Self::InputRequired => vec![Self::Working, Self::Canceled],
            Self::AuthRequired  => vec![Self::Working, Self::Canceled],
            Self::Completed | Self::Failed | Self::Canceled | Self::Rejected => vec![],
        }
    }
}

/// Contract mode for delegation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum ContractMode {
    Urgent,
    Economical,
    Balanced,
}

/// Role in a message exchange
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Role {
    User,
    Agent,
}
```

Update `src/ast/mod.rs`:
```rust
pub mod common;
pub mod epistemic;
pub mod motivational;
pub mod operational;
pub mod communicative;
pub mod connectives;
pub mod phases;

pub use common::*;
pub use phases::Trace;
```

- [ ] **Step 4: Run AST tests**

Run: `cargo test --test ast_tests 2>&1`
Expected: All AST tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/ast/ tests/ast_tests.rs
git commit -m "feat: complete AST type definitions for all 4 RLang layers"
```

---

## Task 4: Parser — Pest Pairs to AST Conversion

**Files:**
- Modify: `src/parser/mod.rs`
- Modify: `src/parser/expressions.rs`
- Modify: `src/parser/statements.rs`
- Modify: `src/parser/metadata.rs`
- Modify: `src/parser/types.rs`
- Modify: `src/parser/blocks.rs`
- Create: `tests/parser_tests.rs`

- [ ] **Step 1: Write parser integration tests**

`tests/parser_tests.rs`:
```rust
use rlang::parser::parse;
use rlang::ast::phases::Phase;
use rlang::ast::common::Operator;

#[test]
fn test_parse_simple_belief() {
    let input = r#"#[phase(Frame)]
{
    let claim: blf<0.7> = obs(rain) | p:0.95 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [obs(clouds) => sup(claim, +0.1)];
}

#[phase(Verify)]
{
    req(claim, obs(rain)) |> verify(claim) -> Ok(());
}

#[phase(Decide)]
{
    assert(claim);
}"#;

    let trace = parse(input).expect("Failed to parse simple belief trace");
    assert_eq!(trace.phases.len(), 4);
    assert_eq!(trace.phases[0].phase, Phase::Frame);
    assert_eq!(trace.phases[1].phase, Phase::Explore);
    assert_eq!(trace.phases[2].phase, Phase::Verify);
    assert_eq!(trace.phases[3].phase, Phase::Decide);
}

#[test]
fn test_parse_operator_call() {
    let input = r#"#[phase(Frame)]
{
    let x = cause(storm, cncl(mtg)) | p:0.7 | ep:infer | src:obs(weather) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let y = obs(test) | p:0.5 | ep:direct | src:Given | scope:loc | t:fresh;
}

#[phase(Verify)]
{
    obs(test) |> verify(x) -> Ok(());
}

#[phase(Decide)]
{
    suspend(x);
}"#;

    let trace = parse(input).expect("Failed to parse operator call");
    assert!(!trace.phases[0].statements.is_empty());
}

#[test]
fn test_parse_with_impl_mode() {
    let input = r#"#[phase(Frame)]
impl Deductive {
    let x = obs(data) | p:0.99 | ep:direct | src:Given | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let y = obs(test) | p:0.5 | ep:direct | src:Given | scope:loc | t:fresh;
}

#[phase(Verify)]
{
    obs(test) |> verify(x) -> Ok(());
}

#[phase(Decide)]
{
    assert(x);
}"#;

    let trace = parse(input).expect("Failed to parse impl mode");
    assert_eq!(trace.phases[0].impl_mode, Some(rlang::ast::phases::ReasoningMode::Deductive));
}

#[test]
fn test_parse_evidence_block() {
    let input = r#"#[phase(Frame)]
{
    let claim = obs(data) | p:0.7 | ep:direct | src:Given | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        obs(a) => sup(claim, +0.2),
        obs(b) => wkn(claim, -0.1),
    ];
}

#[phase(Verify)]
{
    claim |> resolve(ev) -> Ok(resolved);
}

#[phase(Decide)]
{
    assert(resolved);
}"#;

    let trace = parse(input).expect("Failed to parse evidence block");
    assert_eq!(trace.phases.len(), 4);
}

#[test]
fn test_parse_match_expression() {
    let input = r#"#[phase(Frame)]
{
    let claim = obs(data) | p:0.7 | ep:direct | src:Given | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [obs(a) => sup(claim, +0.1)];
}

#[phase(Verify)]
{
    claim |> resolve(ev) -> Ok(resolved);
}

#[phase(Decide)]
{
    match conf(claim) {
        c if c > 0.85 => assert(claim),
        c if c > 0.55 => hedge(claim),
        _ => reject(claim),
    }
}"#;

    let trace = parse(input).expect("Failed to parse match expression");
    assert_eq!(trace.phases[3].phase, Phase::Decide);
}

#[test]
fn test_parse_pipe_chain_with_connectives() {
    let input = r#"#[phase(Frame)]
{
    let x = obs(data) | p:0.9 | ep:direct | src:Given | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    x |> resolve(ev) -> Ok(result);
}

#[phase(Verify)]
{
    req(x, obs(data)) |> verify(x) -> Ok(());
}

#[phase(Decide)]
{
    assert(result);
}"#;

    let trace = parse(input).expect("Failed to parse pipe chain");
    assert_eq!(trace.phases.len(), 4);
}

#[test]
fn test_parse_error_on_invalid_syntax() {
    let input = "this is not valid rlang";
    let result = parse(input);
    assert!(result.is_err());
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cargo test --test parser_tests 2>&1 | head -5`
Expected: Fails because parser returns `todo!()`.

- [ ] **Step 3: Implement metadata parser**

`src/parser/metadata.rs`:
```rust
use pest::iterators::Pair;

use crate::ast::common::{Metadata, MetaField, MetaValue};
use crate::ast::epistemic::{EpMode, Freshness, Scope, Src};
use crate::errors::ParseError;
use crate::grammar::Rule;

pub fn parse_metadata(pair: Pair<Rule>) -> Result<Metadata, ParseError> {
    let mut meta = Metadata::default();

    for field_pair in pair.into_inner() {
        if field_pair.as_rule() != Rule::meta_field {
            continue;
        }
        let mut inner = field_pair.into_inner();
        let key = inner.next().unwrap().as_str();
        let value_pair = inner.next().unwrap();

        match key {
            "p" => {
                meta.confidence = Some(value_pair.as_str().parse::<f64>().map_err(|_| {
                    ParseError::Syntax {
                        line: 0,
                        col: 0,
                        message: format!("invalid confidence value: {}", value_pair.as_str()),
                    }
                })?);
            }
            "ep" => {
                meta.ep_mode = Some(match value_pair.as_str() {
                    "direct" => EpMode::Direct,
                    "infer" => EpMode::Infer,
                    "anl" => EpMode::Anl,
                    "recv" => EpMode::Recv,
                    other => {
                        return Err(ParseError::Syntax {
                            line: 0,
                            col: 0,
                            message: format!("unknown epistemic mode: {}", other),
                        });
                    }
                });
            }
            "src" => {
                meta.source = Some(parse_src(value_pair)?);
            }
            "scope" => {
                meta.scope = Some(match value_pair.as_str() {
                    "all" => Scope::All,
                    "some" => Scope::Some,
                    "none" => Scope::None,
                    "cond" => Scope::Cond,
                    "gen" => Scope::Gen,
                    "loc" => Scope::Loc,
                    other => {
                        return Err(ParseError::Syntax {
                            line: 0,
                            col: 0,
                            message: format!("unknown scope: {}", other),
                        });
                    }
                });
            }
            "t" => {
                meta.freshness = Some(match value_pair.as_str() {
                    "fresh" => Freshness::Fresh,
                    "stale" => Freshness::Stale,
                    "unk" => Freshness::Unk,
                    other => {
                        return Err(ParseError::Syntax {
                            line: 0,
                            col: 0,
                            message: format!("unknown freshness: {}", other),
                        });
                    }
                });
            }
            other => {
                let value = match value_pair.as_rule() {
                    Rule::float_literal => MetaValue::Float(value_pair.as_str().parse().unwrap()),
                    Rule::ident => MetaValue::Ident(value_pair.as_str().to_string()),
                    Rule::string_literal => {
                        let s = value_pair.as_str();
                        MetaValue::Str(s[1..s.len() - 1].to_string())
                    }
                    _ => MetaValue::Ident(value_pair.as_str().to_string()),
                };
                meta.extra.push(MetaField {
                    key: other.to_string(),
                    value,
                });
            }
        }
    }

    Ok(meta)
}

fn parse_src(pair: Pair<Rule>) -> Result<Src, ParseError> {
    match pair.as_rule() {
        Rule::operator_call => {
            let mut inner = pair.into_inner();
            let name = inner.next().unwrap().as_str();
            if name == "obs" {
                let arg = inner.next().unwrap(); // arg_list
                let first_arg = arg.into_inner().next().unwrap(); // first arg
                let ident = first_arg.into_inner().next().unwrap(); // unwrap expr layers
                Ok(Src::Obs(ident.as_str().to_string()))
            } else {
                Ok(Src::Obs(name.to_string()))
            }
        }
        Rule::ident => {
            let s = pair.as_str();
            match s {
                "Given" => Ok(Src::Given),
                other => Ok(Src::Obs(other.to_string())),
            }
        }
        _ => Ok(Src::Given),
    }
}
```

- [ ] **Step 4: Implement expression parser**

`src/parser/expressions.rs`:
```rust
use pest::iterators::Pair;

use crate::ast::common::*;
use crate::ast::connectives::Connective;
use crate::errors::ParseError;
use crate::grammar::Rule;

use super::metadata::parse_metadata;

pub fn parse_expr(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    match pair.as_rule() {
        Rule::expr | Rule::primary_expr | Rule::arg => {
            let inner = pair.into_inner().next().unwrap();
            parse_expr(inner)
        }
        Rule::operator_call => parse_operator_call(pair),
        Rule::result_expr => parse_result_expr(pair),
        Rule::evidence_block => parse_evidence_block(pair),
        Rule::array_literal => parse_array(pair),
        Rule::struct_literal => parse_struct(pair),
        Rule::match_expr => parse_match(pair),
        Rule::pipe_chain => parse_pipe_chain(pair),
        Rule::float_literal => Ok(Expr::Literal(Literal::Float(
            pair.as_str().parse().unwrap(),
        ))),
        Rule::int_literal => Ok(Expr::Literal(Literal::Int(
            pair.as_str().parse().unwrap(),
        ))),
        Rule::string_literal => {
            let s = pair.as_str();
            Ok(Expr::Literal(Literal::Str(s[1..s.len() - 1].to_string())))
        }
        Rule::bool_literal => Ok(Expr::Literal(Literal::Bool(pair.as_str() == "true"))),
        Rule::ident => Ok(Expr::Ident(Ident(pair.as_str().to_string()))),
        Rule::literal => {
            let inner = pair.into_inner().next().unwrap();
            parse_expr(inner)
        }
        _ => Err(ParseError::Syntax {
            line: 0,
            col: 0,
            message: format!("unexpected rule: {:?}", pair.as_rule()),
        }),
    }
}

fn parse_operator_call(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let name_pair = inner.next().unwrap();
    let name_str = name_pair.as_str();

    let operator = match parse_operator_name(name_str) {
        Some(op) => op,
        None => {
            // Treat as generic function call
            let args = if let Some(arg_list) = inner.next() {
                parse_arg_list(arg_list)?
            } else {
                vec![]
            };
            return Ok(Expr::FnCall {
                name: Ident(name_str.to_string()),
                args,
                span: None,
            });
        }
    };

    let args = if let Some(arg_list) = inner.next() {
        parse_arg_list(arg_list)?
    } else {
        vec![]
    };

    Ok(Expr::OperatorCall {
        name: operator,
        args,
        span: None,
    })
}

fn parse_operator_name(name: &str) -> Option<Operator> {
    match name {
        "cause" => Some(Operator::Cause),
        "prvnt" => Some(Operator::Prvnt),
        "enbl" => Some(Operator::Enbl),
        "req" => Some(Operator::Req),
        "obs" => Some(Operator::Obs),
        "sim" => Some(Operator::Sim),
        "confl" => Some(Operator::Confl),
        "chng" => Some(Operator::Chng),
        "cncl" => Some(Operator::Cncl),
        "cntns" => Some(Operator::Cntns),
        "isa" => Some(Operator::Isa),
        "seq" => Some(Operator::Seq),
        "goal" => Some(Operator::Goal),
        "sup" => Some(Operator::Sup),
        "wkn" => Some(Operator::Wkn),
        "neut" => Some(Operator::Neut),
        "resolve" => Some(Operator::Resolve),
        "conf" => Some(Operator::Conf),
        "decay" => Some(Operator::Decay),
        "refresh" => Some(Operator::Refresh),
        "dcmp" => Some(Operator::Dcmp),
        "prioritize" => Some(Operator::Prioritize),
        "select" => Some(Operator::Select),
        "replan" => Some(Operator::Replan),
        "exec" => Some(Operator::Exec),
        "inv" => Some(Operator::Inv),
        "pcv" => Some(Operator::Pcv),
        "rmb" => Some(Operator::Rmb),
        "rcl" => Some(Operator::Rcl),
        "forget" => Some(Operator::Forget),
        "bt" => Some(Operator::Bt),
        "verify" => Some(Operator::Verify),
        "retry_with" => Some(Operator::RetryWith),
        "dlg" => Some(Operator::Dlg),
        "msg" => Some(Operator::Msg),
        "discover" => Some(Operator::Discover),
        "match_capability" => Some(Operator::MatchCapability),
        "negotiate" => Some(Operator::Negotiate),
        "cancel" => Some(Operator::Cancel),
        "poll" => Some(Operator::Poll),
        "subscribe" => Some(Operator::Subscribe),
        "cfp" => Some(Operator::Cfp),
        "propose" => Some(Operator::Propose),
        "accept_proposal" => Some(Operator::AcceptProposal),
        "reject_proposal" => Some(Operator::RejectProposal),
        "inform" => Some(Operator::Inform),
        "query_if" => Some(Operator::QueryIf),
        "agree" => Some(Operator::Agree),
        "refuse" => Some(Operator::Refuse),
        "resolve_conflict" => Some(Operator::ResolveConflict),
        "assert" => Some(Operator::Assert),
        "hedge" => Some(Operator::Hedge),
        "suspend" => Some(Operator::Suspend),
        "reject" => Some(Operator::Reject),
        "emit" => Some(Operator::Emit),
        _ => None,
    }
}

fn parse_arg_list(pair: Pair<Rule>) -> Result<Vec<Expr>, ParseError> {
    let mut args = Vec::new();
    for arg_pair in pair.into_inner() {
        let mut arg_inner = arg_pair.into_inner();
        let expr_pair = arg_inner.next().unwrap();
        let mut expr = parse_expr(expr_pair)?;

        // Check for metadata on the argument
        if let Some(meta_pair) = arg_inner.next() {
            if meta_pair.as_rule() == Rule::metadata {
                let metadata = parse_metadata(meta_pair)?;
                expr = Expr::WithMetadata {
                    expr: Box::new(expr),
                    metadata,
                    span: None,
                };
            }
        }

        args.push(expr);
    }
    Ok(args)
}

fn parse_result_expr(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let variant_str = inner.next().unwrap().as_str();
    let variant = match variant_str {
        "Ok" => ResultVariant::Ok,
        "Err" => ResultVariant::Err,
        "Some" => ResultVariant::Some,
        "None" => ResultVariant::None,
        _ => unreachable!(),
    };
    let inner_expr = if let Some(expr_pair) = inner.next() {
        Some(Box::new(parse_expr(expr_pair)?))
    } else {
        None
    };
    Ok(Expr::ResultExpr {
        variant,
        inner: inner_expr,
        span: None,
    })
}

fn parse_evidence_block(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut items = Vec::new();
    for item_pair in pair.into_inner() {
        if item_pair.as_rule() == Rule::evidence_item {
            let mut inner = item_pair.into_inner();
            let obs = parse_expr(inner.next().unwrap())?;
            let effect = parse_expr(inner.next().unwrap())?;
            items.push(EvidenceItem {
                observation: obs,
                effect,
            });
        }
    }
    Ok(Expr::EvidenceBlock {
        items,
        span: None,
    })
}

fn parse_array(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let elements: Result<Vec<_>, _> = pair.into_inner().map(parse_expr).collect();
    Ok(Expr::Array {
        elements: elements?,
        span: None,
    })
}

fn parse_struct(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let name = Ident(inner.next().unwrap().as_str().to_string());
    let mut fields = Vec::new();
    for field_pair in inner {
        if field_pair.as_rule() == Rule::struct_field {
            let mut field_inner = field_pair.into_inner();
            let key = Ident(field_inner.next().unwrap().as_str().to_string());
            let value = parse_expr(field_inner.next().unwrap())?;
            fields.push((key, value));
        }
    }
    Ok(Expr::Struct {
        name,
        fields,
        span: None,
    })
}

fn parse_match(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let scrutinee = Box::new(parse_expr(inner.next().unwrap())?);
    let mut arms = Vec::new();

    for arm_pair in inner {
        if arm_pair.as_rule() == Rule::match_arm {
            let mut arm_inner = arm_pair.into_inner();
            let pattern = parse_pattern(arm_inner.next().unwrap())?;
            let body = parse_expr(arm_inner.next().unwrap())?;
            arms.push(MatchArm {
                pattern,
                body,
                span: None,
            });
        }
    }

    Ok(Expr::Match {
        scrutinee,
        arms,
        span: None,
    })
}

fn parse_pattern(pair: Pair<Rule>) -> Result<Pattern, ParseError> {
    match pair.as_rule() {
        Rule::pattern => {
            let inner = pair.into_inner().next().unwrap();
            parse_pattern(inner)
        }
        Rule::wildcard => Ok(Pattern::Wildcard),
        Rule::guard_pattern => {
            let mut inner = pair.into_inner();
            let binding = Ident(inner.next().unwrap().as_str().to_string());
            let condition_pair = inner.next().unwrap();
            let mut cond_inner = condition_pair.into_inner();
            let left = Ident(cond_inner.next().unwrap().as_str().to_string());
            let op_str = cond_inner.next().unwrap().as_str();
            let op = match op_str {
                ">" => ComparisonOp::Gt,
                "<" => ComparisonOp::Lt,
                ">=" => ComparisonOp::Gte,
                "<=" => ComparisonOp::Lte,
                "==" => ComparisonOp::Eq,
                "!=" => ComparisonOp::Neq,
                _ => unreachable!(),
            };
            let right = parse_expr(cond_inner.next().unwrap())?;
            Ok(Pattern::Guard {
                binding,
                condition: GuardCondition { left, op, right },
            })
        }
        Rule::ident => Ok(Pattern::Ident(Ident(pair.as_str().to_string()))),
        Rule::literal => {
            let inner = pair.into_inner().next().unwrap();
            match inner.as_rule() {
                Rule::float_literal => Ok(Pattern::Literal(Literal::Float(
                    inner.as_str().parse().unwrap(),
                ))),
                Rule::int_literal => Ok(Pattern::Literal(Literal::Int(
                    inner.as_str().parse().unwrap(),
                ))),
                _ => Ok(Pattern::Ident(Ident(inner.as_str().to_string()))),
            }
        }
        _ => Err(ParseError::Syntax {
            line: 0,
            col: 0,
            message: format!("unexpected pattern rule: {:?}", pair.as_rule()),
        }),
    }
}

pub fn parse_pipe_chain(pair: Pair<Rule>) -> Result<Expr, ParseError> {
    let mut inner = pair.into_inner();
    let first = parse_expr(inner.next().unwrap())?;
    let mut steps = vec![];

    while let Some(conn_pair) = inner.next() {
        let connective = match conn_pair.as_str() {
            "|>" => Connective::Pipe,
            "->" => Connective::Transform,
            "||>" => Connective::FanOut,
            "<|" => Connective::Aggregate,
            "~>" => Connective::Tentative,
            "!>" => Connective::ErrChannel,
            "?>" => Connective::Fallible,
            "@>" => Connective::Store,
            "<@" => Connective::Retrieve,
            _ => {
                return Err(ParseError::Syntax {
                    line: 0,
                    col: 0,
                    message: format!("unknown connective: {}", conn_pair.as_str()),
                });
            }
        };

        if let Some(expr_pair) = inner.next() {
            steps.push((connective, parse_expr(expr_pair)?));
        }
    }

    if steps.is_empty() {
        Ok(first)
    } else {
        Ok(Expr::PipeChain {
            steps: std::iter::once((Connective::Pipe, first))
                .chain(steps)
                .collect(),
            span: None,
        })
    }
}
```

- [ ] **Step 5: Implement statement parser**

`src/parser/statements.rs`:
```rust
use pest::iterators::Pair;

use crate::ast::common::*;
use crate::errors::ParseError;
use crate::grammar::Rule;

use super::expressions::parse_expr;
use super::metadata::parse_metadata;
use super::types::parse_type_annotation;

pub fn parse_statement(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::let_binding => parse_let_binding(inner),
        Rule::match_expr => {
            let expr = parse_expr(inner)?;
            Ok(Statement::ExprStatement { expr, span: None })
        }
        Rule::pipe_chain_stmt => {
            let chain = inner.into_inner().next().unwrap();
            let expr = parse_expr(chain)?;
            Ok(Statement::ExprStatement { expr, span: None })
        }
        Rule::assertion => parse_assertion(inner),
        Rule::comment => {
            // Skip comments in AST
            Ok(Statement::ExprStatement {
                expr: Expr::Literal(Literal::Str("// comment".to_string())),
                span: None,
            })
        }
        _ => Err(ParseError::Syntax {
            line: 0,
            col: 0,
            message: format!("unexpected statement rule: {:?}", inner.as_rule()),
        }),
    }
}

fn parse_let_binding(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    let mut inner = pair.into_inner();
    let name = Ident(inner.next().unwrap().as_str().to_string());

    let mut type_ann = None;
    let mut value = None;
    let mut metadata = None;

    for part in inner {
        match part.as_rule() {
            Rule::type_annotation => {
                type_ann = Some(parse_type_annotation(part)?);
            }
            Rule::metadata => {
                metadata = Some(parse_metadata(part)?);
            }
            _ => {
                if value.is_none() {
                    value = Some(parse_expr(part)?);
                }
            }
        }
    }

    Ok(Statement::Let {
        name,
        type_ann,
        value: value.ok_or(ParseError::Syntax {
            line: 0,
            col: 0,
            message: "let binding missing value".to_string(),
        })?,
        metadata,
        span: None,
    })
}

fn parse_assertion(pair: Pair<Rule>) -> Result<Statement, ParseError> {
    let mut inner = pair.into_inner();
    let kw = inner.next().unwrap().as_str();
    let kind = match kw {
        "assert" => AssertionKind::Assert,
        "hedge" => AssertionKind::Hedge,
        "suspend" => AssertionKind::Suspend,
        "reject" => AssertionKind::Reject,
        "emit" => AssertionKind::Emit,
        _ => unreachable!(),
    };

    let mut args = Vec::new();
    let mut metadata = None;
    for part in inner {
        match part.as_rule() {
            Rule::metadata => {
                metadata = Some(parse_metadata(part)?);
            }
            _ => {
                args.push(parse_expr(part)?);
            }
        }
    }

    Ok(Statement::Assertion {
        kind,
        args,
        metadata,
        span: None,
    })
}
```

- [ ] **Step 6: Implement type annotation parser**

`src/parser/types.rs`:
```rust
use pest::iterators::Pair;

use crate::ast::common::TypeAnnotation;
use crate::ast::common::TypeParam;
use crate::errors::ParseError;
use crate::grammar::Rule;

pub fn parse_type_annotation(pair: Pair<Rule>) -> Result<TypeAnnotation, ParseError> {
    let inner = pair.into_inner().next().unwrap();
    match inner.as_rule() {
        Rule::generic_type => {
            let mut parts = inner.into_inner();
            let base = parts.next().unwrap().as_str().to_string();
            let params_pair = parts.next().unwrap();
            let mut params = Vec::new();
            for param in params_pair.into_inner() {
                params.push(parse_type_param(param)?);
            }
            Ok(TypeAnnotation::Generic { base, params })
        }
        Rule::simple_type | Rule::ident => {
            Ok(TypeAnnotation::Simple(inner.as_str().to_string()))
        }
        _ => Ok(TypeAnnotation::Simple(inner.as_str().to_string())),
    }
}

fn parse_type_param(pair: Pair<Rule>) -> Result<TypeParam, ParseError> {
    match pair.as_rule() {
        Rule::type_param => {
            let inner = pair.into_inner().next().unwrap();
            parse_type_param(inner)
        }
        Rule::float_literal => Ok(TypeParam::Float(pair.as_str().parse().unwrap())),
        Rule::lifetime => {
            let name = pair.into_inner().next().unwrap().as_str().to_string();
            Ok(TypeParam::Lifetime(name))
        }
        Rule::type_annotation => {
            Ok(TypeParam::Type(Box::new(parse_type_annotation(pair)?)))
        }
        Rule::ident => Ok(TypeParam::Ident(pair.as_str().to_string())),
        _ => Ok(TypeParam::Ident(pair.as_str().to_string())),
    }
}
```

- [ ] **Step 7: Implement block parser**

`src/parser/blocks.rs`:
```rust
use pest::iterators::Pair;

use crate::ast::phases::{Phase, PhaseBlock, ReasoningMode, Trace};
use crate::ast::common::Span;
use crate::errors::ParseError;
use crate::grammar::Rule;

use super::statements::parse_statement;

pub fn parse_trace(pair: Pair<Rule>) -> Result<Trace, ParseError> {
    let mut phases = Vec::new();

    for inner in pair.into_inner() {
        match inner.as_rule() {
            Rule::phase_block => {
                phases.push(parse_phase_block(inner)?);
            }
            Rule::EOI => {}
            _ => {}
        }
    }

    Ok(Trace {
        phases,
        span: None,
    })
}

fn parse_phase_block(pair: Pair<Rule>) -> Result<PhaseBlock, ParseError> {
    let mut inner = pair.into_inner();

    // Parse phase attribute
    let attr_pair = inner.next().unwrap();
    let phase_name = attr_pair.into_inner().next().unwrap().as_str();
    let phase = match phase_name {
        "Frame" => Phase::Frame,
        "Explore" => Phase::Explore,
        "Verify" => Phase::Verify,
        "Decide" => Phase::Decide,
        other => {
            return Err(ParseError::Syntax {
                line: 0,
                col: 0,
                message: format!("unknown phase: {}", other),
            });
        }
    };

    // Parse impl block or bare block
    let block_pair = inner.next().unwrap();
    let (impl_mode, statements) = match block_pair.as_rule() {
        Rule::impl_block => {
            let mut block_inner = block_pair.into_inner();
            let mode_str = block_inner.next().unwrap().as_str();
            let mode = match mode_str {
                "Deductive" => ReasoningMode::Deductive,
                "Abductive" => ReasoningMode::Abductive,
                "Analogical" => ReasoningMode::Analogical,
                _ => unreachable!(),
            };
            let stmts: Result<Vec<_>, _> = block_inner.map(parse_statement).collect();
            (Some(mode), stmts?)
        }
        Rule::bare_block => {
            let stmts: Result<Vec<_>, _> = block_pair.into_inner().map(parse_statement).collect();
            (None, stmts?)
        }
        _ => unreachable!(),
    };

    Ok(PhaseBlock {
        phase,
        impl_mode,
        statements,
        span: None,
    })
}
```

- [ ] **Step 8: Wire up the parser module root**

Update `src/parser/mod.rs`:
```rust
pub mod expressions;
pub mod statements;
pub mod metadata;
pub mod types;
pub mod blocks;

use pest::Parser;

use crate::ast::phases::Trace;
use crate::errors::ParseError;
use crate::grammar::{RLangParser, Rule};

pub fn parse(source: &str) -> Result<Trace, ParseError> {
    let pairs = RLangParser::parse(Rule::trace, source).map_err(|e| {
        ParseError::Syntax {
            line: e.line_col.map_or(0, |lc| match lc {
                pest::error::LineColLocation::Pos((l, _)) => l,
                pest::error::LineColLocation::Span((l, _), _) => l,
            }),
            col: e.line_col.map_or(0, |lc| match lc {
                pest::error::LineColLocation::Pos((_, c)) => c,
                pest::error::LineColLocation::Span((_, c), _) => c,
            }),
            message: e.to_string(),
        }
    })?;

    let trace_pair = pairs.into_iter().next().unwrap();
    blocks::parse_trace(trace_pair)
}
```

- [ ] **Step 9: Run parser tests**

Run: `cargo test --test parser_tests 2>&1`
Expected: All parser tests pass.

- [ ] **Step 10: Commit**

```bash
git add src/parser/ tests/parser_tests.rs
git commit -m "feat: parser converts Pest pairs to typed AST for all 4 layers"
```

---

## Task 5: Validator — Phase Ordering and Metadata Completeness

**Files:**
- Modify: `src/validator/mod.rs`
- Modify: `src/validator/phases.rs`
- Modify: `src/validator/metadata.rs`
- Modify: `src/validator/bounds.rs`
- Create: `tests/validator_tests.rs`

- [ ] **Step 1: Write validator tests**

`tests/validator_tests.rs`:
```rust
use rlang::ast::phases::*;
use rlang::ast::common::*;
use rlang::validator::validate;

fn make_trace(phases: Vec<Phase>) -> Trace {
    Trace {
        phases: phases
            .into_iter()
            .map(|p| PhaseBlock {
                phase: p,
                impl_mode: None,
                statements: vec![],
                span: None,
            })
            .collect(),
        span: None,
    }
}

#[test]
fn test_valid_phase_order() {
    let trace = make_trace(vec![Phase::Frame, Phase::Explore, Phase::Verify, Phase::Decide]);
    assert!(validate(&trace).is_ok());
}

#[test]
fn test_missing_frame() {
    let trace = make_trace(vec![Phase::Explore, Phase::Verify, Phase::Decide]);
    let result = validate(&trace);
    assert!(result.is_err());
}

#[test]
fn test_missing_verify() {
    let trace = make_trace(vec![Phase::Frame, Phase::Explore, Phase::Decide]);
    let result = validate(&trace);
    assert!(result.is_err());
}

#[test]
fn test_missing_decide() {
    let trace = make_trace(vec![Phase::Frame, Phase::Explore, Phase::Verify]);
    let result = validate(&trace);
    assert!(result.is_err());
}

#[test]
fn test_duplicate_frame() {
    let trace = make_trace(vec![Phase::Frame, Phase::Frame, Phase::Explore, Phase::Verify, Phase::Decide]);
    let result = validate(&trace);
    assert!(result.is_err());
}

#[test]
fn test_valid_rebloom() {
    // Verify -> Explore -> Verify is allowed (rebloom)
    let trace = make_trace(vec![
        Phase::Frame, Phase::Explore, Phase::Verify,
        Phase::Explore, Phase::Verify, Phase::Decide,
    ]);
    assert!(validate(&trace).is_ok());
}

#[test]
fn test_excessive_rebloom() {
    // More than 3 reblooms should fail
    let mut phases = vec![Phase::Frame, Phase::Explore, Phase::Verify];
    for _ in 0..4 {
        phases.push(Phase::Explore);
        phases.push(Phase::Verify);
    }
    phases.push(Phase::Decide);
    let trace = make_trace(phases);
    let result = validate(&trace);
    assert!(result.is_err());
}

#[test]
fn test_backward_phase_invalid() {
    // Cannot go from Decide back to Frame
    let trace = make_trace(vec![Phase::Frame, Phase::Explore, Phase::Verify, Phase::Decide, Phase::Frame]);
    let result = validate(&trace);
    assert!(result.is_err());
}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cargo test --test validator_tests 2>&1 | head -5`
Expected: Fails because validator returns `todo!()`.

- [ ] **Step 3: Implement phase validator**

`src/validator/phases.rs`:
```rust
use crate::ast::phases::{Phase, Trace};
use crate::errors::ValidationError;

const MAX_REBLOOM: usize = 3;

pub fn validate_phases(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();
    let phases: Vec<Phase> = trace.phases.iter().map(|p| p.phase).collect();

    if phases.is_empty() {
        errors.push(ValidationError::Phase {
            message: "trace has no phases".to_string(),
        });
        return Err(errors);
    }

    // Must start with Frame
    if phases[0] != Phase::Frame {
        errors.push(ValidationError::Phase {
            message: format!(
                "trace must start with Frame, found {:?}",
                phases[0]
            ),
        });
    }

    // Must end with Decide
    if *phases.last().unwrap() != Phase::Decide {
        errors.push(ValidationError::Phase {
            message: format!(
                "trace must end with Decide, found {:?}",
                phases.last().unwrap()
            ),
        });
    }

    // Must contain all four phases
    let has_frame = phases.contains(&Phase::Frame);
    let has_explore = phases.contains(&Phase::Explore);
    let has_verify = phases.contains(&Phase::Verify);
    let has_decide = phases.contains(&Phase::Decide);

    if !has_frame {
        errors.push(ValidationError::Phase {
            message: "trace missing required Frame phase".to_string(),
        });
    }
    if !has_explore {
        errors.push(ValidationError::Phase {
            message: "trace missing required Explore phase".to_string(),
        });
    }
    if !has_verify {
        errors.push(ValidationError::Phase {
            message: "trace missing required Verify phase".to_string(),
        });
    }
    if !has_decide {
        errors.push(ValidationError::Phase {
            message: "trace missing required Decide phase".to_string(),
        });
    }

    // Frame must appear exactly once
    let frame_count = phases.iter().filter(|&&p| p == Phase::Frame).count();
    if frame_count > 1 {
        errors.push(ValidationError::Phase {
            message: format!("Frame phase must appear exactly once, found {}", frame_count),
        });
    }

    // Decide must appear exactly once
    let decide_count = phases.iter().filter(|&&p| p == Phase::Decide).count();
    if decide_count > 1 {
        errors.push(ValidationError::Phase {
            message: format!("Decide phase must appear exactly once, found {}", decide_count),
        });
    }

    // Validate transitions
    let mut rebloom_count = 0;
    for window in phases.windows(2) {
        let (from, to) = (window[0], window[1]);
        let valid = match (from, to) {
            (Phase::Frame, Phase::Explore) => true,
            (Phase::Explore, Phase::Verify) => true,
            (Phase::Verify, Phase::Decide) => true,
            // Rebloom: Verify -> Explore is allowed (bounded)
            (Phase::Verify, Phase::Explore) => {
                rebloom_count += 1;
                if rebloom_count > MAX_REBLOOM {
                    errors.push(ValidationError::Phase {
                        message: format!(
                            "exceeded maximum rebloom count of {} (Verify -> Explore)",
                            MAX_REBLOOM
                        ),
                    });
                    false
                } else {
                    true
                }
            }
            _ => false,
        };

        if !valid && rebloom_count <= MAX_REBLOOM {
            errors.push(ValidationError::Phase {
                message: format!(
                    "invalid phase transition: {:?} -> {:?}",
                    from, to
                ),
            });
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}
```

- [ ] **Step 4: Implement metadata validator**

`src/validator/metadata.rs`:
```rust
use crate::ast::common::{Expr, Statement};
use crate::ast::phases::Trace;
use crate::errors::ValidationError;

/// In strict mode, every belief expression must have a confidence value (p:).
pub fn validate_metadata(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();

    for phase in &trace.phases {
        for stmt in &phase.statements {
            check_statement_metadata(stmt, &mut errors);
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn check_statement_metadata(stmt: &Statement, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { metadata, name, .. } => {
            // Let bindings for beliefs should have confidence
            if let Some(meta) = metadata {
                if meta.confidence.is_none() {
                    errors.push(ValidationError::Metadata {
                        message: format!(
                            "let binding '{}' has metadata but missing required confidence (p:) field",
                            name.0
                        ),
                    });
                }
            }
            // Note: let bindings without metadata (e.g., evidence blocks) are OK
        }
        _ => {}
    }
}
```

- [ ] **Step 5: Wire up validator module root**

`src/validator/mod.rs`:
```rust
pub mod phases;
pub mod metadata;
pub mod bounds;
pub mod resources;
pub mod types;

use crate::ast::phases::Trace;
use crate::errors::ValidationError;

pub fn validate(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut all_errors = Vec::new();

    if let Err(errors) = phases::validate_phases(trace) {
        all_errors.extend(errors);
    }

    if let Err(errors) = metadata::validate_metadata(trace) {
        all_errors.extend(errors);
    }

    // Future: bounds, resources, types validators

    if all_errors.is_empty() {
        Ok(())
    } else {
        Err(all_errors)
    }
}
```

- [ ] **Step 6: Run validator tests**

Run: `cargo test --test validator_tests 2>&1`
Expected: All validator tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/validator/ tests/validator_tests.rs
git commit -m "feat: validator for phase ordering and metadata completeness"
```

---

## Task 6: Test Fixtures and Integration Tests

**Files:**
- Create: `tests/fixtures/valid/simple_belief.rl`
- Create: `tests/fixtures/valid/full_deploy_trace.rl`
- Create: `tests/fixtures/invalid/missing_confidence.rl`
- Create: `tests/fixtures/invalid/skip_verify_phase.rl`
- Create: `tests/integration_tests.rs`

- [ ] **Step 1: Create valid fixture — simple belief trace**

`tests/fixtures/valid/simple_belief.rl`:
```rust
#[phase(Frame)]
{
    let rain: blf<0.95> = obs(rain) | p:0.95 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        obs(dark_clouds) => sup(rain, +0.05),
    ];
    rain |> resolve(ev) -> Ok(confirmed);
}

#[phase(Verify)]
{
    req(rain, obs(rain)) |> verify(rain) -> Ok(());
}

#[phase(Decide)]
{
    match conf(rain) {
        c if c > 0.85 => assert(rain),
        _ => hedge(rain),
    }
}
```

- [ ] **Step 2: Create valid fixture — full deploy trace (from spec)**

`tests/fixtures/valid/full_deploy_trace.rl`:
```rust
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback) | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic) | p:0.90 | ep:direct | src:obs(metrics) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests   => sup(deploy, +0.15),
        risk    => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];

    let deploy_blf = enbl(fix, resolve(bug)) |> resolve(ev) -> Ok(blf_resolved);
}

#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy),
        _ => reject(deploy),
    }
}
```

- [ ] **Step 3: Create invalid fixture — skip verify phase**

`tests/fixtures/invalid/skip_verify_phase.rl`:
```rust
#[phase(Frame)]
{
    let x = obs(data) | p:0.9 | ep:direct | src:Given | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let y = obs(more) | p:0.5 | ep:infer | src:Given | scope:loc | t:fresh;
}

#[phase(Decide)]
{
    assert(x);
}
```

- [ ] **Step 4: Write integration tests**

`tests/integration_tests.rs`:
```rust
use std::fs;
use rlang::parser::parse;
use rlang::validator::validate;

fn parse_and_validate(path: &str) -> Result<(), String> {
    let source = fs::read_to_string(path)
        .map_err(|e| format!("cannot read {}: {}", path, e))?;
    let trace = parse(&source)
        .map_err(|e| format!("parse error in {}: {}", path, e))?;
    validate(&trace)
        .map_err(|errors| {
            let msgs: Vec<String> = errors.iter().map(|e| e.to_string()).collect();
            format!("validation errors in {}: {}", path, msgs.join("; "))
        })
}

#[test]
fn test_valid_simple_belief() {
    parse_and_validate("tests/fixtures/valid/simple_belief.rl")
        .expect("simple_belief.rl should be valid");
}

#[test]
fn test_valid_full_deploy() {
    parse_and_validate("tests/fixtures/valid/full_deploy_trace.rl")
        .expect("full_deploy_trace.rl should be valid");
}

#[test]
fn test_invalid_skip_verify() {
    let result = parse_and_validate("tests/fixtures/invalid/skip_verify_phase.rl");
    assert!(result.is_err(), "skip_verify_phase.rl should fail validation");
    let err = result.unwrap_err();
    assert!(err.contains("Verify"), "error should mention missing Verify phase: {}", err);
}
```

- [ ] **Step 5: Run integration tests**

Run: `cargo test --test integration_tests 2>&1`
Expected: All integration tests pass.

- [ ] **Step 6: Run full test suite**

Run: `cargo test 2>&1`
Expected: All tests pass across grammar, AST, parser, validator, and integration.

- [ ] **Step 7: Commit**

```bash
git add tests/ examples/
git commit -m "feat: test fixtures and integration tests for parse + validate pipeline"
```

---

## Task 7: CLI Polish and Error Reporting

**Files:**
- Modify: `src/main.rs`
- Modify: `src/errors/diagnostic.rs`
- Create: `examples/deploy_decision.rl`

- [ ] **Step 1: Create the example file from the spec**

`examples/deploy_decision.rl`:
```rust
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback_plan) | p:0.85 | ep:direct | src:obs(infra_check) | scope:loc | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic) | p:0.90 | ep:direct | src:obs(metrics) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests   => sup(deploy, +0.15),
        risk    => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];

    let deploy_blf = enbl(fix, resolve(bug)) |> resolve(ev) -> Ok(blf_resolved);
}

#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy, cond: enbl(rollback_plan, deploy)),
        _ => reject(deploy),
    }
}
```

- [ ] **Step 2: Implement diagnostic error formatting**

`src/errors/diagnostic.rs`:
```rust
use super::{ParseError, ValidationError};
use std::fmt;

pub struct Diagnostic<'a> {
    pub source: &'a str,
    pub filename: &'a str,
}

impl<'a> Diagnostic<'a> {
    pub fn format_parse_error(&self, err: &ParseError) -> String {
        match err {
            ParseError::Syntax { line, col, message } => {
                let line_content = self.source.lines().nth(line.saturating_sub(1)).unwrap_or("");
                format!(
                    "error[E0001]: {}\n --> {}:{}:{}\n  |\n{} | {}\n  | {}^\n",
                    message,
                    self.filename,
                    line,
                    col,
                    line,
                    line_content,
                    " ".repeat(col.saturating_sub(1))
                )
            }
            ParseError::UnexpectedToken { expected, found } => {
                format!(
                    "error[E0002]: expected {}, found {}\n --> {}\n",
                    expected, found, self.filename
                )
            }
        }
    }

    pub fn format_validation_error(&self, err: &ValidationError) -> String {
        match err {
            ValidationError::Phase { message } => {
                format!("error[V0001]: phase violation: {}\n --> {}\n", message, self.filename)
            }
            ValidationError::Metadata { message } => {
                format!("error[V0002]: metadata violation: {}\n --> {}\n", message, self.filename)
            }
            ValidationError::Bounds { message } => {
                format!("error[V0003]: bounds violation: {}\n --> {}\n", message, self.filename)
            }
            ValidationError::Resource { message } => {
                format!("error[V0004]: resource violation: {}\n --> {}\n", message, self.filename)
            }
            ValidationError::Type { message } => {
                format!("error[V0005]: type error: {}\n --> {}\n", message, self.filename)
            }
        }
    }
}
```

- [ ] **Step 3: Verify CLI works end-to-end**

Run: `cargo run -- examples/deploy_decision.rl`
Expected: `OK: 4 phases, N statements`

Run: `cargo run -- examples/deploy_decision.rl --ast | head -20`
Expected: JSON AST output

Run: `cargo run -- tests/fixtures/invalid/skip_verify_phase.rl`
Expected: Validation error about missing Verify phase, exit code 1

- [ ] **Step 4: Commit**

```bash
git add examples/ src/errors/diagnostic.rs src/main.rs
git commit -m "feat: CLI with Rust-style error diagnostics"
```

---

## Summary

| Task | What it builds | Dependencies |
|------|---------------|-------------|
| 1 | Project scaffold, Cargo.toml, module stubs | None |
| 2 | PEG grammar (`.pest` file) | Task 1 |
| 3 | Complete AST type definitions | Task 1 |
| 4 | Parser (Pest -> AST) | Tasks 2, 3 |
| 5 | Validator (phase ordering, metadata) | Tasks 3, 4 |
| 6 | Test fixtures + integration tests | Tasks 4, 5 |
| 7 | CLI + error reporting | Tasks 5, 6 |

**Parallelism:** Tasks 2 and 3 can run in parallel. Task 4 depends on both. Tasks 5 and 6 depend on 4. Task 7 depends on 5+6.

```
Task 1 (scaffold)
  ├── Task 2 (grammar)  ──┐
  └── Task 3 (AST)     ──┤
                          └── Task 4 (parser)
                                ├── Task 5 (validator)
                                └── Task 6 (fixtures + integration)
                                      └── Task 7 (CLI + diagnostics)
```
