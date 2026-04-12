# Metadata Reference

[Back to Dictionary Index](./README.md) | [Previous: Type System](./07-types.md) | [Next: Connectives](./09-connectives.md)

---

## Overview

Metadata is attached to expressions using `|` pipe separators. Every belief and many other expressions carry metadata that describes confidence, provenance, scope, and freshness.

**Syntax:**
```rust
expr | key:value | key:value | key:value;
```

**Grammar rule:**
```
metadata   = { ("|" ~ meta_field)+ }
meta_field = { meta_key ~ ":" ~ meta_value }
meta_key   = { "p" | "ep" | "src" | "scope" | "t"
             | "priority" | "deadline" | "success" | "mode"
             | "req" | "cond" }
meta_value = { operator_call | float_literal | ident | string_literal }
```

---

## Core Metadata Fields

### p: (confidence)

**Required** for beliefs. A float in the range 0.0..=1.0 representing the agent's confidence in the claim.

| Value Range | Interpretation | Decide Action |
|-------------|---------------|---------------|
| 0.85 - 1.0 | High confidence | `assert()` |
| 0.55 - 0.85 | Moderate confidence | `hedge()` |
| 0.30 - 0.55 | Low confidence | `suspend()` |
| 0.0 - 0.30 | Very low confidence | `reject()` |

**Example:**
```rust
let tests: blf<0.99> = obs(tests_pass) | p:0.99;
```

**Validation:** The validator rejects confidence values outside 0.0..=1.0.

**Anti-pattern note:** Confidence should be computed from evidence via `resolve()`, not asserted directly. Asserting arbitrary confidence values is confidence theater (anti-pattern #7).

---

### ep: (epistemic mode)

How the belief was formed. Determines the epistemological status of the claim.

| Value | Full Name | Meaning |
|-------|-----------|---------|
| `direct` | Direct | Directly observed -- highest epistemic status |
| `infer` | Inferred | Logically inferred from other beliefs |
| `anl` | Analogical | Reasoned by analogy from similar cases |
| `recv` | Received | Received from another agent (v0.2) |

**Example:**
```rust
let claim = cause(bug, crash) | ep:infer | src:chain(log_analysis, stack_trace);
let report = obs(status) | ep:recv | src:agent(monitor_agent);
```

**AST type:** `EpMode { Direct, Infer, Anl, Recv }`

---

### src: (source)

Where the belief came from. Tracks provenance for auditability.

| Value | Meaning | Example |
|-------|---------|---------|
| `obs(id)` | From direct observation | `src:obs(sensor_data)` |
| `chain(ids...)` | Inferred from chain of beliefs | `src:chain(a, b, c)` |
| `agent(id)` | Received from another agent | `src:agent(monitor_bot)` |
| `mem(id)` | Retrieved from memory | `src:mem(past_deployment)` |
| `Given` | Provided as input/premise | `src:Given` |

**Example:**
```rust
let tests = obs(tests_pass) | src:ci_pipeline;
let risk = obs(no_rollback) | src:obs(infra_check);
let advice = blf<0.7> = recv(recommendation) | src:agent(expert_agent);
```

**AST type:** `Src { Obs(String), Chain(Vec<String>), Agent(String), Mem(String), Given }`

---

### scope:

How broadly the claim applies. Constrains generalization.

| Value | Full Name | Meaning | Example |
|-------|-----------|---------|---------|
| `all` | Universal | All instances satisfy the claim | "All tests pass" |
| `some` | Existential | Some instances satisfy | "Some endpoints are slow" |
| `none` | Negative universal | No instances satisfy | "No data loss occurred" |
| `cond` | Conditional | Holds under stated conditions | "If traffic < threshold" |
| `gen` | General tendency | Generally true, with exceptions | "Deploys usually succeed" |
| `loc` | Local | Only applies in this context | "Tests pass in staging" |

**Example:**
```rust
let tests = obs(tests_pass) | scope:loc;     // Tests pass locally (staging)
let rule = cause(leak, crash) | scope:gen;    // Generally true
let claim = obs(no_outage) | scope:all;       // Universal claim
```

**AST type:** `Scope { All, Some, None, Cond, Gen, Loc }`

---

### t: (freshness)

Temporal freshness of the information. Rust lifetime analog.

| Value | Meaning | Implication |
|-------|---------|-------------|
| `fresh` | Recently observed/verified | Can be asserted directly |
| `stale` | Not recently verified, may have changed | Must `decay()` or `refresh()` before asserting |
| `unk` | Freshness unknown | Treat with caution |

**Example:**
```rust
let current = obs(metrics) | t:fresh;          // Just observed
let old = obs(last_week_data) | t:stale;       // May be outdated
let inherited = recv(claim) | t:unk;            // Don't know when observed
```

**Rules:**
- `'stale` beliefs cannot be directly asserted
- Use `decay(amount)` to reduce confidence of stale beliefs
- Use `refresh(new_obs)` to restore `'fresh` with new evidence

**AST type:** `Freshness { Fresh, Stale, Unk }`

---

## Extended Metadata Fields

### priority:

Goal/task priority level.

| Value | Meaning |
|-------|---------|
| `critical` | Must be achieved, blocks everything |
| `high` | Should be achieved soon |
| `normal` | Standard priority |
| `low` | Nice to have |
| `background` | Only if nothing else needs doing |

**Example:**
```rust
let goal = goal(deploy) | priority:high;
```

---

### deadline:

Temporal constraint on a goal or task.

| Value | Meaning |
|-------|---------|
| `urgent` | ASAP -- minimal reasoning budget |
| `by(timestamp)` | Hard deadline |
| `within(duration)` | Relative deadline |
| `flexible` | No time pressure |
| `none` | No deadline |

**Example:**
```rust
let goal = goal(deploy) | deadline:within(2h);
let task = exec(backup) | deadline:urgent;
```

---

### success:

Success criterion for a goal -- a predicate that determines when the goal is achieved.

**Example:**
```rust
let goal = goal(deploy) | success:obs(health_check_pass);
```

---

### mode:

Contract mode for delegation -- quality-speed tradeoff.

| Value | Meaning |
|-------|---------|
| `Urgent` | Minimal reasoning, tight timeout |
| `Economical` | Low effort, moderate timeout |
| `Balanced` | Full reasoning, generous timeout |
| `Custom(profile)` | Custom resource profile |

**Example:**
```rust
let contract = Contract { ... } | mode:Balanced;
```

---

### req:

Dependency references within a decomposed goal.

**Example:**
```rust
let subgoals = dcmp(goal, [
    goal(verify_tests) | priority:critical,
    goal(create_rollback) | priority:high,
    goal(execute_deploy) | req:[$0, $1],    // Depends on first two
]);
```

---

### cond:

Conditions attached to a hedged assertion.

**Example:**
```rust
hedge(deploy, cond: [enbl(rollback_plan, deploy)]);
```

---

## Metadata Abbreviations

RLang uses abbreviated forms for maximum token density:

| Full Form | Abbreviated | Context |
|-----------|-------------|---------|
| `confidence` | `p` | Metadata field |
| `epistemic` | `ep` | Metadata field |
| `source` | `src` | Metadata field |
| `timestamp` | `t` | Metadata field |

The abbreviated forms are the default in reasoning traces. Full forms exist for clarity in specifications and documentation.

---

## Complete Example

```rust
let claim: blf<0.85> = cause(storm, cncl(outdoor_event))
    | p:0.85
    | ep:infer
    | src:chain(weather_report, historical_data)
    | scope:loc
    | t:fresh;
```

This declares a belief with:
- **p:0.85** -- 85% confidence
- **ep:infer** -- logically inferred (not directly observed)
- **src:chain(...)** -- derived from a chain of two sources
- **scope:loc** -- applies locally to this context
- **t:fresh** -- recently verified

---

*Next: [Connectives Reference](./09-connectives.md)*
