# Language Overview

[Back to Dictionary Index](./README.md)

---

## What is RLang?

RLang is a strongly-typed, Rust-inspired reasoning language designed as the internal scratchpad for AI agents. It replaces natural language chain-of-thought (CoT) with structured, typed, verifiable reasoning traces.

**RLang is not a human conversation language.** It is a machine scratchpad built for correctness, density, and auditability.

### Key properties

- **3-5x token compression** over English reasoning traces
- **Structural error prevention** for 7 known reasoning failure modes
- **Complete agentic coverage** -- beliefs, goals, actions, inter-agent communication
- **Rust-proximate syntax** -- models trained on RLang internalize Rust correctness guarantees
- **Formal grammar** -- PEG-parseable, validator-checkable
- **A2A protocol alignment** -- native agent discovery, delegation, and task lifecycle

### What it replaces

English chain-of-thought traces where only 40-60% of tokens are productive. The remaining tokens are self-reflection markers ("Wait, let me reconsider..."), problem restatement, hedging, circular reasoning, and structural transitions. RLang eliminates all of these structurally.

---

## The 4-Layer Architecture

RLang organizes all reasoning into four composable layers. Each layer has its own types, operators, and validation rules. Higher layers reference lower ones.

```
+-------------------------------------------------------------------+
|  Layer 4: COMMUNICATIVE                                           |
|  How do I coordinate with other agents?                           |
|  Operators: dlg, msg, discover, negotiate, cfp, propose, ...     |
|  Types: CommAct, AgentCard, Contract, TrustModel, TaskState       |
+-------------------------------------------------------------------+
|  Layer 3: OPERATIONAL                                             |
|  What do I do in the world?                                       |
|  Operators: exec, inv, pcv, rmb, rcl, forget, bt, verify, ...    |
|  Types: Action, ObsFeed, Reflection, MemType                      |
+-------------------------------------------------------------------+
|  Layer 2: MOTIVATIONAL                                            |
|  What do I want to achieve?                                       |
|  Operators: dcmp, prioritize, select, replan                      |
|  Types: Goal, Intent, Desire, Plan, ResourceBudget                |
+-------------------------------------------------------------------+
|  Layer 1: EPISTEMIC                                               |
|  What do I know and how certain am I?                             |
|  Operators: cause, obs, sim, confl, sup, wkn, resolve, ...       |
|  Types: blf, Evidence, EpMode, Scope, Src, Freshness              |
+-------------------------------------------------------------------+
```

**Layer 1 (Epistemic)** is the foundation. It models beliefs with typed confidence, evidence provenance, temporal freshness, and epistemic mode. Every claim must be wrapped in a `blf` type.

**Layer 2 (Motivational)** builds on epistemic beliefs to model goals, desires, intentions, and plans. Goals have priority, deadlines, success criteria, and resource budgets. Draws from BDI (Belief-Desire-Intention) logic.

**Layer 3 (Operational)** models the Observe-Think-Act loop: actions, tool invocation, environmental feedback, memory operations, and bounded self-correction. Draws from ReAct, Reflexion, and Inner Monologue patterns.

**Layer 4 (Communicative)** models inter-agent messaging, task delegation, trust, and conflict resolution. Aligned with A2A Protocol v1.0 and grounded in FIPA-ACL speech act theory.

---

## The 4-Phase System

Every reasoning trace must pass through four phases in strict order. The parser enforces this structure. Skipping a phase or unbounded looping is a structural error.

```
Frame ──> Explore ──> Verify ──> Decide
                        |  ^
                        |  |  (bounded: max_rebloom, default 3)
                        +--+
```

| Phase | Purpose | Key Activities |
|-------|---------|----------------|
| **Frame** | Reformulate the problem | Extract constraints, identify context, declare goals, set up beliefs |
| **Explore** | Generate and evaluate | Decompose goals, evaluate evidence, discover agents, build plans |
| **Verify** | Check work | Test against constraints, validate requirements, bounded backtracking |
| **Decide** | Assert conclusions | Commit to actions via match/assert/hedge/suspend/reject, delegate, emit output |

### Phase transition rules

- `Frame -> Explore` -- mandatory, exactly once
- `Explore -> Verify` -- mandatory, exactly once
- `Verify -> Explore` -- allowed, bounded by `max_rebloom` (default: 3). This is the "rebloom" mechanism for iterative refinement.
- `Verify -> Decide` -- mandatory terminal transition
- `Decide -> _` -- no further transitions (terminal phase)

See [Phase System Reference](./02-phases.md) for complete details.

---

## Rust Alignment Principles

Every RLang construct mirrors a Rust concept. This is not cosmetic -- it ensures models trained on RLang internalize Rust's correctness guarantees.

| Rust Concept | RLang Equivalent | Purpose |
|-------------|------------------|---------|
| `enum` (sum types) | All operator results, task states, communicative acts | Exhaustive classification |
| `struct` | All compound types (beliefs, goals, contracts) | Structured data |
| `Result<T, E>` | All fallible operations return `Ok<T>` or `Err<E>` | Explicit error handling |
| `Option<T>` | Optional fields use `Some<T>` or `None` | No null values |
| `trait` / `impl` | Reasoning modes: `impl Deductive`, `impl Abductive`, `impl Analogical` | Constrained reasoning |
| `match` | All branching is exhaustive pattern matching | No silent fallthrough |
| Lifetimes (`'a`) | Information freshness: `'fresh`, `'stale`, `'unk` | Prevent stale-data reasoning |
| Ownership | Beliefs owned by trace; delegation transfers ownership | Clear data provenance |
| `#[derive]`, `#[cfg]` | `#[phase(Frame)]`, `#[bounded(3)]` | Parser-enforced structure |
| `mod` | Namespacing for domain-specific operator extensions | Modularity |

---

## How to Read RLang Traces

A minimal RLang trace has four phase blocks:

```rust
// Phase 1: Frame -- set up the problem
#[phase(Frame)]
impl Deductive {
    // Declare beliefs with typed confidence and metadata
    let rain: blf<0.95> = obs(rain) | p:0.95 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
}

// Phase 2: Explore -- evaluate evidence
#[phase(Explore)]
{
    // Build evidence block and resolve
    let ev = [obs(dark_clouds) => sup(rain, +0.05)];
    rain |> resolve(ev) -> Ok(confirmed);
}

// Phase 3: Verify -- check constraints
#[phase(Verify)]
{
    req(rain, obs(rain)) |> verify(rain) -> Ok(());
}

// Phase 4: Decide -- commit to conclusion
#[phase(Decide)]
{
    match conf(rain) {
        c if c > 0.85 => assert(rain),
        _ => hedge(rain),
    }
}
```

### Reading guide

1. **Phase attributes** (`#[phase(Frame)]`) mark the reasoning phase. The parser enforces ordering.
2. **`impl` blocks** optionally declare a reasoning mode (Deductive, Abductive, Analogical).
3. **`let` bindings** declare typed values with optional metadata after `|` separators.
4. **Operator calls** like `obs()`, `cause()`, `sup()` are the core vocabulary.
5. **Pipe chains** using `|>`, `->`, `~>` etc. wire expressions together.
6. **Evidence blocks** `[obs => sup(...)]` collect evidence for resolution.
7. **`match` expressions** in Decide phase branch on confidence, always using assert/hedge/suspend/reject.
8. **Metadata** after `|` provides confidence (`p:`), epistemic mode (`ep:`), source (`src:`), scope (`scope:`), and freshness (`t:`).

### Terminology

| Term | Meaning |
|------|---------|
| **Trace** | A complete reasoning record with all 4 phases |
| **Phase block** | One `#[phase(X)] { ... }` section |
| **Belief (blf)** | A typed claim with confidence, source, and freshness |
| **Evidence** | Supporting/weakening data for a belief |
| **Connective** | An operator that wires expressions together (`\|>`, `->`, etc.) |
| **Rebloom** | A bounded Verify-to-Explore transition for iterative refinement |
| **Assertion** | A terminal decision: assert, hedge, suspend, or reject |

---

*Next: [Phase System Reference](./02-phases.md)*
