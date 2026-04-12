# RLang Language Dictionary

The definitive reference for every construct in the RLang reasoning language.

---

## Table of Contents

### Foundations

| # | Document | Description |
|---|----------|-------------|
| 01 | [Language Overview](./01-language-overview.md) | What RLang is, 4-layer architecture, 4-phase system, Rust alignment |
| 02 | [Phase System](./02-phases.md) | Frame, Explore, Verify, Decide -- transitions, constraints, rebloom |

### Operators by Layer

| # | Document | Layer | Operators |
|---|----------|-------|-----------|
| 03 | [Epistemic Operators](./03-operators-epistemic.md) | Layer 1 | cause, prvnt, enbl, req, obs, sim, confl, chng, cncl, cntns, isa, seq, goal, sup, wkn, neut, resolve, conf, decay, refresh |
| 04 | [Motivational Operators](./04-operators-motivational.md) | Layer 2 | dcmp, prioritize, select, replan |
| 05 | [Operational Operators](./05-operators-operational.md) | Layer 3 | exec, inv, pcv, rmb, rcl, forget, bt, verify, retry_with |
| 06 | [Communicative Operators](./06-operators-communicative.md) | Layer 4 | dlg, msg, discover, match_capability, negotiate, cancel, poll, subscribe, cfp, propose, accept_proposal, reject_proposal, inform, query_if, agree, refuse, resolve_conflict |

### Type System and Syntax

| # | Document | Description |
|---|----------|-------------|
| 07 | [Type System](./07-types.md) | Primitives, blf, goal, action, communicative, result, and collection types |
| 08 | [Metadata](./08-metadata.md) | p, ep, src, scope, t, priority, deadline, and extended fields |
| 09 | [Connectives](./09-connectives.md) | All 9 connective operators: pipe, transform, fan-out, aggregate, tentative, error, fallible, store, retrieve |

### Subsystems

| # | Document | Description |
|---|----------|-------------|
| 10 | [Evidence System](./10-evidence.md) | Evidence blocks, sup/wkn/neut, resolve, confidence branching |
| 11 | [Anti-Patterns](./11-anti-patterns.md) | 7 prevented failure modes with structural enforcement |
| 12 | [A2A Protocol Mapping](./12-a2a-mapping.md) | TaskState machine, Agent Cards, contracts, topologies |

### Reference

| # | Document | Description |
|---|----------|-------------|
| 13 | [Formal Grammar](./13-grammar.md) | Complete PEG grammar annotated with explanations |
| 14 | [Complete Examples](./14-examples.md) | 5 fully annotated RLang traces with English comparisons |

---

## How to Use This Dictionary

- **New to RLang?** Start with [Language Overview](./01-language-overview.md) and [Phase System](./02-phases.md).
- **Looking up an operator?** Find it in the appropriate layer document (03-06).
- **Writing a trace?** Use [Connectives](./09-connectives.md) and [Metadata](./08-metadata.md) as quick references.
- **Debugging a validation error?** Check [Anti-Patterns](./11-anti-patterns.md) for the error message.
- **Building multi-agent systems?** See [Communicative Operators](./06-operators-communicative.md) and [A2A Mapping](./12-a2a-mapping.md).

---

## Operator Quick Reference

| Operator | Layer | Arity | Purpose |
|----------|-------|-------|---------|
| `cause` | Epistemic | 2 | a causes b |
| `prvnt` | Epistemic | 2 | a prevents b |
| `enbl` | Epistemic | 2 | a enables b |
| `req` | Epistemic | 2 | a requires b |
| `obs` | Epistemic | 1 | observe x |
| `sim` | Epistemic | 2 | a is similar to b |
| `confl` | Epistemic | 2 | a conflicts with b |
| `chng` | Epistemic | 3 | x changes from a to b |
| `cncl` | Epistemic | 2 | cancel/negate x |
| `cntns` | Epistemic | 2 | a contains b |
| `isa` | Epistemic | 2 | a is a type of b |
| `seq` | Epistemic | variadic | temporal sequence |
| `goal` | Epistemic | 1 | declare a goal |
| `sup` | Epistemic | 2 | support (evidence +delta) |
| `wkn` | Epistemic | 2 | weaken (evidence -delta) |
| `neut` | Epistemic | 2 | neutral evidence |
| `resolve` | Epistemic | variadic | resolve evidence to confidence |
| `conf` | Epistemic | variadic | get confidence value |
| `decay` | Epistemic | variadic | reduce stale confidence |
| `refresh` | Epistemic | variadic | restore freshness |
| `dcmp` | Motivational | 2 | decompose goal into subgoals |
| `prioritize` | Motivational | 2 | rank goals by criteria |
| `select` | Motivational | 1 | select goal for pursuit |
| `replan` | Motivational | 2 | revise plan with reason |
| `exec` | Operational | 1 | execute an action |
| `inv` | Operational | 2 | invoke a tool |
| `pcv` | Operational | 1 | perceive/observe environment |
| `rmb` | Operational | 2 | remember (store to memory) |
| `rcl` | Operational | 1 | recall (retrieve from memory) |
| `forget` | Operational | 1 | explicitly forget |
| `bt` | Operational | 1 | backtrack (bounded retry) |
| `verify` | Operational | 1 | verify a result |
| `retry_with` | Operational | 2 | retry with new data |
| `dlg` | Communicative | 2 | delegate to agent |
| `msg` | Communicative | 2 | send message |
| `discover` | Communicative | 1 | discover agent by capability |
| `match_capability` | Communicative | 2 | match need to agent |
| `negotiate` | Communicative | 2 | negotiate terms |
| `cancel` | Communicative | 1 | cancel a task |
| `poll` | Communicative | 1 | poll task status |
| `subscribe` | Communicative | 2 | subscribe to updates |
| `cfp` | Communicative | 1 | call for proposals |
| `propose` | Communicative | 2 | propose to perform task |
| `accept_proposal` | Communicative | 1 | accept a proposal |
| `reject_proposal` | Communicative | 1 | reject a proposal |
| `inform` | Communicative | 2 | inform agent of fact |
| `query_if` | Communicative | 2 | ask agent about proposition |
| `agree` | Communicative | 1 | commit to action |
| `refuse` | Communicative | 1 | decline action |
| `resolve_conflict` | Communicative | 2 | resolve inter-agent conflict |

---

*RLang v0.2 -- Language Dictionary*
