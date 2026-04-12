use crate::ast::common::{Expr, Operator, Statement};
use crate::ast::connectives::Connective;
use crate::ast::phases::{Phase, Trace};
use crate::errors::ValidationError;

const MAX_DELEGATION_DEPTH: usize = 3;

/// Validate resource conservation rules:
/// - Delegation (Dlg) operators only allowed in Explore or Decide phases
/// - Delegation nesting depth must not exceed MAX_DELEGATION_DEPTH
/// - Pipe chains must not mix incompatible connectives (Store @> followed by ErrChannel !>)
pub fn validate_resources(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();

    for block in &trace.phases {
        for stmt in &block.statements {
            check_delegation_phase(stmt, block.phase, &mut errors);
            check_delegation_depth(stmt, 0, &mut errors);
            check_pipe_compatibility(stmt, &mut errors);
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

/// Check that Dlg operators only appear in Explore or Decide phases.
fn check_delegation_phase(stmt: &Statement, phase: Phase, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { value, .. } => check_dlg_phase_expr(value, phase, errors),
        Statement::ExprStatement { expr, .. } => check_dlg_phase_expr(expr, phase, errors),
        Statement::Assertion { args, .. } => {
            for arg in args {
                check_dlg_phase_expr(arg, phase, errors);
            }
        }
    }
}

fn check_dlg_phase_expr(expr: &Expr, phase: Phase, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::OperatorCall { name, args, .. } => {
            if *name == Operator::Dlg && phase != Phase::Explore && phase != Phase::Decide {
                errors.push(ValidationError::Resource {
                    message: format!(
                        "delegation (dlg) operator not allowed in {:?} phase; only Explore or Decide",
                        phase
                    ),
                });
            }
            for arg in args {
                check_dlg_phase_expr(arg, phase, errors);
            }
        }
        Expr::FnCall { args, .. } => {
            for arg in args {
                check_dlg_phase_expr(arg, phase, errors);
            }
        }
        Expr::PipeChain { steps, .. } => {
            for (_, step_expr) in steps {
                check_dlg_phase_expr(step_expr, phase, errors);
            }
        }
        Expr::Match { scrutinee, arms, .. } => {
            check_dlg_phase_expr(scrutinee, phase, errors);
            for arm in arms {
                check_dlg_phase_expr(&arm.body, phase, errors);
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_dlg_phase_expr(inner, phase, errors);
        }
        Expr::EvidenceBlock { items, .. } => {
            for item in items {
                check_dlg_phase_expr(&item.observation, phase, errors);
                check_dlg_phase_expr(&item.effect, phase, errors);
            }
        }
        Expr::Array { elements, .. } => {
            for el in elements {
                check_dlg_phase_expr(el, phase, errors);
            }
        }
        Expr::ResultExpr { inner, .. } => {
            if let Some(inner_expr) = inner {
                check_dlg_phase_expr(inner_expr, phase, errors);
            }
        }
        Expr::Struct { fields, .. } => {
            for (_, val) in fields {
                check_dlg_phase_expr(val, phase, errors);
            }
        }
        Expr::Literal(_) | Expr::Ident(_) => {}
    }
}

/// Track delegation nesting depth. A Dlg whose argument contains another Dlg increments depth.
fn check_delegation_depth(stmt: &Statement, depth: usize, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { value, .. } => check_dlg_depth_expr(value, depth, errors),
        Statement::ExprStatement { expr, .. } => check_dlg_depth_expr(expr, depth, errors),
        Statement::Assertion { args, .. } => {
            for arg in args {
                check_dlg_depth_expr(arg, depth, errors);
            }
        }
    }
}

fn check_dlg_depth_expr(expr: &Expr, depth: usize, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::OperatorCall { name, args, .. } => {
            let new_depth = if *name == Operator::Dlg {
                depth + 1
            } else {
                depth
            };
            if new_depth > MAX_DELEGATION_DEPTH {
                errors.push(ValidationError::Resource {
                    message: format!(
                        "delegation nesting depth {} exceeds maximum of {}",
                        new_depth, MAX_DELEGATION_DEPTH
                    ),
                });
            }
            for arg in args {
                check_dlg_depth_expr(arg, new_depth, errors);
            }
        }
        Expr::FnCall { args, .. } => {
            for arg in args {
                check_dlg_depth_expr(arg, depth, errors);
            }
        }
        Expr::PipeChain { steps, .. } => {
            for (_, step_expr) in steps {
                check_dlg_depth_expr(step_expr, depth, errors);
            }
        }
        Expr::Match { scrutinee, arms, .. } => {
            check_dlg_depth_expr(scrutinee, depth, errors);
            for arm in arms {
                check_dlg_depth_expr(&arm.body, depth, errors);
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_dlg_depth_expr(inner, depth, errors);
        }
        Expr::EvidenceBlock { items, .. } => {
            for item in items {
                check_dlg_depth_expr(&item.observation, depth, errors);
                check_dlg_depth_expr(&item.effect, depth, errors);
            }
        }
        Expr::Array { elements, .. } => {
            for el in elements {
                check_dlg_depth_expr(el, depth, errors);
            }
        }
        Expr::ResultExpr { inner, .. } => {
            if let Some(inner_expr) = inner {
                check_dlg_depth_expr(inner_expr, depth, errors);
            }
        }
        Expr::Struct { fields, .. } => {
            for (_, val) in fields {
                check_dlg_depth_expr(val, depth, errors);
            }
        }
        Expr::Literal(_) | Expr::Ident(_) => {}
    }
}

/// Check pipe chains for incompatible connective combinations.
/// Specifically: Store (@>) followed by ErrChannel (!>) is invalid.
fn check_pipe_compatibility(stmt: &Statement, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { value, .. } => check_pipe_compat_expr(value, errors),
        Statement::ExprStatement { expr, .. } => check_pipe_compat_expr(expr, errors),
        Statement::Assertion { args, .. } => {
            for arg in args {
                check_pipe_compat_expr(arg, errors);
            }
        }
    }
}

fn check_pipe_compat_expr(expr: &Expr, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::PipeChain { steps, .. } => {
            // Check adjacent connectives for incompatible pairs
            for window in steps.windows(2) {
                let (conn_a, _) = &window[0];
                let (conn_b, _) = &window[1];
                if *conn_a == Connective::Store && *conn_b == Connective::ErrChannel {
                    errors.push(ValidationError::Resource {
                        message: "incompatible pipe chain: Store (@>) followed by ErrChannel (!>)".to_string(),
                    });
                }
            }
            // Recurse into step expressions
            for (_, step_expr) in steps {
                check_pipe_compat_expr(step_expr, errors);
            }
        }
        Expr::OperatorCall { args, .. } => {
            for arg in args {
                check_pipe_compat_expr(arg, errors);
            }
        }
        Expr::FnCall { args, .. } => {
            for arg in args {
                check_pipe_compat_expr(arg, errors);
            }
        }
        Expr::Match { scrutinee, arms, .. } => {
            check_pipe_compat_expr(scrutinee, errors);
            for arm in arms {
                check_pipe_compat_expr(&arm.body, errors);
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_pipe_compat_expr(inner, errors);
        }
        Expr::EvidenceBlock { items, .. } => {
            for item in items {
                check_pipe_compat_expr(&item.observation, errors);
                check_pipe_compat_expr(&item.effect, errors);
            }
        }
        Expr::Array { elements, .. } => {
            for el in elements {
                check_pipe_compat_expr(el, errors);
            }
        }
        Expr::ResultExpr { inner, .. } => {
            if let Some(inner_expr) = inner {
                check_pipe_compat_expr(inner_expr, errors);
            }
        }
        Expr::Struct { fields, .. } => {
            for (_, val) in fields {
                check_pipe_compat_expr(val, errors);
            }
        }
        Expr::Literal(_) | Expr::Ident(_) => {}
    }
}
