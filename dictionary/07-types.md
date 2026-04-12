# Type System Reference

[Back to Dictionary Index](./README.md) | [Previous: Communicative Operators](./06-operators-communicative.md) | [Next: Metadata](./08-metadata.md)

---

## Overview

RLang is strongly typed. Every value has a type, every operator returns a typed result, and the type system enforces correctness at parse and validation time.

---

## Primitive Types

| Type | Description | Example |
|------|-------------|---------|
| `f64` | 64-bit floating point number | `0.85`, `3.14` |
| `i64` | 64-bit integer | `42`, `100` |
| `String` | UTF-8 string | `"hello"`, `"ci_pipeline"` |
| `bool` | Boolean | `true`, `false` |

These correspond to the `Literal` enum in the AST: `Float(f64)`, `Int(i64)`, `Str(String)`, `Bool(bool)`.

---

## Belief Type: blf

The fundamental epistemic unit. Every claim must be wrapped in a `blf` type.

**Syntax:**
```rust
blf<confidence, lifetime>
```

**Components:**
- `confidence` (f64, 0.0..=1.0) -- how certain the agent is
- `lifetime` (optional) -- `'fresh`, `'stale`, or `'unk`

**Full structure:**
```rust
struct Blf<'a, T> {
    claim: T,           // The proposition being believed
    p: f64,             // Confidence: 0.0..=1.0 (required)
    ep: EpMode,         // How the belief was formed
    src: Src,           // Where it came from
    scope: Scope,       // How broadly it applies
    fresh: Lifetime,    // 'fresh | 'stale | 'unk
}
```

**Examples:**
```rust
let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | t:fresh;
let risk: blf<0.85> = obs(no_rollback) | p:0.85 | ep:infer | src:obs(infra) | t:fresh;
```

**Rules:**
- Confidence must be in range 0.0..=1.0 (validator enforced)
- Stale beliefs (`'stale`) cannot be directly asserted -- must `decay()` or `refresh()` first
- Confidence is computed from evidence via `resolve()`, not arbitrarily asserted (anti-pattern #7)

---

## Goal Types

### goal\<T\>

A desire that has been evaluated and selected for pursuit. Has a defined target, success criteria, and resource bounds.

```rust
struct Goal<T> {
    target: T,
    priority: Priority,
    deadline: Deadline,
    success: Predicate<T>,
    status: GoalStatus,
    parent: Option<GoalId>,
}
```

**Example:**
```rust
let deploy_goal: goal<Deploy> = goal(self, deploy(fix))
    | priority:high | deadline:within(2h);
```

### intent\<T\>

A goal the agent has committed to, with an attached plan. Intent = Goal + Plan + Resource Commitment.

```rust
struct Intent<T> {
    goal: Goal<T>,
    plan: Plan,
    resources: ResourceBudget,
    progress: usize,
}
```

### desire\<T\>

What the agent wants to achieve. Not yet committed to.

```rust
struct Desire<T> {
    target: T,
    priority: Priority,
    rationale: Vec<BlfId>,
}
```

### GoalStatus

```rust
enum GoalStatus {
    Pending,              // Not yet started
    Active,               // Currently being pursued
    Achieved,             // Success criteria met
    Failed(Reason),       // Cannot be achieved
    Abandoned(Reason),    // Voluntarily given up
    Blocked(Vec<GoalId>), // Waiting on dependencies
}
```

### Priority

```rust
enum Priority {
    Critical,    // Must be achieved, blocks everything else
    High,        // Should be achieved soon
    Normal,      // Standard priority
    Low,         // Nice to have
    Background,  // Only if nothing else needs doing
}
```

### Deadline

```rust
enum Deadline {
    Urgent,              // ASAP
    By(Timestamp),       // Hard deadline
    Within(Duration),    // Relative deadline
    Flexible,            // No time pressure
    None,                // No deadline
}
```

---

## Action Types

### action\<T\>

An action the agent can take in the world.

```rust
enum Action<T> {
    Invoke { tool: ToolId, args: T, expected: Blf<f64> },
    Exec { op: Operation, args: T },
    Delegate { to: AgentId, task: Task, contract: Contract },
    Remember { key: MemKey, value: T, mem_type: MemType },
    Recall { query: Query, mem_type: MemType },
    Emit { content: T, format: OutputFormat },
}
```

### obs_feed\<T\>

Environmental feedback received after an action.

```rust
struct ObsFeed<T> {
    data: T,
    source: FeedSource,
    timestamp: Timestamp,
    relevance: f64,
}
```

### reflection

A structured reflection on a failed attempt.

```rust
struct Reflection {
    attempt: TraceId,
    outcome: ActionResult<()>,
    diagnosis: DiagnosisKind,
    revision: Option<Plan>,
}
```

### DiagnosisKind

```rust
enum DiagnosisKind {
    WrongApproach(Reason),
    MissingInfo(Vec<Query>),
    ConstraintViolation(Constraint),
    ToolFailure(ToolId, ToolErr),
    InsufficientEvidence,
    ConflictingEvidence(ConflictId),
}
```

### MemType

```rust
enum MemType {
    Episodic,     // Specific past events
    Semantic,     // General knowledge
    Procedural,   // Skills and plans
    Working,      // Current context
}
```

---

## Communicative Types

### CommAct

A typed communicative act between agents (12 variants from FIPA-ACL).

```rust
enum CommActKind {
    // Informative
    Inform, Confirm, Disconfirm,
    // Requestive
    Request, QueryIf,
    // Negotiation
    Cfp, Propose, Accept, Reject,
    // Commitment
    Agree, Refuse,
    // Lifecycle
    Failure,
}
```

### AgentCard

Agent self-description, mirrors A2A AgentCard.

```rust
struct AgentCard {
    id: String,
    name: String,
    description: String,
    skills: Vec<Skill>,
    capabilities: Capabilities,
    interfaces: Vec<Interface>,
}
```

### Contract

A formal seven-tuple agreement between agents (Ye & Tan 2025).

```rust
struct Contract {
    input_spec: Schema,
    output_spec: Schema,
    required_skills: Vec<SkillId>,
    resources: ResourceBudget,
    temporal: TimeConstraints,
    success: Predicate,
    termination: Predicate,
    mode: ContractMode,
}
```

### TrustModel

Multi-source trust model (FIRE: Huynh et al. 2006).

```rust
struct TrustModel {
    interaction: HashMap<AgentId, f64>,   // Direct experience
    role_based: HashMap<RoleId, f64>,     // Role-based trust
    witness: HashMap<AgentId, Vec<(AgentId, f64)>>,  // Third-party
    certified: HashMap<AgentId, Vec<Certificate>>,    // Credentials
}
```

### TaskState

A2A-aligned task lifecycle states. See [A2A Mapping](./12-a2a-mapping.md).

```rust
enum TaskState {
    Submitted, Working, InputRequired, AuthRequired,
    Completed, Failed, Canceled, Rejected,
}
```

---

## Result Types

RLang uses Rust-style `Result` and `Option` for all fallible operations.

### Ok\<T\> / Err\<E\>

```rust
resolve(ev) -> Ok(blf<0.70>)
resolve(ev) -> Err(InsufEv)
```

### Some\<T\> / None

```rust
let parent: Option<GoalId> = Some(parent_goal);
let parent: Option<GoalId> = None;
```

These are expressed in the AST as `ResultVariant`: `Ok`, `Err`, `Some`, `None`.

---

## Collection Types

### Vec

Ordered collection.

```rust
let skills: Vec<Skill> = [skill_a, skill_b, skill_c];
```

### HashMap

Key-value mapping.

```rust
let trust_scores: HashMap<AgentId, f64> = { agent_a: 0.85, agent_b: 0.72 };
```

---

## Type Annotation Syntax

Type annotations follow Rust syntax with generics:

```rust
// Simple type
let x: f64 = 0.85;

// Generic type with confidence
let claim: blf<0.7> = cause(storm, cncl(mtg));

// Generic type with lifetime
let stale: blf<0.9, 'stale> = obs(old_data);

// Nested generic
let result: Result<blf<0.7>, String> = resolve(ev);

// Goal type
let g: goal<Deploy> = goal(self, deploy(fix));
```

**Grammar rule:**
```
type_annotation = { generic_type | simple_type }
generic_type    = { simple_type ~ "<" ~ type_params ~ ">" }
type_params     = { type_param ~ ("," ~ type_param)* }
type_param      = { float_literal | lifetime | type_annotation | ident }
```

**Built-in simple types:**
`blf`, `goal`, `intent`, `action`, `obs_feed`, `reflection`, `Contract`, `Evidence`, `Plan`, `Task`, `CommAct`, `AgentCard`, `TrustModel`, `Result`, `Option`, `Vec`, `HashMap`

---

## ResourceBudget

Resource constraints for intents and contracts.

```rust
struct ResourceBudget {
    tokens: u64,          // Max reasoning tokens
    api_calls: u32,       // Max external API calls
    wall_time: Duration,  // Max wall-clock time
    delegations: u8,      // Max sub-delegations
    cost: Option<f64>,    // Max monetary cost
}
```

**Conservation law:** When delegating, child budgets must sum to <= parent budget.

---

*Next: [Metadata Reference](./08-metadata.md)*
