use crate::ast::common::{Expr, Operator, Statement};
use crate::ast::phases::Trace;
use crate::errors::ValidationError;

/// Validate operator arity and evidence structure:
/// - obs() requires exactly 1 argument
/// - cause(), prvnt(), enbl(), req(), sim(), confl(), seq() require exactly 2 arguments
/// - chng() requires exactly 3 arguments
/// - sup(), wkn() require exactly 2 arguments
/// - Evidence items must use only sup, wkn, or neut as effect operators
pub fn validate_types(trace: &Trace) -> Result<(), Vec<ValidationError>> {
    let mut errors = Vec::new();

    for block in &trace.phases {
        for stmt in &block.statements {
            check_statement_types(stmt, &mut errors);
        }
    }

    if errors.is_empty() {
        Ok(())
    } else {
        Err(errors)
    }
}

fn check_statement_types(stmt: &Statement, errors: &mut Vec<ValidationError>) {
    match stmt {
        Statement::Let { value, .. } => check_expr_types(value, errors),
        Statement::ExprStatement { expr, .. } => check_expr_types(expr, errors),
        Statement::Assertion { args, .. } => {
            for arg in args {
                check_expr_types(arg, errors);
            }
        }
    }
}

fn check_expr_types(expr: &Expr, errors: &mut Vec<ValidationError>) {
    match expr {
        Expr::OperatorCall { name, args, .. } => {
            check_operator_arity(*name, args.len(), errors);
            for arg in args {
                check_expr_types(arg, errors);
            }
        }
        Expr::FnCall { args, .. } => {
            for arg in args {
                check_expr_types(arg, errors);
            }
        }
        Expr::PipeChain { steps, .. } => {
            for (_, step_expr) in steps {
                check_expr_types(step_expr, errors);
            }
        }
        Expr::Match { scrutinee, arms, .. } => {
            check_expr_types(scrutinee, errors);
            for arm in arms {
                check_expr_types(&arm.body, errors);
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_expr_types(inner, errors);
        }
        Expr::EvidenceBlock { items, .. } => {
            for item in items {
                check_expr_types(&item.observation, errors);
                check_expr_types(&item.effect, errors);
                check_evidence_effect(&item.effect, errors);
            }
        }
        Expr::Array { elements, .. } => {
            for el in elements {
                check_expr_types(el, errors);
            }
        }
        Expr::ResultExpr { inner, .. } => {
            if let Some(inner_expr) = inner {
                check_expr_types(inner_expr, errors);
            }
        }
        Expr::Struct { fields, .. } => {
            for (_, val) in fields {
                check_expr_types(val, errors);
            }
        }
        Expr::Literal(_) | Expr::Ident(_) => {}
    }
}

/// Check that an operator is called with the correct number of arguments.
fn check_operator_arity(op: Operator, arg_count: usize, errors: &mut Vec<ValidationError>) {
    let expected = expected_arity(op);
    if let Some(expected_count) = expected {
        if arg_count != expected_count {
            errors.push(ValidationError::Type {
                message: format!(
                    "operator {:?} requires {} argument(s), got {}",
                    op, expected_count, arg_count
                ),
            });
        }
    }
}

/// Return the expected arity for operators that have fixed arity, or None for variable-arity.
fn expected_arity(op: Operator) -> Option<usize> {
    match op {
        // 1-argument operators
        Operator::Obs => Some(1),
        // 2-argument operators
        Operator::Cause
        | Operator::Prvnt
        | Operator::Enbl
        | Operator::Req
        | Operator::Sim
        | Operator::Confl
        | Operator::Seq
        | Operator::Sup
        | Operator::Wkn => Some(2),
        // 3-argument operators
        Operator::Chng => Some(3),
        // All other operators: variable arity (no static check)
        _ => None,
    }
}

/// Evidence effect must be sup, wkn, or neut operator call.
fn check_evidence_effect(effect: &Expr, errors: &mut Vec<ValidationError>) {
    match effect {
        Expr::OperatorCall { name, .. } => {
            if *name != Operator::Sup && *name != Operator::Wkn && *name != Operator::Neut {
                errors.push(ValidationError::Type {
                    message: format!(
                        "evidence effect must use sup, wkn, or neut operator, found {:?}",
                        name
                    ),
                });
            }
        }
        Expr::WithMetadata { expr: inner, .. } => {
            check_evidence_effect(inner, errors);
        }
        _ => {
            errors.push(ValidationError::Type {
                message: "evidence effect must be a sup(), wkn(), or neut() operator call".to_string(),
            });
        }
    }
}
