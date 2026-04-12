use serde::{Deserialize, Serialize};

// ============================================================================
// Task Lifecycle — A2A State Machine
// ============================================================================

/// A2A-aligned task state
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum TaskState {
    Submitted,
    Working,
    InputRequired,
    AuthRequired,
    Completed,
    Failed,
    Canceled,
    Rejected,
}

impl TaskState {
    pub fn is_terminal(&self) -> bool {
        matches!(self, Self::Completed | Self::Failed | Self::Canceled | Self::Rejected)
    }

    pub fn valid_transitions(&self) -> Vec<TaskState> {
        match self {
            Self::Submitted     => vec![Self::Working, Self::Rejected, Self::Canceled],
            Self::Working       => vec![Self::Completed, Self::Failed, Self::Canceled, Self::InputRequired, Self::AuthRequired],
            Self::InputRequired => vec![Self::Working, Self::Canceled],
            Self::AuthRequired  => vec![Self::Working, Self::Canceled],
            Self::Completed | Self::Failed | Self::Canceled | Self::Rejected => vec![],
        }
    }

    /// Check whether transitioning from self to `target` is valid.
    pub fn can_transition_to(&self, target: &TaskState) -> bool {
        self.valid_transitions().contains(target)
    }
}

// ============================================================================
// Agent Identity and Discovery — A2A AgentCard
// ============================================================================

/// Agent self-description — mirrors A2A AgentCard.
/// Published at `/.well-known/agent-card.json` in the A2A protocol.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct AgentCardExpr {
    pub id: String,
    pub name: String,
    pub description: String,
    pub skills: Vec<SkillExpr>,
    pub capabilities: CapabilitiesExpr,
    pub interfaces: Vec<InterfaceExpr>,
}

/// A single skill an agent can perform.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct SkillExpr {
    pub id: String,
    pub name: String,
    pub description: String,
    pub tags: Vec<String>,
    pub input_modes: Vec<String>,
    pub output_modes: Vec<String>,
}

/// Agent capability flags — what protocol features the agent supports.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct CapabilitiesExpr {
    pub streaming: bool,
    pub push_notifications: bool,
    pub extended_card: bool,
}

impl Default for CapabilitiesExpr {
    fn default() -> Self {
        Self {
            streaming: false,
            push_notifications: false,
            extended_card: false,
        }
    }
}

/// Protocol binding — how an agent communicates.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub enum InterfaceExpr {
    JsonRpc { url: String, version: String },
    Grpc { url: String, version: String },
    HttpJson { url: String, version: String },
}

// ============================================================================
// Communicative Acts — FIPA-ACL inspired, 12 core acts
// ============================================================================

/// A typed communicative act between agents.
/// Every inter-agent message is one of these — no untyped messages.
/// Drawn from FIPA-ACL's 22 speech acts, compressed to the 12 most common.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum CommActKind {
    // === Informative ===
    /// Assert a proposition to another agent
    Inform,
    /// Confirm a previously communicated proposition
    Confirm,
    /// Deny a previously communicated proposition
    Disconfirm,

    // === Requestive ===
    /// Request another agent to perform an action
    Request,
    /// Ask whether a proposition is true
    QueryIf,

    // === Negotiation ===
    /// Call for proposals — broadcast task to candidate agents
    Cfp,
    /// Propose to perform a task under conditions
    Propose,
    /// Accept a proposal
    Accept,
    /// Reject a proposal with reason
    Reject,

    // === Commitment ===
    /// Commit to performing an action
    Agree,
    /// Decline to perform an action
    Refuse,

    // === Lifecycle ===
    /// Report task failure
    Failure,
}

impl CommActKind {
    /// Returns all 12 communicative act variants.
    pub fn all_variants() -> Vec<CommActKind> {
        vec![
            Self::Inform,
            Self::Confirm,
            Self::Disconfirm,
            Self::Request,
            Self::QueryIf,
            Self::Cfp,
            Self::Propose,
            Self::Accept,
            Self::Reject,
            Self::Agree,
            Self::Refuse,
            Self::Failure,
        ]
    }

    /// Returns the category of this communicative act.
    pub fn category(&self) -> &'static str {
        match self {
            Self::Inform | Self::Confirm | Self::Disconfirm => "Informative",
            Self::Request | Self::QueryIf => "Requestive",
            Self::Cfp | Self::Propose | Self::Accept | Self::Reject => "Negotiation",
            Self::Agree | Self::Refuse => "Commitment",
            Self::Failure => "Lifecycle",
        }
    }
}

// ============================================================================
// Role in a message exchange
// ============================================================================

/// Role in a message exchange — A2A aligned
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize, Deserialize)]
pub enum Role {
    User,
    Agent,
}

// ============================================================================
// Agent Contracts — Ye & Tan (2025) seven-tuple
// ============================================================================

/// Contract mode for delegation — quality-speed tradeoff
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ContractMode {
    Urgent,
    Economical,
    Balanced,
    Custom { profile: String },
}

/// A formal agreement between delegating and delegated agent.
/// Seven-tuple: (Input, Output, Skills, Resources, Time, Success, Termination)
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ContractExpr {
    /// What the agent will receive
    pub input_spec: String,
    /// What it must produce
    pub output_spec: String,
    /// Capabilities needed (skill IDs)
    pub required_skills: Vec<String>,
    /// Resource limits (serialized as key-value pairs)
    pub resources: Vec<(String, f64)>,
    /// Deadline and duration bounds
    pub temporal: TimeConstraintsExpr,
    /// How to know it succeeded (predicate expression as string)
    pub success: String,
    /// When to force-stop (predicate expression as string)
    pub termination: String,
    /// Quality-speed tradeoff
    pub mode: ContractMode,
}

/// Temporal constraints for contracts and tasks.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TimeConstraintsExpr {
    /// Absolute deadline (ISO 8601 string or None)
    pub deadline: Option<String>,
    /// Maximum allowed duration in seconds
    pub max_duration: Option<f64>,
    /// How often to checkpoint progress, in seconds
    pub checkpoint_interval: Option<f64>,
}

impl Default for TimeConstraintsExpr {
    fn default() -> Self {
        Self {
            deadline: None,
            max_duration: None,
            checkpoint_interval: None,
        }
    }
}

// ============================================================================
// Trust Model — FIRE (Huynh et al. 2006), four trust sources
// ============================================================================

/// Multi-source trust model.
/// Uses Vec of tuples instead of HashMap for serialization compatibility.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct TrustModelExpr {
    /// Direct experience with agents: (agent_id, trust_score)
    pub interaction: Vec<(String, f64)>,
    /// Trust based on agent's role: (role_id, trust_score)
    pub role_based: Vec<(String, f64)>,
    /// Third-party reports: (agent_id, Vec<(witness_id, trust_score)>)
    pub witness: Vec<(String, Vec<(String, f64)>)>,
    /// Formally attested credentials: (agent_id, Vec<certificate_id>)
    pub certified: Vec<(String, Vec<String>)>,
}

impl Default for TrustModelExpr {
    fn default() -> Self {
        Self {
            interaction: Vec::new(),
            role_based: Vec::new(),
            witness: Vec::new(),
            certified: Vec::new(),
        }
    }
}

// ============================================================================
// Conflict Resolution
// ============================================================================

/// A detected conflict between agents.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ConflictExpr {
    /// Agents have incompatible objectives
    Goal {
        agents: Vec<String>,
        goals: Vec<(String, String)>,
    },
    /// Agents hold contradictory beliefs about facts
    Belief {
        agents: Vec<String>,
        claims: Vec<(String, String)>,
    },
    /// Agents propose incompatible action sequences
    Plan {
        agents: Vec<String>,
        plans: Vec<(String, String)>,
    },
}

/// Resolution strategy — selected based on context.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ConflictResolverExpr {
    /// Resolve by authority ranking
    Priority(Vec<String>),
    /// Resolve by evidence weight
    Evidence,
    /// Resolve by structured debate (bounded rounds)
    Debate { max_rounds: u8, judge: String },
    /// Resolve by majority vote
    Vote { threshold: f64 },
    /// Escalate to arbiter
    Arbitrate { arbiter: String },
}

/// Resolution outcome.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum ResolutionExpr {
    /// Conflict was resolved
    Resolved {
        outcome: String,
        justification: Vec<String>,
    },
    /// No resolution reached — positions remain
    Deadlock {
        positions: Vec<(String, String)>,
    },
    /// Escalated to higher authority
    Escalated {
        to: String,
        context: String,
    },
}

// ============================================================================
// Monitoring and Intervention
// ============================================================================

/// Policy for monitoring delegated tasks.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MonitorPolicyExpr {
    /// How often to check task progress, in seconds
    pub check_interval: f64,
    /// Conditions that trigger intervention
    pub triggers: Vec<InterventionTriggerExpr>,
    /// What to do when escalation is needed (agent ID)
    pub escalation: Option<String>,
}

/// Conditions that trigger intervention in a delegated task.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum InterventionTriggerExpr {
    /// Time budget at risk (threshold 0.0..1.0)
    DeadlineRisk { threshold: f64 },
    /// Resource consumption exceeding budget (threshold 0.0..1.0)
    ResourceOverrun { threshold: f64 },
    /// Quality metric dropped below acceptable level
    QualityDrop { metric: String, min_score: f64 },
    /// No progress for given duration in seconds
    NoProgress { duration: f64 },
    /// Agent's context has drifted from original task
    ContextDrift { similarity_threshold: f64 },
    /// External conditions changed
    ExternalChange { condition: String },
}

/// What to do when intervention is triggered.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum InterventionActionExpr {
    /// No action needed
    Continue,
    /// Redirect the agent with guidance
    SendGuidance(String),
    /// Give more resource budget: Vec of (resource_name, amount)
    AddResources(Vec<(String, f64)>),
    /// Cancel and reassign with reason
    Revoke { reason: String },
    /// Pass to higher authority
    Escalate { to: String },
    /// Resume doing it yourself
    TakeOver,
}

// ============================================================================
// Multi-Agent Orchestration Topologies
// ============================================================================

/// Orchestration topologies — how agents are organized.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum TopologyExpr {
    /// Central coordinator delegates to workers
    Star {
        orchestrator: String,
        workers: Vec<String>,
    },
    /// Sequential pipeline: A -> B -> C
    Chain {
        stages: Vec<String>,
    },
    /// Hierarchical delegation with sub-delegation
    Tree {
        root: String,
        children: Vec<(String, Vec<String>)>,
    },
    /// Arbitrary peer-to-peer communication
    Graph {
        agents: Vec<String>,
        edges: Vec<(String, String)>,
    },
    /// Shared workspace with opportunistic contribution
    Blackboard {
        controller: String,
        contributors: Vec<String>,
    },
}

// ============================================================================
// Messages and Parts — A2A aligned
// ============================================================================

/// A single unit of communication between agents — A2A Message.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct MessageExpr {
    /// Unique message ID
    pub id: String,
    /// Context ID for conversation continuity
    pub context_id: Option<String>,
    /// Associated task ID
    pub task_id: Option<String>,
    /// Who sent this message
    pub role: Role,
    /// Content parts
    pub parts: Vec<PartExpr>,
    /// Referenced task IDs for cross-task context
    pub reference_tasks: Vec<String>,
}

/// Content container — must be exactly one variant.
/// Mirrors A2A Part with text, data, raw, url.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub enum PartExpr {
    /// Plain text content
    Text(String),
    /// Structured data (serialized as JSON string)
    Data {
        content: String,
        media_type: Option<String>,
    },
    /// Raw bytes (base64 encoded)
    Raw {
        content: String,
        filename: Option<String>,
        media_type: Option<String>,
    },
    /// URL reference to content
    Url {
        url: String,
        media_type: Option<String>,
    },
}

// ============================================================================
// Artifacts — A2A task output containers
// ============================================================================

/// Task output container — A2A Artifact.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct ArtifactExpr {
    /// Unique within task
    pub id: String,
    /// Human-readable name
    pub name: Option<String>,
    /// Human-readable description
    pub description: Option<String>,
    /// Content parts (at least one)
    pub parts: Vec<PartExpr>,
}

// ============================================================================
// Tests (unit tests for this module)
// ============================================================================

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn task_state_terminal_states_have_no_transitions() {
        let terminals = vec![
            TaskState::Completed,
            TaskState::Failed,
            TaskState::Canceled,
            TaskState::Rejected,
        ];
        for state in terminals {
            assert!(
                state.valid_transitions().is_empty(),
                "{:?} is terminal but has transitions",
                state
            );
            assert!(state.is_terminal());
        }
    }

    #[test]
    fn task_state_non_terminal_states_have_transitions() {
        let non_terminals = vec![
            TaskState::Submitted,
            TaskState::Working,
            TaskState::InputRequired,
            TaskState::AuthRequired,
        ];
        for state in non_terminals {
            assert!(
                !state.valid_transitions().is_empty(),
                "{:?} is non-terminal but has no transitions",
                state
            );
            assert!(!state.is_terminal());
        }
    }

    #[test]
    fn task_state_valid_transition_check() {
        assert!(TaskState::Submitted.can_transition_to(&TaskState::Working));
        assert!(TaskState::Submitted.can_transition_to(&TaskState::Rejected));
        assert!(!TaskState::Submitted.can_transition_to(&TaskState::Completed));
        assert!(!TaskState::Completed.can_transition_to(&TaskState::Working));
    }

    #[test]
    fn comm_act_kind_has_12_variants() {
        let all = CommActKind::all_variants();
        assert_eq!(all.len(), 12);
    }

    #[test]
    fn comm_act_kind_categories_are_correct() {
        assert_eq!(CommActKind::Inform.category(), "Informative");
        assert_eq!(CommActKind::Confirm.category(), "Informative");
        assert_eq!(CommActKind::Disconfirm.category(), "Informative");
        assert_eq!(CommActKind::Request.category(), "Requestive");
        assert_eq!(CommActKind::QueryIf.category(), "Requestive");
        assert_eq!(CommActKind::Cfp.category(), "Negotiation");
        assert_eq!(CommActKind::Propose.category(), "Negotiation");
        assert_eq!(CommActKind::Accept.category(), "Negotiation");
        assert_eq!(CommActKind::Reject.category(), "Negotiation");
        assert_eq!(CommActKind::Agree.category(), "Commitment");
        assert_eq!(CommActKind::Refuse.category(), "Commitment");
        assert_eq!(CommActKind::Failure.category(), "Lifecycle");
    }
}
