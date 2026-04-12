use crate::ast::common::{Expr, Operator, Statement};
use crate::ast::phases::{Phase, Trace};
use crate::errors::ValidationError;

const MAX_BACKTRACK: usize = 3;

/// Validate bounded backtracking rules:
/// - Backtrack (Bt) operators only allowed in Verify or Explore phases
/// - Total backtrack count per trace must not exceed MAX_BACKTRACK
/// - Match expressions in Decide phase may only use assert/hedge/suspend/reject
pub fn validate_bounds(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();
    let mut total_bt_count: usize = 0;

    for block in &trace.phases {
        for stmt in &block.statements {
            count_backtracks_in_statement(stmt, &mut total_bt_count);
            check_backtrack_phase(stmt, block.phase, &mut errors);
        }

        // Decide phase: match expressions may only use assert/hedge/suspend/reject
        if block.phase == Phase::Decide {
            for stmt in &block.statements {
                check_decide_match(stmt, &mut errors);
            }
        }
    }

    if total_bt_count > MAX_BACKTRACK {
        errors.push(ValidationError::Bounds {
            message: format!(
                "trace has {} backtrack operations, maximum allowed is {}",
                total_bt_count, MAX_BACKTRACK
            ),
        });
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// Recursively count all Bt operator calls in a statement.
fn count_backtracks_in_statement(stmt: &Statement, count: &mut usize) {
    match stmt {
        Statement::Let { value, .. } => count_backtracks_in_expr(value, count),
        Statement::ExprStatement { expr, .. } => count_backtracks_in_expr(expr, count),
        Statement::Assertion { args, .. } => {
            for arg in args {
                count_backtracks_in_expr(arg, count);
            }
        }
    }
}

fn count_backtracks_in_expr(expr: &Expr, count: &mut usize) {
    match expr {
        Expr::OperatorCall { name, args, .. } => {
            if *name == Operator::Bt {
                *count += 1;
            }
            for arg in args {
                count_backtracks_in_expr(arg, count);
            }
        }
        Expr::FnCall { args, .. } => {
            for arg in args {
                count_backtracks_in_expr(arg, count);
            }
        }
        Expr::PipeChain { steps, .. } => {
            for (_, step_expr) in steps {
                count_backtracks_in_expr(step_expr, count);
            }
        }
        Expr::Match { scrutinee, arms, .. } => {
            count_backtracks_in_expr(scrutinee, count);
            for arm in arms {
                count_backtracks_in_expr(&arm.body, count);
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            count_backtracks_in_expr(inner, count);
        }
        Expr::EvidenceBlock { items, .. } => {
            for item in items {
                count_backtracks_in_expr(&item.observation, count);
                count_backtracks_in_expr(&item.effect, count);
            }
        }
        Expr::Array { elements, .. } => {
            for el in elements {
                count_backtracks_in_expr(el, count);
            }
        }
        Expr::ResultExpr { inner, .. } => {
            if let Some(inner_expr) = inner {
                count_backtracks_in_expr(inner_expr, count);
            }
        }
        Expr::Struct { fields, .. } => {
            for (_, val) in fields {
                count_backtracks_in_expr(val, count);
            }
        }
        Expr::Literal(_) | Expr::Ident(_) => {}
    }
}

/// Check that Bt operators only appear in Verify or Explore phases.
fn check_backtrack_phase(stmt: &Statement, phase: Phase, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { value, .. } => check_bt_phase_expr(value, phase, errors),
        Statement::ExprStatement { expr, .. } => check_bt_phase_expr(expr, phase, errors),
        Statement::Assertion { args, .. } => {
            for arg in args {
                check_bt_phase_expr(arg, phase, errors);
            }
        }
    }
}

fn check_bt_phase_expr(expr: &Expr, phase: Phase, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::OperatorCall { name, args, .. } => {
            if *name == Operator::Bt && phase != Phase::Verify && phase != Phase::Explore {
                errors.push(ValidationError::Bounds {
                    message: format!(
                        "backtrack (bt) operator not allowed in {:?} phase; only Verify or Explore",
                        phase
                    ),
                });
            }
            for arg in args {
                check_bt_phase_expr(arg, phase, errors);
            }
        }
        Expr::FnCall { args, .. } => {
            for arg in args {
                check_bt_phase_expr(arg, phase, errors);
            }
        }
        Expr::PipeChain { steps, .. } => {
            for (_, step_expr) in steps {
                check_bt_phase_expr(step_expr, phase, errors);
            }
        }
        Expr::Match { scrutinee, arms, .. } => {
            check_bt_phase_expr(scrutinee, phase, errors);
            for arm in arms {
                check_bt_phase_expr(&arm.body, phase, errors);
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_bt_phase_expr(inner, phase, errors);
        }
        Expr::EvidenceBlock { items, .. } => {
            for item in items {
                check_bt_phase_expr(&item.observation, phase, errors);
                check_bt_phase_expr(&item.effect, phase, errors);
            }
        }
        Expr::Array { elements, .. } => {
            for el in elements {
                check_bt_phase_expr(el, phase, errors);
            }
        }
        Expr::ResultExpr { inner, .. } => {
            if let Some(inner_expr) = inner {
                check_bt_phase_expr(inner_expr, phase, errors);
            }
        }
        Expr::Struct { fields, .. } => {
            for (_, val) in fields {
                check_bt_phase_expr(val, phase, errors);
            }
        }
        Expr::Literal(_) | Expr::Ident(_) => {}
    }
}

/// In Decide phase, match arms should only use assert/hedge/suspend/reject operators.
fn check_decide_match(stmt: &Statement, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { value, .. } => check_decide_match_expr(value, errors),
        Statement::ExprStatement { expr, .. } => check_decide_match_expr(expr, errors),
        Statement::Assertion { .. } => {
            // Assertions themselves are fine in Decide
        }
    }
}

fn check_decide_match_expr(expr: &Expr, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::Match { arms, .. } => {
            for arm in arms {
                check_decide_arm_body(&arm.body, errors);
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_decide_match_expr(inner, errors);
        }
        _ => {}
    }
}

const DECIDE_ALLOWED_OPS: &[Operator] = &[
    Operator::Assert,
    Operator::Hedge,
    Operator::Suspend,
    Operator::Reject,
];

fn check_decide_arm_body(expr: &Expr, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::OperatorCall { name, .. } => {
            if !DECIDE_ALLOWED_OPS.contains(name) {
                errors.push(ValidationError::Bounds {
                    message: format!(
                        "match arm in Decide phase uses operator {:?}; only assert, hedge, suspend, reject are allowed",
                        name
                    ),
                });
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_decide_arm_body(inner, errors);
        }
        _ => {
            // Non-operator expressions in match arms are OK (e.g., literals, idents)
        }
    }
}
