use rand::prelude::*;

use super::templates::{Category, SlotFillers, TrainingExample, get_template};

/// Domain-specific content pools for slot filling
struct ContentPool {
    subjects: Vec<(&'static str, &'static str)>, // (identifier-safe name, display)
    actions: Vec<(&'static str, &'static str)>,
    contexts: Vec<&'static str>,
    evidence_pos: Vec<&'static str>,
    evidence_neg: Vec<&'static str>,
    domain: &'static str,
}

fn content_pools() -> Vec<ContentPool> {
    vec![
        ContentPool {
            domain: "software_engineering",
            subjects: vec![
                ("test_coverage", "test coverage"),
                ("api_latency", "API latency"),
                ("memory_usage", "memory usage"),
                ("deployment", "deployment readiness"),
                ("code_quality", "code quality"),
            ],
            actions: vec![
                ("deploy", "deploy the service"),
                ("refactor", "refactor the module"),
                ("migrate", "migrate the database"),
                ("scale", "scale the infrastructure"),
                ("rollback", "rollback the release"),
            ],
            contexts: vec![
                "production_env", "staging_env", "ci_pipeline",
                "load_test", "security_audit",
            ],
            evidence_pos: vec![
                "tests_passing", "metrics_stable", "review_approved",
                "benchmarks_good", "coverage_high",
            ],
            evidence_neg: vec![
                "flaky_tests", "latency_spike", "dependency_issue",
                "resource_limit", "config_drift",
            ],
        },
        ContentPool {
            domain: "project_management",
            subjects: vec![
                ("timeline", "project timeline"),
                ("budget", "budget allocation"),
                ("team_capacity", "team capacity"),
                ("stakeholder_alignment", "stakeholder alignment"),
                ("risk_profile", "risk profile"),
            ],
            actions: vec![
                ("launch", "launch the project"),
                ("reallocate", "reallocate resources"),
                ("escalate", "escalate the issue"),
                ("negotiate", "negotiate the contract"),
                ("prioritize", "prioritize the backlog"),
            ],
            contexts: vec![
                "quarterly_review", "sprint_planning", "budget_cycle",
                "hiring_freeze", "market_shift",
            ],
            evidence_pos: vec![
                "milestone_met", "team_available", "funding_secured",
                "sponsor_engaged", "scope_clear",
            ],
            evidence_neg: vec![
                "deadline_risk", "scope_creep", "turnover_high",
                "budget_tight", "dependency_blocked",
            ],
        },
        ContentPool {
            domain: "data_science",
            subjects: vec![
                ("model_accuracy", "model accuracy"),
                ("data_quality", "data quality"),
                ("feature_importance", "feature importance"),
                ("training_loss", "training loss"),
                ("inference_speed", "inference speed"),
            ],
            actions: vec![
                ("retrain", "retrain the model"),
                ("validate", "validate the pipeline"),
                ("optimize", "optimize hyperparameters"),
                ("evaluate", "evaluate the results"),
                ("preprocess", "preprocess the dataset"),
            ],
            contexts: vec![
                "experiment_run", "ab_test", "production_model",
                "benchmark_suite", "data_pipeline",
            ],
            evidence_pos: vec![
                "accuracy_improved", "loss_converged", "metrics_up",
                "validation_passed", "performance_gain",
            ],
            evidence_neg: vec![
                "overfitting_detected", "data_drift", "bias_found",
                "latency_increase", "sample_imbalance",
            ],
        },
        ContentPool {
            domain: "security",
            subjects: vec![
                ("vulnerability", "vulnerability status"),
                ("access_control", "access control policy"),
                ("threat_level", "threat level"),
                ("compliance", "compliance status"),
                ("incident", "incident severity"),
            ],
            actions: vec![
                ("patch", "patch the vulnerability"),
                ("audit", "audit the system"),
                ("isolate", "isolate the threat"),
                ("remediate", "remediate the finding"),
                ("harden", "harden the configuration"),
            ],
            contexts: vec![
                "security_scan", "pen_test", "audit_report",
                "threat_intel", "incident_response",
            ],
            evidence_pos: vec![
                "scan_clean", "controls_verified", "patch_available",
                "logs_normal", "compliance_met",
            ],
            evidence_neg: vec![
                "exploit_active", "config_exposed", "unpatched_cve",
                "anomaly_detected", "access_violation",
            ],
        },
    ]
}

/// Generate a single training example for a given category
pub fn generate_one(category: Category, rng: &mut impl Rng) -> TrainingExample {
    let pools = content_pools();
    let pool = &pools[rng.gen_range(0..pools.len())];
    let template = get_template(category);

    let (subject_id, _subject_display) = pool.subjects[rng.gen_range(0..pool.subjects.len())];
    let (action_id, _action_display) = pool.actions[rng.gen_range(0..pool.actions.len())];
    let context = pool.contexts[rng.gen_range(0..pool.contexts.len())];
    let ev_pos = pool.evidence_pos[rng.gen_range(0..pool.evidence_pos.len())];
    let ev_neg = pool.evidence_neg[rng.gen_range(0..pool.evidence_neg.len())];

    let confidence = 0.60 + rng.gen_range(0.0..0.35_f64); // 0.60..0.95

    let fillers = SlotFillers {
        subject: subject_id.to_string(),
        object: format!("{}_outcome", subject_id),
        action: action_id.to_string(),
        context: context.to_string(),
        confidence,
        evidence_pos: ev_pos.to_string(),
        evidence_neg: ev_neg.to_string(),
        domain: pool.domain.to_string(),
    };

    let prompt = (template.prompt_template)(&fillers);
    let rlang_trace = (template.trace_template)(&fillers);
    let conclusion = (template.conclusion_template)(&fillers);

    TrainingExample {
        prompt,
        rlang_trace,
        conclusion,
        domain: pool.domain.to_string(),
        difficulty: template.difficulty.to_string(),
    }
}

/// Generate a batch of training examples.
/// Validates each generated trace using the parser before including it.
/// Returns only examples whose traces parse and validate successfully.
pub fn generate_batch(
    count: usize,
    categories: &[Category],
) -> Vec<TrainingExample> {
    let mut rng = rand::thread_rng();
    let mut results = Vec::with_capacity(count);
    let mut attempts = 0;
    let max_attempts = count * 3; // Allow some failures

    while results.len() < count && attempts < max_attempts {
        let cat = categories[rng.gen_range(0..categories.len())];
        let example = generate_one(cat, &mut rng);

        // Validate: parse the generated trace
        match crate::parser::parse(&example.rlang_trace) {
            Ok(trace) => {
                // Also run the validator
                match crate::validator::validate(&trace) {
                    Ok(()) => results.push(example),
                    Err(_) => {
                        // Validation failed, skip this example
                    }
                }
            }
            Err(_) => {
                // Parse failed, skip this example
            }
        }
        attempts += 1;
    }

    results
}

/// Generate a batch with a specific seed for reproducibility
pub fn generate_batch_seeded(
    count: usize,
    categories: &[Category],
    seed: u64,
) -> Vec<TrainingExample> {
    let mut rng = StdRng::seed_from_u64(seed);
    let mut results = Vec::with_capacity(count);
    let mut attempts = 0;
    let max_attempts = count * 3;

    while results.len() < count && attempts < max_attempts {
        let cat = categories[rng.gen_range(0..categories.len())];
        let example = generate_one(cat, &mut rng);

        match crate::parser::parse(&example.rlang_trace) {
            Ok(trace) => {
                match crate::validator::validate(&trace) {
                    Ok(()) => results.push(example),
                    Err(_) => {}
                }
            }
            Err(_) => {}
        }
        attempts += 1;
    }

    results
}
