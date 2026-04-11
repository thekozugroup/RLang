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
