use serde::{Deserialize, Serialize};

/// A single training example: English prompt -> RLang trace -> English conclusion
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct TrainingExample {
    pub prompt: String,
    pub rlang_trace: String,
    pub conclusion: String,
    pub domain: String,
    pub difficulty: String,
}

/// The 10 template categories for training data generation
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash, Serialize, Deserialize)]
pub enum Category {
    Causal,
    RiskAssessment,
    EvidenceEvaluation,
    GoalDecomposition,
    Delegation,
    ConflictResolution,
    ToolSelection,
    SelfCorrection,
    MemoryRetrieval,
    MultiStepPlanning,
}

impl Category {
    pub fn all() -> &'static [Category] {
        &[
            Category::Causal,
            Category::RiskAssessment,
            Category::EvidenceEvaluation,
            Category::GoalDecomposition,
            Category::Delegation,
            Category::ConflictResolution,
            Category::ToolSelection,
            Category::SelfCorrection,
            Category::MemoryRetrieval,
            Category::MultiStepPlanning,
        ]
    }

    pub fn as_str(&self) -> &'static str {
        match self {
            Category::Causal => "causal",
            Category::RiskAssessment => "risk",
            Category::EvidenceEvaluation => "evidence",
            Category::GoalDecomposition => "goal",
            Category::Delegation => "delegation",
            Category::ConflictResolution => "conflict",
            Category::ToolSelection => "tool",
            Category::SelfCorrection => "correction",
            Category::MemoryRetrieval => "memory",
            Category::MultiStepPlanning => "planning",
        }
    }

    pub fn from_str(s: &str) -> Option<Category> {
        match s {
            "causal" => Some(Category::Causal),
            "risk" => Some(Category::RiskAssessment),
            "evidence" => Some(Category::EvidenceEvaluation),
            "goal" => Some(Category::GoalDecomposition),
            "delegation" => Some(Category::Delegation),
            "conflict" => Some(Category::ConflictResolution),
            "tool" => Some(Category::ToolSelection),
            "correction" => Some(Category::SelfCorrection),
            "memory" => Some(Category::MemoryRetrieval),
            "planning" => Some(Category::MultiStepPlanning),
            _ => None,
        }
    }
}

/// Content slot fillers for template instantiation
pub struct SlotFillers {
    pub subject: String,
    pub object: String,
    pub action: String,
    pub context: String,
    pub confidence: f64,
    pub evidence_pos: String,
    pub evidence_neg: String,
    pub domain: String,
}

/// A template that can produce valid RLang traces
pub struct Template {
    pub category: Category,
    pub difficulty: &'static str,
    pub prompt_template: fn(&SlotFillers) -> String,
    pub trace_template: fn(&SlotFillers) -> String,
    pub conclusion_template: fn(&SlotFillers) -> String,
}

// ---------------------------------------------------------------------------
// Template definitions for each of the 10 categories
// ---------------------------------------------------------------------------

pub fn causal_template() -> Template {
    Template {
        category: Category::Causal,
        difficulty: "medium",
        prompt_template: |s| {
            format!(
                "Will {} cause {}? Consider the available evidence in the {} domain.",
                s.subject, s.object, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let {subject}: blf<{conf:.2}> = obs({subject}) | p:{conf:.2} | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
    let {object}: blf<0.50> = cause({subject}, {object}) | p:0.50 | ep:infer | src:obs(analysis) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup({object}, +0.20),
        obs({ev_neg}) => wkn({object}, -0.10),
    ];
    {object} |> resolve(ev) -> Ok(resolved);
}}

#[phase(Verify)]
{{
    req({object}, obs({subject})) |> verify({object}) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf({object}) {{
        c if c > 0.70 => assert({object}),
        c if c > 0.40 => hedge({object}),
        _ => suspend({object}),
    }}
}}"#,
                subject = s.subject,
                object = s.object,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "Based on the evidence, {} does appear to cause {} with moderate confidence. \
                 The positive evidence ({}) outweighs the negative ({}).",
                s.subject, s.object, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn risk_assessment_template() -> Template {
    Template {
        category: Category::RiskAssessment,
        difficulty: "hard",
        prompt_template: |s| {
            format!(
                "Should we proceed with {} given the risks? Evaluate the {} context.",
                s.action, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let benefit: blf<{conf:.2}> = obs({action}_benefit) | p:{conf:.2} | ep:direct | src:obs(analysis) | scope:loc | t:fresh;
    let risk_factor: blf<0.75> = obs({action}_risk) | p:0.75 | ep:direct | src:obs(assessment) | scope:loc | t:fresh;
    let mitigation: blf<0.60> = obs({action}_mitigation) | p:0.60 | ep:infer | src:obs(planning) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup({action}_decision, +0.15),
        obs({ev_neg}) => wkn({action}_decision, -0.25),
        mitigation => sup({action}_decision, +0.10),
    ];
    {action}_decision |> resolve(ev) -> Ok(assessed);
}}

#[phase(Verify)]
{{
    req({action}_decision, obs({action}_benefit)) |> verify({action}_decision) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf({action}_decision) {{
        c if c > 0.80 => assert({action}_decision),
        c if c > 0.50 => hedge({action}_decision),
        _ => reject({action}_decision),
    }}
}}"#,
                action = s.action,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "After risk assessment, proceeding with {} carries moderate risk. \
                 Mitigation strategies exist but the negative factors ({}) require careful monitoring.",
                s.action, s.evidence_neg
            )
        },
    }
}

pub fn evidence_evaluation_template() -> Template {
    Template {
        category: Category::EvidenceEvaluation,
        difficulty: "medium",
        prompt_template: |s| {
            format!(
                "What does the evidence suggest about {}? Analyze in the {} domain.",
                s.subject, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let claim: blf<0.50> = obs({subject}) | p:0.50 | ep:infer | src:obs(initial) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup(claim, +0.20),
        obs({ev_neg}) => wkn(claim, -0.15),
        obs({context}) => sup(claim, +0.10),
    ];
    claim |> resolve(ev) -> Ok(evaluated);
}}

#[phase(Verify)]
{{
    req(claim, obs({subject})) |> verify(claim) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf(claim) {{
        c if c > 0.85 => assert(claim),
        c if c > 0.55 => hedge(claim),
        _ => suspend(claim),
    }}
}}"#,
                subject = s.subject,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
                context = s.context,
            )
        },
        conclusion_template: |s| {
            format!(
                "The evidence about {} is mixed but leans positive. \
                 Key supporting evidence: {}. Counterevidence: {}.",
                s.subject, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn goal_decomposition_template() -> Template {
    Template {
        category: Category::GoalDecomposition,
        difficulty: "hard",
        prompt_template: |s| {
            format!(
                "How do we achieve {}? Break it down into steps in the {} domain.",
                s.action, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let target: blf<{conf:.2}> = obs({action}_target) | p:{conf:.2} | ep:direct | src:obs(requirements) | scope:loc | t:fresh;
    let feasibility: blf<0.70> = obs({action}_feasible) | p:0.70 | ep:infer | src:obs(analysis) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup({action}_plan, +0.20),
        obs({ev_neg}) => wkn({action}_plan, -0.10),
    ];
    {action}_plan |> resolve(ev) -> Ok(decomposed);
}}

#[phase(Verify)]
{{
    req({action}_plan, obs({action}_target)) |> verify({action}_plan) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf({action}_plan) {{
        c if c > 0.75 => assert({action}_plan),
        c if c > 0.45 => hedge({action}_plan),
        _ => suspend({action}_plan),
    }}
}}"#,
                action = s.action,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "To achieve {}, the goal should be decomposed into sequential sub-tasks. \
                 Feasibility is moderate given {} but constrained by {}.",
                s.action, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn delegation_template() -> Template {
    Template {
        category: Category::Delegation,
        difficulty: "hard",
        prompt_template: |s| {
            format!(
                "Should we delegate {} to another agent? Evaluate capability and trust in the {} domain.",
                s.action, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let capability: blf<{conf:.2}> = obs(agent_capability) | p:{conf:.2} | ep:direct | src:obs(agent_card) | scope:loc | t:fresh;
    let trust_level: blf<0.65> = obs(agent_trust) | p:0.65 | ep:infer | src:obs(history) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup(delegate_decision, +0.20),
        obs({ev_neg}) => wkn(delegate_decision, -0.15),
    ];
    delegate_decision |> resolve(ev) -> Ok(evaluated);
}}

#[phase(Verify)]
{{
    req(delegate_decision, obs(agent_capability)) |> verify(delegate_decision) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf(delegate_decision) {{
        c if c > 0.75 => assert(delegate_decision),
        c if c > 0.50 => hedge(delegate_decision),
        _ => reject(delegate_decision),
    }}
}}"#,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "Delegation of {} is recommended with monitoring. \
                 Agent capability is confirmed ({}) but trust constraints ({}) require oversight.",
                s.action, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn conflict_resolution_template() -> Template {
    Template {
        category: Category::ConflictResolution,
        difficulty: "hard",
        prompt_template: |s| {
            format!(
                "There is a conflict about {} in the {} domain. How should we resolve it?",
                s.subject, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let position_a: blf<{conf:.2}> = obs({subject}_view_a) | p:{conf:.2} | ep:direct | src:obs(agent_a) | scope:loc | t:fresh;
    let position_b: blf<0.60> = obs({subject}_view_b) | p:0.60 | ep:direct | src:obs(agent_b) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup(resolution, +0.20),
        obs({ev_neg}) => wkn(resolution, -0.15),
    ];
    resolution |> resolve(ev) -> Ok(resolved);
}}

#[phase(Verify)]
{{
    req(resolution, obs({subject}_view_a)) |> verify(resolution) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf(resolution) {{
        c if c > 0.70 => assert(resolution),
        c if c > 0.45 => hedge(resolution),
        _ => suspend(resolution),
    }}
}}"#,
                subject = s.subject,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "The conflict about {} can be resolved by weighing both positions. \
                 Evidence favors the approach supported by {}, though {} introduces uncertainty.",
                s.subject, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn tool_selection_template() -> Template {
    Template {
        category: Category::ToolSelection,
        difficulty: "medium",
        prompt_template: |s| {
            format!(
                "Which tool should we use for {} in the {} domain?",
                s.action, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let tool_fit: blf<{conf:.2}> = obs({action}_tool_fit) | p:{conf:.2} | ep:direct | src:obs(tool_registry) | scope:loc | t:fresh;
    let tool_cost: blf<0.70> = obs({action}_tool_cost) | p:0.70 | ep:infer | src:obs(metrics) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup(tool_choice, +0.25),
        obs({ev_neg}) => wkn(tool_choice, -0.10),
    ];
    tool_choice |> resolve(ev) -> Ok(selected);
}}

#[phase(Verify)]
{{
    req(tool_choice, obs({action}_tool_fit)) |> verify(tool_choice) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf(tool_choice) {{
        c if c > 0.80 => assert(tool_choice),
        c if c > 0.50 => hedge(tool_choice),
        _ => suspend(tool_choice),
    }}
}}"#,
                action = s.action,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "The best tool for {} is selected based on fitness ({}) and cost considerations. \
                 Minor concerns about {} noted but manageable.",
                s.action, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn self_correction_template() -> Template {
    Template {
        category: Category::SelfCorrection,
        difficulty: "hard",
        prompt_template: |s| {
            format!(
                "The previous approach to {} failed. What should we try now in the {} domain?",
                s.action, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let failure: blf<0.90> = obs({action}_failed) | p:0.90 | ep:direct | src:obs(result) | scope:loc | t:fresh;
    let alt_approach: blf<{conf:.2}> = obs({action}_alternative) | p:{conf:.2} | ep:infer | src:obs(analysis) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup(retry_plan, +0.25),
        obs({ev_neg}) => wkn(retry_plan, -0.10),
    ];
    retry_plan |> resolve(ev) -> Ok(revised);
}}

#[phase(Verify)]
{{
    req(retry_plan, obs({action}_alternative)) |> verify(retry_plan) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf(retry_plan) {{
        c if c > 0.70 => assert(retry_plan),
        c if c > 0.40 => hedge(retry_plan),
        _ => reject(retry_plan),
    }}
}}"#,
                action = s.action,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "After the failure of the initial approach to {}, a revised strategy is recommended. \
                 The alternative is supported by {} but must account for {}.",
                s.action, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn memory_retrieval_template() -> Template {
    Template {
        category: Category::MemoryRetrieval,
        difficulty: "easy",
        prompt_template: |s| {
            format!(
                "What do we know about {} from past experience in the {} domain?",
                s.subject, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let recalled: blf<{conf:.2}> = obs({subject}_memory) | p:{conf:.2} | ep:direct | src:obs(memory_store) | scope:loc | t:stale;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup(recall_result, +0.15),
        obs({ev_neg}) => wkn(recall_result, -0.10),
    ];
    recall_result |> resolve(ev) -> Ok(retrieved);
}}

#[phase(Verify)]
{{
    req(recall_result, obs({subject}_memory)) |> verify(recall_result) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf(recall_result) {{
        c if c > 0.75 => assert(recall_result),
        c if c > 0.45 => hedge(recall_result),
        _ => suspend(recall_result),
    }}
}}"#,
                subject = s.subject,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "Memory retrieval about {} yielded relevant past experience. \
                 The recalled information ({}) is partially supported but may be stale ({}).",
                s.subject, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

pub fn multi_step_planning_template() -> Template {
    Template {
        category: Category::MultiStepPlanning,
        difficulty: "hard",
        prompt_template: |s| {
            format!(
                "Plan the steps needed to complete {} in the {} domain.",
                s.action, s.domain
            )
        },
        trace_template: |s| {
            format!(
                r#"#[phase(Frame)]
impl Deductive {{
    let objective: blf<{conf:.2}> = obs({action}_objective) | p:{conf:.2} | ep:direct | src:obs(requirements) | scope:loc | t:fresh;
    let constraints: blf<0.80> = obs({action}_constraints) | p:0.80 | ep:direct | src:obs(environment) | scope:loc | t:fresh;
}}

#[phase(Explore)]
{{
    let ev = [
        obs({ev_pos}) => sup(execution_plan, +0.20),
        obs({ev_neg}) => wkn(execution_plan, -0.15),
    ];
    execution_plan |> resolve(ev) -> Ok(planned);
}}

#[phase(Verify)]
{{
    req(execution_plan, obs({action}_objective)) |> verify(execution_plan) -> Ok(());
}}

#[phase(Decide)]
{{
    match conf(execution_plan) {{
        c if c > 0.75 => assert(execution_plan),
        c if c > 0.45 => hedge(execution_plan),
        _ => suspend(execution_plan),
    }}
}}"#,
                action = s.action,
                conf = s.confidence,
                ev_pos = s.evidence_pos,
                ev_neg = s.evidence_neg,
            )
        },
        conclusion_template: |s| {
            format!(
                "A multi-step plan for {} has been constructed. \
                 Key enablers include {} while {} may require contingency planning.",
                s.action, s.evidence_pos, s.evidence_neg
            )
        },
    }
}

/// Get the template function for a given category
pub fn get_template(category: Category) -> Template {
    match category {
        Category::Causal => causal_template(),
        Category::RiskAssessment => risk_assessment_template(),
        Category::EvidenceEvaluation => evidence_evaluation_template(),
        Category::GoalDecomposition => goal_decomposition_template(),
        Category::Delegation => delegation_template(),
        Category::ConflictResolution => conflict_resolution_template(),
        Category::ToolSelection => tool_selection_template(),
        Category::SelfCorrection => self_correction_template(),
        Category::MemoryRetrieval => memory_retrieval_template(),
        Category::MultiStepPlanning => multi_step_planning_template(),
    }
}
