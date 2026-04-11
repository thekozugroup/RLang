use rlang::parser::parse;

// ─── Basic let binding with metadata ──────────────────────────
#[test]
fn test_parse_simple_let_binding() {
    let source = r#"
#[phase(Frame)]
{
    let rain: blf<0.95> = obs(rain) | p:0.95 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
}
"#;
    let trace = parse(source).expect("should parse simple let binding");
    assert_eq!(trace.phases.len(), 1);
    let phase = &trace.phases[0];
    assert_eq!(phase.phase, rlang::ast::phases::Phase::Frame);
    assert!(phase.impl_mode.is_none());
    assert_eq!(phase.statements.len(), 1);
}

// ─── Phase block with impl (reasoning mode) ─────────────────
#[test]
fn test_parse_impl_block() {
    let source = r#"
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
}
"#;
    let trace = parse(source).expect("should parse impl block");
    assert_eq!(trace.phases.len(), 1);
    let phase = &trace.phases[0];
    assert_eq!(
        phase.impl_mode,
        Some(rlang::ast::phases::ReasoningMode::Deductive)
    );
    assert_eq!(phase.statements.len(), 1);
}

// ─── Evidence block inside let binding ──────────────────────
#[test]
fn test_parse_evidence_block() {
    let source = r#"
#[phase(Explore)]
{
    let ev = [
        obs(dark_clouds) => sup(rain, +0.05),
    ];
}
"#;
    let trace = parse(source).expect("should parse evidence block");
    assert_eq!(trace.phases.len(), 1);
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Pipe chain with transform ──────────────────────────────
#[test]
fn test_parse_pipe_chain() {
    let source = r#"
#[phase(Explore)]
{
    rain |> resolve(ev) -> Ok(confirmed);
}
"#;
    let trace = parse(source).expect("should parse pipe chain");
    assert_eq!(trace.phases.len(), 1);
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Match expression ────────────────────────────────────────
#[test]
fn test_parse_match_expression() {
    let source = r#"
#[phase(Decide)]
{
    match conf(rain) {
        c if c > 0.85 => assert(rain),
        _ => hedge(rain),
    }
}
"#;
    let trace = parse(source).expect("should parse match expression");
    assert_eq!(trace.phases.len(), 1);
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Assertion statements ────────────────────────────────────
#[test]
fn test_parse_assertion() {
    let source = r#"
#[phase(Decide)]
{
    assert(deploy) | p:0.92;
}
"#;
    let trace = parse(source).expect("should parse assertion");
    assert_eq!(trace.phases.len(), 1);
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Multiple phase blocks ──────────────────────────────────
#[test]
fn test_parse_multiple_phases() {
    let source = r#"
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
"#;
    let trace = parse(source).expect("should parse multi-phase trace");
    assert_eq!(trace.phases.len(), 4);
    assert_eq!(trace.phases[0].phase, rlang::ast::phases::Phase::Frame);
    assert_eq!(trace.phases[1].phase, rlang::ast::phases::Phase::Explore);
    assert_eq!(trace.phases[2].phase, rlang::ast::phases::Phase::Verify);
    assert_eq!(trace.phases[3].phase, rlang::ast::phases::Phase::Decide);
}

// ─── Verify operator call parsing ────────────────────────────
#[test]
fn test_parse_operator_call_is_operator() {
    let source = r#"
#[phase(Frame)]
{
    let x = obs(sensor_data);
}
"#;
    let trace = parse(source).expect("should parse operator call");
    let stmt = &trace.phases[0].statements[0];
    match stmt {
        rlang::ast::common::Statement::Let { value, .. } => {
            match value {
                rlang::ast::common::Expr::OperatorCall { name, .. } => {
                    assert_eq!(*name, rlang::ast::common::Operator::Obs);
                }
                other => panic!("expected OperatorCall, got {:?}", other),
            }
        }
        other => panic!("expected Let, got {:?}", other),
    }
}

// ─── Unknown function call ───────────────────────────────────
#[test]
fn test_parse_fn_call() {
    let source = r#"
#[phase(Frame)]
{
    let x = my_custom_fn(a, b);
}
"#;
    let trace = parse(source).expect("should parse fn call");
    let stmt = &trace.phases[0].statements[0];
    match stmt {
        rlang::ast::common::Statement::Let { value, .. } => {
            match value {
                rlang::ast::common::Expr::FnCall { name, .. } => {
                    assert_eq!(name.0, "my_custom_fn");
                }
                other => panic!("expected FnCall, got {:?}", other),
            }
        }
        other => panic!("expected Let, got {:?}", other),
    }
}

// ─── Error handling: invalid source ──────────────────────────
#[test]
fn test_parse_error_invalid_syntax() {
    let result = parse("not valid rlang at all");
    assert!(result.is_err(), "should produce parse error");
}

// ─── Connective: fan-out ─────────────────────────────────────
#[test]
fn test_parse_fanout_connective() {
    let source = r#"
#[phase(Explore)]
{
    decompose(goal) ||> apply(strategy);
}
"#;
    let trace = parse(source).expect("should parse fan-out connective");
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Connective: tentative ──────────────────────────────────
#[test]
fn test_parse_tentative_connective() {
    let source = r#"
#[phase(Explore)]
{
    hypothesis ~> test_fn(hypothesis);
}
"#;
    let trace = parse(source).expect("should parse tentative connective");
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Connective: error channel ──────────────────────────────
#[test]
fn test_parse_error_channel() {
    let source = r#"
#[phase(Explore)]
{
    exec(deploy) !> handle_error(e);
}
"#;
    let trace = parse(source).expect("should parse error channel");
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Connective: memory store ───────────────────────────────
#[test]
fn test_parse_memory_store() {
    let source = r#"
#[phase(Explore)]
{
    obs(user_pref) @> rmb(prefs, semantic);
}
"#;
    let trace = parse(source).expect("should parse memory store");
    assert_eq!(trace.phases[0].statements.len(), 1);
}

// ─── Result expression ──────────────────────────────────────
#[test]
fn test_parse_result_expr_ok() {
    let source = r#"
#[phase(Verify)]
{
    let result = Ok(confirmed);
}
"#;
    let trace = parse(source).expect("should parse result expr");
    let stmt = &trace.phases[0].statements[0];
    match stmt {
        rlang::ast::common::Statement::Let { value, .. } => {
            match value {
                rlang::ast::common::Expr::ResultExpr { variant, .. } => {
                    assert_eq!(*variant, rlang::ast::common::ResultVariant::Ok);
                }
                other => panic!("expected ResultExpr, got {:?}", other),
            }
        }
        other => panic!("expected Let, got {:?}", other),
    }
}

// ─── Let without type annotation ─────────────────────────────
#[test]
fn test_parse_let_without_type() {
    let source = r#"
#[phase(Explore)]
{
    let ev = obs(data);
}
"#;
    let trace = parse(source).expect("should parse let without type");
    assert_eq!(trace.phases[0].statements.len(), 1);
    match &trace.phases[0].statements[0] {
        rlang::ast::common::Statement::Let { type_ann, .. } => {
            assert!(type_ann.is_none());
        }
        other => panic!("expected Let, got {:?}", other),
    }
}

// ─── Metadata on assertion ────────────────────────────────────
#[test]
fn test_parse_assertion_with_metadata() {
    let source = r#"
#[phase(Decide)]
{
    hedge(claim) | p:0.5;
}
"#;
    let trace = parse(source).expect("should parse assertion with metadata");
    assert_eq!(trace.phases[0].statements.len(), 1);
    match &trace.phases[0].statements[0] {
        rlang::ast::common::Statement::Assertion { kind, metadata, .. } => {
            assert_eq!(*kind, rlang::ast::common::AssertionKind::Hedge);
            assert!(metadata.is_some());
        }
        other => panic!("expected Assertion, got {:?}", other),
    }
}

// ─── Full deploy trace (integration test) ───────────────────
#[test]
fn test_parse_full_deploy_trace() {
    let source = r#"
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback) | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic) | p:0.90 | ep:direct | src:obs(metrics) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests => sup(deploy, +0.15),
        risk => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];
    deploy |> resolve(ev) -> Ok(ready);
}

#[phase(Verify)]
{
    req(tests, obs(tests_pass)) |> verify(deploy) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.50 => hedge(deploy),
        _ => suspend(deploy),
    }
}
"#;
    let trace = parse(source).expect("should parse full deploy trace");
    assert_eq!(trace.phases.len(), 4);
    // Frame has 3 let bindings
    assert_eq!(trace.phases[0].statements.len(), 3);
    // Explore has let + pipe chain
    assert_eq!(trace.phases[1].statements.len(), 2);
    // Verify has pipe chain
    assert_eq!(trace.phases[2].statements.len(), 1);
    // Decide has match
    assert_eq!(trace.phases[3].statements.len(), 1);
}
