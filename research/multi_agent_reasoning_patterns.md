# Multi-Agent Reasoning Patterns for RLang

## Research Summary

This document maps the formal foundations of multi-agent communication, delegation,
trust, and coordination to concrete primitives needed in RLang -- a formal reasoning
language for AI agents. Sources span classical multi-agent systems theory (FIPA-ACL,
Contract Net Protocol, speech act theory), modern protocol specifications (Google A2A),
and recent academic work on agent contracts, multi-agent debate, and epistemic conflict
resolution.

---

## 1. Communicative Acts as Reasoning Primitives

### 1.1 Speech Act Theory Foundation

Speech Act Theory (Austin 1962, Searle 1969) decomposes communication into three layers:

| Layer | Description | RLang Relevance |
|-------|-------------|-----------------|
| **Locutionary** | The physical utterance / message content | Message payload type |
| **Illocutionary** | The speaker's intention (inform, request, propose) | Communicative act type -- core primitive |
| **Perlocutionary** | The effect achieved (persuade, convince) | Outcome / belief update reasoning |

The illocutionary layer is the critical one for RLang: each message between agents is
not just data but an *intentional action* that carries semantic force.

### 1.2 FIPA-ACL Communicative Acts Taxonomy

FIPA (Foundation for Intelligent Physical Agents) standardized 22 communicative acts
organized into categories. These map directly to reasoning primitives:

**Informative Acts** -- Sharing knowledge:
```
inform(sender, receiver, proposition)     -- Assert a fact
confirm(sender, receiver, proposition)    -- Verify a previously communicated fact
disconfirm(sender, receiver, proposition) -- Deny a previously communicated fact
inform_if(sender, receiver, proposition)  -- Inform whether proposition is true
inform_ref(sender, receiver, reference)   -- Provide a referenced value
```

**Requestive Acts** -- Requesting action or information:
```
request(sender, receiver, action)              -- Ask another agent to perform action
request_when(sender, receiver, action, condition) -- Conditional request
request_whenever(sender, receiver, action, condition) -- Recurring conditional request
query_if(sender, receiver, proposition)        -- Ask if proposition is true
query_ref(sender, receiver, reference)         -- Ask for a referenced value
```

**Negotiation Acts** -- Task allocation and agreement:
```
cfp(sender, receiver, task, conditions)       -- Call for proposals
propose(sender, receiver, action, conditions) -- Offer to perform under conditions
accept_proposal(sender, receiver, proposal)   -- Accept a proposal
reject_proposal(sender, receiver, proposal, reason) -- Reject with reason
```

**Commitment Acts** -- Promises and refusals:
```
agree(sender, receiver, action, conditions)   -- Commit to perform action
refuse(sender, receiver, action, reason)      -- Decline to perform action
cancel(sender, receiver, action)              -- Cancel previous request/commitment
```

**Interaction Management:**
```
subscribe(sender, receiver, reference)        -- Request ongoing updates
not_understood(sender, receiver, action, reason) -- Signal comprehension failure
failure(sender, receiver, action, reason)     -- Report action failure
```

### 1.3 Proposed RLang Mapping: `CommAct` Type

```
type CommAct =
  | Inform    of { sender: AgentId, receiver: AgentId, content: Proposition }
  | Request   of { sender: AgentId, receiver: AgentId, action: Action }
  | Propose   of { sender: AgentId, receiver: AgentId, action: Action, conditions: Constraints }
  | Accept    of { sender: AgentId, receiver: AgentId, proposal: ProposalRef }
  | Reject    of { sender: AgentId, receiver: AgentId, proposal: ProposalRef, reason: Reason }
  | Confirm   of { sender: AgentId, receiver: AgentId, content: Proposition }
  | Query     of { sender: AgentId, receiver: AgentId, question: Question }
  | Agree     of { sender: AgentId, receiver: AgentId, action: Action }
  | Refuse    of { sender: AgentId, receiver: AgentId, action: Action, reason: Reason }
  | Cancel    of { sender: AgentId, receiver: AgentId, reference: CommRef }
  | Subscribe of { sender: AgentId, receiver: AgentId, topic: Topic }
  | Failure   of { sender: AgentId, receiver: AgentId, action: Action, reason: Reason }
```

---

## 2. Delegation Reasoning

### 2.1 The Delegation Decision

When an agent faces a task, it must reason about whether to handle it locally or
delegate. This requires several sub-judgments:

**Capability Assessment:**
- Do I have the skills/tools to accomplish this task?
- Does another agent have better capabilities for this?
- What is the expected quality difference?

**Resource Assessment:**
- Do I have sufficient resources (time, tokens, API calls)?
- Would delegation free resources for higher-priority work?
- What are the communication overhead costs?

**Trust Assessment:**
- Do I trust the candidate agent's output quality?
- What is their track record (reputation)?
- What verification will I need to perform on their output?

### 2.2 Contract Net Protocol (Smith, 1980)

The Contract Net Protocol formalizes task delegation as a market mechanism:

```
1. Manager announces task  -->  cfp(manager, *, task_spec)
2. Contractors evaluate     -->  [internal capability matching]
3. Contractors bid          -->  propose(contractor, manager, offer)
4. Manager evaluates bids   -->  [ranking by capability, cost, trust]
5. Manager awards contract  -->  accept_proposal(manager, winner, proposal)
6. Manager rejects losers   -->  reject_proposal(manager, loser, proposal, reason)
7. Contractor executes      -->  [task execution]
8. Contractor reports       -->  inform(contractor, manager, result)
```

**Key reasoning at each step:**
- Step 2: Contractor must introspect on own capabilities vs. task requirements
- Step 4: Manager must reason about quality, cost, and trust tradeoffs
- Step 7-8: Manager must monitor progress and decide when to intervene

### 2.3 Agent Contracts Framework (Ye & Tan, 2025)

Recent work formalizes delegation with resource governance. An Agent Contract is a
seven-tuple:

```
C = (I, O, S, R, T, Phi, Psi)
```

| Component | Meaning | RLang Type |
|-----------|---------|------------|
| **I** | Input specification -- schema and constraints | `InputSpec` |
| **O** | Output specification -- schema and quality criteria | `OutputSpec` |
| **S** | Skill set -- available tools, functions, knowledge | `Set<Capability>` |
| **R** | Resource constraints -- multi-dimensional budget | `ResourceBudget` |
| **T** | Temporal constraints -- deadlines and duration limits | `TimeConstraints` |
| **Phi** | Success criteria -- measurable completion conditions | `Predicate` |
| **Psi** | Termination conditions -- forced stop events | `Predicate` |

**Conservation Law for Delegation:**
When a parent agent delegates to child agents, the sum of child budgets must not
exceed the parent budget:

```
forall delegation D from parent P to children [C1, C2, ..., Cn]:
  sum(R(Ci)) <= R(P)
```

This is a critical formal property -- it prevents unbounded resource consumption
in recursive delegation hierarchies.

**Contract Modes** allow quality-resource tradeoffs:
- URGENT: minimal reasoning, tight timeout (speed over quality)
- ECONOMICAL: low reasoning effort, moderate timeout
- BALANCED: full reasoning, generous timeout (quality over speed)

### 2.4 Proposed RLang Mapping: Delegation Primitives

```
type DelegationDecision =
  | DoMyself     of { reason: Reason, estimated_cost: ResourceBudget }
  | Delegate     of { to: AgentId, contract: Contract, reason: Reason }
  | Decompose    of { subtasks: List<(Task, DelegationDecision)> }
  | RequestBids  of { task: Task, candidates: Set<AgentId>, deadline: Time }

type Contract = {
  input_spec:     InputSpec,
  output_spec:    OutputSpec,
  capabilities:   Set<Capability>,
  resources:      ResourceBudget,
  temporal:       TimeConstraints,
  success:        Predicate,
  termination:    Predicate,
  mode:           ContractMode
}

type ContractMode = Urgent | Economical | Balanced | Custom of ResourceProfile

-- Conservation law as a type constraint:
invariant delegation_conservation:
  forall parent_contract, child_contracts:
    sum(child_contracts.map(.resources)) <= parent_contract.resources
```

---

## 3. Agent Discovery and Capability Matching

### 3.1 A2A Protocol Agent Cards

Google's Agent2Agent (A2A) protocol (v1.0, 2025) introduced Agent Cards as the
discovery mechanism. An Agent Card is a JSON document that describes:

- **Identity**: name, description, provider, version
- **Skills**: structured list of capabilities with descriptions
- **Interaction modes**: sync, async, streaming
- **Authentication**: required auth schemes
- **Endpoint**: URL for communication

**Capability matching** involves:
1. Semantic similarity between task requirements and agent skill descriptions
2. Credibility scores based on past performance
3. Contextual relevance to the current task domain
4. Real-time availability checks

### 3.2 A2A Task Lifecycle

A2A defines explicit task states that map to monitoring needs:

```
SUBMITTED --> WORKING --> COMPLETED    (happy path)
                     \-> FAILED       (error path)
                     \-> CANCELED     (abort path)
                     \-> INPUT_REQUIRED (needs human/agent input)
                     \-> REJECTED     (agent refuses task)
                     \-> AUTH_REQUIRED (authentication needed)
```

The `INPUT_REQUIRED` and `REJECTED` states are particularly interesting for RLang --
they represent points where the delegating agent must reason about how to proceed.

### 3.3 Proposed RLang Mapping: Discovery and Matching

```
type AgentCard = {
  id:            AgentId,
  name:          String,
  description:   String,
  skills:        List<SkillDescriptor>,
  interaction:   Set<InteractionMode>,
  auth:          AuthRequirements,
  endpoint:      Endpoint
}

type SkillDescriptor = {
  name:        String,
  description: String,
  input_schema:  Schema,
  output_schema: Schema
}

type InteractionMode = Sync | Async | Streaming

-- Capability matching as a reasoning primitive:
reason match_capability(task: Task, candidates: List<AgentCard>) -> RankedList<AgentCard>:
  for each candidate in candidates:
    semantic_score   = similarity(task.description, candidate.skills)
    trust_score      = reputation(candidate.id)
    availability     = check_available(candidate.endpoint)
    relevance_score  = domain_match(task.domain, candidate.skills)
    combined_score   = weighted_sum(semantic_score, trust_score, availability, relevance_score)
  return sorted_by(combined_score, descending)

type TaskState =
  | Submitted
  | Working     of { progress: Option<Progress> }
  | Completed   of { artifacts: List<Artifact> }
  | Failed      of { error: Error }
  | Canceled    of { reason: Reason }
  | InputRequired of { prompt: Query }
  | Rejected    of { reason: Reason }
  | AuthRequired of { scheme: AuthScheme }
```

---

## 4. Trust and Verification

### 4.1 Trust Models in Multi-Agent Systems

Trust in multi-agent systems has been studied extensively. The FIRE model identifies
four sources of trust:

| Trust Source | Description | Update Mechanism |
|-------------|-------------|------------------|
| **Interaction trust** | Direct experience with agent | Bayesian update after each interaction |
| **Role-based trust** | Trust based on agent's assigned role | Defined by system architecture |
| **Witness reputation** | Third-party reports about agent | Aggregation with credibility weighting |
| **Certified reputation** | Formally attested track records | Verified credentials / certificates |

### 4.2 Trust Reasoning for Delegation

An agent must reason about trust at multiple points:

**Pre-delegation:**
- Is this agent trustworthy enough for this task's sensitivity level?
- What is the minimum trust threshold for this task type?
- Should I require verification checkpoints?

**During execution:**
- Are intermediate results consistent with expectations?
- Should I intervene based on progress signals?
- Has trust changed based on observed behavior?

**Post-execution:**
- Does the output meet quality criteria?
- Should I verify the output independently?
- How should I update my trust model?

### 4.3 Verification Strategies

```
type VerificationStrategy =
  | NoVerification                          -- Full trust
  | SpotCheck    of { sample_rate: Float }  -- Random sampling
  | CrossVerify  of { verifier: AgentId }   -- Second opinion
  | FormalProof  of { prover: Prover }      -- Formal verification
  | Consensus    of { agents: Set<AgentId>, threshold: Float } -- Multi-agent agreement
  | GroundTruth  of { oracle: Oracle }      -- Check against known truth
```

### 4.4 Proposed RLang Mapping: Trust Primitives

```
type TrustScore = Float  -- [0.0, 1.0]

type TrustModel = {
  interaction_trust:  Map<AgentId, TrustScore>,
  role_trust:         Map<Role, TrustScore>,
  witness_reputation: Map<AgentId, List<(AgentId, TrustScore)>>,
  certified_trust:    Map<AgentId, List<Certificate>>
}

-- Trust computation:
reason compute_trust(model: TrustModel, agent: AgentId) -> TrustScore:
  direct    = model.interaction_trust.get(agent, default=0.5)
  role      = model.role_trust.get(agent.role, default=0.5)
  witness   = weighted_average(model.witness_reputation.get(agent, []))
  certified = max_cert_level(model.certified_trust.get(agent, []))
  return weighted_combination(direct, role, witness, certified)

-- Trust-gated delegation:
reason should_delegate(task: Task, candidate: AgentId, trust: TrustModel) -> DelegationDecision:
  trust_score = compute_trust(trust, candidate)
  min_trust   = task.sensitivity.min_trust_threshold
  if trust_score < min_trust:
    return DoMyself { reason: InsufficientTrust(candidate, trust_score, min_trust) }
  verification = select_verification(trust_score, task.sensitivity)
  contract = build_contract(task, verification)
  return Delegate { to: candidate, contract: contract }

-- Trust update after interaction:
reason update_trust(model: TrustModel, agent: AgentId, outcome: TaskOutcome) -> TrustModel:
  current = model.interaction_trust.get(agent, 0.5)
  updated = bayesian_update(current, outcome.quality, outcome.met_contract)
  return model.with(interaction_trust = model.interaction_trust.set(agent, updated))
```

---

## 5. Multi-Agent Debate and Conflict Resolution

### 5.1 Multi-Agent Debate (MAD) Framework

Multi-agent debate (Du et al., 2023; Liang et al., 2024) uses multiple LLM instances
to improve reasoning quality through structured argumentation:

**Protocol:**
1. Multiple agents independently generate answers to a question
2. Agents share their answers and reasoning
3. Each agent revises its answer considering others' arguments
4. Repeat rounds 2-3 until consensus or max rounds
5. A judge agent (or voting) selects the final answer

**Key finding:** Debate improves factuality and reasoning, but recent analysis (ICLR 2025)
shows it does not consistently outperform simpler strategies at scale -- the reasoning
overhead can exceed the quality gains.

**RLang implication:** Debate should be a *composable pattern*, not a built-in primitive.
The primitives needed are: parallel execution, argument collection, belief revision,
and consensus checking.

### 5.2 Epistemic Conflict Resolution

When agents receive conflicting information, they need formal mechanisms for belief
revision (Alchourron, Gardenfors, Makinson -- AGM theory):

**Conflict types:**
1. **Goal conflict** -- agents have incompatible objectives
2. **Belief conflict** -- agents hold contradictory beliefs about facts
3. **Plan conflict** -- agents propose incompatible action sequences

**Resolution strategies:**

| Strategy | When to Use | RLang Pattern |
|----------|-------------|---------------|
| **Priority ordering** | Clear authority hierarchy | `resolve_by_priority(beliefs, agent_ranks)` |
| **Evidence weighting** | Beliefs have supporting evidence | `resolve_by_evidence(beliefs, evidence_strengths)` |
| **Argumentation** | Complex disputes needing justification | `resolve_by_debate(positions, max_rounds)` |
| **Voting** | Democratic / equal-authority contexts | `resolve_by_vote(positions, threshold)` |
| **Arbitration** | Deadlock requiring external authority | `resolve_by_arbiter(positions, arbiter)` |

### 5.3 Proposed RLang Mapping: Conflict Resolution

```
type Conflict =
  | GoalConflict   of { agents: Set<AgentId>, goals: Map<AgentId, Goal> }
  | BeliefConflict of { agents: Set<AgentId>, beliefs: Map<AgentId, Proposition> }
  | PlanConflict   of { agents: Set<AgentId>, plans: Map<AgentId, Plan> }

type Resolution =
  | Resolved   of { outcome: Proposition, justification: Argument }
  | Deadlock   of { remaining_positions: Map<AgentId, Proposition> }
  | Escalated  of { to: AgentId, context: Conflict }

type ConflictResolver =
  | PriorityBased  of { ranking: List<AgentId> }
  | EvidenceBased  of { weight_fn: Evidence -> Float }
  | DebateBased    of { max_rounds: Int, judge: AgentId }
  | VoteBased      of { threshold: Float }
  | ArbitrationBased of { arbiter: AgentId }

reason resolve_conflict(conflict: Conflict, strategy: ConflictResolver) -> Resolution:
  match strategy:
    PriorityBased { ranking } ->
      highest = first(ranking, where: agent in conflict.agents)
      return Resolved { outcome: conflict.positions[highest], justification: AuthorityArg(highest) }
    EvidenceBased { weight_fn } ->
      scored = conflict.positions.map_values(|p| sum(p.evidence.map(weight_fn)))
      winner = max_by(scored, value)
      return Resolved { outcome: winner.key, justification: EvidenceArg(winner) }
    DebateBased { max_rounds, judge } ->
      positions = conflict.positions
      for round in 1..max_rounds:
        positions = debate_round(positions) -- each agent revises
        if consensus(positions): return Resolved { ... }
      return judge_decides(judge, positions)
    ...
```

---

## 6. Shared Context and State Management

### 6.1 Four Types of Shared Context

Multi-agent coordination requires maintaining four types of shared context:

| Context Type | Description | Example |
|-------------|-------------|---------|
| **Temporal** | Conversation history, event log | Message history between agents |
| **Social** | Agent roles, relationships, trust | Who delegated to whom, authority structure |
| **Task** | Goal state, progress, dependencies | Task graph with completion status |
| **Domain** | Specialized knowledge relevant to task | Shared facts, ontology, constraints |

### 6.2 A2A Context Management

A2A uses `contextId` to maintain conversation continuity across task interactions.
Messages within the same context share history. This is analogous to a "thread" --
multiple tasks can share a conversation context.

### 6.3 State Synchronization Patterns

**Immutable State Passing:**
Each agent works with a versioned, immutable state object. When it completes its
subtask, it produces a new state version and passes it to the next agent. This avoids
race conditions.

**Event Sourcing:**
All state changes are recorded as events. Any agent can reconstruct the current state
by replaying the event log from any checkpoint.

**Blackboard Pattern:**
A shared data structure (blackboard) that all agents can read from and write to.
A controller decides which agent should act next based on the blackboard state.

### 6.4 Proposed RLang Mapping: Context Primitives

```
type SharedContext = {
  id:        ContextId,
  temporal:  List<TimestampedEvent>,
  social:    SocialGraph,
  task:      TaskGraph,
  domain:    KnowledgeBase
}

type SocialGraph = {
  agents:       Set<AgentId>,
  roles:        Map<AgentId, Role>,
  delegations:  List<Delegation>,
  trust:        TrustModel
}

type TaskGraph = {
  tasks:         Map<TaskId, Task>,
  dependencies:  DAG<TaskId>,
  status:        Map<TaskId, TaskState>,
  assignments:   Map<TaskId, AgentId>
}

-- Context operations:
reason update_context(ctx: SharedContext, event: Event) -> SharedContext:
  return ctx.with(
    temporal = ctx.temporal.append(timestamped(event)),
    task     = apply_task_event(ctx.task, event),
    domain   = apply_domain_event(ctx.domain, event)
  )

-- Context scoping for delegation:
reason scope_context(parent_ctx: SharedContext, task: Task) -> SharedContext:
  -- Only pass relevant context to child agent
  relevant_history = filter(parent_ctx.temporal, related_to(task))
  relevant_domain  = extract(parent_ctx.domain, task.domain_needs)
  return SharedContext {
    id: new_context_id(),
    temporal: relevant_history,
    social: parent_ctx.social, -- preserve full social graph
    task: subtask_graph(parent_ctx.task, task),
    domain: relevant_domain
  }
```

---

## 7. Monitoring and Intervention

### 7.1 When to Intervene in Delegated Tasks

A delegating agent must continuously reason about whether to intervene:

**Intervention triggers:**
1. **Deadline approaching** -- task progress insufficient for remaining time
2. **Resource overrun** -- agent consuming more resources than budgeted
3. **Quality degradation** -- intermediate outputs below quality threshold
4. **Stuck/looping** -- no progress for extended period (the $47K recursive loop problem)
5. **Context drift** -- agent's work diverging from original intent
6. **External change** -- conditions changed making original task obsolete

### 7.2 Proposed RLang Mapping: Monitoring Primitives

```
type MonitoringPolicy = {
  check_interval:  Duration,
  triggers:        List<InterventionTrigger>,
  escalation:      EscalationPolicy
}

type InterventionTrigger =
  | DeadlineRisk    of { threshold: Float }  -- 0.8 = intervene at 80% time with <50% progress
  | ResourceOverrun of { threshold: Float }  -- fraction of budget consumed
  | QualityDrop     of { metric: QualityMetric, min_score: Float }
  | NoProgress      of { duration: Duration }
  | ContextDrift    of { similarity_threshold: Float }
  | ExternalChange  of { condition: Predicate }

type InterventionAction =
  | Continue                          -- No action needed
  | SendGuidance  of { message: CommAct }  -- Redirect the agent
  | AddResources  of { budget: ResourceBudget }  -- Give more resources
  | RevokeTask    of { reason: Reason }    -- Cancel and reassign
  | Escalate      of { to: AgentId }       -- Pass to higher authority
  | TakeOver                               -- Resume doing it myself

reason should_intervene(
  policy: MonitoringPolicy,
  task: Task,
  status: TaskState,
  elapsed: Duration,
  resources_used: ResourceBudget
) -> InterventionAction:
  for trigger in policy.triggers:
    match trigger:
      DeadlineRisk { threshold } ->
        time_fraction = elapsed / task.deadline
        progress_fraction = estimate_progress(status)
        if time_fraction > threshold and progress_fraction < time_fraction:
          return evaluate_intervention(task, status)
      ResourceOverrun { threshold } ->
        if resources_used / task.contract.resources > threshold:
          return RevokeTask { reason: ResourceExceeded }
      NoProgress { duration } ->
        if time_since_last_update(status) > duration:
          return SendGuidance { message: Request("status_update") }
      ...
  return Continue
```

---

## 8. Streaming, Partial Results, and Interruptions

### 8.1 A2A Streaming Model

A2A supports Server-Sent Events (SSE) for streaming task updates. The delegating
agent receives a stream of `TaskStatusUpdateEvent` and `TaskArtifactUpdateEvent`
messages, enabling real-time monitoring.

### 8.2 Handling Partial Results

When a task is interrupted or fails partway through, the delegating agent must reason
about what to do with partial results:

```
type PartialResult = {
  completed_parts:   List<Artifact>,
  in_progress_parts: List<PartialArtifact>,
  remaining_parts:   List<TaskSpec>,
  failure_reason:    Option<Reason>
}

reason handle_partial_result(partial: PartialResult, original_task: Task) -> Action:
  -- Can we use what we have?
  if sufficient_for_goal(partial.completed_parts, original_task.success_criteria):
    return AcceptPartial { artifacts: partial.completed_parts }
  -- Can we complete the rest ourselves or re-delegate?
  remaining_cost = estimate_cost(partial.remaining_parts)
  if within_budget(remaining_cost, available_resources()):
    return CompleteSelf { completed: partial.completed_parts, todo: partial.remaining_parts }
  -- Re-delegate remaining work
  return Redelegate { completed: partial.completed_parts, todo: partial.remaining_parts }
```

---

## 9. Comprehensive Primitive Inventory

### 9.1 New Primitives Beyond Single-Agent Reasoning

Multi-agent reasoning requires these primitives that do NOT exist in single-agent
reasoning systems:

| Category | Primitive | Purpose |
|----------|-----------|---------|
| **Identity** | `AgentId`, `AgentCard` | Agent identification and capability description |
| **Communication** | `CommAct` (22 speech acts) | Typed, intentional inter-agent messages |
| **Discovery** | `discover`, `match_capability` | Find agents and match to task needs |
| **Delegation** | `Contract`, `delegate`, `DelegationDecision` | Formalize task handoff with constraints |
| **Trust** | `TrustModel`, `TrustScore`, `compute_trust` | Reason about agent reliability |
| **Verification** | `VerificationStrategy`, `verify_output` | Check delegated work quality |
| **Context** | `SharedContext`, `scope_context` | Maintain and share state across agents |
| **Monitoring** | `MonitoringPolicy`, `should_intervene` | Track delegated tasks, decide when to act |
| **Conflict** | `Conflict`, `ConflictResolver`, `Resolution` | Handle disagreements between agents |
| **Negotiation** | `cfp`, `propose`, `accept`, `reject` | Market-based task allocation |
| **Resource Gov.** | `ResourceBudget`, conservation laws | Bound agent resource consumption |
| **Task Lifecycle** | `TaskState` (8 states) | Track task progress through defined stages |
| **Partial Results** | `PartialResult`, `handle_partial` | Reason about incomplete work |
| **Streaming** | `subscribe`, `on_update` | React to real-time task progress |

### 9.2 Type System Extensions

Multi-agent reasoning requires extending a single-agent type system with:

1. **Agent types**: `AgentId`, `AgentCard`, `Role`, `Capability`
2. **Communication types**: `CommAct`, `Message`, `Conversation`, `ContextId`
3. **Contract types**: `Contract`, `ContractMode`, `ResourceBudget`, `TimeConstraints`
4. **Trust types**: `TrustScore`, `TrustModel`, `Certificate`, `Reputation`
5. **Coordination types**: `TaskGraph`, `SocialGraph`, `SharedContext`
6. **Conflict types**: `Conflict`, `Resolution`, `ConflictResolver`
7. **Monitoring types**: `MonitoringPolicy`, `InterventionTrigger`, `InterventionAction`

### 9.3 Key Invariants for Type Checking

```
-- Resource conservation in delegation hierarchies
invariant resource_conservation:
  forall parent, children:
    sum(children.map(.contract.resources)) <= parent.contract.resources

-- Trust monotonicity -- trust can only be updated through defined mechanisms
invariant trust_update_integrity:
  forall agent, trust_change:
    trust_change.source in { DirectExperience, WitnessReport, CertifiedCredential }

-- Communication well-formedness -- responses match request types
invariant comm_coherence:
  Accept(proposal_ref) implies exists Propose(proposal_ref) in history
  Reject(proposal_ref) implies exists Propose(proposal_ref) in history
  Agree(action) implies exists Request(action) in history

-- Task lifecycle validity -- only valid state transitions
invariant task_lifecycle:
  Submitted -> { Working, Rejected, Canceled }
  Working   -> { Completed, Failed, Canceled, InputRequired }
  InputRequired -> { Working, Canceled }
```

---

## 10. Architectural Patterns

### 10.1 Orchestration Topologies

| Pattern | Description | When to Use |
|---------|-------------|-------------|
| **Star** | Central orchestrator delegates to all workers | Simple fan-out tasks |
| **Chain** | Sequential pipeline A -> B -> C | Multi-stage processing |
| **Tree** | Hierarchical delegation with sub-delegation | Complex decomposition |
| **Graph** | Arbitrary peer-to-peer communication | Collaborative exploration |
| **Blackboard** | Shared workspace with opportunistic contribution | Creative / exploratory tasks |

### 10.2 Pattern Composition in RLang

```
-- Sequential pipeline
reason pipeline(stages: List<AgentId>, input: Data) -> Result:
  current = input
  for agent in stages:
    contract = build_stage_contract(agent, current)
    current = delegate(agent, contract)
    if current is Failed: return handle_failure(agent, current)
  return current

-- Parallel fan-out with aggregation
reason fan_out(task: Task, agents: Set<AgentId>, aggregator: Results -> Result) -> Result:
  contracts = agents.map(|a| (a, build_contract(task, a)))
  results = parallel_delegate(contracts)
  return aggregator(results)

-- Hierarchical decomposition
reason decompose(task: Task, max_depth: Int) -> Result:
  if max_depth == 0 or is_atomic(task):
    return execute_locally(task)
  subtasks = decompose_task(task)
  results = subtasks.map(|st|
    candidate = match_capability(st, discover_agents())
    if should_delegate(st, candidate.first):
      delegate(candidate.first, build_contract(st))
    else:
      decompose(st, max_depth - 1)
  )
  return combine_results(results, task.combination_strategy)
```

---

## 11. Open Questions for RLang Design

1. **Synchrony model**: Should RLang assume synchronous message passing, or model
   async communication with explicit futures/promises?

2. **Trust as first-class**: Should trust scores be part of the type system (like
   taint tracking in security) or computed dynamically?

3. **Contract enforcement**: Compile-time checking of conservation laws vs. runtime
   monitoring? Both?

4. **Communication overhead**: How to reason about the cost of communication itself
   when deciding whether to delegate?

5. **Partial observability**: Agents cannot see each other's internal state. How
   should RLang model this epistemic limitation?

6. **Dynamic agent pools**: How to handle agents appearing and disappearing at
   runtime? (A2A handles this with discovery, but the type system implications
   are non-trivial.)

7. **Failure semantics**: What happens when a delegated task fails mid-stream?
   Compensating transactions? Rollback? Accept partial?

8. **Meta-reasoning cost**: The overhead of deciding whether to delegate can exceed
   the cost of just doing the task. How to bound meta-reasoning?

---

## 12. Source References

### Specifications and Standards
- [A2A Protocol Specification v1.0](https://a2a-protocol.org/latest/specification/) -- Google/Linux Foundation, 2025
- [A2A GitHub Repository](https://github.com/a2aproject/A2A)
- [FIPA Communicative Act Library](http://www.fipa.org/specs/fipa00037/SC00037J.html) -- FIPA, 2002
- [FIPA ACL Introduction (SmythOS)](https://smythos.com/developers/agent-development/fipa-agent-communication-language/)

### Academic Papers
- [Agent Contracts: A Formal Framework for Resource-Bounded Autonomous AI Systems](https://arxiv.org/html/2601.08815v1) -- Ye & Tan, 2025 (COINE/AAMAS 2026)
- [The Orchestration of Multi-Agent Systems](https://arxiv.org/html/2601.13671v1) -- Adimulam, Gupta, Kumar, 2025
- [Improving Factuality and Reasoning through Multiagent Debate](https://arxiv.org/abs/2305.14325) -- Du et al., 2023 (ICML 2024)
- [Multi-LLM-Agents Debate: Performance, Efficiency, and Scaling](https://d2jud02ci9yv69.cloudfront.net/2025-04-28-mad-159/blog/mad/) -- ICLR 2025 Blogpost
- [Contract Net Protocol](https://en.wikipedia.org/wiki/Contract_Net_Protocol) -- Smith, 1980
- [Trust and Reputation Models for Multiagent Systems](https://dl.acm.org/doi/10.1145/2816826) -- ACM Computing Surveys
- [Argumentation-Based Cooperative Multi-source Epistemic Conflict Resolution](https://link.springer.com/chapter/10.1007/978-3-642-33690-4_15)
- [Belief Revision in Multi-Agent Systems](https://eprints.soton.ac.uk/252143/1/ECAI94.pdf) -- ECAI 1994

### Industry and Protocol Resources
- [Announcing the Agent2Agent Protocol](https://developers.googleblog.com/en/a2a-a-new-era-of-agent-interoperability/) -- Google Developers Blog
- [A2A Protocol Upgrade (v0.3)](https://cloud.google.com/blog/products/ai-machine-learning/agent2agent-protocol-is-getting-an-upgrade) -- Google Cloud Blog
- [Developer's Guide to Multi-Agent Patterns in ADK](https://developers.googleblog.com/developers-guide-to-multi-agent-patterns-in-adk/) -- Google Developers
- [Agent Discovery in A2A](https://a2a-protocol.org/latest/topics/agent-discovery/)
- [What is A2A? (IBM)](https://www.ibm.com/think/topics/agent2agent-protocol)
- [Agent Name Service (ANS)](https://arxiv.org/html/2505.10609) -- Universal agent directory proposal
- [Agent Communication & Discovery Protocol (ACDP)](https://www.cmdzero.io/blog-posts/introducing-the-agent-communication-discovery-protocol-acdp-a-proposal-for-ai-agents-to-discover-and-collaborate-with-each-other)
