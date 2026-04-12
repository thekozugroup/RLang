# Connective Operators Reference

[Back to Dictionary Index](./README.md) | [Previous: Metadata](./08-metadata.md) | [Next: Evidence System](./10-evidence.md)

---

## Overview

Connectives wire expressions together in RLang. They define how data flows between operations. There are 9 connective operators organized into 5 categories.

**Grammar rule:**
```
connective = {
    "||>"   // fan-out (must be before |>)
    | "|>"  // sequential pipe
    | "<|"  // aggregate
    | "<@"  // memory retrieve
    | "~>"  // tentative
    | "!>"  // error channel
    | "?>"  // fallible
    | "@>"  // memory store
    | "->"  // transform
}
```

**Note:** `||>` must be parsed before `|>` to avoid the parser matching `|` + `|>` instead of `||>`.

---

## Sequential Connectives

### |> (Pipe)

**Name:** Pipe

**Semantics:** Passes the result of the left expression to the right expression as input. Sequential execution.

**Precedence:** Standard left-to-right

**Example:**
```rust
obs(logs) |> analyze() |> cause(bug, crash);
```

**When to use:** For linear data flow where each step depends on the previous.

**Alternatives:** Use `||>` when steps can run in parallel. Use `~>` when the step is exploratory and may be reverted.

---

### -> (Transform)

**Name:** Transform / Resolve

**Semantics:** Transforms or resolves the left expression into the right expression. Implies the left produces the right as a typed result.

**Precedence:** Standard left-to-right

**Example:**
```rust
resolve(ev) -> Ok(blf<0.70>);
enbl(fix, resolve(bug)) |> resolve(ev) -> Ok(ready);
```

**When to use:** For resolution steps, type transformations, and Result matching. Commonly used after `resolve()` to indicate the expected result type.

**Alternatives:** Use `|>` for simple data passing without type transformation.

---

## Parallel Connectives

### ||> (Fan-out)

**Name:** Fan-out

**Semantics:** Executes multiple branches in parallel. Each branch receives the same input and produces independent results.

**Precedence:** Standard left-to-right

**Example:**
```rust
decompose(goal) ||> [
    delegate(agent_a, subtask_1),
    delegate(agent_b, subtask_2),
    delegate(agent_c, subtask_3),
] <| synthesize(results);
```

**When to use:** For parallel task execution, concurrent delegation, or evaluating multiple hypotheses simultaneously.

**Alternatives:** Use `|>` for sequential execution. Use multiple separate pipe chains if the branches are truly independent.

---

### <| (Aggregate)

**Name:** Aggregate

**Semantics:** Merges multiple results into one. Collects outputs from parallel branches.

**Precedence:** Standard left-to-right

**Example:**
```rust
[result_a, result_b, result_c] <| synthesize(all_results);
```

**When to use:** After `||>` fan-out to collect and combine parallel results. For merging evidence from multiple sources.

**Alternatives:** Explicit array construction if aggregation logic is complex.

---

## Exploratory Connective

### ~> (Tentative)

**Name:** Tentative

**Semantics:** Exploratory step that can be reverted without cost. Marks a hypothesis or approach as provisional.

**Precedence:** Standard left-to-right

**Example:**
```rust
hypothesis ~> test(hypothesis) -> match {
    Ok(confirmed) => assert(confirmed),
    Err(_) => backtrack(hypothesis),
};
```

**When to use:** For hypothesis testing, provisional reasoning, or approaches that may need to be abandoned. Makes the exploratory nature explicit.

**Alternatives:** Use `|>` when the step is committed (not revertible). Use `?>` when there is a specific fallback.

---

## Error Connectives

### !> (Error Channel)

**Name:** Error Channel

**Semantics:** Routes errors to a handler. If the left expression produces an error, the right expression handles it. Successful results pass through.

**Precedence:** Standard left-to-right

**Example:**
```rust
execute(deploy) !> match {
    ToolFailure(e) => replan(deploy, e),
    Timeout => retry_with(deploy, extended_deadline),
    _ => escalate(deploy),
};
```

**When to use:** For structured error handling. When you need to match on specific error types and handle each differently.

**Alternatives:** Use `?>` for simple try-or-fallback. Use `match` on a Result for inline error handling.

---

### ?> (Fallible)

**Name:** Fallible

**Semantics:** Try the left expression; on failure, try the right expression. Like Rust's `?` operator combined with a fallback.

**Precedence:** Standard left-to-right

**Example:**
```rust
inv(primary_api, request) ?> inv(backup_api, request);
rcl("cache") ?> inv(database, query);
```

**When to use:** For simple fallback chains where you want to try alternatives in order. When you do not need to match on specific error types.

**Alternatives:** Use `!>` when you need error-type-specific handling. Use `match` on a Result for complex branching.

---

## Memory Connectives

### @> (Store)

**Name:** Store

**Semantics:** Pipes the result of the left expression into memory storage. The value is written to the specified memory key.

**Precedence:** Standard left-to-right

**Example:**
```rust
obs(user_preference) @> rmb("prefs", Semantic);
inv(api, request) |> process(result) @> rmb("cache", Working);
```

**When to use:** For persisting results to memory during a pipeline. When you want to save intermediate or final results for later retrieval.

**Alternatives:** Explicit `rmb()` call as a separate statement.

---

### <@ (Retrieve)

**Name:** Retrieve

**Semantics:** Pulls data from memory into the pipeline. The retrieved value becomes the input for subsequent operations.

**Precedence:** Standard left-to-right

**Example:**
```rust
rcl("prefs", Semantic) <@ |> apply_to(response);
rcl("previous_attempt") <@ |> sim(current_approach, recalled);
```

**When to use:** For incorporating stored knowledge into the current reasoning pipeline. When you need to recall previously memorized data.

**Alternatives:** Explicit `rcl()` call as a separate let binding.

---

## Connective Summary Table

| Symbol | Name | Category | Purpose | Common pairing |
|--------|------|----------|---------|----------------|
| `\|>` | Pipe | Sequential | Pass result to next | Most operators |
| `->` | Transform | Sequential | Resolve/transform | `resolve()`, Result types |
| `\|\|>` | Fan-out | Parallel | Execute in parallel | `<\|` for aggregation |
| `<\|` | Aggregate | Parallel | Merge results | `\|\|>` for fan-out |
| `~>` | Tentative | Exploratory | Revertible step | `bt()` for backtrack |
| `!>` | Error Channel | Error | Route errors | `match` on error types |
| `?>` | Fallible | Error | Try-or-fallback | Fallback chains |
| `@>` | Store | Memory | Write to memory | `rmb()` |
| `<@` | Retrieve | Memory | Read from memory | `rcl()` |

---

## Pipe Chain Grammar

A pipe chain is one or more primary expressions connected by connectives:

```
pipe_chain = { primary_expr ~ (connective ~ primary_expr?)+ }
```

The `primary_expr?` is optional for connectives like `<@` that may not need a right-hand operand.

**Complex example combining multiple connectives:**
```rust
obs(logs)                          // Observe logs
    |> analyze()                   // Sequential: analyze
    |> cause(bug, crash)           // Sequential: identify cause
    ~> hypothesis(fix)             // Tentative: propose fix
    |> inv(test_suite, fix)        // Sequential: test fix
    !> bt(reflection)              // Error: backtrack on failure
    -> Ok(verified_fix)            // Transform: resolve to success
    @> rmb("fix_history", Episodic); // Store: remember the fix
```

---

*Next: [Evidence System Reference](./10-evidence.md)*
