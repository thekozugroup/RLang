//! Semantic analysis for RLang ASTs.
//!
//! This module performs deeper validation beyond phase ordering and metadata:
//! - Operator arity checking (each operator has a defined argument count)
//! - Confidence range validation (0.0..=1.0)
//! - Evidence block structure validation (items must use sup/wkn/neut)
//! - Decide-phase match arm validation (arms must use assert/hedge/suspend/reject)

use crate::ast::common::*;
use crate::ast::phases::{Phase, Trace};
use crate::errors::ValidationError;

/// Expected argument count for each operator.
/// Returns `None` for variadic operators that accept any count.
pub fn operator_arity(op: Operator) -> Option<usize> {
    match op {
        // Layer 1: Epistemic — binary relations
        Operator::Cause => Some(2),
        Operator::Prvnt => Some(2),
        Operator::Enbl  => Some(2),
        Operator::Req   => Some(2),
        Operator::Sim   => Some(2),
        Operator::Confl => Some(2),
        Operator::Cncl  => Some(2),
        Operator::Cntns => Some(2),
        Operator::Isa   => Some(2),

        // Layer 1: Epistemic — unary
        Operator::Obs  => Some(1),
        Operator::Goal => Some(1),

        // Layer 1: Epistemic — ternary (thing, from, to)
        Operator::Chng => Some(3),

        // Layer 1: Epistemic — variadic sequence
        Operator::Seq => None,

        // Layer 1: Evidence modifiers (claim, weight)
        Operator::Sup  => Some(2),
        Operator::Wkn  => Some(2),
        Operator::Neut => Some(2),

        // Layer 1: Resolution — when used in pipe chains the first arg is
        // implicit (piped in), so the explicit arg count is 1. Allow 1..=2
        // to support both standalone and piped usage.
        Operator::Resolve => None, // 1 (piped) or 2 (standalone)
        Operator::Conf    => None, // 1 (piped) or 2 (standalone)
        Operator::Decay   => None, // 1 (piped) or 2 (standalone)
        Operator::Refresh => None, // 1 (piped) or 2 (standalone)

        // Layer 2: Motivational
        Operator::Dcmp       => Some(2), // (goal, subgoals)
        Operator::Prioritize => Some(2), // (goals, criteria)
        Operator::Select     => Some(1), // (goal)
        Operator::Replan     => Some(2), // (intent, reason)

        // Layer 3: Operational
        Operator::Exec      => Some(1), // (action)
        Operator::Inv       => Some(2), // (tool, args)
        Operator::Pcv       => Some(1), // (observation)
        Operator::Rmb       => Some(2), // (key, value)
        Operator::Rcl       => Some(1), // (query)
        Operator::Forget    => Some(1), // (key)
        Operator::Bt        => Some(1), // (reflection)
        Operator::Verify    => Some(1), // (result)
        Operator::RetryWith => Some(2), // (attempt, new_data)

        // Layer 4: Communicative
        Operator::Dlg             => Some(2), // (agent, task)
        Operator::Msg             => Some(2), // (to, content)
        Operator::Discover        => Some(1), // (capability)
        Operator::MatchCapability => Some(2), // (need, agent)
        Operator::Negotiate       => Some(2), // (terms, counter)
        Operator::Cancel          => Some(1), // (task)
        Operator::Poll            => Some(1), // (task)
        Operator::Subscribe       => Some(2), // (source, filter)
        Operator::Cfp             => Some(1), // (task_spec)
        Operator::Propose         => Some(2), // (to, offer)
        Operator::AcceptProposal  => Some(1), // (proposal)
        Operator::RejectProposal  => Some(1), // (proposal)
        Operator::Inform          => Some(2), // (to, info)
        Operator::QueryIf         => Some(2), // (to, question)
        Operator::Agree           => Some(1), // (proposal)
        Operator::Refuse          => Some(1), // (request)
        Operator::ResolveConflict => Some(2), // (conflict, strategy)

        // Built-in assertions — variadic
        Operator::Assert  => None,
        Operator::Hedge   => None,
        Operator::Suspend => None,
        Operator::Reject  => None,
        Operator::Emit    => None,
    }
}

/// Run all semantic checks on a trace.
pub fn validate_semantics(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();

    for block in &trace.phases {
        for stmt in &block.statements {
            check_statement(stmt, block.phase, &mut errors);
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn check_statement(stmt: &Statement, phase: Phase, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { value, metadata, .. } => {
            check_expr(value, phase, errors);
            if let Some(meta) = metadata {
                check_confidence_range(meta, errors);
            }
        }
        Statement::ExprStatement { expr, .. } => {
            check_expr(expr, phase, errors);
        }
        Statement::Assertion { metadata, .. } => {
            if let Some(meta) = metadata {
                check_confidence_range(meta, errors);
            }
        }
    }
}

fn check_expr(expr: &Expr, phase: Phase, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::OperatorCall { name, args, .. } => {
            check_operator_arity(*name, args.len(), errors);
            for arg in args {
                check_expr(arg, phase, errors);
            }
        }
        Expr::FnCall { args, .. } => {
            for arg in args {
                check_expr(arg, phase, errors);
            }
        }
        Expr::PipeChain { steps, .. } => {
            for (_, step_expr) in steps {
                check_expr(step_expr, phase, errors);
            }
        }
        Expr::Match { scrutinee, arms, .. } => {
            check_expr(scrutinee, phase, errors);
            if phase == Phase::Decide {
                check_decide_match_arms(arms, errors);
            }
            for arm in arms {
                check_expr(&arm.body, phase, errors);
            }
        }
        Expr::EvidenceBlock { items, .. } => {
            check_evidence_items(items, errors);
            for item in items {
                check_expr(&item.observation, phase, errors);
                check_expr(&item.effect, phase, errors);
            }
        }
        Expr::Array { elements, .. } => {
            for el in elements {
                check_expr(el, phase, errors);
            }
        }
        Expr::Struct { fields, .. } => {
            for (_, val) in fields {
                check_expr(val, phase, errors);
            }
        }
        Expr::WithMetadata { expr, metadata, .. } => {
            check_expr(expr, phase, errors);
            check_confidence_range(metadata, errors);
        }
        Expr::ResultExpr { inner, .. } => {
            if let Some(inner) = inner {
                check_expr(inner, phase, errors);
            }
        }
        // Literals and identifiers need no semantic checks
        Expr::Literal(_) | Expr::Ident(_) => {}
    }
}

/// Check that an operator call has the correct number of arguments.
fn check_operator_arity(op: Operator, arg_count: usize, errors: &mut Vec<ValidationError>) {
    if let Some(expected) = operator_arity(op) {
        if arg_count != expected {
            errors.push(ValidationError::Semantic {
                message: format!(
                    "operator {:?} expects {} argument(s), got {}",
                    op, expected, arg_count
                ),
            });
        }
    }
}

/// Check that confidence values are in range 0.0..=1.0.
fn check_confidence_range(meta: &Metadata, errors: &mut Vec<ValidationError>) {
    if let Some(conf) = meta.confidence {
        if !(0.0..=1.0).contains(&conf) {
            errors.push(ValidationError::Semantic {
                message: format!(
                    "confidence value {} is out of range 0.0..=1.0",
                    conf
                ),
            });
        }
    }
}

/// Check that evidence items use sup/wkn/neut operators on the effect side.
fn check_evidence_items(items: &[EvidenceItem], errors: &mut Vec<ValidationError>) {
    for item in items {
        match &item.effect {
            Expr::OperatorCall { name, .. }
                if matches!(name, Operator::Sup | Operator::Wkn | Operator::Neut) => {}
            _ => {
                errors.push(ValidationError::Semantic {
                    message: "evidence item effect must use sup(), wkn(), or neut() operator"
                        .to_string(),
                });
            }
        }
    }
}

/// Check that match arms in a Decide phase use assert/hedge/suspend/reject.
fn check_decide_match_arms(arms: &[MatchArm], errors: &mut Vec<ValidationError>) {
    for arm in arms {
        match &arm.body {
            Expr::OperatorCall { name, .. }
                if matches!(
                    name,
                    Operator::Assert | Operator::Hedge | Operator::Suspend | Operator::Reject
                ) => {}
            // Also accept assertion-style fn calls by name
            Expr::FnCall { name, .. }
                if matches!(
                    name.0.as_str(),
                    "assert" | "hedge" | "suspend" | "reject"
                ) => {}
            _ => {
                errors.push(ValidationError::Semantic {
                    message:
                        "match arms in Decide phase must use assert(), hedge(), suspend(), or reject()"
                            .to_string(),
                });
            }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_operator_arity_cause() {
        assert_eq!(operator_arity(Operator::Cause), Some(2));
    }

    #[test]
    fn test_operator_arity_obs() {
        assert_eq!(operator_arity(Operator::Obs), Some(1));
    }

    #[test]
    fn test_operator_arity_chng() {
        assert_eq!(operator_arity(Operator::Chng), Some(3));
    }

    #[test]
    fn test_operator_arity_seq_variadic() {
        assert_eq!(operator_arity(Operator::Seq), None);
    }
}
