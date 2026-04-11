use rlang::parser::parse;
use rlang::validator::validate;

// ─── Helper: load fixture file relative to project root ─────
fn load_fixture(path: &str) -> String {
    let manifest_dir = env!("CARGO_MANIFEST_DIR");
    let full_path = format!("{}/{}", manifest_dir, path);
    std::fs::read_to_string(&full_path)
        .unwrap_or_else(|e| panic!("failed to read fixture {}: {}", full_path, e))
}

// ═══════════════════════════════════════════════════════════════
// Valid fixtures: parse + validate should succeed
// ═══════════════════════════════════════════════════════════════

#[test]
fn test_valid_simple_belief() {
    let source = load_fixture("tests/fixtures/valid/simple_belief.rl");
    let trace = parse(&source).expect("simple_belief.rl should parse successfully");
    validate(&trace).expect("simple_belief.rl should pass validation");

    // Verify structural expectations
    assert_eq!(trace.phases.len(), 4);
    assert_eq!(trace.phases[0].phase, rlang::ast::phases::Phase::Frame);
    assert_eq!(trace.phases[1].phase, rlang::ast::phases::Phase::Explore);
    assert_eq!(trace.phases[2].phase, rlang::ast::phases::Phase::Verify);
    assert_eq!(trace.phases[3].phase, rlang::ast::phases::Phase::Decide);
}

#[test]
fn test_valid_full_deploy_trace() {
    let source = load_fixture("tests/fixtures/valid/full_deploy_trace.rl");
    let trace = parse(&source).expect("full_deploy_trace.rl should parse successfully");
    validate(&trace).expect("full_deploy_trace.rl should pass validation");

    // Verify structural expectations
    assert_eq!(trace.phases.len(), 4);
    // Frame has impl Deductive with 3 let bindings
    assert!(trace.phases[0].impl_mode.is_some());
    assert_eq!(trace.phases[0].statements.len(), 3);
    // Explore has let + pipe chain
    assert_eq!(trace.phases[1].statements.len(), 2);
    // Verify has pipe chain
    assert_eq!(trace.phases[2].statements.len(), 1);
    // Decide has match
    assert_eq!(trace.phases[3].statements.len(), 1);
}

// ═══════════════════════════════════════════════════════════════
// Invalid fixtures: parse should succeed but validate should fail
// ═══════════════════════════════════════════════════════════════

#[test]
fn test_invalid_skip_verify_phase() {
    let source = load_fixture("tests/fixtures/invalid/skip_verify_phase.rl");
    let trace = parse(&source).expect("skip_verify_phase.rl should parse successfully (grammar is valid)");

    let result = validate(&trace);
    assert!(result.is_err(), "skip_verify_phase.rl should fail validation");

    let errors = result.unwrap_err();
    let messages: Vec<String> = errors.iter().map(|e| format!("{}", e)).collect();
    // Must report the missing Verify phase
    assert!(
        messages.iter().any(|m| m.contains("Verify")),
        "should report missing Verify phase, got: {:?}",
        messages
    );
}

// ═══════════════════════════════════════════════════════════════
// Garbage input: should fail at parse stage
// ═══════════════════════════════════════════════════════════════

#[test]
fn test_garbage_input_fails_parse() {
    let source = "this is not valid RLang at all {{{{";
    let result = parse(source);
    assert!(result.is_err(), "garbage input should fail at parse stage");
}

#[test]
fn test_empty_input_fails_parse() {
    let source = "";
    let result = parse(source);
    assert!(result.is_err(), "empty input should fail at parse stage");
}
