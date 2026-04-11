use pest::Parser;
use rlang::grammar::RLangParser;
use rlang::grammar::Rule;

#[test]
fn test_float_literal() {
    let result = RLangParser::parse(Rule::float_literal, "0.7");
    assert!(result.is_ok(), "Failed to parse float: {:?}", result.err());
}

#[test]
fn test_float_literal_boundaries() {
    assert!(RLangParser::parse(Rule::float_literal, "0.0").is_ok());
    assert!(RLangParser::parse(Rule::float_literal, "1.0").is_ok());
    assert!(RLangParser::parse(Rule::float_literal, "0.99").is_ok());
}

#[test]
fn test_identifier() {
    assert!(RLangParser::parse(Rule::ident, "storm").is_ok());
    assert!(RLangParser::parse(Rule::ident, "agent_b").is_ok());
    assert!(RLangParser::parse(Rule::ident, "mtg").is_ok());
    assert!(RLangParser::parse(Rule::ident, "health_check_pass").is_ok());
}

#[test]
fn test_operator_call_simple() {
    let result = RLangParser::parse(Rule::operator_call, "obs(rain)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_operator_call_two_args() {
    let result = RLangParser::parse(Rule::operator_call, "cause(storm, cncl(mtg))");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_operator_call_three_args() {
    let result = RLangParser::parse(Rule::operator_call, "chng(state, idle, run)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_metadata_single() {
    let result = RLangParser::parse(Rule::metadata, "| p:0.7");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_metadata_full() {
    let result = RLangParser::parse(Rule::metadata, "| p:0.7 | ep:infer | src:obs(rpt) | scope:loc | t:fresh");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_evidence_item_sup() {
    let result = RLangParser::parse(Rule::evidence_item, "obs(dark_clouds) => sup(claim, +0.20)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_evidence_item_wkn() {
    let result = RLangParser::parse(Rule::evidence_item, "obs(no_notice) => wkn(claim, -0.15)");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_evidence_block() {
    let input = r#"[
    obs(dark_clouds) => sup(claim, +0.20),
    obs(no_notice) => wkn(claim, -0.15),
    obs(empty_lot) => sup(claim, +0.10),
]"#;
    let result = RLangParser::parse(Rule::evidence_block, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_let_binding_belief() {
    let input = r#"let claim: blf<0.7> = cause(storm, cncl(mtg)) | p:0.7 | ep:infer | src:obs(rpt) | scope:loc | t:fresh;"#;
    let result = RLangParser::parse(Rule::let_binding, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_pipe_chain() {
    let input = "claim |> resolve(ev) -> Ok(blf_resolved)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_match_expr() {
    let input = r#"match conf(claim) {
    c if c > 0.85 => assert(claim),
    c if c > 0.55 => hedge(claim),
    c if c > 0.30 => suspend(claim),
    _ => reject(claim),
}"#;
    let result = RLangParser::parse(Rule::match_expr, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_phase_attribute() {
    let result = RLangParser::parse(Rule::phase_attr, "#[phase(Frame)]");
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_phase_block() {
    let input = r#"#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
}"#;
    let result = RLangParser::parse(Rule::phase_block, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_fanout() {
    let input = "decompose(goal) ||> [delegate(a, t1), delegate(b, t2)] <| synthesize(results)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_tentative() {
    let input = "hypothesis ~> test(hypothesis)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_error_channel() {
    let input = "execute(deploy) !> handle_error(e)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_memory_store() {
    let input = "obs(user_pref) @> remember(prefs, Semantic)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_connective_memory_retrieve() {
    let input = "recall(prefs, Semantic) <@ |> apply_to(response)";
    let result = RLangParser::parse(Rule::pipe_chain, input);
    assert!(result.is_ok(), "Failed: {:?}", result.err());
}

#[test]
fn test_full_trace() {
    let input = r#"#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback) | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests => sup(deploy, +0.15),
        risk  => wkn(deploy, -0.25),
    ];
    let deploy_blf = enbl(fix, resolve(bug)) |> resolve(ev) -> Ok(blf_resolved);
}

#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy),
        _ => reject(deploy),
    }
}"#;
    let result = RLangParser::parse(Rule::trace, input);
    assert!(result.is_ok(), "Failed to parse full trace: {:?}", result.err());
}
