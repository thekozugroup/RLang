# RLang
## A Rust-Inspired Synthetic Reasoning Language for Lightweight AI Agents

**Specification Draft v0.1**

---

## Executive Summary

RLang is a compact, strongly-typed reasoning language designed to serve as the internal scratchpad language for lightweight AI agents. It is not intended for human conversation. Its sole purpose is to give a small model a dense, unambiguous medium in which to think before rendering output in a natural language such as English.

The core premise is straightforward: English is a poor substrate for machine reasoning. It is redundant, ambiguous, scope-implicit, and carries emotional and rhetorical weight that contaminates logical inference. A model forced to reason in English must spend significant capacity parsing and generating natural language structures that add no logical value.

RLang draws its syntax and philosophy from Rust — a language already praised for enforcing correctness, eliminating implicit behavior, and making errors visible at the structural level. These properties translate directly into desirable reasoning behaviors.

**Primary Goals:**

- Maximum semantic density per token
- Unambiguous logical scope at all times
- Explicit epistemic state — confidence, source, and freshness — baked into the grammar
- Structural proximity to Rust for dual-use in code-reasoning tasks
- Human-parseable without being human-optimized

An agent trained to reason in RLang produces internal chain-of-thought traces that look like typed Rust expressions — structured, traceable, and free from the fluent-sounding hallucinations that natural language reasoning enables. Errors become type errors. Uncertainty becomes a typed field. Conclusions are resolved expressions, not guesses dressed in hedging prose.

---

## Design Principles

### 1. No Implicit Behavior

Everything the model asserts must be explicitly encoded. There is no equivalent of "it goes without saying." If a causal link exists, it is written. If confidence is absent, the expression is malformed. This mirrors Rust's philosophy that implicit coercions are a source of bugs.

### 2. Typed Epistemic State

Every belief or claim carries a confidence value between `0.0` and `1.0`. This is not optional prose hedging — it is a required field. A statement without a confidence annotation is a compile-time error in the language. The type system encodes not just what is claimed, but how certain the claim is and why.

### 3. Abbreviated but Anchored Vocabulary

Keywords are shortened aggressively — but not replaced by pure symbols. This preserves a training corpus anchor. A model trained on natural language can generalize to abbreviated forms. A model trained on arbitrary glyphs cannot. The goal is the maximum compression that still permits corpus-grounded learning.

### 4. Rust-Proximate Structure

RLang is syntactically close enough to Rust that a model trained on RLang reasoning traces will internalize Rust idioms as a byproduct. Ownership, lifetimes, Result types, and match expressions appear in reasoning chains, not just in code. This is a deliberate dual-use feature for agents that both reason and generate Rust code.

### 5. Separable Reasoning and Output Phases

RLang is strictly a scratchpad language. The agent reasons in RLang, then renders output in natural language. These are two distinct phases that must never blur. The rendering step is a translation function, not a continuation of reasoning. This enforces clean separation between internal inference and external communication.

---

## Syntax Overview

### Core Structure

Every RLang expression follows a subject-operator-object pattern with mandatory metadata fields. The pipe operator `|` separates the core claim from its metadata. Arrows `->` denote resolution or transformation. The `|>` operator chains reasoning steps.

```rust
// General form:
<operator>(<subject>, <object>) | <metadata>

// Metadata fields:
p:<0.0-1.0>           // confidence (required)
src:<label>           // source of inference
ep:<direct|infer|anl> // epistemic mode
scope:<cond|gen|loc>  // scope of claim
t:<fresh|stale|unk>   // temporal freshness
```

---

### Epistemic Modes

The `ep:` field encodes how the model arrived at a claim. There are three modes:

| Token | Meaning | Example |
|---|---|---|
| `ep:direct` | Directly observed | `obs(rain) \| p:0.95 \| ep:direct` |
| `ep:infer` | Logically inferred | `cause(rain, wet) \| p:0.8 \| ep:infer` |
| `ep:anl` | Analogical reasoning | `sim(case_a, case_b) \| p:0.6 \| ep:anl` |

---

### Core Operators

RLang defines a minimal set of primitive operators from which all reasoning composes. No operator is added unless it cannot be expressed as a composition of existing ones.

| Token | Meaning | Example |
|---|---|---|
| `cause(a,b)` | a causes b | `cause(storm, cncl(mtg)) \| p:0.7` |
| `prvnt(a,b)` | a prevents b | `prvnt(vaccine, infect) \| p:0.88` |
| `enbl(a,b)` | a enables b | `enbl(auth, access) \| p:1.0` |
| `obs(x)` | x is observed | `obs(err_log) \| p:0.99 \| ep:direct` |
| `sim(a,b)` | a is similar to b | `sim(bug_a, bug_b) \| p:0.65 \| ep:anl` |
| `chng(x,a,b)` | x changes from a to b | `chng(state, idle, run)` |
| `cncl(x)` | x is negated or canceled | `cncl(mtg) \| p:0.7` |
| `cntns(a,b)` | a contains b | `cntns(scope, edge_case)` |

---

### Belief and Resolution

A `blf` is a typed claim with a confidence value. It is resolved through an evidence block and returns either `Ok<T>` or `Err(reason)` — directly mirroring Rust's Result type.

```rust
let claim: blf<0.7> = cause(storm, cncl(mtg));

let ev = [
    obs(dark_clouds)    => sup(claim, +0.20),
    obs(no_notice)      => wkn(claim, -0.15),
    obs(empty_lot)      => sup(claim, +0.10),
];

claim |> resolve(ev)
    -> Ok<blf<0.65>>
    | Err(insuf_ev)
```

---

### Conditional Branching

Branching uses Rust-style match expressions. The model is forced to handle all meaningful confidence ranges explicitly — no silent fallthrough.

```rust
match conf(claim) {
    c if c > 0.85 => assert(claim),
    c if c > 0.55 => hedge(claim),
    c if c > 0.30 => suspend(claim),
    _             => reject(claim),
}
```

---

### Lifetimes for Information Freshness

Borrowed from Rust's lifetime system, the `'fresh` and `'stale` markers indicate whether the information a belief is grounded in can be trusted at inference time. A stale belief cannot be asserted without an explicit refresh or a confidence penalty.

```rust
let old_data: blf<0.9, 'stale> = cause(bug, crash);

// Cannot assert stale belief directly — must degrade confidence
let degraded = old_data.decay(0.15);
// -> blf<0.75, 'stale>

// Or refresh with new observation
let refreshed = old_data.refresh(obs(new_log));
// -> blf<0.9, 'fresh>
```

---

### Trait-Based Reasoning Modes

Analogous to Rust traits, reasoning mode is declared explicitly with `impl`. This forces the model to commit to the kind of inference it is performing before it performs it.

```rust
impl Deductive {
    // Conclusion follows necessarily from premises
    if enbl(key, access) && obs(key_present) {
        assert(access) | p:0.99
    }
}

impl Abductive {
    // Best explanation for observed evidence
    obs(crash) => cause?(mem_leak) | p:0.72 | ep:infer
}

impl Analogical {
    // Transfer from known case to new case
    sim(proj_a, proj_b) | p:0.6 => transfer(fix_a -> fix_b)
}
```

---

## Complete Reasoning Example

The following illustrates a full RLang reasoning trace for the question: *"Should we deploy the fix to production?"*

```rust
impl Deductive {

    // Observe current state
    let state: obs(tests_pass)      | p:0.99 | ep:direct | t:fresh
    let risk:  obs(no_rollback_plan) | p:0.85 | ep:direct | t:fresh

    // Form primary belief
    let deploy: blf<0.7> = enbl(fix, resolve(bug));

    // Weight evidence
    let ev = [
        state              => sup(deploy, +0.15),
        risk               => wkn(deploy, -0.25),
        obs(low_traffic)   => sup(deploy, +0.10),
    ];

    // Resolve
    deploy |> resolve(ev) -> Ok<blf<0.70>>

    // Branch on result
    match conf(deploy) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy, cond: [enbl(rollback_plan, deploy)]),
        _             => reject(deploy),
    }

    // Output: hedge — recommend deploy only if rollback plan exists
}
```

**Rendered English output:** "The fix is ready and tests are passing, but I recommend deploying only once a rollback plan is in place. Without one, the risk outweighs the benefit at current confidence."

---

## Training Notes

### Corpus Generation Strategy

Because no natural corpus of RLang exists, training data must be synthetically generated. The recommended approach is to prompt a large frontier model to produce paired examples: a natural language reasoning problem alongside its RLang chain-of-thought trace, followed by a natural language conclusion.

These paired examples teach the target model to treat RLang as an intermediate scratchpad — inputs arrive in English, processing happens in RLang, outputs render in English. The RLang phase is never shown to the end user.

### Target Model Profile

RLang is designed for small, quantized models in the 1B to 7B parameter range running on edge hardware. The reasoning compression it provides is most valuable where context windows are small and latency is constrained. A model that reasons in 80 dense RLang tokens instead of 300 ambiguous English tokens is meaningfully more efficient at small scale.

### Rust Codegen Synergy

Models fine-tuned on RLang reasoning traces should be evaluated on Rust code generation benchmarks alongside general reasoning benchmarks. The hypothesis is that structural exposure to typed, owned, scope-explicit reasoning will improve Rust codegen quality as a downstream effect — not because the model was trained on more Rust code, but because its reasoning style naturally aligns with Rust's execution model.

---

## Open Questions

- What is the minimum viable vocabulary size for general reasoning coverage?
- Should numeric confidence values be quantized to discrete levels (e.g. 0.25 steps) to reduce token entropy?
- Can RLang be extended with a module system for domain-specific operator libraries — medical, legal, financial?
- Is there a formal grammar expressible as a PEG or EBNF for parser-based validation of reasoning traces?
- How does RLang interact with tool-use and retrieval — should retrieved facts carry an automatic freshness tag?
- Should the rendering phase be a separate fine-tuned model, or a prompted output layer on the same model?

---

*RLang Specification Draft v0.1 — Subject to Revision*
