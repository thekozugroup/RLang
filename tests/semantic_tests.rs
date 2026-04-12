use rlang::ast::common::*;
use rlang::ast::phases::*;
use rlang::semantic::{operator_arity, validate_semantics};

// ── Helpers ──────────────────────────────────────────────────────────────────

fn ident(s: &str) -> Expr {
    Expr::Ident(Ident(s.to_string()))
}

fn op_call(op: Operator, args: Vec<Expr>) -> Expr {
    Expr::OperatorCall {
        name: op,
        args,
        span: None,
    }
}

fn make_trace_with_stmts(phase: Phase, stmts: Vec<Statement>) -> Trace {
    Trace {
        phases: vec![
            PhaseBlock {
                phase: Phase::Frame,
                impl_mode: None,
                statements: if phase == Phase::Frame { stmts.clone() } else { vec![] },
                span: None,
            },
            PhaseBlock {
                phase: Phase::Explore,
                impl_mode: None,
                statements: if phase == Phase::Explore { stmts.clone() } else { vec![] },
                span: None,
            },
            PhaseBlock {
                phase: Phase::Verify,
                impl_mode: None,
                statements: if phase == Phase::Verify { stmts.clone() } else { vec![] },
                span: None,
            },
            PhaseBlock {
                phase: Phase::Decide,
                impl_mode: None,
                statements: if phase == Phase::Decide { stmts } else { vec![] },
                span: None,
            },
        ],
        span: None,
    }
}

// ── Operator Arity Tests ────────────────────────────────────────────────────

#[test]
fn test_cause_correct_arity() {
    let stmt = Statement::ExprStatement {
        expr: op_call(Operator::Cause, vec![ident("a"), ident("b")]),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

#[test]
fn test_cause_wrong_arity_one_arg() {
    let stmt = Statement::ExprStatement {
        expr: op_call(Operator::Cause, vec![ident("a")]),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    let result = validate_semantics(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    assert_eq!(errors.len(), 1);
    assert!(errors[0].to_string().contains("Cause"));
    assert!(errors[0].to_string().contains("expects 2"));
}

#[test]
fn test_cause_wrong_arity_three_args() {
    let stmt = Statement::ExprStatement {
        expr: op_call(Operator::Cause, vec![ident("a"), ident("b"), ident("c")]),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_err());
}

#[test]
fn test_obs_correct_arity() {
    let stmt = Statement::ExprStatement {
        expr: op_call(Operator::Obs, vec![ident("x")]),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

#[test]
fn test_obs_wrong_arity_zero_args() {
    let stmt = Statement::ExprStatement {
        expr: op_call(Operator::Obs, vec![]),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_err());
}

#[test]
fn test_chng_correct_arity() {
    let stmt = Statement::ExprStatement {
        expr: op_call(Operator::Chng, vec![ident("x"), ident("old"), ident("new")]),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

#[test]
fn test_chng_wrong_arity_two_args() {
    let stmt = Statement::ExprStatement {
        expr: op_call(Operator::Chng, vec![ident("x"), ident("old")]),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_err());
}

#[test]
fn test_seq_variadic_accepts_any_count() {
    // seq is variadic — 0, 1, 5 args should all pass
    for count in [0, 1, 3, 5] {
        let args: Vec<Expr> = (0..count).map(|i| ident(&format!("x{}", i))).collect();
        let stmt = Statement::ExprStatement {
            expr: op_call(Operator::Seq, args),
            span: None,
        };
        let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
        assert!(validate_semantics(&trace).is_ok(), "seq with {} args should be ok", count);
    }
}

#[test]
fn test_operator_arity_values() {
    assert_eq!(operator_arity(Operator::Cause), Some(2));
    assert_eq!(operator_arity(Operator::Obs), Some(1));
    assert_eq!(operator_arity(Operator::Chng), Some(3));
    assert_eq!(operator_arity(Operator::Seq), None);
    assert_eq!(operator_arity(Operator::Sup), Some(2));
    assert_eq!(operator_arity(Operator::Dlg), Some(2));
    assert_eq!(operator_arity(Operator::Exec), Some(1));
    assert_eq!(operator_arity(Operator::Inv), Some(2));
}

// ── Confidence Range Tests ──────────────────────────────────────────────────

#[test]
fn test_confidence_in_range() {
    let stmt = Statement::Let {
        name: Ident("x".to_string()),
        type_ann: None,
        value: ident("something"),
        metadata: Some(Metadata {
            confidence: Some(0.7),
            ..Default::default()
        }),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

#[test]
fn test_confidence_at_bounds() {
    // 0.0 and 1.0 are valid
    for val in [0.0, 1.0] {
        let stmt = Statement::Let {
            name: Ident("x".to_string()),
            type_ann: None,
            value: ident("something"),
            metadata: Some(Metadata {
                confidence: Some(val),
                ..Default::default()
            }),
            span: None,
        };
        let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
        assert!(validate_semantics(&trace).is_ok(), "confidence {} should be valid", val);
    }
}

#[test]
fn test_confidence_above_one() {
    let stmt = Statement::Let {
        name: Ident("x".to_string()),
        type_ann: None,
        value: ident("something"),
        metadata: Some(Metadata {
            confidence: Some(1.5),
            ..Default::default()
        }),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    let result = validate_semantics(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    assert!(errors[0].to_string().contains("out of range"));
}

#[test]
fn test_confidence_negative() {
    let stmt = Statement::Let {
        name: Ident("x".to_string()),
        type_ann: None,
        value: ident("something"),
        metadata: Some(Metadata {
            confidence: Some(-0.1),
            ..Default::default()
        }),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    let result = validate_semantics(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    assert!(errors[0].to_string().contains("out of range"));
}

#[test]
fn test_confidence_on_with_metadata_expr() {
    let stmt = Statement::ExprStatement {
        expr: Expr::WithMetadata {
            expr: Box::new(ident("claim")),
            metadata: Metadata {
                confidence: Some(2.0),
                ..Default::default()
            },
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    assert!(validate_semantics(&trace).is_err());
}

// ── Evidence Block Structure Tests ──────────────────────────────────────────

#[test]
fn test_evidence_block_valid() {
    let stmt = Statement::ExprStatement {
        expr: Expr::EvidenceBlock {
            items: vec![
                EvidenceItem {
                    observation: op_call(Operator::Obs, vec![ident("data")]),
                    effect: op_call(Operator::Sup, vec![ident("claim"), Expr::Literal(Literal::Float(0.2))]),
                },
                EvidenceItem {
                    observation: ident("noise"),
                    effect: op_call(Operator::Wkn, vec![ident("claim"), Expr::Literal(Literal::Float(0.1))]),
                },
            ],
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Verify, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

#[test]
fn test_evidence_block_neut_valid() {
    let stmt = Statement::ExprStatement {
        expr: Expr::EvidenceBlock {
            items: vec![EvidenceItem {
                observation: ident("obs"),
                effect: op_call(Operator::Neut, vec![ident("claim"), Expr::Literal(Literal::Float(0.0))]),
            }],
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Verify, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

#[test]
fn test_evidence_block_invalid_effect() {
    let stmt = Statement::ExprStatement {
        expr: Expr::EvidenceBlock {
            items: vec![EvidenceItem {
                observation: ident("obs"),
                effect: op_call(Operator::Cause, vec![ident("a"), ident("b")]),
            }],
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Verify, vec![stmt]);
    let result = validate_semantics(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    assert!(errors[0].to_string().contains("sup()"));
}

#[test]
fn test_evidence_block_ident_effect_invalid() {
    let stmt = Statement::ExprStatement {
        expr: Expr::EvidenceBlock {
            items: vec![EvidenceItem {
                observation: ident("obs"),
                effect: ident("not_a_valid_operator"),
            }],
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Verify, vec![stmt]);
    assert!(validate_semantics(&trace).is_err());
}

// ── Decide Phase Match Arms Tests ───────────────────────────────────────────

#[test]
fn test_decide_match_valid_arms() {
    let stmt = Statement::ExprStatement {
        expr: Expr::Match {
            scrutinee: Box::new(ident("evidence")),
            arms: vec![
                MatchArm {
                    pattern: Pattern::Ident(Ident("high".to_string())),
                    body: op_call(Operator::Assert, vec![ident("conclusion")]),
                    span: None,
                },
                MatchArm {
                    pattern: Pattern::Ident(Ident("medium".to_string())),
                    body: op_call(Operator::Hedge, vec![ident("conclusion")]),
                    span: None,
                },
                MatchArm {
                    pattern: Pattern::Ident(Ident("low".to_string())),
                    body: op_call(Operator::Suspend, vec![ident("conclusion")]),
                    span: None,
                },
                MatchArm {
                    pattern: Pattern::Wildcard,
                    body: op_call(Operator::Reject, vec![ident("conclusion")]),
                    span: None,
                },
            ],
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Decide, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

#[test]
fn test_decide_match_invalid_arm() {
    let stmt = Statement::ExprStatement {
        expr: Expr::Match {
            scrutinee: Box::new(ident("evidence")),
            arms: vec![MatchArm {
                pattern: Pattern::Wildcard,
                body: op_call(Operator::Cause, vec![ident("a"), ident("b")]),
                span: None,
            }],
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Decide, vec![stmt]);
    let result = validate_semantics(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    assert!(errors[0].to_string().contains("Decide phase"));
}

#[test]
fn test_non_decide_match_allows_any_arm() {
    // Outside Decide phase, match arms can use any expression
    let stmt = Statement::ExprStatement {
        expr: Expr::Match {
            scrutinee: Box::new(ident("x")),
            arms: vec![MatchArm {
                pattern: Pattern::Wildcard,
                body: op_call(Operator::Cause, vec![ident("a"), ident("b")]),
                span: None,
            }],
            span: None,
        },
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Explore, vec![stmt]);
    assert!(validate_semantics(&trace).is_ok());
}

// ── Combined / Nested Tests ─────────────────────────────────────────────────

#[test]
fn test_nested_operator_arity_error() {
    // cause(obs(x, y), b) — inner obs has wrong arity
    let stmt = Statement::ExprStatement {
        expr: op_call(
            Operator::Cause,
            vec![
                op_call(Operator::Obs, vec![ident("x"), ident("y")]), // wrong: obs takes 1
                ident("b"),
            ],
        ),
        span: None,
    };
    let trace = make_trace_with_stmts(Phase::Frame, vec![stmt]);
    let result = validate_semantics(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    assert_eq!(errors.len(), 1);
    assert!(errors[0].to_string().contains("Obs"));
}

#[test]
fn test_multiple_errors_collected() {
    // Both arity error and confidence error
    let stmts = vec![
        Statement::ExprStatement {
            expr: op_call(Operator::Cause, vec![ident("a")]), // wrong arity
            span: None,
        },
        Statement::Let {
            name: Ident("b".to_string()),
            type_ann: None,
            value: ident("val"),
            metadata: Some(Metadata {
                confidence: Some(5.0), // out of range
                ..Default::default()
            }),
            span: None,
        },
    ];
    let trace = make_trace_with_stmts(Phase::Frame, stmts);
    let result = validate_semantics(&trace);
    assert!(result.is_err());
    let errors = result.unwrap_err();
    assert!(errors.len() >= 2, "should collect multiple errors, got {}", errors.len());
}
