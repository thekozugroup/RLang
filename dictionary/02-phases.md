# Phase System Reference

[Back to Dictionary Index](./README.md) | [Previous: Language Overview](./01-language-overview.md) | [Next: Epistemic Operators](./03-operators-epistemic.md)

---

## Overview

Every RLang reasoning trace passes through exactly four phases in strict order. The parser enforces this structure at the grammar level. Skipping a phase or creating unbounded loops is a structural error.

```
Frame ──> Explore ──> Verify ──> Decide
                        |  ^
                        |  |  rebloom (max 3)
                        +--+
```

---

## Phase: Frame

**Purpose:** Reformulate the problem, extract constraints, identify context, declare initial beliefs and goals.

**Syntax:**
```rust
#[phase(Frame)]
impl Deductive {   // optional: impl Deductive | Abductive | Analogical
    // statements...
}
```

**Typical operators:**
- `obs()` -- observe initial facts
- `goal()` -- declare goals
- `req()` -- declare requirements/constraints
- `cause()`, `enbl()`, `prvnt()` -- establish causal relationships
- `isa()`, `cntns()` -- structural classification

**What is NOT allowed:**
- Evidence resolution (`resolve()`) -- evidence is evaluated in Explore
- Assertions (`assert()`, `hedge()`) -- decisions happen in Decide
- Delegation (`dlg()`) -- coordination happens after verification

**Valid transitions:**
- `Frame -> Explore` -- mandatory, exactly once

**Example:**
```rust
#[phase(Frame)]
impl Deductive {
    // Observe initial facts with full metadata
    let tests: blf<0.99> = obs(tests_pass)
        | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback)
        | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic)
        | p:0.90 | ep:direct | src:obs(metrics) | scope:loc | t:fresh;

    // Declare the goal
    let deploy_goal: goal<Deploy> = goal(self, deploy(fix))
        | priority:high | deadline:within(2h);
}
```

---

## Phase: Explore

**Purpose:** Decompose goals, generate candidates, apply reasoning methods, evaluate evidence, discover agents, build plans.

**Syntax:**
```rust
#[phase(Explore)]
{
    // statements...
}
```

**Typical operators:**
- `sup()`, `wkn()`, `neut()` -- build evidence
- `resolve()` -- resolve evidence to confidence
- `dcmp()` -- decompose goals into subgoals
- `prioritize()`, `select()` -- goal management
- `discover()`, `match_capability()` -- agent discovery
- `enbl()`, `cause()`, `sim()` -- reasoning about relationships
- `inv()`, `exec()` -- tool invocation and action execution

**What is NOT allowed:**
- Re-entering Frame -- cannot reformulate after exploration begins
- Final assertions (`assert()`, `hedge()`, `reject()`) -- decisions happen in Decide

**Valid transitions:**
- `Explore -> Verify` -- mandatory, exactly once per forward pass

**Example:**
```rust
#[phase(Explore)]
{
    // Build and resolve evidence
    let ev = [
        tests   => sup(deploy, +0.15),
        risk    => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];
    let deploy_blf = enbl(fix, resolve(bug))
        |> resolve(ev) -> Ok(blf<0.70>);

    // Discover an agent for delegation
    let agent_b = discover("monitoring")
        |> match_capability(monitor_goal);
    let trust_b = trust_score(&agent_b.id);
}
```

---

## Phase: Verify

**Purpose:** Check work against constraints, validate requirements, perform bounded backtracking if needed.

**Syntax:**
```rust
#[phase(Verify)]
{
    // statements...
}
```

**Typical operators:**
- `req()` -- check that requirements hold
- `verify()` -- verify a specific result
- `bt()` -- bounded backtrack on failure
- `retry_with()` -- retry with new data
- `conf()` -- check confidence levels

**What is NOT allowed:**
- Re-entering Frame -- the problem is already framed
- Unbounded reblooming -- rebloom count is capped by `max_rebloom`

**Valid transitions:**
- `Verify -> Explore` -- rebloom (bounded, see below)
- `Verify -> Decide` -- mandatory terminal transition

**Example:**
```rust
#[phase(Verify)]
{
    // Check that deployment requirements hold
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
    req(monitor_goal, trust_b >= 0.6) |> verify(trust_b) -> Ok(());

    // Verify resource conservation
    let total_budget = self.intent.resources;
    let monitor_budget = monitor_contract.resources;
    assert(monitor_budget <= total_budget);
}
```

---

## Phase: Decide

**Purpose:** Assert conclusions, select actions, delegate tasks, render output. This is the terminal phase -- no further transitions are allowed.

**Syntax:**
```rust
#[phase(Decide)]
{
    // statements...
}
```

**Typical operators:**
- `assert()` -- commit to a conclusion with high confidence
- `hedge()` -- conditional assertion with requirements
- `suspend()` -- hold decision, gather more evidence
- `reject()` -- discard a proposition
- `emit()` -- output a result
- `dlg()` -- delegate a task to another agent

**What is NOT allowed:**
- Any further phase transitions -- Decide is terminal
- Match arms that do not use assert/hedge/suspend/reject (validator enforces this)

**Valid transitions:**
- None -- Decide is terminal

**Validator rule:** All match arms in Decide phase must use `assert()`, `hedge()`, `suspend()`, or `reject()` as their body expression.

**Example:**
```rust
#[phase(Decide)]
{
    // Branch on confidence
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy_goal),
        c if c > 0.55 => hedge(deploy_goal, cond: [
            enbl(rollback_plan, deploy_goal),
        ]),
        _ => reject(deploy_goal),
    }

    // Delegate monitoring
    dlg(agent_b.id, monitor_goal, monitor_contract)
        -> Ok(task_id);

    // Emit the decision
    emit(Decision {
        deploy: Hedge { condition: "rollback plan required" },
        monitoring: Delegated { to: agent_b.id, task: task_id },
    });
}
```

---

## Rebloom Rules

**Rebloom** is the mechanism for iterative refinement: when verification reveals issues, the trace can loop back to Explore for additional reasoning.

### Rules

1. **Direction:** Rebloom is only `Verify -> Explore`. No other backward transitions are allowed.
2. **Bounded:** The maximum number of reblooms is controlled by `max_rebloom` (default: 3).
3. **Must add new information:** Each rebloom should introduce novel evidence or a revised approach, not repeat the same reasoning.
4. **Counted:** The parser/validator tracks rebloom count and rejects traces that exceed the limit.

### Rebloom flow

```
Frame -> Explore -> Verify --[issue found]--> Explore -> Verify --[ok]--> Decide
                                              (rebloom 1)
```

### Why rebloom exists

Verification may reveal:
- Missing evidence that needs to be gathered
- A constraint violation requiring a revised plan
- New information from a tool invocation or agent response

Without rebloom, the only option would be to fail. With bounded rebloom, the agent can refine its reasoning while being structurally prevented from infinite loops.

### Rebloom vs. backtrack

| Mechanism | Scope | Trigger | Bound |
|-----------|-------|---------|-------|
| Rebloom | Phase-level: Verify -> Explore | Verification failure | `max_rebloom` (default 3) |
| Backtrack (`bt`) | Within a phase: retry a step | Action/tool failure | `max_retries` per operation |

---

## Reasoning Modes

Each phase block can optionally declare a reasoning mode via `impl`:

```rust
#[phase(Frame)]
impl Deductive {
    // Conclusions follow necessarily from premises
}

#[phase(Explore)]
impl Abductive {
    // Best explanation for observed evidence
}

#[phase(Verify)]
impl Analogical {
    // Transfer reasoning from known case to new case
}
```

| Mode | Keyword | When to use |
|------|---------|-------------|
| **Deductive** | `impl Deductive` | Conclusion follows necessarily from premises |
| **Abductive** | `impl Abductive` | Inferring the best explanation for observations |
| **Analogical** | `impl Analogical` | Transferring knowledge from a known case to a new case |

If no `impl` is specified, the phase block uses a bare `{ }` with no declared reasoning mode.

---

## Phase Ordering Summary

| From | To | Allowed? | Condition |
|------|----|----------|-----------|
| Frame | Explore | Yes | Mandatory, exactly once |
| Frame | Verify | No | Must go through Explore |
| Frame | Decide | No | Must go through Explore and Verify |
| Explore | Verify | Yes | Mandatory, exactly once per forward pass |
| Explore | Decide | No | Must go through Verify |
| Explore | Frame | No | Cannot re-enter Frame |
| Verify | Decide | Yes | Mandatory terminal transition |
| Verify | Explore | Yes | Bounded by max_rebloom (default 3) |
| Verify | Frame | No | Cannot re-enter Frame |
| Decide | Any | No | Terminal phase |

---

*Next: [Epistemic Operators](./03-operators-epistemic.md)*
