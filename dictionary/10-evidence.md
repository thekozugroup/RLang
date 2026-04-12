# Evidence System Reference

[Back to Dictionary Index](./README.md) | [Previous: Connectives](./09-connectives.md) | [Next: Anti-Patterns](./11-anti-patterns.md)

---

## Overview

The evidence system is how RLang computes confidence. Instead of asserting arbitrary confidence values (confidence theater), confidence is derived from evidence blocks that support, weaken, or neutrally reference a claim. The `resolve()` operator aggregates evidence into a final confidence value.

This is central to anti-pattern #7 prevention: confidence is computed, never asserted.

---

## Evidence Block Syntax

Evidence blocks are array-like structures where each item maps an observation to an evidence effect.

**Syntax:**
```rust
let ev = [
    observation_1 => effect_1,
    observation_2 => effect_2,
    observation_3 => effect_3,
];
```

**Grammar rule:**
```
evidence_block = { "[" ~ evidence_item ~ ("," ~ evidence_item)* ~ ","? ~ "]" }
evidence_item  = { expr ~ "=>" ~ expr }
```

**Validator rule:** The effect side of each evidence item must use `sup()`, `wkn()`, or `neut()`. Any other operator on the effect side is a semantic error.

**Error message:** `"evidence item effect must use sup(), wkn(), or neut() operator"`

---

## Evidence Operators

### sup() -- Support

Adds supporting evidence with a positive confidence delta.

**Signature:** `sup(claim, +delta)` -- binary

**Semantics:** Increases the confidence in `claim` by `delta`. The delta is a positive float prefixed with `+`.

**Example:**
```rust
obs(tests_pass) => sup(deploy, +0.15)    // Tests passing supports deployment
obs(low_traffic) => sup(deploy, +0.10)   // Low traffic supports deployment
```

**Rules:**
- Delta must be positive: `+0.05`, `+0.10`, `+0.15`, `+0.20`
- Multiple sup() effects on the same claim are additive
- Larger deltas indicate stronger supporting evidence

---

### wkn() -- Weaken

Adds weakening evidence with a negative confidence delta.

**Signature:** `wkn(claim, -delta)` -- binary

**Semantics:** Decreases the confidence in `claim` by `delta`. The delta is a negative float prefixed with `-`.

**Example:**
```rust
obs(no_rollback) => wkn(deploy, -0.25)    // No rollback plan weakens deployment case
obs(high_traffic) => wkn(deploy, -0.15)   // High traffic weakens deployment case
```

**Rules:**
- Delta must be negative: `-0.10`, `-0.15`, `-0.25`
- Multiple wkn() effects on the same claim are additive (cumulative weakening)
- Larger absolute deltas indicate stronger weakening evidence

---

### neut() -- Neutral

Records neutral evidence that is relevant but neither supports nor weakens.

**Signature:** `neut(claim, weight)` -- binary

**Semantics:** Documents that evidence was considered and found to be neutral. Important for audit trails.

**Example:**
```rust
obs(team_size) => neut(deploy, 0.0)       // Team size is relevant but not decisive
obs(day_of_week) => neut(deploy, 0.0)     // Day noted but not a factor
```

**Rules:**
- Weight is typically `0.0`
- Documents what was evaluated for completeness
- Does not change the final confidence

---

## Resolution: resolve()

The `resolve()` operator aggregates all evidence into a final confidence value.

**Signature:** `resolve(evidence)` -- takes an evidence block and produces a Result

**Semantics:** Computes the net confidence by applying all evidence deltas to a base confidence. Returns `Ok(blf<computed>)` on success or `Err(reason)` on failure.

**Example:**
```rust
// Build evidence
let ev = [
    tests   => sup(deploy, +0.15),
    risk    => wkn(deploy, -0.25),
    traffic => sup(deploy, +0.10),
];

// Resolve: base confidence + deltas = final confidence
let deploy_blf = resolve(ev) -> Ok(blf<0.70>);
```

**In pipe chains:**
```rust
claim |> resolve(ev) -> match {
    Ok(resolved) => resolved,
    Err(InsufEv) => suspend(claim),
    Err(Conflict(a, b)) => confl(a, b),
    Err(Stale(blf)) => blf.decay(0.15),
};
```

**Error conditions:**
- `InsufEv` -- not enough evidence to reach a conclusion
- `Conflict(a, b)` -- contradictory evidence that cannot be resolved
- `Stale(blf)` -- evidence is stale and unreliable

---

## Confidence Branching

After resolving evidence, use `conf()` to extract the confidence value and branch on it.

**Pattern:**
```rust
match conf(claim) {
    c if c > 0.85 => assert(claim),              // High: commit
    c if c > 0.55 => hedge(claim, cond: [...]),   // Medium: conditional
    c if c > 0.30 => suspend(claim),              // Low: hold
    _             => reject(claim),               // Very low: discard
}
```

**Validator rule:** In the Decide phase, all match arms must use `assert()`, `hedge()`, `suspend()`, or `reject()` as their body. Any other expression is a semantic error.

**Error message:** `"match arms in Decide phase must use assert(), hedge(), suspend(), or reject()"`

---

## Complete Evidence Flow

Here is the full evidence lifecycle from observation to decision:

### Step 1: Observe (Frame phase)

```rust
#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass)
        | p:0.99 | ep:direct | src:ci_pipeline | t:fresh;
    let risk: blf<0.85> = obs(no_rollback)
        | p:0.85 | ep:direct | src:obs(infra) | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic)
        | p:0.90 | ep:direct | src:obs(metrics) | t:fresh;
}
```

### Step 2: Build evidence and resolve (Explore phase)

```rust
#[phase(Explore)]
{
    let ev = [
        tests   => sup(deploy, +0.15),
        risk    => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];
    let deploy_blf = resolve(ev) -> Ok(blf<0.70>);
}
```

### Step 3: Verify constraints (Verify phase)

```rust
#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}
```

### Step 4: Branch on confidence (Decide phase)

```rust
#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy),
        _ => reject(deploy),
    }
}
```

---

## Lifetime and Freshness in Evidence

Stale beliefs cannot be directly asserted. They must be handled explicitly:

**Option 1: Decay** -- reduce confidence to acknowledge staleness:
```rust
let degraded: blf<0.75, 'stale> = old_data |> decay(0.15);
```

**Option 2: Refresh** -- restore freshness with new observation:
```rust
let refreshed: blf<0.9, 'fresh> = old_data |> refresh(obs(new_log));
```

**Attempting to assert a stale belief directly is an error.** This prevents reasoning on outdated information without acknowledging the risk.

---

## Evidence Best Practices

1. **Always compute confidence from evidence** -- never assert arbitrary `p:` values without backing evidence
2. **Balance sup() and wkn()** -- good reasoning considers both supporting and weakening evidence
3. **Document neutral evidence with neut()** -- shows what was considered for auditability
4. **Handle all resolve() error cases** -- insufficient evidence, conflicts, and staleness
5. **Use appropriate delta magnitudes** -- small deltas (0.05-0.10) for weak evidence, larger (0.15-0.25) for strong evidence

---

*Next: [Anti-Pattern Prevention Reference](./11-anti-patterns.md)*
