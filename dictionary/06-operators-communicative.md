# Layer 4: Communicative Operators

[Back to Dictionary Index](./README.md) | [Previous: Operational Operators](./05-operators-operational.md) | [Next: Type System](./07-types.md)

---

## Overview

The communicative layer models inter-agent messaging, task delegation, trust, and conflict resolution. Aligned with A2A Protocol v1.0 and grounded in FIPA-ACL speech act theory.

There are 17 communicative operators:

| Operator | Arity | Category | A2A Mapping |
|----------|-------|----------|-------------|
| `dlg` | 2 | Delegation | Task submission |
| `msg` | 2 | Messaging | Message send |
| `discover` | 1 | Discovery | AgentCard lookup |
| `match_capability` | 2 | Discovery | Skill matching |
| `negotiate` | 2 | Negotiation | Contract terms |
| `cancel` | 1 | Lifecycle | Task cancellation |
| `poll` | 1 | Lifecycle | Task status check |
| `subscribe` | 2 | Lifecycle | Push notifications |
| `cfp` | 1 | Negotiation | Call for proposals |
| `propose` | 2 | Negotiation | Proposal submission |
| `accept_proposal` | 1 | Negotiation | Accept proposal |
| `reject_proposal` | 1 | Negotiation | Reject proposal |
| `inform` | 2 | Informative | Assert to agent |
| `query_if` | 2 | Requestive | Ask agent |
| `agree` | 1 | Commitment | Commit to action |
| `refuse` | 1 | Commitment | Decline action |
| `resolve_conflict` | 2 | Conflict | Resolve disagreement |

---

## Delegation

### dlg

**Signature:** `dlg(agent, task)` -- binary (arity 2)

**Purpose:** Delegates a task to another agent with an associated contract. The primary mechanism for inter-agent task assignment.

**A2A mapping:** Submits a task to a remote agent, transitioning to `TaskState::Submitted`.

**Example:**
```rust
dlg(agent_b.id, monitor_goal, monitor_contract)
    -> Ok(task_id: "mon-001");

// With trust check
let score = trust_model.trust_score(&candidate);
req(score >= 0.6) |> dlg(candidate, task) -> Ok(task_id);
```

**Common patterns:**
- Always paired with a contract: `dlg(agent, task) |> contract(terms)`
- Trust-gated: check `trust_score >= threshold` before delegating
- Resource conservation: child budget <= parent budget
- Used in Decide phase for final delegation actions
- Track with `poll()` or `subscribe()` after delegation

---

## Messaging

### msg

**Signature:** `msg(to, content)` -- binary (arity 2)

**Purpose:** Sends a typed message to another agent. All messages are one of the 12 `CommActKind` variants -- no untyped messages.

**A2A mapping:** Sends an A2A Message with Parts.

**Example:**
```rust
msg(agent_a, Inform { content: deployment_status })
    | role:agent;
```

**Common patterns:**
- Send status updates: `msg(orchestrator, status_update)`
- Respond to queries: `msg(requester, QueryResponse { ... })`
- Part of dialogue chains: `msg(a, request) |> poll(response)`

---

## Discovery

### discover

**Signature:** `discover(capability)` -- unary (arity 1)

**Purpose:** Discovers agents by capability. Looks up agents whose `AgentCard` skills match the requested capability.

**A2A mapping:** Queries `/.well-known/agent-card.json` endpoints to find agents with matching skills.

**Example:**
```rust
let candidates = discover("monitoring")
    |> match_capability(monitor_goal);
```

**Common patterns:**
- First step in delegation: `discover(skill) |> match_capability(need) |> dlg(agent, task)`
- Returns AgentCard with id, name, description, skills, capabilities
- Filter by skill tags, input/output modes

---

### match_capability

**Signature:** `match_capability(need, agent)` -- binary (arity 2)

**Purpose:** Matches a specific need against an agent's capabilities. Verifies that the agent has the required skills for the task.

**A2A mapping:** Checks AgentCard skills against task requirements.

**Example:**
```rust
let agent_b = discover("monitoring")
    |> match_capability(monitor_goal);
```

**Common patterns:**
- Always follows `discover()`: `discover(cap) |> match_capability(need)`
- Returns matched agent or error if no suitable agent found
- Check capabilities: streaming, push_notifications, extended_card

---

## Negotiation

### negotiate

**Signature:** `negotiate(terms, counter)` -- binary (arity 2)

**Purpose:** Negotiates contract terms with another agent. Supports iterative negotiation with counter-proposals.

**A2A mapping:** Part of the contract negotiation flow before task commitment.

**Example:**
```rust
let agreed_terms = negotiate(initial_contract, agent_b_counter)
    -> Ok(final_contract);
```

**Common patterns:**
- Follows discovery: `discover(cap) |> negotiate(terms, counter)`
- May iterate: `negotiate(v1) -> Err(counter) -> negotiate(v2, counter)`
- Bounded negotiation rounds prevent infinite back-and-forth

---

### cfp

**Signature:** `cfp(task_spec)` -- unary (arity 1)

**Purpose:** Call for proposals -- broadcasts a task specification to candidate agents, requesting bids. From the Contract Net Protocol (Smith, 1980).

**A2A mapping:** Broadcast task request to multiple agents.

**FIPA-ACL mapping:** `cfp` communicative act.

**Example:**
```rust
let proposals = cfp(TaskSpec {
    description: "24h post-deploy monitoring",
    requirements: ["health_check", "alert_on_failure"],
    budget: ResourceBudget { wall_time: "24h", api_calls: 100 },
});
```

**Common patterns:**
- Competitive bidding: `cfp(spec) |> evaluate(proposals) |> accept_proposal(best)`
- Chain: `cfp(spec) -> [propose(a, offer_a), propose(b, offer_b)] -> select(best)`

---

### propose

**Signature:** `propose(to, offer)` -- binary (arity 2)

**Purpose:** Proposes to perform a task under specified conditions. Response to a `cfp()`.

**FIPA-ACL mapping:** `propose` communicative act.

**Example:**
```rust
propose(orchestrator, Offer {
    action: monitor(deployment),
    conditions: Contract { wall_time: "24h", cost: 0.50 },
});
```

**Common patterns:**
- Response to `cfp()`: agent evaluates task and responds with offer
- Includes conditions and resource requirements

---

### accept_proposal

**Signature:** `accept_proposal(proposal)` -- unary (arity 1)

**Purpose:** Accepts a proposal, committing both parties to the agreed terms.

**FIPA-ACL mapping:** `accept-proposal` communicative act.

**Example:**
```rust
accept_proposal(agent_b_proposal) -> Ok(contract);
```

---

### reject_proposal

**Signature:** `reject_proposal(proposal)` -- unary (arity 1)

**Purpose:** Rejects a proposal with an implicit or explicit reason.

**FIPA-ACL mapping:** `reject-proposal` communicative act.

**Example:**
```rust
reject_proposal(expensive_proposal);
```

---

## Informative

### inform

**Signature:** `inform(to, info)` -- binary (arity 2)

**Purpose:** Asserts a proposition to another agent. The fundamental informative speech act.

**FIPA-ACL mapping:** `inform` communicative act (Informative category).

**Example:**
```rust
inform(agent_a, deployment_completed) | p:0.99;
```

**Common patterns:**
- Share beliefs: `inform(partner, obs(status))`
- Report results: `inform(orchestrator, task_result)`
- Used for status updates in multi-agent workflows

---

### query_if

**Signature:** `query_if(to, question)` -- binary (arity 2)

**Purpose:** Asks another agent whether a proposition is true.

**FIPA-ACL mapping:** `query-if` communicative act (Requestive category).

**Example:**
```rust
let answer = query_if(agent_b, "is_service_healthy?")
    -> Ok(blf<0.95>);
```

**Common patterns:**
- Gather remote evidence: `query_if(expert, hypothesis) |> sup(claim, delta)`
- Verify remote state: `query_if(monitor, health_status)`

---

## Commitment

### agree

**Signature:** `agree(proposal)` -- unary (arity 1)

**Purpose:** Commits to performing an action. A formal commitment speech act.

**FIPA-ACL mapping:** `agree` communicative act (Commitment category).

**Example:**
```rust
agree(monitoring_task) | contract:monitor_contract;
```

---

### refuse

**Signature:** `refuse(request)` -- unary (arity 1)

**Purpose:** Declines to perform a requested action with a reason.

**FIPA-ACL mapping:** `refuse` communicative act (Commitment category).

**Example:**
```rust
refuse(complex_task) | reason:"insufficient_resources";
```

---

## Lifecycle

### cancel

**Signature:** `cancel(task)` -- unary (arity 1)

**Purpose:** Cancels a previously delegated task.

**A2A mapping:** Transitions task to `TaskState::Canceled`.

**Example:**
```rust
cancel(task_id) -> Ok(());
```

---

### poll

**Signature:** `poll(task)` -- unary (arity 1)

**Purpose:** Polls the status of a delegated task.

**A2A mapping:** Queries current `TaskState`.

**Example:**
```rust
let status = poll(task_id) -> match {
    Working { progress: 0.5 } => continue_waiting(),
    Completed { artifacts } => process(artifacts),
    Failed { error } => bt(Reflection { diagnosis: ToolFailure(...) }),
};
```

---

### subscribe

**Signature:** `subscribe(source, filter)` -- binary (arity 2)

**Purpose:** Subscribes to push notifications from a task or agent. Receives streaming updates instead of polling.

**A2A mapping:** Enables push notifications for a task.

**Example:**
```rust
subscribe(task_id, "status_changes") |> on_update(handler);
```

---

## Conflict Resolution

### resolve_conflict

**Signature:** `resolve_conflict(conflict, strategy)` -- binary (arity 2)

**Purpose:** Resolves a detected conflict between agents using a specified strategy.

**Example:**
```rust
let resolution = resolve_conflict(
    Conflict::Belief {
        agents: [agent_a, agent_b],
        claims: [(agent_a, "service_healthy"), (agent_b, "service_degraded")],
    },
    ConflictResolver::Evidence
) -> match {
    Resolved { outcome, justification } => inform_all(outcome),
    Deadlock { positions } => Arbitrate { arbiter: supervisor },
    Escalated { to, context } => dlg(to, context),
};
```

**Resolution strategies:**

| Strategy | Mechanism |
|----------|-----------|
| `Priority(agents)` | Resolve by authority ranking |
| `Evidence` | Resolve by evidence weight |
| `Debate { max_rounds, judge }` | Structured debate with bounded rounds |
| `Vote { threshold }` | Majority vote |
| `Arbitrate { arbiter }` | Escalate to designated arbiter |

**Conflict types:**

| Type | Description |
|------|-------------|
| `Goal` | Agents have incompatible objectives |
| `Belief` | Agents hold contradictory beliefs |
| `Plan` | Agents propose incompatible action sequences |

**Resolution outcomes:**

| Outcome | Description |
|---------|-------------|
| `Resolved` | Conflict was resolved with justification |
| `Deadlock` | No resolution reached, positions remain |
| `Escalated` | Passed to higher authority |

---

*Next: [Type System Reference](./07-types.md)*
