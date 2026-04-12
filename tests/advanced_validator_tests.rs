use rlang::ast::common::*;
use rlang::ast::phases::*;
use rlang::validator::validate;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/// Build a minimal valid trace (Frame, Explore, Verify, Decide) with empty statements.
fn minimal_valid_trace() -> Trace {
    Trace {
        phases: vec![
            PhaseBlock {
                phase: Phase::Frame,
                impl_mode: None,
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
    }
}

fn op_call(op: Operator, args: Vec<Expr>) -> Expr {
    Expr::OperatorCall {
        name: op,
        args,
        span: None,
    }
}

fn ident_expr(name: &str) -> Expr {
    Expr::Ident(Ident(name.to_string()))
}

fn lit_float(v: f64) -> Expr {
    Expr::Literal(Literal::Float(v))
}

fn expr_stmt(expr: Expr) -> Statement {
    Statement::ExprStatement { expr, span: None }
}

fn let_stmt(name: &str, value: Expr) -> Statement {
    Statement::Let {
        name: Ident(name.to_string()),
        type_ann: None,
        value,
        metadata: None,
        span: None,
    }
}

// ---------------------------------------------------------------------------
// Bounds: backtrack in wrong phase should error
// ---------------------------------------------------------------------------

#[test]
fn test_backtrack_in_frame_phase_errors() {
    let mut trace = minimal_valid_trace();
    // Add a bt() call inside the Frame phase
    trace.phases[0].statements.push(expr_stmt(
        op_call(Operator::Bt, vec![ident_expr("plan")]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_bounds = errors.iter().any(|e| matches!(e, rlang::errors::ValidationError::Bounds { .. }));
    assert!(has_bounds, "expected Bounds error for bt in Frame phase");
}

#[test]
fn test_backtrack_in_decide_phase_errors() {
    let mut trace = minimal_valid_trace();
    // Add a bt() call inside the Decide phase
    trace.phases[3].statements.push(expr_stmt(
        op_call(Operator::Bt, vec![ident_expr("plan")]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_bounds = errors.iter().any(|e| matches!(e, rlang::errors::ValidationError::Bounds { .. }));
    assert!(has_bounds, "expected Bounds error for bt in Decide phase");
}

#[test]
fn test_backtrack_in_verify_phase_is_ok() {
    let mut trace = minimal_valid_trace();
    // bt() in Verify is allowed
    trace.phases[2].statements.push(expr_stmt(
        op_call(Operator::Bt, vec![ident_expr("plan")]),
    ));
    assert!(validate(&trace).is_ok());
}

// ---------------------------------------------------------------------------
// Bounds: excessive backtrack count should error
// ---------------------------------------------------------------------------

#[test]
fn test_excessive_backtrack_count_errors() {
    let mut trace = minimal_valid_trace();
    // Add 4 bt() calls in Verify (exceeds max of 3)
    for _ in 0..4 {
        trace.phases[2].statements.push(expr_stmt(
            op_call(Operator::Bt, vec![ident_expr("plan")]),
        ));
    }
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_bounds = errors.iter().any(|e| {
        if let rlang::errors::ValidationError::Bounds { message } = e {
            message.contains("backtrack operations")
        } else {
            false
        }
    });
    assert!(has_bounds, "expected Bounds error for excessive backtrack count");
}

#[test]
fn test_three_backtracks_is_ok() {
    let mut trace = minimal_valid_trace();
    // Exactly 3 bt() calls is OK
    for _ in 0..3 {
        trace.phases[2].statements.push(expr_stmt(
            op_call(Operator::Bt, vec![ident_expr("plan")]),
        ));
    }
    assert!(validate(&trace).is_ok());
}

// ---------------------------------------------------------------------------
// Resources: delegation in Frame phase should error
// ---------------------------------------------------------------------------

#[test]
fn test_delegation_in_frame_phase_errors() {
    let mut trace = minimal_valid_trace();
    // Add dlg() in Frame
    trace.phases[0].statements.push(expr_stmt(
        op_call(Operator::Dlg, vec![ident_expr("agent"), ident_expr("task")]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_resource = errors.iter().any(|e| matches!(e, rlang::errors::ValidationError::Resource { .. }));
    assert!(has_resource, "expected Resource error for dlg in Frame phase");
}

#[test]
fn test_delegation_in_verify_phase_errors() {
    let mut trace = minimal_valid_trace();
    // Add dlg() in Verify
    trace.phases[2].statements.push(expr_stmt(
        op_call(Operator::Dlg, vec![ident_expr("agent"), ident_expr("task")]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_resource = errors.iter().any(|e| matches!(e, rlang::errors::ValidationError::Resource { .. }));
    assert!(has_resource, "expected Resource error for dlg in Verify phase");
}

#[test]
fn test_delegation_in_explore_phase_is_ok() {
    let mut trace = minimal_valid_trace();
    // dlg() in Explore is allowed
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Dlg, vec![ident_expr("agent"), ident_expr("task")]),
    ));
    assert!(validate(&trace).is_ok());
}

// ---------------------------------------------------------------------------
// Types: obs() with wrong arg count should error
// ---------------------------------------------------------------------------

#[test]
fn test_obs_with_zero_args_errors() {
    let mut trace = minimal_valid_trace();
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Obs, vec![]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_type = errors.iter().any(|e| {
        if let rlang::errors::ValidationError::Type { message } = e {
            message.contains("Obs") && message.contains("1 argument")
        } else {
            false
        }
    });
    assert!(has_type, "expected Type error for obs() with 0 args");
}

#[test]
fn test_obs_with_two_args_errors() {
    let mut trace = minimal_valid_trace();
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Obs, vec![ident_expr("a"), ident_expr("b")]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
}

#[test]
fn test_obs_with_one_arg_is_ok() {
    let mut trace = minimal_valid_trace();
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Obs, vec![ident_expr("sensor_data")]),
    ));
    assert!(validate(&trace).is_ok());
}

// ---------------------------------------------------------------------------
// Types: cause() with wrong arg count should error
// ---------------------------------------------------------------------------

#[test]
fn test_cause_with_one_arg_errors() {
    let mut trace = minimal_valid_trace();
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Cause, vec![ident_expr("a")]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_type = errors.iter().any(|e| {
        if let rlang::errors::ValidationError::Type { message } = e {
            message.contains("Cause") && message.contains("2 argument")
        } else {
            false
        }
    });
    assert!(has_type, "expected Type error for cause() with 1 arg");
}

#[test]
fn test_cause_with_two_args_is_ok() {
    let mut trace = minimal_valid_trace();
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Cause, vec![ident_expr("a"), ident_expr("b")]),
    ));
    assert!(validate(&trace).is_ok());
}

// ---------------------------------------------------------------------------
// Types: chng() with wrong arg count should error
// ---------------------------------------------------------------------------

#[test]
fn test_chng_with_two_args_errors() {
    let mut trace = minimal_valid_trace();
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Chng, vec![ident_expr("a"), ident_expr("b")]),
    ));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_type = errors.iter().any(|e| {
        if let rlang::errors::ValidationError::Type { message } = e {
            message.contains("Chng") && message.contains("3 argument")
        } else {
            false
        }
    });
    assert!(has_type, "expected Type error for chng() with 2 args");
}

#[test]
fn test_chng_with_three_args_is_ok() {
    let mut trace = minimal_valid_trace();
    trace.phases[1].statements.push(expr_stmt(
        op_call(Operator::Chng, vec![ident_expr("a"), ident_expr("b"), ident_expr("c")]),
    ));
    assert!(validate(&trace).is_ok());
}

// ---------------------------------------------------------------------------
// Types: evidence item with non-sup/wkn/neut effect should error
// ---------------------------------------------------------------------------

#[test]
fn test_evidence_with_cause_effect_errors() {
    let mut trace = minimal_valid_trace();
    // Evidence block where effect uses cause() instead of sup/wkn/neut
    trace.phases[2].statements.push(expr_stmt(Expr::EvidenceBlock {
        items: vec![EvidenceItem {
            observation: op_call(Operator::Obs, vec![ident_expr("x")]),
            effect: op_call(Operator::Cause, vec![ident_expr("claim"), lit_float(0.3)]),
        }],
        span: None,
    }));
    let result = validate(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    let has_type = errors.iter().any(|e| {
        if let rlang::errors::ValidationError::Type { message } = e {
            message.contains("evidence effect") && message.contains("sup, wkn, or neut")
        } else {
            false
        }
    });
    assert!(has_type, "expected Type error for evidence with cause() effect");
}

#[test]
fn test_evidence_with_sup_effect_is_ok() {
    let mut trace = minimal_valid_trace();
    trace.phases[2].statements.push(expr_stmt(Expr::EvidenceBlock {
        items: vec![EvidenceItem {
            observation: op_call(Operator::Obs, vec![ident_expr("x")]),
            effect: op_call(Operator::Sup, vec![ident_expr("claim"), lit_float(0.3)]),
        }],
        span: None,
    }));
    assert!(validate(&trace).is_ok());
}

#[test]
fn test_evidence_with_wkn_effect_is_ok() {
    let mut trace = minimal_valid_trace();
    trace.phases[2].statements.push(expr_stmt(Expr::EvidenceBlock {
        items: vec![EvidenceItem {
            observation: op_call(Operator::Obs, vec![ident_expr("x")]),
            effect: op_call(Operator::Wkn, vec![ident_expr("claim"), lit_float(0.2)]),
        }],
        span: None,
    }));
    assert!(validate(&trace).is_ok());
}

#[test]
fn test_evidence_with_neut_effect_is_ok() {
    let mut trace = minimal_valid_trace();
    trace.phases[2].statements.push(expr_stmt(Expr::EvidenceBlock {
        items: vec![EvidenceItem {
            observation: op_call(Operator::Obs, vec![ident_expr("x")]),
            effect: op_call(Operator::Neut, vec![ident_expr("claim"), lit_float(0.0)]),
        }],
        span: None,
    }));
    assert!(validate(&trace).is_ok());
}

// ---------------------------------------------------------------------------
// Integration: valid trace with operators across all phases passes
// ---------------------------------------------------------------------------

#[test]
fn test_valid_trace_with_all_operators_passes() {
    let trace = Trace {
        phases: vec![
            PhaseBlock {
                phase: Phase::Frame,
                impl_mode: None,
                statements: vec![
                    // Frame: set up observations and causal claims
                    let_stmt("sensor", op_call(Operator::Obs, vec![ident_expr("temp")])),
                    let_stmt(
                        "hypothesis",
                        op_call(Operator::Cause, vec![ident_expr("heat"), ident_expr("expansion")]),
                    ),
                ],
                span: None,
            },
            PhaseBlock {
                phase: Phase::Explore,
                impl_mode: None,
                statements: vec![
                    // Explore: delegation is allowed here
                    expr_stmt(op_call(
                        Operator::Dlg,
                        vec![ident_expr("sub_agent"), ident_expr("research_task")],
                    )),
                    // chng with 3 args
                    expr_stmt(op_call(
                        Operator::Chng,
                        vec![ident_expr("state"), ident_expr("old"), ident_expr("new")],
                    )),
                ],
                span: None,
            },
            PhaseBlock {
                phase: Phase::Verify,
                impl_mode: None,
                statements: vec![
                    // Verify: backtrack is OK, evidence with sup/wkn
                    expr_stmt(op_call(Operator::Bt, vec![ident_expr("plan")])),
                    expr_stmt(Expr::EvidenceBlock {
                        items: vec![
                            EvidenceItem {
                                observation: op_call(Operator::Obs, vec![ident_expr("data")]),
                                effect: op_call(Operator::Sup, vec![ident_expr("claim"), lit_float(0.8)]),
                            },
                            EvidenceItem {
                                observation: op_call(Operator::Obs, vec![ident_expr("noise")]),
                                effect: op_call(Operator::Wkn, vec![ident_expr("claim"), lit_float(0.1)]),
                            },
                        ],
                        span: None,
                    }),
                ],
                span: None,
            },
            PhaseBlock {
                phase: Phase::Decide,
                impl_mode: None,
                statements: vec![
                    // Decide: assertions are fine
                    Statement::Assertion {
                        kind: AssertionKind::Assert,
                        args: vec![ident_expr("conclusion")],
                        metadata: None,
                        span: None,
                    },
                ],
                span: None,
            },
        ],
        span: None,
    };
    assert!(validate(&trace).is_ok(), "valid trace with all operators should pass");
}
