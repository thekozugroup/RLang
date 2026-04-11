use rlang::ast::phases::*;
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
