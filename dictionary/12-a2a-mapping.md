# A2A Protocol Mapping

[Back to Dictionary Index](./README.md) | [Previous: Anti-Patterns](./11-anti-patterns.md) | [Next: Grammar](./13-grammar.md)

---

## Overview

RLang's communicative layer (Layer 4) is aligned with the A2A (Agent-to-Agent) Protocol v1.0, published by Google and the Linux Foundation under Apache 2.0. This document describes how RLang constructs map to A2A protocol concepts.

---

## TaskState State Machine

RLang's `TaskState` enum directly mirrors the A2A Protocol's 8 task states with enforced valid transitions.

### States

| State | Terminal? | Description |
|-------|-----------|-------------|
| `Submitted` | No | Task has been submitted to an agent |
| `Working` | No | Agent is actively working on the task |
| `InputRequired` | No | Agent needs additional input to continue |
| `AuthRequired` | No | Agent needs authorization to proceed |
| `Completed` | Yes | Task finished successfully |
| `Failed` | Yes | Task failed with an error |
| `Canceled` | Yes | Task was canceled |
| `Rejected` | Yes | Task was rejected by the agent |

### Transition Diagram

```
                    +---> Rejected
                    |
Submitted --------+---> Working --------+---> Completed
                    |       |            |
                    |       +---> Failed |
                    |       |            |
                    +-------+---> Canceled
                            |
                            +---> InputRequired ---> Working
                            |                   +--> Canceled
                            |
                            +---> AuthRequired ----> Working
                                                +--> Canceled
```

### Valid Transitions (from AST)

```rust
impl TaskState {
    fn valid_transitions(&self) -> Vec<TaskState> {
        match self {
            Submitted     => [Working, Rejected, Canceled],
            Working       => [Completed, Failed, Canceled, InputRequired, AuthRequired],
            InputRequired => [Working, Canceled],
            AuthRequired  => [Working, Canceled],
            Completed | Failed | Canceled | Rejected => [],  // Terminal
        }
    }
}
```

### RLang operators that trigger transitions

| Transition | RLang Operator |
|------------|---------------|
| -> Submitted | `dlg(agent, task)` |
| Submitted -> Working | `agree(task)` |
| Submitted -> Rejected | `refuse(task)` |
| Working -> Completed | `inform(delegator, result)` |
| Working -> Failed | `inform(delegator, Failure { ... })` |
| Any -> Canceled | `cancel(task)` |
| Working -> InputRequired | `query_if(delegator, question)` |

---

## Agent Cards and Discovery

### AgentCard Structure

RLang's `AgentCardExpr` mirrors the A2A AgentCard published at `/.well-known/agent-card.json`.

```rust
struct AgentCard {
    id: String,              // Unique agent identifier
    name: String,            // Human-readable name
    description: String,     // What the agent does
    skills: Vec<Skill>,      // Capabilities offered
    capabilities: Capabilities,  // Protocol feature flags
    interfaces: Vec<Interface>,  // How to communicate
}
```

### Skill Structure

```rust
struct Skill {
    id: String,
    name: String,
    description: String,
    tags: Vec<String>,            // Searchable tags
    input_modes: Vec<String>,     // Accepted input media types
    output_modes: Vec<String>,    // Produced output media types
}
```

### Capabilities

```rust
struct Capabilities {
    streaming: bool,              // Supports streaming responses
    push_notifications: bool,     // Can push updates
    extended_card: bool,          // Has extended metadata
}
```

### Discovery Flow in RLang

```rust
// Step 1: Discover agents with matching capabilities
let candidates = discover("monitoring");

// Step 2: Match specific capability to need
let agent_b = match_capability(monitor_goal, candidates);

// Step 3: Check trust before delegating
let trust = trust_model.trust_score(&agent_b.id);
req(trust >= 0.6);

// Step 4: Delegate with contract
dlg(agent_b.id, monitor_goal, contract) -> Ok(task_id);
```

---

## Message and Part Types

### Message (A2A Message)

```rust
struct Message {
    id: String,
    context_id: Option<String>,   // Conversation continuity
    task_id: Option<String>,      // Associated task
    role: Role,                   // User or Agent
    parts: Vec<Part>,             // Content
    reference_tasks: Vec<String>, // Cross-task references
}

enum Role {
    User,    // From client/delegator
    Agent,   // From server/delegate
}
```

### Part (A2A Part)

Content container with exactly one variant:

```rust
enum Part {
    Text(String),                                // Plain text
    Data { content: String, media_type: Option<String> },  // Structured data (JSON)
    Raw { content: String, filename: Option<String>, media_type: Option<String> },  // Base64 bytes
    Url { url: String, media_type: Option<String> },       // URL reference
}
```

### Artifact (A2A Artifact)

Task output container:

```rust
struct Artifact {
    id: String,
    name: Option<String>,
    description: Option<String>,
    parts: Vec<Part>,             // At least one part
}
```

---

## Contract and Delegation Patterns

### Contract Seven-Tuple

From Ye & Tan (2025). Formalizes delegation agreements.

| Tuple Element | RLang Field | Description |
|--------------|-------------|-------------|
| Input | `input_spec` | What the agent will receive |
| Output | `output_spec` | What it must produce |
| Skills | `required_skills` | Capabilities needed |
| Resources | `resources` | Budget limits |
| Time | `temporal` | Deadline and duration |
| Success | `success` | How to know it succeeded |
| Termination | `termination` | When to force-stop |

### Contract Mode

```rust
enum ContractMode {
    Urgent,       // Minimal reasoning, tight timeout
    Economical,   // Low effort, moderate timeout
    Balanced,     // Full reasoning, generous timeout
    Custom { profile: String },  // Custom resource profile
}
```

### Delegation Pattern

```rust
// 1. Define the contract
let monitor_contract = Contract {
    input_spec: "deploy_id, health_endpoint",
    output_spec: "alert_on_failure",
    resources: ResourceBudget { wall_time: "24h", api_calls: 100 },
    success: "no_alerts_24h OR alert_handled",
    mode: Balanced,
};

// 2. Trust-gated delegation
let score = trust_model.trust_score(&agent_b.id);
req(score >= 0.6);

// 3. Delegate
dlg(agent_b.id, monitor_goal, monitor_contract)
    -> Ok(task_id);
```

### Resource Conservation Law

When delegating, child resource budgets must sum to less than or equal to the parent budget:

```rust
// Enforced by validator
children.iter().map(|c| c.resources).sum() <= parent.resources
```

---

## Monitoring and Intervention

### Monitor Policy

```rust
struct MonitorPolicy {
    check_interval: f64,                  // Seconds between checks
    triggers: Vec<InterventionTrigger>,   // When to intervene
    escalation: Option<String>,           // Who to escalate to
}
```

### Intervention Triggers

| Trigger | Description |
|---------|-------------|
| `DeadlineRisk { threshold }` | Time budget at risk |
| `ResourceOverrun { threshold }` | Spending exceeding budget |
| `QualityDrop { metric, min_score }` | Quality below acceptable |
| `NoProgress { duration }` | Stuck with no progress |
| `ContextDrift { similarity_threshold }` | Drifted from original task |
| `ExternalChange { condition }` | Environment changed |

### Intervention Actions

| Action | Description |
|--------|-------------|
| `Continue` | No action needed |
| `SendGuidance(msg)` | Redirect the agent |
| `AddResources(budget)` | Increase budget |
| `Revoke { reason }` | Cancel and reassign |
| `Escalate { to }` | Pass to authority |
| `TakeOver` | Resume doing it yourself |

---

## Orchestration Topologies

RLang supports 5 multi-agent orchestration patterns:

### Star

Central coordinator delegates to workers.

```rust
Topology::Star {
    orchestrator: "coordinator",
    workers: ["agent_a", "agent_b", "agent_c"],
}
```

```
        agent_a
       /
coord --- agent_b
       \
        agent_c
```

### Chain

Sequential pipeline where each agent processes and passes forward.

```rust
Topology::Chain {
    stages: ["preprocessor", "analyzer", "reporter"],
}
```

```
preprocessor -> analyzer -> reporter
```

### Tree

Hierarchical delegation with sub-delegation.

```rust
Topology::Tree {
    root: "lead",
    children: [("manager_a", ["worker_1", "worker_2"]),
               ("manager_b", ["worker_3"])],
}
```

```
         lead
        /    \
    mgr_a    mgr_b
    /   \      |
  w_1   w_2   w_3
```

### Graph

Arbitrary peer-to-peer communication.

```rust
Topology::Graph {
    agents: ["a", "b", "c", "d"],
    edges: [("a", "b"), ("b", "c"), ("a", "d"), ("c", "d")],
}
```

### Blackboard

Shared workspace with opportunistic contribution.

```rust
Topology::Blackboard {
    controller: "moderator",
    contributors: ["specialist_a", "specialist_b", "specialist_c"],
}
```

---

## FIPA-ACL Mapping

RLang's 12 communicative act kinds map to FIPA-ACL speech acts:

| RLang CommActKind | FIPA-ACL Act | Category |
|-------------------|-------------|----------|
| `Inform` | inform | Informative |
| `Confirm` | confirm | Informative |
| `Disconfirm` | disconfirm | Informative |
| `Request` | request | Requestive |
| `QueryIf` | query-if | Requestive |
| `Cfp` | cfp | Negotiation |
| `Propose` | propose | Negotiation |
| `Accept` | accept-proposal | Negotiation |
| `Reject` | reject-proposal | Negotiation |
| `Agree` | agree | Commitment |
| `Refuse` | refuse | Commitment |
| `Failure` | failure | Lifecycle |

---

*Next: [Formal Grammar Reference](./13-grammar.md)*
