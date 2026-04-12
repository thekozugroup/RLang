# Anti-Pattern Prevention Reference

[Back to Dictionary Index](./README.md) | [Previous: Evidence System](./10-evidence.md) | [Next: A2A Mapping](./12-a2a-mapping.md)

---

## Overview

RLang's grammar and type system structurally prevent 7 known reasoning failure modes identified in research across 6M+ reasoning traces. Each failure mode is caught at a specific enforcement level: parser (grammar), type system, or validator.

| # | Failure Mode | Prevention Mechanism | Enforcement Level |
|---|-------------|----------------------|-------------------|
| 1 | Circular reasoning | Phase system: cannot re-enter Frame after Explore | Parser (grammar) |
| 2 | Infinite reflection | `#[bounded(max_retries)]` on all backtrack operations | Type system |
| 3 | Constraint forgetting | `req()` constraints persist across all phases, checked at Decide | Validator |
| 4 | Premature commitment | Verify phase is mandatory before Decide | Parser (grammar) |
| 5 | Over-verification | Single Verify phase; rebloom bounded by `max_rebloom` | Parser + config |
| 6 | Rumination | Backtrack requires `DiagnosisKind` + novel `revision.plan` | Type system |
| 7 | Confidence theater | `p:` computed from evidence via `resolve()`, not asserted | Type system |

---

## Failure Mode #1: Circular Reasoning

### What it is

The model revisits the same argument or line of reasoning in loops, never making forward progress. Common in English CoT where the model says "Wait, let me reconsider..." and returns to a previously evaluated point.

### How it manifests in English reasoning

```
Let me think about this... The tests pass, so we should deploy.
Actually, wait -- what about the rollback plan?
Hmm, but the tests pass, so maybe it's fine...
Let me reconsider the rollback plan again...
But the tests pass...
```

### How RLang prevents it

The phase system enforces strict forward progress. Once the trace moves from Frame to Explore, it cannot re-enter Frame. The only backward transition is the bounded rebloom from Verify to Explore.

```
Frame -> Explore -> Verify -> Decide   (forward only)
                      |  ^
                      +--+             (bounded rebloom, max 3)
```

### What would trigger the error

A trace that attempts to declare a second `#[phase(Frame)]` block after an `#[phase(Explore)]` block.

### Validator error

The parser rejects any trace where phase blocks appear out of order. The phase ordering `Frame=0, Explore=1, Verify=2, Decide=3` is enforced by the grammar's `phase_name` rule combined with the validator's phase sequence check.

---

## Failure Mode #2: Infinite Reflection

### What it is

Self-correction chains that never terminate. The model keeps reflecting on its own reasoning, generating ever-longer chains of "let me reconsider" without converging.

### How it manifests in English reasoning

```
I think the answer is X.
Wait, let me check that again... Actually, maybe Y.
Hmm, but on reflection, X might be better after all.
Let me reconsider one more time...
Actually, thinking about it more carefully...
[continues indefinitely]
```

### How RLang prevents it

All backtrack operations (`bt()`) are bounded by `#[bounded(max_retries)]`. The type system enforces that `max_retries` is a finite `u8` value (default: 3).

```rust
#[bounded(max_retries: 3)]
fn backtrack<T>(
    failed: Reflection,
    max_retries: u8,
) -> Result<T, BacktrackErr> {
    // At most 3 retries before giving up
}
```

### What would trigger the error

A backtrack operation that exceeds its `max_retries` count.

### Validator error

`BacktrackErr::MaxRetries(3)` -- the operation has exhausted its retry budget.

---

## Failure Mode #3: Constraint Forgetting

### What it is

Losing track of requirements during long reasoning chains. The model establishes constraints early but fails to check them before making a decision.

### How it manifests in English reasoning

```
We need tests to pass AND a rollback plan before deploying.
[200 tokens of analysis later...]
Since the tests pass, let's deploy!
[Forgot about the rollback plan requirement]
```

### How RLang prevents it

`req()` constraints are declared in early phases and persist across all phases. The validator checks that all `req()` constraints are verified before the Decide phase.

```rust
#[phase(Frame)]
{
    req(deploy, obs(tests_pass));       // Constraint 1
    req(deploy, obs(rollback_plan));    // Constraint 2
}

#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
    req(deploy, obs(rollback_plan)) |> verify(rollback) -> Ok(());
    // Both constraints explicitly checked
}
```

### What would trigger the error

A trace that declares `req()` constraints but does not `verify()` them before Decide.

### Validator error

The validator reports any `req()` constraint that was not paired with a corresponding `verify()` in the Verify phase.

---

## Failure Mode #4: Premature Commitment

### What it is

Locking into a conclusion without verification. The model jumps from analysis directly to a decision without checking its work.

### How it manifests in English reasoning

```
The tests pass, so we should deploy. Done!
[Never checked rollback plan, traffic, or other constraints]
```

### How RLang prevents it

The Verify phase is mandatory before Decide. The parser enforces that a `#[phase(Verify)]` block must appear between `#[phase(Explore)]` and `#[phase(Decide)]`.

```
Frame -> Explore -> Verify -> Decide
                    ^^^^^^
                    Cannot skip this
```

### What would trigger the error

A trace that goes directly from `#[phase(Explore)]` to `#[phase(Decide)]` without a `#[phase(Verify)]` block.

### Validator error

The parser rejects traces with missing phases. All four phases must be present in order.

---

## Failure Mode #5: Over-Verification

### What it is

Checking the same thing repeatedly without progress. The model keeps re-verifying results it has already confirmed.

### How it manifests in English reasoning

```
Let me verify the tests pass... yes, they pass.
But let me double-check... yes, still passing.
One more time to be sure... confirmed, passing.
Actually, let me verify once more...
```

### How RLang prevents it

There is a single Verify phase. The rebloom mechanism (Verify -> Explore -> Verify) is bounded by `max_rebloom` (default: 3). Each rebloom must introduce new information, not re-verify existing results.

### What would trigger the error

A trace that exceeds `max_rebloom` transitions from Verify back to Explore.

### Validator error

`RebloomExceeded { count: 4, max: 3 }` -- the trace attempted more verify-explore cycles than allowed.

---

## Failure Mode #6: Rumination

### What it is

Revisiting a failed approach without new insight. The model retries the same strategy hoping for different results.

### How it manifests in English reasoning

```
Let me try approach A... it failed.
OK, let me try approach A again with slight tweaks... failed again.
What if I try approach A one more time...
```

### How RLang prevents it

Every backtrack (`bt()`) requires a structured `Reflection` with a typed `DiagnosisKind` and a `revision.plan` that must differ from the failed plan. The validator checks structural inequality between the previous and revised plans.

```rust
let reflection = Reflection {
    attempt: deploy_attempt_1,
    outcome: Err("timeout"),
    diagnosis: ToolFailure(deploy_tool, "connection refused"),  // Typed diagnosis
    revision: Some(new_plan),  // Must differ from failed plan
};

bt(reflection);
```

### What would trigger the error

A backtrack where `revision.plan == previous.plan` (structurally identical retry).

### Validator error

The validator checks the invariant: `revision.plan != previous.plan`. If the plans are structurally equal, the backtrack is rejected as rumination.

---

## Failure Mode #7: Confidence Theater

### What it is

Expressing uncertainty through prose without information gain. The model asserts confidence levels arbitrarily without grounding them in evidence.

### How it manifests in English reasoning

```
I'm fairly confident that we should deploy.
I think maybe around 70% sure.
[Where did 70% come from? No evidence evaluated.]
```

### How RLang prevents it

Confidence (`p:`) must be computed from evidence via `resolve()`, not asserted through prose. The evidence system requires explicit `sup()`, `wkn()`, and `neut()` items that contribute to the final confidence value.

```rust
// WRONG: arbitrary confidence assertion
// let claim: blf<0.9> = cause(a, b);  // Where does 0.9 come from?

// CORRECT: confidence computed from evidence
let ev = [
    obs(tests) => sup(deploy, +0.15),
    obs(risk)  => wkn(deploy, -0.25),
];
let claim = resolve(ev) -> Ok(blf<0.70>);  // 0.70 derived from evidence
```

### What would trigger the error

Assigning a confidence value to a belief without evidence resolution backing it.

### Validator error

The type system enforces that `blf` confidence values are produced by `resolve()` operations, not arbitrary assignment.

---

## Enforcement Level Summary

| Level | What it catches | When |
|-------|----------------|------|
| **Parser (grammar)** | Phase ordering, phase presence, syntax structure | Parse time |
| **Type system** | Bounded operations, typed diagnoses, plan novelty | Type check time |
| **Validator** | Confidence ranges, evidence structure, match arm types, constraint checking | Validation time |

---

*Next: [A2A Protocol Mapping](./12-a2a-mapping.md)*
