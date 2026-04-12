use rlang::ast::communicative::*;

// ============================================================================
// TaskState Tests
// ============================================================================

#[test]
fn task_state_submitted_transitions() {
    let transitions = TaskState::Submitted.valid_transitions();
    assert!(transitions.contains(&TaskState::Working));
    assert!(transitions.contains(&TaskState::Rejected));
    assert!(transitions.contains(&TaskState::Canceled));
    assert!(!transitions.contains(&TaskState::Completed));
    assert!(!transitions.contains(&TaskState::Failed));
}

#[test]
fn task_state_working_transitions() {
    let transitions = TaskState::Working.valid_transitions();
    assert!(transitions.contains(&TaskState::Completed));
    assert!(transitions.contains(&TaskState::Failed));
    assert!(transitions.contains(&TaskState::Canceled));
    assert!(transitions.contains(&TaskState::InputRequired));
    assert!(transitions.contains(&TaskState::AuthRequired));
    assert!(!transitions.contains(&TaskState::Submitted));
    assert!(!transitions.contains(&TaskState::Rejected));
}

#[test]
fn task_state_input_required_transitions() {
    let transitions = TaskState::InputRequired.valid_transitions();
    assert!(transitions.contains(&TaskState::Working));
    assert!(transitions.contains(&TaskState::Canceled));
    assert_eq!(transitions.len(), 2);
}

#[test]
fn task_state_auth_required_transitions() {
    let transitions = TaskState::AuthRequired.valid_transitions();
    assert!(transitions.contains(&TaskState::Working));
    assert!(transitions.contains(&TaskState::Canceled));
    assert_eq!(transitions.len(), 2);
}

#[test]
fn task_state_terminal_states_have_empty_transitions() {
    let terminal_states = vec![
        TaskState::Completed,
        TaskState::Failed,
        TaskState::Canceled,
        TaskState::Rejected,
    ];
    for state in terminal_states {
        assert!(
            state.valid_transitions().is_empty(),
            "Terminal state {:?} should have no valid transitions",
            state
        );
        assert!(state.is_terminal(), "{:?} should be terminal", state);
    }
}

#[test]
fn task_state_can_transition_to_valid() {
    assert!(TaskState::Submitted.can_transition_to(&TaskState::Working));
    assert!(TaskState::Working.can_transition_to(&TaskState::Completed));
    assert!(TaskState::Working.can_transition_to(&TaskState::InputRequired));
    assert!(TaskState::InputRequired.can_transition_to(&TaskState::Working));
}

#[test]
fn task_state_can_transition_to_invalid() {
    assert!(!TaskState::Submitted.can_transition_to(&TaskState::Completed));
    assert!(!TaskState::Submitted.can_transition_to(&TaskState::Failed));
    assert!(!TaskState::Completed.can_transition_to(&TaskState::Working));
    assert!(!TaskState::Failed.can_transition_to(&TaskState::Submitted));
    assert!(!TaskState::Canceled.can_transition_to(&TaskState::Working));
    assert!(!TaskState::Rejected.can_transition_to(&TaskState::Submitted));
}

#[test]
fn task_state_no_self_transitions() {
    let all_states = vec![
        TaskState::Submitted,
        TaskState::Working,
        TaskState::InputRequired,
        TaskState::AuthRequired,
        TaskState::Completed,
        TaskState::Failed,
        TaskState::Canceled,
        TaskState::Rejected,
    ];
    for state in &all_states {
        assert!(
            !state.can_transition_to(state),
            "{:?} should not be able to transition to itself",
            state
        );
    }
}

// ============================================================================
// CommActKind Tests
// ============================================================================

#[test]
fn comm_act_kind_has_all_12_variants() {
    let all = CommActKind::all_variants();
    assert_eq!(all.len(), 12, "CommActKind should have exactly 12 variants");
}

#[test]
fn comm_act_kind_contains_all_expected_variants() {
    let all = CommActKind::all_variants();
    assert!(all.contains(&CommActKind::Inform));
    assert!(all.contains(&CommActKind::Confirm));
    assert!(all.contains(&CommActKind::Disconfirm));
    assert!(all.contains(&CommActKind::Request));
    assert!(all.contains(&CommActKind::QueryIf));
    assert!(all.contains(&CommActKind::Cfp));
    assert!(all.contains(&CommActKind::Propose));
    assert!(all.contains(&CommActKind::Accept));
    assert!(all.contains(&CommActKind::Reject));
    assert!(all.contains(&CommActKind::Agree));
    assert!(all.contains(&CommActKind::Refuse));
    assert!(all.contains(&CommActKind::Failure));
}

#[test]
fn comm_act_kind_categories() {
    // Informative: 3 acts
    assert_eq!(CommActKind::Inform.category(), "Informative");
    assert_eq!(CommActKind::Confirm.category(), "Informative");
    assert_eq!(CommActKind::Disconfirm.category(), "Informative");

    // Requestive: 2 acts
    assert_eq!(CommActKind::Request.category(), "Requestive");
    assert_eq!(CommActKind::QueryIf.category(), "Requestive");

    // Negotiation: 4 acts
    assert_eq!(CommActKind::Cfp.category(), "Negotiation");
    assert_eq!(CommActKind::Propose.category(), "Negotiation");
    assert_eq!(CommActKind::Accept.category(), "Negotiation");
    assert_eq!(CommActKind::Reject.category(), "Negotiation");

    // Commitment: 2 acts
    assert_eq!(CommActKind::Agree.category(), "Commitment");
    assert_eq!(CommActKind::Refuse.category(), "Commitment");

    // Lifecycle: 1 act
    assert_eq!(CommActKind::Failure.category(), "Lifecycle");
}

// ============================================================================
// ContractExpr Tests
// ============================================================================

#[test]
fn contract_expr_construction() {
    let contract = ContractExpr {
        input_spec: "text/plain".to_string(),
        output_spec: "application/json".to_string(),
        required_skills: vec!["translation".to_string(), "summarization".to_string()],
        resources: vec![
            ("api_calls".to_string(), 100.0),
            ("wall_time".to_string(), 300.0),
        ],
        temporal: TimeConstraintsExpr {
            deadline: Some("2026-12-31T23:59:59Z".to_string()),
            max_duration: Some(3600.0),
            checkpoint_interval: Some(300.0),
        },
        success: "output.quality > 0.8".to_string(),
        termination: "elapsed > max_duration".to_string(),
        mode: ContractMode::Balanced,
    };

    assert_eq!(contract.required_skills.len(), 2);
    assert_eq!(contract.resources.len(), 2);
    assert!(contract.temporal.deadline.is_some());
    assert!(contract.temporal.max_duration.is_some());
    assert!(contract.temporal.checkpoint_interval.is_some());
    assert_eq!(contract.mode, ContractMode::Balanced);
}

#[test]
fn contract_expr_serialization_roundtrip() {
    let contract = ContractExpr {
        input_spec: "text/plain".to_string(),
        output_spec: "application/json".to_string(),
        required_skills: vec!["analysis".to_string()],
        resources: vec![("tokens".to_string(), 5000.0)],
        temporal: TimeConstraintsExpr::default(),
        success: "true".to_string(),
        termination: "false".to_string(),
        mode: ContractMode::Urgent,
    };

    let json = serde_json::to_string(&contract).expect("serialize");
    let deserialized: ContractExpr = serde_json::from_str(&json).expect("deserialize");
    assert_eq!(contract, deserialized);
}

#[test]
fn contract_mode_custom_variant() {
    let mode = ContractMode::Custom {
        profile: "high_quality_slow".to_string(),
    };
    let json = serde_json::to_string(&mode).expect("serialize");
    let deserialized: ContractMode = serde_json::from_str(&json).expect("deserialize");
    assert_eq!(mode, deserialized);
}

#[test]
fn time_constraints_defaults() {
    let tc = TimeConstraintsExpr::default();
    assert!(tc.deadline.is_none());
    assert!(tc.max_duration.is_none());
    assert!(tc.checkpoint_interval.is_none());
}

// ============================================================================
// TopologyExpr Tests
// ============================================================================

#[test]
fn topology_star_construction() {
    let topo = TopologyExpr::Star {
        orchestrator: "coordinator".to_string(),
        workers: vec!["worker_a".to_string(), "worker_b".to_string()],
    };
    match &topo {
        TopologyExpr::Star { orchestrator, workers } => {
            assert_eq!(orchestrator, "coordinator");
            assert_eq!(workers.len(), 2);
        }
        _ => panic!("Expected Star topology"),
    }
}

#[test]
fn topology_chain_construction() {
    let topo = TopologyExpr::Chain {
        stages: vec!["stage_1".to_string(), "stage_2".to_string(), "stage_3".to_string()],
    };
    match &topo {
        TopologyExpr::Chain { stages } => {
            assert_eq!(stages.len(), 3);
        }
        _ => panic!("Expected Chain topology"),
    }
}

#[test]
fn topology_tree_construction() {
    let topo = TopologyExpr::Tree {
        root: "root_agent".to_string(),
        children: vec![
            ("root_agent".to_string(), vec!["child_a".to_string(), "child_b".to_string()]),
        ],
    };
    match &topo {
        TopologyExpr::Tree { root, children } => {
            assert_eq!(root, "root_agent");
            assert_eq!(children.len(), 1);
        }
        _ => panic!("Expected Tree topology"),
    }
}

#[test]
fn topology_graph_construction() {
    let topo = TopologyExpr::Graph {
        agents: vec!["a".to_string(), "b".to_string(), "c".to_string()],
        edges: vec![
            ("a".to_string(), "b".to_string()),
            ("b".to_string(), "c".to_string()),
        ],
    };
    match &topo {
        TopologyExpr::Graph { agents, edges } => {
            assert_eq!(agents.len(), 3);
            assert_eq!(edges.len(), 2);
        }
        _ => panic!("Expected Graph topology"),
    }
}

#[test]
fn topology_blackboard_construction() {
    let topo = TopologyExpr::Blackboard {
        controller: "controller".to_string(),
        contributors: vec!["agent_1".to_string(), "agent_2".to_string()],
    };
    match &topo {
        TopologyExpr::Blackboard { controller, contributors } => {
            assert_eq!(controller, "controller");
            assert_eq!(contributors.len(), 2);
        }
        _ => panic!("Expected Blackboard topology"),
    }
}

#[test]
fn topology_all_5_variants_are_distinct() {
    let topologies: Vec<TopologyExpr> = vec![
        TopologyExpr::Star { orchestrator: "o".to_string(), workers: vec![] },
        TopologyExpr::Chain { stages: vec![] },
        TopologyExpr::Tree { root: "r".to_string(), children: vec![] },
        TopologyExpr::Graph { agents: vec![], edges: vec![] },
        TopologyExpr::Blackboard { controller: "c".to_string(), contributors: vec![] },
    ];
    // Verify all 5 are different from each other
    for i in 0..topologies.len() {
        for j in (i + 1)..topologies.len() {
            assert_ne!(
                topologies[i], topologies[j],
                "Topology variants {} and {} should be distinct",
                i, j
            );
        }
    }
}

// ============================================================================
// AgentCardExpr Tests
// ============================================================================

#[test]
fn agent_card_construction() {
    let card = AgentCardExpr {
        id: "agent-001".to_string(),
        name: "Translation Agent".to_string(),
        description: "Translates text between languages".to_string(),
        skills: vec![SkillExpr {
            id: "skill-translate".to_string(),
            name: "translate".to_string(),
            description: "Translate text".to_string(),
            tags: vec!["translation".to_string(), "nlp".to_string()],
            input_modes: vec!["text/plain".to_string()],
            output_modes: vec!["text/plain".to_string()],
        }],
        capabilities: CapabilitiesExpr {
            streaming: true,
            push_notifications: false,
            extended_card: false,
        },
        interfaces: vec![InterfaceExpr::JsonRpc {
            url: "https://agent.example.com/rpc".to_string(),
            version: "2.0".to_string(),
        }],
    };

    assert_eq!(card.id, "agent-001");
    assert_eq!(card.skills.len(), 1);
    assert_eq!(card.skills[0].tags.len(), 2);
    assert!(card.capabilities.streaming);
    assert!(!card.capabilities.push_notifications);
}

#[test]
fn agent_card_serialization_roundtrip() {
    let card = AgentCardExpr {
        id: "a1".to_string(),
        name: "Test".to_string(),
        description: "Test agent".to_string(),
        skills: vec![],
        capabilities: CapabilitiesExpr::default(),
        interfaces: vec![],
    };

    let json = serde_json::to_string(&card).expect("serialize");
    let deserialized: AgentCardExpr = serde_json::from_str(&json).expect("deserialize");
    assert_eq!(card, deserialized);
}

// ============================================================================
// TrustModelExpr Tests
// ============================================================================

#[test]
fn trust_model_default_is_empty() {
    let trust = TrustModelExpr::default();
    assert!(trust.interaction.is_empty());
    assert!(trust.role_based.is_empty());
    assert!(trust.witness.is_empty());
    assert!(trust.certified.is_empty());
}

#[test]
fn trust_model_construction_with_data() {
    let trust = TrustModelExpr {
        interaction: vec![
            ("agent-a".to_string(), 0.8),
            ("agent-b".to_string(), 0.6),
        ],
        role_based: vec![
            ("translator".to_string(), 0.9),
        ],
        witness: vec![
            ("agent-a".to_string(), vec![
                ("witness-1".to_string(), 0.7),
                ("witness-2".to_string(), 0.85),
            ]),
        ],
        certified: vec![
            ("agent-a".to_string(), vec!["cert-iso9001".to_string()]),
        ],
    };

    assert_eq!(trust.interaction.len(), 2);
    assert_eq!(trust.role_based.len(), 1);
    assert_eq!(trust.witness.len(), 1);
    assert_eq!(trust.witness[0].1.len(), 2);
    assert_eq!(trust.certified[0].1.len(), 1);
}

#[test]
fn trust_model_serialization_roundtrip() {
    let trust = TrustModelExpr {
        interaction: vec![("a".to_string(), 0.5)],
        role_based: vec![],
        witness: vec![],
        certified: vec![],
    };

    let json = serde_json::to_string(&trust).expect("serialize");
    let deserialized: TrustModelExpr = serde_json::from_str(&json).expect("deserialize");
    assert_eq!(trust, deserialized);
}

// ============================================================================
// ConflictExpr / ConflictResolverExpr / ResolutionExpr Tests
// ============================================================================

#[test]
fn conflict_types_construction() {
    let goal_conflict = ConflictExpr::Goal {
        agents: vec!["a".to_string(), "b".to_string()],
        goals: vec![("a".to_string(), "goal_1".to_string()), ("b".to_string(), "goal_2".to_string())],
    };
    let belief_conflict = ConflictExpr::Belief {
        agents: vec!["a".to_string(), "b".to_string()],
        claims: vec![("a".to_string(), "claim_1".to_string())],
    };
    let plan_conflict = ConflictExpr::Plan {
        agents: vec!["a".to_string()],
        plans: vec![("a".to_string(), "plan_1".to_string())],
    };

    // Ensure all three variants are distinct
    assert_ne!(goal_conflict, belief_conflict);
    assert_ne!(belief_conflict, plan_conflict);
    assert_ne!(goal_conflict, plan_conflict);
}

#[test]
fn conflict_resolver_all_variants() {
    let resolvers: Vec<ConflictResolverExpr> = vec![
        ConflictResolverExpr::Priority(vec!["a".to_string()]),
        ConflictResolverExpr::Evidence,
        ConflictResolverExpr::Debate { max_rounds: 3, judge: "j".to_string() },
        ConflictResolverExpr::Vote { threshold: 0.5 },
        ConflictResolverExpr::Arbitrate { arbiter: "arb".to_string() },
    ];
    assert_eq!(resolvers.len(), 5);
}

#[test]
fn resolution_variants() {
    let resolved = ResolutionExpr::Resolved {
        outcome: "belief_a".to_string(),
        justification: vec!["evidence_1".to_string()],
    };
    let deadlock = ResolutionExpr::Deadlock {
        positions: vec![("a".to_string(), "pos_a".to_string())],
    };
    let escalated = ResolutionExpr::Escalated {
        to: "arbiter".to_string(),
        context: "conflict_context".to_string(),
    };

    assert_ne!(resolved, deadlock);
    assert_ne!(deadlock, escalated);
    assert_ne!(resolved, escalated);
}

// ============================================================================
// MonitorPolicyExpr / InterventionTriggerExpr / InterventionActionExpr Tests
// ============================================================================

#[test]
fn monitor_policy_construction() {
    let policy = MonitorPolicyExpr {
        check_interval: 30.0,
        triggers: vec![
            InterventionTriggerExpr::DeadlineRisk { threshold: 0.8 },
            InterventionTriggerExpr::NoProgress { duration: 120.0 },
        ],
        escalation: Some("supervisor".to_string()),
    };
    assert_eq!(policy.triggers.len(), 2);
    assert!(policy.escalation.is_some());
}

#[test]
fn intervention_trigger_all_variants() {
    let triggers: Vec<InterventionTriggerExpr> = vec![
        InterventionTriggerExpr::DeadlineRisk { threshold: 0.8 },
        InterventionTriggerExpr::ResourceOverrun { threshold: 0.9 },
        InterventionTriggerExpr::QualityDrop { metric: "accuracy".to_string(), min_score: 0.7 },
        InterventionTriggerExpr::NoProgress { duration: 60.0 },
        InterventionTriggerExpr::ContextDrift { similarity_threshold: 0.5 },
        InterventionTriggerExpr::ExternalChange { condition: "market_shift".to_string() },
    ];
    assert_eq!(triggers.len(), 6);
}

#[test]
fn intervention_action_all_variants() {
    let actions: Vec<InterventionActionExpr> = vec![
        InterventionActionExpr::Continue,
        InterventionActionExpr::SendGuidance("focus on task".to_string()),
        InterventionActionExpr::AddResources(vec![("tokens".to_string(), 1000.0)]),
        InterventionActionExpr::Revoke { reason: "timeout".to_string() },
        InterventionActionExpr::Escalate { to: "manager".to_string() },
        InterventionActionExpr::TakeOver,
    ];
    assert_eq!(actions.len(), 6);
}

// ============================================================================
// MessageExpr / PartExpr / ArtifactExpr Tests
// ============================================================================

#[test]
fn message_expr_construction() {
    let msg = MessageExpr {
        id: "msg-001".to_string(),
        context_id: Some("ctx-456".to_string()),
        task_id: Some("task-123".to_string()),
        role: Role::User,
        parts: vec![PartExpr::Text("Hello, agent".to_string())],
        reference_tasks: vec!["task-100".to_string()],
    };
    assert_eq!(msg.parts.len(), 1);
    assert_eq!(msg.role, Role::User);
    assert!(msg.context_id.is_some());
}

#[test]
fn part_expr_all_variants() {
    let parts: Vec<PartExpr> = vec![
        PartExpr::Text("hello".to_string()),
        PartExpr::Data {
            content: r#"{"key": "value"}"#.to_string(),
            media_type: Some("application/json".to_string()),
        },
        PartExpr::Raw {
            content: "base64data".to_string(),
            filename: Some("file.bin".to_string()),
            media_type: Some("application/octet-stream".to_string()),
        },
        PartExpr::Url {
            url: "https://example.com/doc.pdf".to_string(),
            media_type: Some("application/pdf".to_string()),
        },
    ];
    assert_eq!(parts.len(), 4);
}

#[test]
fn artifact_expr_construction() {
    let artifact = ArtifactExpr {
        id: "artifact-001".to_string(),
        name: Some("Translation Result".to_string()),
        description: Some("Translated document".to_string()),
        parts: vec![PartExpr::Text("Translated text here".to_string())],
    };
    assert_eq!(artifact.id, "artifact-001");
    assert!(artifact.name.is_some());
    assert_eq!(artifact.parts.len(), 1);
}

#[test]
fn artifact_expr_serialization_roundtrip() {
    let artifact = ArtifactExpr {
        id: "a1".to_string(),
        name: None,
        description: None,
        parts: vec![PartExpr::Text("data".to_string())],
    };

    let json = serde_json::to_string(&artifact).expect("serialize");
    let deserialized: ArtifactExpr = serde_json::from_str(&json).expect("deserialize");
    assert_eq!(artifact, deserialized);
}

// ============================================================================
// InterfaceExpr Tests
// ============================================================================

#[test]
fn interface_all_variants() {
    let interfaces: Vec<InterfaceExpr> = vec![
        InterfaceExpr::JsonRpc { url: "http://localhost:8080".to_string(), version: "2.0".to_string() },
        InterfaceExpr::Grpc { url: "http://localhost:9090".to_string(), version: "1.0".to_string() },
        InterfaceExpr::HttpJson { url: "http://localhost:3000".to_string(), version: "1.0".to_string() },
    ];
    assert_eq!(interfaces.len(), 3);
    // All variants are distinct
    assert_ne!(interfaces[0], interfaces[1]);
    assert_ne!(interfaces[1], interfaces[2]);
}
