# Layer 1: Epistemic Operators

[Back to Dictionary Index](./README.md) | [Previous: Phase System](./02-phases.md) | [Next: Motivational Operators](./04-operators-motivational.md)

---

## Overview

The epistemic layer is the foundation of RLang. It models beliefs, evidence, confidence, and the relationships between propositions. Every other layer builds on epistemic types.

Epistemic operators are organized into 7 categories:
- **Causal** (4): cause, prvnt, enbl, req
- **Evidence** (1): obs
- **State** (2): chng, cncl
- **Structure** (3): cntns, isa, sim
- **Temporal** (1): seq
- **Intent** (2): goal, confl
- **Evidence Modifiers** (3): sup, wkn, neut
- **Resolution** (4): resolve, conf, decay, refresh

---

## Causal Operators

### cause

**Signature:** `cause(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` causes `b`.

**Category:** Causal

**Example:**
```rust
let failure = cause(memory_leak, crash) | p:0.85 | ep:infer | src:obs(logs);
```

**Common patterns:**
- Pair with `obs()` for observed causal links: `obs(leak) |> cause(leak, crash)`
- Chain with `prvnt()` for prevention: `cause(a, b) |> prvnt(fix, b)`
- Use in evidence blocks: `cause(storm, outage) => sup(cancel_deploy, +0.20)`

---

### prvnt

**Signature:** `prvnt(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` prevents `b`.

**Category:** Causal

**Example:**
```rust
let protection = prvnt(firewall, breach) | p:0.90 | ep:direct | src:obs(sec_audit);
```

**Common patterns:**
- Pair with `cause()` to model intervention: `cause(bug, crash) |> prvnt(fix, crash)`
- Use in Verify phase to check safeguards: `req(deploy, prvnt(rollback, data_loss))`

---

### enbl

**Signature:** `enbl(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` enables `b` (makes `b` possible, does not guarantee it).

**Category:** Causal

**Example:**
```rust
let readiness = enbl(tests_pass, deploy) | p:0.95 | ep:direct | src:ci_pipeline;
```

**Common patterns:**
- Distinguish from `cause()`: enable is possibility, cause is determination
- Chain in Explore: `enbl(fix, resolve(bug)) |> resolve(ev) -> Ok(ready)`
- Used in Decide for conditional assertions: `hedge(deploy, cond: [enbl(rollback, deploy)])`

---

### req

**Signature:** `req(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` requires `b` (a cannot exist/succeed without b). Requirements persist across all phases and are checked at Decide.

**Category:** Causal

**Example:**
```rust
req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
```

**Common patterns:**
- Central to Verify phase: check all requirements before deciding
- Anti-pattern prevention: prevents constraint forgetting (failure mode #3)
- Chain with `verify()`: `req(goal, condition) |> verify(condition) -> Ok(())`

---

## Evidence Operator

### obs

**Signature:** `obs(x)` -- unary (arity 1)

**Purpose:** Declares that `x` is directly observed.

**Category:** Evidence

**Example:**
```rust
let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | t:fresh;
```

**Common patterns:**
- Primary way to introduce facts in Frame phase
- Source of evidence in evidence blocks: `obs(dark_clouds) => sup(rain, +0.20)`
- Chain with other operators: `obs(crash_log) |> cause(bug, crash)`
- Nest in `src:` metadata: `src:obs(sensor_data)`

---

## State Operators

### chng

**Signature:** `chng(x, from, to)` -- ternary (arity 3)

**Purpose:** Declares that `x` changes from state `from` to state `to`.

**Category:** State

**Example:**
```rust
let migration = chng(database, v1_schema, v2_schema) | p:0.80 | ep:infer;
```

**Common patterns:**
- Model state transitions: `chng(service, healthy, degraded)`
- Track environment changes: `chng(traffic, low, high) |> wkn(deploy_confidence, -0.10)`

---

### cncl

**Signature:** `cncl(a, b)` -- binary (arity 2)

**Purpose:** Negates or cancels a proposition.

**Category:** State

**Example:**
```rust
let cancellation = cncl(storm, meeting) | p:0.75 | ep:infer | src:obs(weather);
```

**Common patterns:**
- Cancel a planned action: `cncl(deploy, production)`
- In causal chains: `cause(storm, cncl(outdoor_event))`
- Evidence for weakening: `cncl(previous_plan) => wkn(approach, -0.30)`

---

## Structure Operators

### cntns

**Signature:** `cntns(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` contains `b` (containment relationship).

**Category:** Structure

**Example:**
```rust
let membership = cntns(team_alpha, agent_b) | p:0.99 | ep:direct;
```

**Common patterns:**
- Model set membership: `cntns(valid_states, current_state)`
- Compose with `isa()`: `isa(error, runtime_error) |> cntns(critical_errors, error)`

---

### isa

**Signature:** `isa(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` is a type/category of `b` (classification).

**Category:** Structure

**Example:**
```rust
let classification = isa(timeout_error, recoverable_error) | p:0.95 | ep:infer;
```

**Common patterns:**
- Taxonomic reasoning: `isa(python, programming_language)`
- Type-based branching: `isa(error, retryable) |> retry_with(attempt, new_config)`

---

### sim

**Signature:** `sim(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` is similar to `b` (analogical link).

**Category:** Structure

**Example:**
```rust
let analogy = sim(current_outage, prev_outage_march) | p:0.70 | ep:anl;
```

**Common patterns:**
- Foundation for analogical reasoning: `sim(proj_a, proj_b) |> transfer(fix_a, fix_b)`
- Used in `impl Analogical` blocks
- Evidence for hypotheses: `sim(pattern_a, pattern_b) => sup(hypothesis, +0.15)`

---

## Temporal Operator

### seq

**Signature:** `seq(a, b, ...)` -- variadic

**Purpose:** Declares a temporal sequence (a occurs before b, etc.).

**Category:** Temporal

**Example:**
```rust
let workflow = seq(build, test, deploy, monitor);
```

**Common patterns:**
- Model ordered processes: `seq(compile, lint, test, deploy)`
- Express temporal dependencies in plans
- Compose with `req()`: `req(deploy, seq(build, test))`

---

## Intent Operators

### goal

**Signature:** `goal(target)` -- unary (arity 1)

**Purpose:** Declares a goal to be achieved.

**Category:** Intent

**Example:**
```rust
let deploy_goal: goal<Deploy> = goal(self, deploy(fix))
    | priority:high | deadline:within(2h);
```

**Common patterns:**
- Typically declared in Frame phase
- Compose with motivational operators: `goal(deploy) |> dcmp(subgoals)`
- Used as target in delegation: `dlg(agent_b, monitor_goal)`

---

### confl

**Signature:** `confl(a, b)` -- binary (arity 2)

**Purpose:** Declares that `a` conflicts with `b` (contradiction detected).

**Category:** Intent

**Example:**
```rust
let contradiction = confl(deploy_now, wait_for_tests) | p:0.90 | ep:infer;
```

**Common patterns:**
- Trigger conflict resolution: `confl(a, b) |> resolve_conflict(conflict, strategy)`
- Evidence for weakening: `confl(claim_a, claim_b) => wkn(claim_a, -0.20)`
- In evidence resolution error handling: `Err(Conflict(a, b)) => confl(a, b)`

---

## Evidence Modifiers

### sup

**Signature:** `sup(claim, delta)` -- binary (arity 2)

**Purpose:** Adds supporting evidence with a positive confidence delta.

**Category:** Evidence Modifier

**Example:**
```rust
let ev = [
    obs(tests_pass)  => sup(deploy, +0.15),
    obs(low_traffic)  => sup(deploy, +0.10),
];
```

**Common patterns:**
- Always used inside evidence blocks `[ ... ]`
- Delta is positive: `+0.05`, `+0.15`, `+0.20`
- Paired with `wkn()` for balanced evaluation
- See [Evidence System](./10-evidence.md) for full details

---

### wkn

**Signature:** `wkn(claim, delta)` -- binary (arity 2)

**Purpose:** Adds weakening evidence with a negative confidence delta.

**Category:** Evidence Modifier

**Example:**
```rust
let ev = [
    obs(no_rollback)  => wkn(deploy, -0.25),
    obs(high_traffic)  => wkn(deploy, -0.15),
];
```

**Common patterns:**
- Always used inside evidence blocks `[ ... ]`
- Delta is negative: `-0.10`, `-0.25`
- Paired with `sup()` for balanced evaluation

---

### neut

**Signature:** `neut(claim, weight)` -- binary (arity 2)

**Purpose:** Records neutral evidence -- relevant but neither supporting nor weakening.

**Category:** Evidence Modifier

**Example:**
```rust
let ev = [
    obs(team_size)  => neut(deploy, 0.0),
];
```

**Common patterns:**
- Documents that evidence was considered but found neutral
- Important for audit trails -- shows what was evaluated
- Weight is typically `0.0`

---

## Resolution Operators

### resolve

**Signature:** `resolve(evidence)` -- variadic (1 or 2 args)

**Purpose:** Resolves an evidence block into a final confidence value. Returns `Ok(blf)` or `Err(reason)`.

**Category:** Resolution

**Example:**
```rust
let deploy_blf = resolve(ev) -> Ok(blf<0.70>);

// In a pipe chain
claim |> resolve(ev) -> match {
    Ok(resolved) => resolved,
    Err(InsufEv) => suspend(claim),
}
```

**Common patterns:**
- Core of the evidence system -- computes confidence from evidence
- Always produces a `Result`: `Ok(blf)` or `Err(reason)`
- Central to anti-pattern #7 prevention: confidence is computed, never asserted
- See [Evidence System](./10-evidence.md) for full resolution mechanics

---

### conf

**Signature:** `conf(belief)` -- variadic (1 or 2 args)

**Purpose:** Extracts the confidence value from a belief for branching.

**Category:** Resolution

**Example:**
```rust
match conf(deploy_blf) {
    c if c > 0.80 => assert(deploy),
    c if c > 0.55 => hedge(deploy),
    _ => reject(deploy),
}
```

**Common patterns:**
- Primary mechanism for confidence-based branching in Decide phase
- Used in guard patterns: `c if c > threshold`
- See [Evidence System](./10-evidence.md) for confidence branching patterns

---

### decay

**Signature:** `decay(belief, amount)` -- variadic (1 or 2 args)

**Purpose:** Reduces confidence of a stale belief by a specified amount.

**Category:** Resolution

**Example:**
```rust
let degraded: blf<0.75> = old_data.decay(0.15);
// or in pipe form
old_data |> decay(0.15) -> blf<0.75, 'stale>;
```

**Common patterns:**
- Used when stale data must be incorporated at reduced confidence
- Alternative to `refresh()` when re-observation is not possible
- Part of the freshness/lifetime system

---

### refresh

**Signature:** `refresh(belief, new_observation)` -- variadic (1 or 2 args)

**Purpose:** Refreshes a stale belief with new evidence, restoring `'fresh` lifetime.

**Category:** Resolution

**Example:**
```rust
let refreshed: blf<0.9, 'fresh> = old_data |> refresh(obs(new_log));
```

**Common patterns:**
- Converts `'stale` to `'fresh` by providing new observation
- Preferred over `decay()` when fresh data is available
- Part of the freshness/lifetime system

---

## Assertion Operators

These are built-in operators used primarily in the Decide phase. They have variadic arity.

### assert

**Purpose:** Commit to a proposition with high confidence.

```rust
assert(deploy_goal);
```

### hedge

**Purpose:** Conditionally commit, with stated conditions.

```rust
hedge(deploy_goal, cond: [enbl(rollback_plan, deploy_goal)]);
```

### suspend

**Purpose:** Hold a decision pending more evidence.

```rust
suspend(claim);
```

### reject

**Purpose:** Discard a proposition.

```rust
reject(risky_plan);
```

### emit

**Purpose:** Output a result to the user/consumer.

```rust
emit(Decision { deploy: true, confidence: 0.85 });
```

---

*Next: [Motivational Operators](./04-operators-motivational.md)*
