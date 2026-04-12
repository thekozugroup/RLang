# Layer 2: Motivational Operators

[Back to Dictionary Index](./README.md) | [Previous: Epistemic Operators](./03-operators-epistemic.md) | [Next: Operational Operators](./05-operators-operational.md)

---

## Overview

The motivational layer models goals, desires, intentions, and plans. It builds on the epistemic layer (Layer 1) and draws from BDI (Belief-Desire-Intention) logic formalized by Rao & Georgeff (1995).

There are 4 motivational operators:

| Operator | Arity | Purpose |
|----------|-------|---------|
| `dcmp` | 2 | Decompose a goal into subgoals |
| `prioritize` | 2 | Rank goals by criteria |
| `select` | 1 | Select a goal for pursuit |
| `replan` | 2 | Revise a plan with reason |

---

## dcmp

**Signature:** `dcmp(goal, subgoals)` -- binary (arity 2)

**Purpose:** Decomposes a goal into an ordered list of subgoals. Mirrors the dominant Divide & Conquer pattern found in o1 research. Returns `Err` if the goal is atomic and cannot be decomposed further.

**Category:** Goal Decomposition

**Example:**
```rust
let subgoals = dcmp(deploy_goal, [
    goal(self, verify(tests_pass))     | priority:critical,
    goal(self, create(rollback_plan))  | priority:high,
    goal(self, execute(deploy_cmd))    | priority:high | req:[$0, $1],
    goal(self, verify(health_check))   | priority:critical | req:[$2],
]);
```

**Common patterns:**
- Hierarchical decomposition: break a complex goal into manageable subgoals
- Subgoals can reference each other with `req:[$index]` for dependency ordering
- Resource conservation law: sum of subgoal budgets must be <= parent budget
- Chain with `prioritize()`: `dcmp(goal, parts) |> prioritize(parts, criteria)`
- Nested decomposition via `SubPlan` step kind for recursive goals

**Related types:**
- `PlanExpr` -- the resulting plan with steps and dependencies
- `StepKind` -- each step can be Reason, Act, Delegate, Verify, Branch, or SubPlan
- `ResourceBudget` -- resource constraints that must satisfy conservation laws

---

## prioritize

**Signature:** `prioritize(goals, criteria)` -- binary (arity 2)

**Purpose:** Ranks a set of goals by specified criteria, producing an ordered list. Criteria can be priority level, deadline urgency, resource cost, or custom metrics.

**Category:** Goal Selection

**Example:**
```rust
let ranked = prioritize(
    [deploy_goal, monitor_goal, cleanup_goal],
    criteria: [priority, deadline, resource_cost]
);
```

**Common patterns:**
- Typically follows `dcmp()`: decompose then prioritize subgoals
- Feeds into `select()`: `prioritize(goals, criteria) |> select(top)`
- Use priority enum values: Critical, High, Normal, Low, Background
- Use deadline values: Urgent, By(timestamp), Within(duration), Flexible, None

**Priority levels:**

| Level | Meaning |
|-------|---------|
| `Critical` | Must be achieved, blocks everything else |
| `High` | Should be achieved soon |
| `Normal` | Standard priority |
| `Low` | Nice to have, do if resources permit |
| `Background` | Only if nothing else needs doing |

**Deadline levels:**

| Level | Meaning |
|-------|---------|
| `Urgent` | ASAP -- minimal reasoning budget |
| `By(timestamp)` | Hard deadline at specific time |
| `Within(duration)` | Relative deadline (e.g., `within(2h)`) |
| `Flexible` | No time pressure |
| `None` | No deadline |

---

## select

**Signature:** `select(goal)` -- unary (arity 1)

**Purpose:** Selects a goal for active pursuit, converting it from a desire/candidate into a committed intention. This is the BDI commitment point: once selected, the agent allocates resources and begins planning.

**Category:** Goal Commitment

**Example:**
```rust
let intent = select(deploy_goal) | priority:high | deadline:within(2h);
```

**Common patterns:**
- The transition from "want" to "will": `prioritize(goals, criteria) |> select(top)`
- Creates an intent from a goal: Intent = Goal + Plan + ResourceBudget
- Typically happens in Explore phase after evidence evaluation
- Only select goals that have sufficient evidence support

**Related types:**
- `GoalStatus` -- tracks goal lifecycle: Pending, Active, Achieved, Failed, Abandoned, Blocked
- `IntentExpr` -- the committed intent with goal, plan, resources, and progress

---

## replan

**Signature:** `replan(intent, reason)` -- binary (arity 2)

**Purpose:** Revises an existing plan after a failure or new information. The revised plan must differ structurally from the previous plan (enforced by the validator to prevent rumination).

**Category:** Plan Revision

**Example:**
```rust
let revised = replan(deploy_intent, "rollback plan missing") |> match {
    Ok(new_plan) => execute(new_plan),
    Err(e) => escalate(deploy_goal),
};
```

**Common patterns:**
- Triggered by `bt()` (backtrack) in the operational layer
- Anti-pattern prevention: prevents rumination (failure mode #6) by requiring novel strategies
- The validator checks that `revision.plan != previous.plan`
- Often used during rebloom (Verify -> Explore transitions)
- Chain: `bt(reflection) |> replan(intent, diagnosis) -> execute(new_plan)`

**Related types:**
- `DiagnosisKind` -- why the plan failed: WrongApproach, MissingInfo, ConstraintViolation, ToolFailure, InsufficientEvidence, ConflictingEvidence
- `PlanStatus` -- Draft, Ready, InProgress, Completed, Failed, Replanned

---

## Motivational Type Hierarchy

```
Desire<T>     -- What the agent wants (not committed)
    |
    v  (evaluate + select)
Goal<T>       -- What the agent will pursue (has criteria + bounds)
    |
    v  (plan + commit resources)
Intent<T>     -- What the agent is doing (has plan + budget + progress)
```

This progression models the BDI lifecycle: beliefs inform desires, desires are evaluated into goals, and goals with committed plans become intentions.

---

*Next: [Operational Operators](./05-operators-operational.md)*
