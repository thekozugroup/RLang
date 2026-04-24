# RLang Conversion Guide

Complete reference for converting reasoning traces to valid RLang. No other document needed.

---

## 1. Quick Syntax Reference

### 1.1 Operators — Layer 1: Epistemic

| Operator | Arity | Category | Purpose | Example |
|----------|-------|----------|---------|---------|
| `cause(a, b)` | 2 | Causal | A causes B | `cause(bug, crash)` |
| `prvnt(a, b)` | 2 | Causal | A prevents B | `prvnt(rollback, loss)` |
| `enbl(a, b)` | 2 | Causal | A enables B | `enbl(fix, deploy)` |
| `req(a, b)` | 2 | Causal | A requires B | `req(deploy, tests_pass)` |
| `obs(x)` | 1 | Evidence | Observe a fact | `obs(tests_pass)` |
| `chng(a, b)` | 2 | State | A changes to B | `chng(status, healthy)` |
| `cncl(x)` | 1 | State | X is cancelled | `cncl(meeting)` |
| `cntns(a, b)` | 2 | Structure | A contains B | `cntns(system, module)` |
| `isa(a, b)` | 2 | Structure | A is a B | `isa(timeout, error)` |
| `sim(a, b)` | 2 | Structure | A is similar to B | `sim(case_a, case_b)` |
| `seq(a, b)` | 2 | Temporal | A then B | `seq(build, deploy)` |
| `goal(who, what)` | 2 | Intent | Who has what goal | `goal(self, deploy(fix))` |
| `confl(a, b)` | 2 | Intent | A conflicts with B | `confl(goal_a, goal_b)` |
| `sup(claim, +delta)` | 2 | Evidence Modifier | Strengthen belief | `sup(deploy, +0.15)` |
| `wkn(claim, -delta)` | 2 | Evidence Modifier | Weaken belief | `wkn(deploy, -0.25)` |
| `neut(claim, obs)` | 2 | Evidence Modifier | Neutral observation | `neut(deploy, mixed_data)` |
| `resolve(ev)` | 1 | Resolution | Resolve evidence block | `resolve(ev) -> Ok(blf<0.70>)` |
| `conf(claim)` | 1 | Resolution | Extract confidence value | `conf(deploy_blf)` |
| `decay(amount)` | 1 | Resolution | Reduce stale confidence | `old_data \|> decay(0.15)` |
| `refresh(belief, obs)` | 2 | Resolution | Restore fresh lifetime | `old \|> refresh(obs(new_log))` |
| `assert(x)` | 1 | Assertion | Commit to proposition | `assert(deploy_goal)` |
| `hedge(x, cond:[...])` | 1+ | Assertion | Conditional commitment | `hedge(deploy, cond:[rollback])` |
| `suspend(x)` | 1 | Assertion | Hold decision | `suspend(claim)` |
| `reject(x)` | 1 | Assertion | Discard proposition | `reject(deploy_goal)` |
| `emit(x)` | 1 | Assertion | Output result | `emit(Decision { ... })` |

### 1.2 Operators — Layer 2: Motivational

| Operator | Arity | Purpose | Example |
|----------|-------|---------|---------|
| `dcmp(goal, subgoals)` | 2 | Decompose goal into subgoals | `dcmp(release, [build, test, deploy])` |
| `prioritize(goals, criteria)` | 2 | Rank goals by criteria | `prioritize([g1, g2], [priority, deadline])` |
| `select(goal)` | 1 | Select goal for pursuit | `select(top_goal)` |
| `replan(intent, diagnosis)` | 2 | Revise plan with reason | `replan(intent, WrongApproach("timeout"))` |

### 1.3 Operators — Layer 3: Operational

| Operator | Arity | Purpose | Example |
|----------|-------|---------|---------|
| `exec(action)` | 1 | Execute primitive operation | `exec(run_tests)` |
| `inv(tool, args)` | 2 | Invoke external tool | `inv(deploy_tool, {env: "prod"})` |
| `pcv(source)` | 1 | Perceive environment | `pcv(metrics_feed)` |
| `rmb(key, value)` | 2 | Store to memory | `rmb("last_deploy", result)` |
| `rcl(key)` | 1 | Retrieve from memory | `rcl("last_deploy")` |
| `forget(key)` | 1 | Delete from memory | `forget("working_state")` |
| `bt(reflection)` | 1 | Bounded backtrack | `bt(Reflection { ... })` |
| `verify(result)` | 1 | Verify a result | `verify(deploy) -> Ok(())` |
| `retry_with(attempt, data)` | 2 | Retry with new data | `retry_with(failed.attempt, new_data)` |

### 1.4 Operators — Layer 4: Communicative

| Operator | Arity | Category | Purpose |
|----------|-------|----------|---------|
| `dlg(agent, task)` | 2 | Delegation | Delegate task to agent |
| `msg(agent, content)` | 2 | Messaging | Send message to agent |
| `discover(capability)` | 1 | Discovery | Find agents with capability |
| `match_capability(agent, goal)` | 2 | Discovery | Verify agent can fulfill goal |
| `negotiate(agent, terms)` | 2 | Negotiation | Negotiate contract |
| `cfp(task)` | 1 | Negotiation | Call for proposals |
| `propose(agent, offer)` | 2 | Negotiation | Submit proposal |
| `accept_proposal(proposal)` | 1 | Negotiation | Accept a proposal |
| `reject_proposal(proposal)` | 1 | Negotiation | Reject a proposal |
| `inform(agent, belief)` | 2 | Informative | Assert fact to agent |
| `query_if(agent, query)` | 2 | Informative | Ask agent a question |
| `agree(action)` | 1 | Commitment | Commit to action |
| `refuse(action)` | 1 | Commitment | Decline action |
| `cancel(task_id)` | 1 | Lifecycle | Cancel a delegated task |
| `poll(task_id)` | 1 | Lifecycle | Check task status |
| `subscribe(task_id, event)` | 2 | Lifecycle | Subscribe to task events |
| `resolve_conflict(a, b)` | 2 | Conflict | Resolve disagreement between agents |

### 1.5 Connectives

| Symbol | Name | Category | Purpose | Example |
|--------|------|----------|---------|---------|
| `\|>` | Pipe | Sequential | Pass result to next | `obs(x) \|> resolve(ev)` |
| `->` | Transform | Sequential | Resolve/transform | `resolve(ev) -> Ok(blf<0.7>)` |
| `\|\|>` | Fan-out | Parallel | Execute in parallel | `[a, b] \|\|> exec` |
| `<\|` | Aggregate | Parallel | Merge results | `results <\| merge` |
| `~>` | Tentative | Exploratory | Revertible step | `plan ~> exec(step)` |
| `!>` | Error Channel | Error | Route errors | `exec(x) !> bt(reflection)` |
| `?>` | Fallible | Error | Try-or-fallback | `inv(tool) ?> fallback` |
| `@>` | Store | Memory | Write to memory | `result @> rmb("key")` |
| `<@` | Retrieve | Memory | Read from memory | `rcl("key") <@ claim` |

### 1.6 Types

| Type | Syntax | Purpose |
|------|--------|---------|
| `blf<p>` | `blf<0.85>` | Belief with confidence |
| `blf<p, 'lt>` | `blf<0.9, 'stale>` | Belief with lifetime |
| `goal<T>` | `goal<Deploy>` | Goal with target type |
| `intent<T>` | `intent<Plan>` | Committed intention |
| `desire<T>` | `desire<Outcome>` | Unconditional desire |
| `action<T>` | `action<Deploy>` | Executable action |
| `obs_feed<T>` | `obs_feed<Metrics>` | Observation stream |
| `reflection` | `Reflection { ... }` | Backtrack reflection |
| `Contract` | `Contract { ... }` | Delegation contract |
| `AgentCard` | `AgentCard { ... }` | Agent capability card |
| `TrustModel` | `TrustModel { ... }` | Trust scoring model |
| `TaskState` | `Submitted \| Working \| ...` | A2A task lifecycle |
| `Result<T, E>` | `Ok(v) \| Err(e)` | Success or error |
| `Option<T>` | `Some(v) \| None` | Present or absent |
| `Vec<T>` | `Vec<blf>` | Ordered collection |
| `HashMap<K,V>` | `HashMap<str, blf>` | Key-value store |

**TaskState variants:** `Submitted`, `Working`, `InputRequired`, `AuthRequired`, `Completed`, `Failed`, `Canceled`, `Rejected`

**MemType variants:** `Episodic`, `Semantic`, `Procedural`, `Working`

**DiagnosisKind variants:** `WrongApproach(reason)`, `MissingInfo(queries)`, `ConstraintViolation(constraint)`, `ToolFailure(tool_id, error)`, `InsufficientEvidence`, `ConflictingEvidence(conflict_id)`

**GoalStatus variants:** `Active`, `Suspended`, `Completed`, `Failed`, `Delegated`

**Priority variants:** `Critical`, `High`, `Normal`, `Low`, `Background`

**Deadline variants:** `Urgent`, `By(timestamp)`, `Within(duration)`, `Flexible`, `None`

### 1.7 Metadata Fields

Attach to any expression with `| key:value`:

```rust
expr | p:0.85 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
```

| Field | Key | Values | Purpose |
|-------|-----|--------|---------|
| Confidence | `p` | `0.0..=1.0` | How certain (required on `blf`) |
| Epistemic mode | `ep` | `direct`, `infer`, `anl`, `recv` | How belief was formed |
| Source | `src` | `obs(id)`, `chain(ids)`, `agent(id)`, `mem(id)`, `Given` | Provenance |
| Scope | `scope` | `all`, `some`, `none`, `cond`, `gen`, `loc` | How broadly claim applies |
| Freshness | `t` | `fresh`, `stale`, `unk` | Temporal validity |
| Priority | `priority` | `Critical`, `High`, `Normal`, `Low`, `Background` | Goal urgency |
| Deadline | `deadline` | `Urgent`, `By(ts)`, `Within(dur)`, `Flexible`, `None` | Time constraint |
| Success | `success` | predicate | Goal completion criteria |
| Mode | `mode` | `Urgent`, `Economical`, `Balanced`, `Custom(p)` | Contract quality-speed |
| Requirement | `req` | expression | Precondition |
| Condition | `cond` | expression | Conditional constraint |

---

## 2. Phase Structure

### 2.1 Mandatory Order

```
Frame -> Explore -> Verify -> Decide
                 ^         |
                 |_rebloom_| (max 3x)
```

All four phases are required. The parser rejects traces with missing or out-of-order phases. `Decide` is terminal — no transitions out.

### 2.2 Phase Syntax

```rust
#[phase(Frame)]
impl Deductive {     // impl mode is optional: Deductive | Abductive | Analogical
    // ...
}

#[phase(Explore)]
{
    // ...
}

#[phase(Verify)]
{
    // ...
}

#[phase(Decide)]
{
    // ...
}
```

### 2.3 What Belongs in Each Phase

**Frame** — problem formulation and context:
- `obs()` — observe initial facts with full metadata
- `goal()` — declare goals with priority and deadline
- `req()` — declare constraints that must hold throughout
- `cause()`, `enbl()`, `prvnt()` — causal structure
- `isa()`, `cntns()` — structural classification
- NOT allowed: `resolve()`, `assert()`, `hedge()`, `dlg()`

**Explore** — reasoning, evidence evaluation, plan building:
- Evidence blocks `[obs => sup/wkn/neut, ...]`
- `resolve()` — evaluate evidence to get confidence
- `dcmp()`, `prioritize()`, `select()` — goal management
- `enbl()`, `cause()`, `sim()` — relationship reasoning
- `discover()`, `match_capability()` — agent discovery
- `inv()`, `exec()` — tool invocation
- NOT allowed: final assertions, re-entering Frame

**Verify** — constraint checking and bounded retry:
- `req()` — check requirements hold
- `verify()` — verify specific results
- `bt()` — bounded backtrack on failure
- `retry_with()` — retry with new data
- `conf()` — check confidence thresholds
- Rebloom to Explore if issues found (bounded by `max_rebloom`, default 3)
- NOT allowed: re-entering Frame, unbounded rebloom

**Decide** — terminal actions and output:
- `match conf(x) { ... }` — branch on confidence
- Match arms must use: `assert()`, `hedge()`, `suspend()`, or `reject()`
- `dlg()` — delegate to other agents
- `emit()` — output the final result
- NOT allowed: any further phase transitions

### 2.4 Confidence Branching Pattern (Decide)

```rust
match conf(claim) {
    c if c > 0.85 => assert(claim),
    c if c > 0.55 => hedge(claim, cond: [enbl(fallback, claim)]),
    c if c > 0.30 => suspend(claim),
    _             => reject(claim),
}
```

### 2.5 Rebloom Pattern

```rust
#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
    // If verify fails:
    // -> rebloom back to Explore with new evidence (counted against max_rebloom)
}
```

---

## 3. Conversion Examples

### 3.1 Short: Simple Belief Resolution

**English input:**
> "I see rain outside and there are dark clouds. Is it raining?"

**RLang:**

```rust
#[phase(Frame)]
{
    let rain: blf<0.95> = obs(rain)
        | p:0.95 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        obs(dark_clouds) => sup(rain, +0.05),
    ];
    rain |> resolve(ev) -> Ok(confirmed);
}

#[phase(Verify)]
{
    req(rain, obs(rain)) |> verify(rain) -> Ok(());
}

#[phase(Decide)]
{
    match conf(rain) {
        c if c > 0.85 => assert(rain),
        _ => hedge(rain),
    }
}
```

### 3.2 Medium: Deployment Decision

**English input:**
> "CI passes all tests (99% confidence). Infrastructure has no rollback plan (risk). Traffic is low. Should we deploy?"

**RLang:**

```rust
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass)
        | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback)
        | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic)
        | p:0.90 | ep:direct | src:obs(metrics) | scope:loc | t:fresh;
    let deploy_goal: goal<Deploy> = goal(self, deploy(fix))
        | priority:high | deadline:within(2h);
}

#[phase(Explore)]
{
    let ev = [
        tests   => sup(deploy, +0.15),
        risk    => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];
    let deploy_blf = deploy |> resolve(ev) -> Ok(blf<0.70>);
}

#[phase(Verify)]
{
    req(tests, obs(tests_pass)) |> verify(deploy) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy_goal),
        c if c > 0.55 => hedge(deploy_goal, cond: [
            enbl(rollback_plan, deploy_goal),
        ]),
        _ => reject(deploy_goal),
    }
    emit(Decision { deploy: Hedge { condition: "rollback plan required" } });
}
```

### 3.3 Long: Multi-Step Goal Decomposition with Agent Delegation

**English input:**
> "We need to release v2.0. That means: build the artifact, run tests, deploy to prod, and set up monitoring. Find a monitoring agent, check if it can be trusted, delegate monitoring to it, and execute the rest ourselves."

**RLang:**

```rust
#[phase(Frame)]
impl Deductive {
    let release_goal: goal<Release> = goal(self, release(v2_0))
        | priority:Critical | deadline:within(4h);
    let build_obs: blf<0.95> = obs(build_ready)
        | p:0.95 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let tests_obs: blf<0.99> = obs(tests_pass)
        | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let infra_obs: blf<0.80> = obs(prod_healthy)
        | p:0.80 | ep:direct | src:obs(infra_check) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    // Decompose release into ordered subgoals
    let subgoals = dcmp(release_goal, [
        goal(self, build(artifact)),
        goal(self, test(artifact)),
        goal(self, deploy(artifact, prod)),
        goal(self, monitor(prod)),
    ]);
    let ranked = prioritize(subgoals, criteria: [seq, priority]);

    // Build deployment evidence
    let ev = [
        build_obs  => sup(deploy_ready, +0.20),
        tests_obs  => sup(deploy_ready, +0.25),
        infra_obs  => sup(deploy_ready, +0.15),
    ];
    let deploy_blf = deploy_ready |> resolve(ev) -> Ok(blf<0.82>);

    // Discover and vet monitoring agent
    let monitor_agent = discover("monitoring")
        |> match_capability(goal(self, monitor(prod)));
    let trust = trust_model.trust_score(&monitor_agent.id);

    // Execute sequential steps
    exec(build(artifact)) |> rmb("build_result", Ok(artifact));
    exec(test(artifact))  |> verify(tests_pass) -> Ok(());

    let monitor_contract = Contract {
        resources: ResourceBudget { tokens: 5000, api_calls: 100,
                                    wall_time: within(2h), delegations: 0,
                                    cost: None },
        mode: Balanced,
        success: pred(service_healthy),
    };
}

#[phase(Verify)]
{
    req(deploy_ready, obs(tests_pass))   |> verify(deploy_blf) -> Ok(());
    req(monitor_agent, trust >= 0.60)    |> verify(trust) -> Ok(());
    // Resource conservation: child budget <= parent budget
    assert(monitor_contract.resources.tokens <= release_goal.resources.tokens);
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.75 => {
            assert(goal(self, deploy(artifact, prod)));
            exec(deploy(artifact, prod)) -> Ok(deploy_id);

            dlg(monitor_agent.id, goal(self, monitor(prod)), monitor_contract)
                -> Ok(task_id: "mon-001");

            emit(Decision {
                release:    Completed { artifact: artifact },
                deploy:     Asserted  { env: prod },
                monitoring: Delegated { to: monitor_agent.id, task: "mon-001" },
            });
        },
        c if c > 0.50 => hedge(release_goal, cond: [enbl(rollback_plan, deploy)]),
        _ => suspend(release_goal),
    }
}
```

---

## 4. Anti-Patterns to Avoid

| # | Anti-Pattern | What It Looks Like | How RLang Prevents It |
|---|-------------|-------------------|----------------------|
| 1 | **Circular Reasoning** | Re-entering Frame after Explore to redefine the problem | Parser rejects out-of-order phases; Frame is a one-way door |
| 2 | **Infinite Reflection** | Unbounded `bt()` loops that never terminate | All backtrack ops require `#[bounded(max_retries: N)]`; type system enforces |
| 3 | **Constraint Forgetting** | Establishing `req()` in Frame, then ignoring it in Decide | `req()` persists across all phases; validator checks at Decide |
| 4 | **Premature Commitment** | Skipping Verify and asserting in Explore | Verify phase is mandatory before Decide; parser rejects missing phases |
| 5 | **Over-Verification** | Endless re-checking that never reaches Decide | Rebloom bounded by `max_rebloom` (default 3); exceeding it is a parse error |
| 6 | **Rumination** | Repeating the same failed approach in `bt()` with no new plan | `bt()` requires a typed `DiagnosisKind` and a novel `revision.plan`; validator enforces novelty |
| 7 | **Confidence Theater** | Assigning `p:0.9` with no evidence, just stating high confidence | `p:` on `blf` must be derived from `resolve()` over an evidence block; arbitrary assertion is a validator error |

**Specific things NOT to do:**

```rust
// WRONG: confidence pulled from thin air
let claim: blf<0.9> = obs(x) | p:0.9;   // ok IF evidence supports it
assert(claim);                            // ERROR if p: not derived from resolve()

// WRONG: asserting in Explore
#[phase(Explore)] { assert(x); }         // assert belongs in Decide only

// WRONG: resolve in Frame
#[phase(Frame)] { resolve(ev); }         // resolve belongs in Explore

// WRONG: stale belief asserted directly
let old: blf<0.9, 'stale> = rcl("past");
assert(old);                              // ERROR: must decay() or refresh() first

// WRONG: evidence item without sup/wkn/neut
let ev = [ obs(x) => cause(a, b) ];     // ERROR: effect side must be sup/wkn/neut

// WRONG: Decide match arm not using assert/hedge/suspend/reject
#[phase(Decide)] {
    match conf(x) { c if c > 0.8 => exec(action) }  // ERROR
}
```

---

## 5. Feature Checklist

Use this checklist when converting. Apply every applicable feature:

**Beliefs & Evidence**
- [ ] Every initial fact uses `obs()` with full metadata (`p`, `ep`, `src`, `scope`, `t`)
- [ ] Evidence blocks use `[obs => sup/wkn/neut, ...]` syntax with signed deltas
- [ ] Confidence derived from `resolve(ev)` — never assigned arbitrarily
- [ ] Stale beliefs use `decay()` or `refresh()` before assertion
- [ ] `conf()` used to branch in Decide, not raw confidence numbers

**Goals & Plans**
- [ ] Goals declared with `goal(self, target)` + `priority:` + `deadline:`
- [ ] Complex goals decomposed with `dcmp()` then `prioritize()`
- [ ] `select()` used to pick the active goal
- [ ] `replan()` used with typed `DiagnosisKind` when plans fail

**Actions & Memory**
- [ ] Tool calls use `inv(tool, args)` not plain function calls
- [ ] Side effects stored with `rmb(key, value)`
- [ ] Prior knowledge retrieved with `rcl(key)`
- [ ] Backtrack uses `bt(Reflection { attempt, outcome, diagnosis, revision })`
- [ ] All `bt()` calls are inside `#[bounded(max_retries: N)]`
- [ ] `retry_with(attempt, new_data)` for data-level retries

**Phase Compliance**
- [ ] All four phases present in order: Frame, Explore, Verify, Decide
- [ ] `req()` constraints declared in Frame and verified in Verify
- [ ] Rebloom count ≤ 3 (default `max_rebloom`)
- [ ] All Decide match arms use `assert/hedge/suspend/reject`
- [ ] `emit()` outputs the final result in Decide

**Multi-Agent (when applicable)**
- [ ] `discover()` + `match_capability()` used to find agents
- [ ] `trust_model.trust_score()` checked before `dlg()`
- [ ] `dlg()` paired with a `Contract` including `ResourceBudget`
- [ ] Child budget ≤ parent budget (conservation law)
- [ ] `poll()` or `subscribe()` used to track delegated tasks

**Connectives**
- [ ] `|>` for sequential pipelines
- [ ] `->` for transformations and result extraction
- [ ] `!>` for error routing to `bt()`
- [ ] `?>` for try-or-fallback chains
- [ ] `||>` + `<|` for parallel fan-out/aggregate

---

## 6. System Prompt Variants

Rotate these prompts across batch conversion tasks to maintain variety in the training data.

---

**Variant A — Direct Instruction**

```
You are an RLang converter. Convert the following English reasoning trace to valid RLang.

RLang is a strongly-typed Rust-inspired language for AI reasoning. All traces must follow the 4-phase structure: Frame → Explore → Verify → Decide. Every belief uses blf<confidence> with metadata (p, ep, src, scope, t). Evidence blocks resolve to confidence via sup/wkn/neut. Decide phase branches on conf() and uses assert/hedge/suspend/reject. No phase may be skipped. No confidence may be asserted without evidence.

Convert the trace below to RLang. Preserve all reasoning. Do not add reasoning that is not present in the source.
```

---

**Variant B — Role + Goal Framing**

```
You are a reasoning trace engineer specializing in RLang, a compressed typed language for AI chain-of-thought. Your task is to convert the English reasoning trace provided into valid RLang syntax.

Requirements:
- Use all four phases in order: #[phase(Frame)], #[phase(Explore)], #[phase(Verify)], #[phase(Decide)]
- Every initial observation must carry p:, ep:, src:, scope:, t: metadata
- Evidence must use sup()/wkn()/neut() and be resolved via resolve()
- Decide must branch via match conf(x) with assert/hedge/suspend/reject arms
- Apply motivational (dcmp, prioritize, select), operational (exec, inv, bt), and communicative (dlg, discover) operators wherever the source reasoning implies those actions

Convert:
```

---

**Variant C — Compression-Focused**

```
Convert the following reasoning trace to RLang. RLang achieves 3–5x token compression over English CoT by replacing prose with typed, structured operators.

Key rules:
1. Frame phase: obs() facts + goal() declarations + req() constraints
2. Explore phase: evidence blocks [obs => sup/wkn/neut] + resolve() + dcmp/select for goals
3. Verify phase: req() checks + verify() + bt() with DiagnosisKind if steps fail
4. Decide phase: match conf(x) { c if c > T => assert/hedge/suspend/reject } + emit()
5. blf<p> on every belief, with metadata pipe: | p:X | ep:Y | src:Z | scope:W | t:V
6. Stale beliefs must decay() or refresh() before assertion
7. All bt() bounded by #[bounded(max_retries: N)]

Source trace:
```

---

**Variant D — Structured Extraction**

```
Task: Convert an English reasoning trace to RLang format.

RLang has 4 mandatory phases in fixed order:
- #[phase(Frame)] — what is observed and what is the goal
- #[phase(Explore)] — evidence evaluation and plan building  
- #[phase(Verify)] — constraint checking, possibly rebloom to Explore (max 3x)
- #[phase(Decide)] — final assertion via confidence branching, emit() output

For each piece of reasoning in the source:
- Identify which phase it belongs to
- Select the correct operator (cause, obs, req, sup, wkn, resolve, dcmp, exec, dlg, etc.)
- Attach appropriate metadata (p, ep, src, scope, t)
- Wire expressions with connectives (|>, ->, !>, ?>)

Apply the full feature set when the source implies it. Do not invent reasoning not present in the source. Do not omit reasoning that is present.

Trace to convert:
```

---

**Variant E — Adversarial / Anti-Pattern Aware**

```
Convert the following reasoning trace to valid RLang. Be vigilant against the 7 known anti-patterns:

1. Circular reasoning — do not re-enter Frame after Explore
2. Infinite reflection — all bt() must be inside #[bounded(max_retries: N)]
3. Constraint forgetting — req() declared in Frame must be verified in Verify
4. Premature commitment — Verify phase is mandatory; do not skip it
5. Over-verification — rebloom at most 3 times
6. Rumination — bt() requires DiagnosisKind + a novel revision plan
7. Confidence theater — p: on blf must come from resolve(), not arbitrary assignment

The output must be parseable RLang with all four phases present in order. Match arms in Decide must use assert/hedge/suspend/reject only. Evidence items must use sup/wkn/neut on the effect side only.

Trace:
```
