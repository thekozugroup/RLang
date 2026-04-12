# Layer 3: Operational Operators

[Back to Dictionary Index](./README.md) | [Previous: Motivational Operators](./04-operators-motivational.md) | [Next: Communicative Operators](./06-operators-communicative.md)

---

## Overview

The operational layer models actions, tool use, environmental feedback, memory, and self-correction. It implements the Observe-Think-Act loop with bounded self-correction. Draws from ReAct, Reflexion, and Inner Monologue patterns.

There are 9 operational operators:

| Operator | Arity | Purpose |
|----------|-------|---------|
| `exec` | 1 | Execute a primitive operation |
| `inv` | 2 | Invoke an external tool |
| `pcv` | 1 | Perceive/observe the environment |
| `rmb` | 2 | Remember (store to memory) |
| `rcl` | 1 | Recall (retrieve from memory) |
| `forget` | 1 | Explicitly forget (free memory) |
| `bt` | 1 | Backtrack (bounded retry) |
| `verify` | 1 | Verify a result |
| `retry_with` | 2 | Retry with new data |

---

## exec

**Signature:** `exec(action)` -- unary (arity 1)

**Purpose:** Executes a primitive operation. Actions are not beliefs -- they change state rather than describing it. Returns `ActionResult<T>`.

**Category:** Action Execution

**Example:**
```rust
let result = exec(deploy_command) |> match {
    Ok(output) => obs(output),
    Err(e) => bt(Reflection { diagnosis: ToolFailure(deploy, e) }),
};
```

**Common patterns:**
- Always returns a typed result: `Ok(T)`, `Err(ActionErr)`, `Partial(T, remaining)`, `Timeout`, `Blocked(reason)`
- Chain with error handling: `exec(action) !> handle_error()`
- Pair with `verify()`: `exec(deploy) |> verify(health_check)`
- Used in Explore and Decide phases for action execution

---

## inv

**Signature:** `inv(tool, args)` -- binary (arity 2)

**Purpose:** Invokes an external tool with specified arguments. Tools are typed interfaces to the outside world (APIs, CLIs, databases).

**Category:** Tool Invocation

**Example:**
```rust
let api_result = inv(github_api, PullRequest { repo: "main", branch: "fix-123" })
    | p:0.90 | src:obs(api_response);
```

**Common patterns:**
- External interaction: `inv(database, query) -> Ok(rows)`
- Chain with observation: `inv(tool, args) |> obs(result) |> cause(result, next_step)`
- Error handling: `inv(api, request) !> match { Timeout => retry_with(...), _ => escalate(...) }`
- Track expected outcome: `inv(tool, args) | expected:0.85` for hypothesis testing

---

## pcv

**Signature:** `pcv(observation)` -- unary (arity 1)

**Purpose:** Perceives or observes the environment. The mandatory perception step before reasoning in the Observe-Think-Act loop.

**Category:** Perception

**Example:**
```rust
let env_state = pcv(system_metrics) | src:obs(monitoring) | t:fresh;
```

**Common patterns:**
- Start of every OTA loop iteration: `pcv(env) |> reason(obs, goal) |> exec(plan)`
- Feed into evidence: `pcv(new_data) |> sup(hypothesis, +0.10)`
- Environmental feedback: returns `ObsFeed<T>` with data, source, timestamp, and relevance

**Related types:**
- `ObsFeedExpr` -- structured feedback with data, source, timestamp, relevance
- `FeedSource` -- where feedback came from: Env, Tool, Agent, User

---

## rmb

**Signature:** `rmb(key, value)` -- binary (arity 2)

**Purpose:** Stores information in typed memory. Memory is categorized into four types for structured retrieval.

**Category:** Memory -- Store

**Example:**
```rust
rmb(user_preferences, prefs) | mem_type:semantic;

// In a pipe chain
obs(user_choice) @> rmb("choice_history", Episodic);
```

**Common patterns:**
- Store with connective: `result @> rmb("key", mem_type)`
- Pair with `rcl()`: `rmb("config", Semantic)` ... later ... `rcl("config", Semantic)`
- Memory types determine retrieval characteristics

**Memory types:**

| Type | Purpose | Example |
|------|---------|---------|
| `Episodic` | Specific past events and experiences | Previous deployment outcomes |
| `Semantic` | General knowledge and facts | API endpoint configurations |
| `Procedural` | How to do things (skills, plans) | Deployment procedures |
| `Working` | Current context / scratchpad | Active task state |

---

## rcl

**Signature:** `rcl(query)` -- unary (arity 1)

**Purpose:** Retrieves information from memory with relevance filtering. Returns (value, relevance_score) pairs.

**Category:** Memory -- Retrieve

**Example:**
```rust
let prev_deploys = rcl("deployment_history") | mem_type:episodic;

// In a pipe chain
rcl("user_prefs") <@ |> apply_to(response);
```

**Common patterns:**
- Retrieve with connective: `<@ rcl("key")`
- Chain with reasoning: `rcl("similar_case") |> sim(current_case, recalled_case)`
- Feed into evidence: `rcl("past_failure") |> wkn(risky_approach, -0.15)`

---

## forget

**Signature:** `forget(key)` -- unary (arity 1)

**Purpose:** Explicitly removes information from memory. Frees memory resources.

**Category:** Memory -- Delete

**Example:**
```rust
forget("temporary_context");
forget("stale_cache");
```

**Common patterns:**
- Cleanup after task completion: `exec(task) |> forget("working_state")`
- Replace stale data: `forget("old_config") |> rmb("config", new_config)`
- Resource management in long-running agents

---

## bt

**Signature:** `bt(reflection)` -- unary (arity 1)

**Purpose:** Initiates a bounded backtrack after a failure. Requires a structured `Reflection` with typed diagnosis -- not free-form text. Always bounded by `max_retries`.

**Category:** Self-Correction

**Example:**
```rust
let retry = bt(Reflection {
    attempt: deploy_attempt_1,
    outcome: Err("timeout"),
    diagnosis: ToolFailure(deploy_tool, "connection refused"),
    revision: Some(new_plan),
});
```

**Common patterns:**
- Triggered by action failure: `exec(action) !> bt(reflection)`
- Must provide `DiagnosisKind` -- prevents rumination (anti-pattern #6)
- Revision plan must differ from failed plan -- checked by validator
- Always bounded: `#[bounded(max_retries: 3)]`
- Chain with `replan()`: `bt(reflection) |> replan(intent, diagnosis)`

**DiagnosisKind variants:**

| Variant | Meaning |
|---------|---------|
| `WrongApproach(reason)` | Method was unsuitable |
| `MissingInfo(queries)` | Need more data |
| `ConstraintViolation(constraint)` | Broke a requirement |
| `ToolFailure(tool_id, error)` | External tool failed |
| `InsufficientEvidence` | Not enough evidence to conclude |
| `ConflictingEvidence(conflict_id)` | Evidence contradicts itself |

---

## verify

**Signature:** `verify(result)` -- unary (arity 1)

**Purpose:** Verifies that a result meets expected criteria. Central to the Verify phase.

**Category:** Verification

**Example:**
```rust
req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
req(trust_b >= 0.6) |> verify(trust_b) -> Ok(());
```

**Common patterns:**
- The primary operator in the Verify phase
- Chain with `req()`: `req(condition) |> verify(value) -> Ok(())`
- Failed verification triggers rebloom or backtrack
- Returns `Ok(())` for success, `Err(reason)` for failure

---

## retry_with

**Signature:** `retry_with(attempt, new_data)` -- binary (arity 2)

**Purpose:** Retries a failed attempt with new data or configuration. Unlike `bt()`, which requires a full reflection, `retry_with` is for simpler retries where the approach is correct but the data was insufficient.

**Category:** Self-Correction

**Example:**
```rust
// Missing info diagnosis -> gather data and retry
match failed.diagnosis {
    MissingInfo(queries) => {
        let data = queries |> rcl(Semantic);
        retry_with(failed.attempt, data)
    },
    Timeout => retry_with(deploy, extended_deadline),
}
```

**Common patterns:**
- Simpler than `bt()` for data-level retries
- Chain: `exec(action) !> retry_with(action, new_config)`
- Used within backtrack handlers: `bt(reflection) -> retry_with(attempt, data)`
- Still bounded by the enclosing `#[bounded]` attribute

---

*Next: [Communicative Operators](./06-operators-communicative.md)*
