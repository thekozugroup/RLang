use rlang::training::templates::{Category, TrainingExample};
use rlang::training::generator;
use rlang::training::export;

/// Helper: generate one example for a category and verify it parses + validates
fn assert_category_produces_valid_trace(category: Category) {
    let mut rng = rand::thread_rng();
    // Try up to 5 times with different random seeds
    let mut success = false;
    for _ in 0..5 {
        let example = generator::generate_one(category, &mut rng);

        // Verify the example has all fields populated
        assert!(!example.prompt.is_empty(), "prompt should not be empty for {:?}", category);
        assert!(!example.rlang_trace.is_empty(), "rlang_trace should not be empty for {:?}", category);
        assert!(!example.conclusion.is_empty(), "conclusion should not be empty for {:?}", category);
        assert!(!example.domain.is_empty(), "domain should not be empty for {:?}", category);
        assert!(!example.difficulty.is_empty(), "difficulty should not be empty for {:?}", category);

        // Parse the generated trace
        match rlang::parser::parse(&example.rlang_trace) {
            Ok(trace) => {
                // Validate the parsed trace
                match rlang::validator::validate(&trace) {
                    Ok(()) => {
                        // Check structural properties
                        assert_eq!(trace.phases.len(), 4, "trace should have 4 phases for {:?}", category);
                        success = true;
                        break;
                    }
                    Err(errors) => {
                        eprintln!("Validation errors for {:?}: {:?}", category, errors);
                        eprintln!("Trace:\n{}", example.rlang_trace);
                        // Try again with different random content
                        continue;
                    }
                }
            }
            Err(e) => {
                eprintln!("Parse error for {:?}: {:?}", category, e);
                eprintln!("Trace:\n{}", example.rlang_trace);
                // Try again
                continue;
            }
        }
    }
    assert!(success, "Failed to generate a valid trace for {:?} after 5 attempts", category);
}

// -----------------------------------------------------------------------
// Test each of the 10 template categories produces valid TrainingExamples
// -----------------------------------------------------------------------

#[test]
fn test_causal_template_valid() {
    assert_category_produces_valid_trace(Category::Causal);
}

#[test]
fn test_risk_assessment_template_valid() {
    assert_category_produces_valid_trace(Category::RiskAssessment);
}

#[test]
fn test_evidence_evaluation_template_valid() {
    assert_category_produces_valid_trace(Category::EvidenceEvaluation);
}

#[test]
fn test_goal_decomposition_template_valid() {
    assert_category_produces_valid_trace(Category::GoalDecomposition);
}

#[test]
fn test_delegation_template_valid() {
    assert_category_produces_valid_trace(Category::Delegation);
}

#[test]
fn test_conflict_resolution_template_valid() {
    assert_category_produces_valid_trace(Category::ConflictResolution);
}

#[test]
fn test_tool_selection_template_valid() {
    assert_category_produces_valid_trace(Category::ToolSelection);
}

#[test]
fn test_self_correction_template_valid() {
    assert_category_produces_valid_trace(Category::SelfCorrection);
}

#[test]
fn test_memory_retrieval_template_valid() {
    assert_category_produces_valid_trace(Category::MemoryRetrieval);
}

#[test]
fn test_multi_step_planning_template_valid() {
    assert_category_produces_valid_trace(Category::MultiStepPlanning);
}

// -----------------------------------------------------------------------
// Test batch generation with mixed categories
// -----------------------------------------------------------------------

#[test]
fn test_batch_generation_all_categories() {
    let examples = generator::generate_batch(10, Category::all());
    assert!(
        !examples.is_empty(),
        "batch generation should produce at least some valid examples"
    );
    // All returned examples should have valid RLang traces
    for example in &examples {
        let trace = rlang::parser::parse(&example.rlang_trace)
            .expect("batch-generated trace should parse");
        rlang::validator::validate(&trace)
            .expect("batch-generated trace should validate");
    }
}

#[test]
fn test_batch_generation_single_category() {
    let categories = &[Category::Causal];
    let examples = generator::generate_batch(5, categories);
    assert!(!examples.is_empty(), "should generate at least some causal examples");
}

#[test]
fn test_batch_generation_seeded_reproducibility() {
    let categories = Category::all();
    let batch_a = generator::generate_batch_seeded(5, categories, 42);
    let batch_b = generator::generate_batch_seeded(5, categories, 42);

    assert_eq!(batch_a.len(), batch_b.len(), "seeded batches should have same length");
    for (a, b) in batch_a.iter().zip(batch_b.iter()) {
        assert_eq!(a.rlang_trace, b.rlang_trace, "seeded batches should produce identical traces");
    }
}

// -----------------------------------------------------------------------
// Test JSONL export format
// -----------------------------------------------------------------------

#[test]
fn test_jsonl_export_format() {
    let examples = vec![
        TrainingExample {
            prompt: "Will rain cause flooding?".to_string(),
            rlang_trace: "#[phase(Frame)]\n{\n    let rain: blf<0.90> = obs(rain) | p:0.90 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;\n}\n\n#[phase(Explore)]\n{\n    let ev = [\n        obs(heavy_rain) => sup(flood, +0.20),\n    ];\n    flood |> resolve(ev) -> Ok(resolved);\n}\n\n#[phase(Verify)]\n{\n    req(flood, obs(rain)) |> verify(flood) -> Ok(());\n}\n\n#[phase(Decide)]\n{\n    match conf(flood) {\n        c if c > 0.70 => assert(flood),\n        _ => hedge(flood),\n    }\n}".to_string(),
            conclusion: "Rain is likely to cause flooding.".to_string(),
            domain: "weather".to_string(),
            difficulty: "easy".to_string(),
        },
    ];

    let jsonl = export::to_jsonl(&examples);
    let lines: Vec<&str> = jsonl.lines().collect();
    assert_eq!(lines.len(), 1, "should produce one line for one example");

    // Verify it's valid JSON
    let parsed: serde_json::Value =
        serde_json::from_str(lines[0]).expect("JSONL line should be valid JSON");
    assert_eq!(parsed["prompt"], "Will rain cause flooding?");
    assert_eq!(parsed["domain"], "weather");
    assert_eq!(parsed["difficulty"], "easy");
    assert!(parsed["rlang_trace"].as_str().unwrap().contains("#[phase(Frame)]"));
}

#[test]
fn test_jsonl_export_multiple() {
    let examples = vec![
        TrainingExample {
            prompt: "Question 1".to_string(),
            rlang_trace: "trace 1".to_string(),
            conclusion: "Conclusion 1".to_string(),
            domain: "test".to_string(),
            difficulty: "easy".to_string(),
        },
        TrainingExample {
            prompt: "Question 2".to_string(),
            rlang_trace: "trace 2".to_string(),
            conclusion: "Conclusion 2".to_string(),
            domain: "test".to_string(),
            difficulty: "hard".to_string(),
        },
    ];

    let jsonl = export::to_jsonl(&examples);
    let lines: Vec<&str> = jsonl.lines().collect();
    assert_eq!(lines.len(), 2, "should produce two lines for two examples");

    // Each line should be valid JSON
    for line in &lines {
        serde_json::from_str::<serde_json::Value>(line)
            .expect("each JSONL line should be valid JSON");
    }
}

// -----------------------------------------------------------------------
// Test ShareGPT export format
// -----------------------------------------------------------------------

#[test]
fn test_sharegpt_export_format() {
    let examples = vec![
        TrainingExample {
            prompt: "Should we deploy?".to_string(),
            rlang_trace: "trace content".to_string(),
            conclusion: "Yes, deploy.".to_string(),
            domain: "software".to_string(),
            difficulty: "medium".to_string(),
        },
    ];

    let sharegpt = export::to_sharegpt(&examples);

    // Verify it's valid JSON
    let parsed: serde_json::Value =
        serde_json::from_str(&sharegpt).expect("ShareGPT output should be valid JSON");

    // Should be an array of conversations
    let array = parsed.as_array().expect("should be an array");
    assert_eq!(array.len(), 1);

    let conv = &array[0]["conversations"];
    let messages = conv.as_array().expect("conversations should be an array");
    assert_eq!(messages.len(), 3, "should have system, user, assistant messages");

    // Check roles
    assert_eq!(messages[0]["from"], "system");
    assert_eq!(messages[1]["from"], "human");
    assert_eq!(messages[2]["from"], "gpt");

    // Check user message
    assert_eq!(messages[1]["value"], "Should we deploy?");

    // Check assistant message contains <think> tags
    let assistant_value = messages[2]["value"].as_str().unwrap();
    assert!(
        assistant_value.contains("<think>"),
        "assistant message should contain <think> tag"
    );
    assert!(
        assistant_value.contains("</think>"),
        "assistant message should contain </think> tag"
    );
    assert!(
        assistant_value.contains("trace content"),
        "assistant message should contain the trace"
    );
    assert!(
        assistant_value.contains("Yes, deploy."),
        "assistant message should contain the conclusion"
    );
}

// -----------------------------------------------------------------------
// Test category parsing
// -----------------------------------------------------------------------

#[test]
fn test_category_from_str() {
    assert_eq!(Category::from_str("causal"), Some(Category::Causal));
    assert_eq!(Category::from_str("risk"), Some(Category::RiskAssessment));
    assert_eq!(Category::from_str("evidence"), Some(Category::EvidenceEvaluation));
    assert_eq!(Category::from_str("goal"), Some(Category::GoalDecomposition));
    assert_eq!(Category::from_str("delegation"), Some(Category::Delegation));
    assert_eq!(Category::from_str("conflict"), Some(Category::ConflictResolution));
    assert_eq!(Category::from_str("tool"), Some(Category::ToolSelection));
    assert_eq!(Category::from_str("correction"), Some(Category::SelfCorrection));
    assert_eq!(Category::from_str("memory"), Some(Category::MemoryRetrieval));
    assert_eq!(Category::from_str("planning"), Some(Category::MultiStepPlanning));
    assert_eq!(Category::from_str("invalid"), None);
}

#[test]
fn test_all_categories() {
    let all = Category::all();
    assert_eq!(all.len(), 10, "should have exactly 10 categories");
}
