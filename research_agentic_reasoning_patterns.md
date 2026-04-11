# Agentic Reasoning Patterns: Structural Analysis for RLang
## Research Synthesis — April 2026

---

## 1. The Seven Recurring Structural Patterns

From surveying the literature on agent reasoning (ReAct, Reflexion, Tree of Thoughts, Inner Monologue, BDI, Graph of Thoughts, Plan-and-Execute), seven distinct structural patterns emerge repeatedly. Each has a characteristic "shape" that could be formalized.

### Pattern 1: Observe-Think-Act (The Core Loop)

**Shape:** Cycle with mandatory observation intake before each action.

```
loop {
    o = perceive(env)
    t = reason(o, memory, goal)
    a = select_action(t, tools)
    r = execute(a)
    if goal_met(r) { break }
}
```

**Source:** ReAct (Yao et al. 2022), HuggingFace Agents Course, Oracle's Agent Loop architecture.

**Primitives:** `perceive`, `reason`, `select_action`, `execute`, `goal_met`
**Connectives:** sequential chaining within loop, conditional break

**RLang implication:** This is the outermost control structure. RLang currently has no loop primitive or action primitive — it reasons about beliefs but not about acting on the world.

---

### Pattern 2: Plan-Decompose-Execute-Verify

**Shape:** Tree-structured decomposition followed by sequential execution with verification gates.

```
plan = decompose(goal) -> [subgoal_1, subgoal_2, ..., subgoal_n]
for sg in plan {
    result = execute(sg)
    if !verify(result, sg) {
        replan(sg, result)
    }
}
verify(results, goal)
```

**Source:** Task decomposition literature (AI21, TDAG framework), Plan-and-Solve strategy, Hierarchical Goal Networks.

**Primitives:** `decompose`, `execute`, `verify`, `replan`
**Connectives:** sequential with conditional branching, tree expansion

**RLang implication:** RLang needs a `decompose` operator that takes a goal and returns ordered subgoals, plus a `verify` gate that checks execution results against expected outcomes.

---

### Pattern 3: Generate-Evaluate-Select (Branching Search)

**Shape:** Fan-out of candidate thoughts, scored, best selected or aggregated.

```
candidates = generate(state, n)
scored = [score(c) for c in candidates]
selected = select(scored, strategy)  // greedy, beam, sample
next_state = apply(selected)
```

**Source:** Tree of Thoughts (Yao et al. 2023), Graph of Thoughts (Besta et al. 2024), CoT-SC (Wang et al. 2022).

**Primitives:** `generate`, `score`, `select`, `apply`
**Connectives:** fan-out (one-to-many), reduce (many-to-one), apply

**Key structural insight from Besta et al.:** The topology matters. CoT is a chain (linear), ToT is a tree (branching + backtrack), GoT is a DAG (branching + aggregation + refinement). The formal operations are:
- **Generate:** Create new thought nodes from existing ones (1 -> N)
- **Aggregate:** Merge multiple thought nodes into one (N -> 1)
- **Refine:** Improve a thought node in-place (1 -> 1)
- **Score:** Evaluate a thought node (1 -> R)

**RLang implication:** RLang's current `resolve(ev)` is a primitive form of aggregate+score. But it lacks `generate` (producing multiple candidate beliefs) and explicit topology control.

---

### Pattern 4: Reflect-Critique-Revise (Self-Correction)

**Shape:** Post-hoc evaluation loop with memory accumulation.

```
result = attempt(task)
reflection = critique(result, goal, criteria)
if reflection.failed {
    memory.store(reflection)
    revised = revise(task, reflection, memory)
    result = attempt(revised)
}
```

**Source:** Reflexion (Shinn et al. 2023), "Failure Makes the Agent Stronger" (2025), Process Reward Models.

**Primitives:** `attempt`, `critique`, `revise`, `store`
**Connectives:** conditional retry, memory accumulation across attempts

**Key insight:** Reflexion stores *verbal* reflections, not weight updates. The agent's memory is a growing log of what went wrong and why. This is episodic, not parametric.

**RLang implication:** RLang has no error recovery or retry semantics. A failed `resolve` just returns `Err`. There is no mechanism to diagnose WHY it failed, store the diagnosis, and try again differently.

---

### Pattern 5: Retrieve-Evaluate-Integrate (Memory-Augmented Reasoning)

**Shape:** Pull from memory, filter by relevance, inject into reasoning context.

```
query = formulate(current_state, goal)
candidates = retrieve(memory, query)
relevant = filter(candidates, relevance_threshold)
context = integrate(relevant, current_state)
conclusion = reason(context)
```

**Source:** A-MEM (Agentic Memory, 2025), Context Engineering (Weaviate), RAG literature, Memory-Augmented Planning.

**Primitives:** `formulate`, `retrieve`, `filter`, `integrate`, `reason`
**Connectives:** pipeline (sequential transformation)

**Key insight:** Memory types matter structurally:
- **Episodic:** Specific past events (what happened)
- **Semantic:** General knowledge (what is true)
- **Procedural:** How to do things (skills/plans)
- **Working:** Current context window contents

Each type has different retrieval strategies (recency vs. importance vs. embedding similarity).

**RLang implication:** RLang's `src:<label>` and `t:<fresh|stale>` partially address this, but there is no explicit retrieval or relevance-filtering step. Beliefs appear but their provenance chain is implicit.

---

### Pattern 6: Goal-Subgoal Hierarchy (Recursive Decomposition)

**Shape:** Recursive tree where each node is either a primitive action or a further decomposable goal.

```
fn achieve(goal) {
    if is_primitive(goal) {
        return execute(goal)
    }
    subgoals = decompose(goal)
    for sg in subgoals {
        result = achieve(sg)  // recursive
        if result.failed {
            return replan_or_fail(goal, sg, result)
        }
    }
    return aggregate(results)
}
```

**Source:** Hierarchical Goal Networks, STEP Planner (2025), HTN planning tradition, Hierarchical RL.

**Primitives:** `is_primitive`, `decompose`, `execute`, `aggregate`, `replan_or_fail`
**Connectives:** recursion, conditional failure propagation

**RLang implication:** RLang is currently flat — there is no nesting of reasoning blocks or recursive goal structure. The spec would need a `goal` type that can contain sub-goals.

---

### Pattern 7: Inner Monologue (Feedback-Integrated Planning)

**Shape:** Interleaved planning with continuous environmental feedback injection.

```
plan = initial_plan(goal)
for step in plan {
    action = execute(step)
    feedback = [
        scene_description(env),
        success_detection(action),
        object_detection(env),
    ]
    if feedback.indicates_failure {
        plan = replan(goal, feedback, remaining_steps)
    }
}
```

**Source:** Google's Inner Monologue (Huang et al. 2022), DAVIS (Knowledge Graph-Powered Inner Monologue, 2024).

**Primitives:** `initial_plan`, `execute`, `scene_description`, `success_detection`, `replan`
**Connectives:** interleaved execution + perception, conditional replanning

**Key insight vs. SayCan:** Inner Monologue outperforms SayCan precisely because it incorporates feedback DURING execution rather than only planning upfront. The agent can self-propose alternative goals when the original is infeasible.

**RLang implication:** RLang has no concept of mid-reasoning environmental feedback. Beliefs are evaluated but the environment doesn't "push back."

---

## 2. Existing Formal Frameworks

### BDI Logic (Belief-Desire-Intention)

The oldest formal agent reasoning framework. Uses modal logic with three modalities:
- **B(p):** Agent believes p
- **D(p):** Agent desires p
- **I(p):** Agent intends p

Formal systems include:
- **BDICTL** (Rao & Georgeff): Combines modal logic with temporal logic CTL*
- **LORA** (Wooldridge): Extends BDICTL with action logic for multi-agent communication
- Key functions: `options: P(B) x P(I) -> P(D)` and `filter: P(B) x P(D) x P(I) -> P(I)`

**Relevance to RLang:** BDI separates epistemic state (belief) from motivational state (desire) from commitment state (intention). RLang currently only models beliefs. Adding `desire` (goals the agent wants to achieve) and `intent` (goals the agent has committed to pursuing) would make it a complete agent reasoning language rather than just an epistemic scratchpad.

### Formal-LLM (2024)

Uses finite automata to constrain LLM plan generation. Plans are generated under automaton supervision — each step must satisfy transition constraints. This prevents hallucinated plans that violate domain rules.

**Relevance to RLang:** Could inform a type-system approach where valid reasoning traces must conform to a grammar (PEG/EBNF), which is already an open question in your spec.

### CodeAgents (2025)

Reformulates all agent reasoning into typed pseudocode: roles, decomposition plans, tool invocations, feedback, and observations all become structured code. Supports error localization and automated evaluation.

**Relevance to RLang:** This is the closest existing work to what RLang is doing — but CodeAgents uses general pseudocode rather than a purpose-built reasoning language.

### AgentSpec (2026)

Defines enforcement rules as three-tuples: (triggering_event, predicates, enforcement_functions). Runtime traces are abstracted into Program Dependence Graphs for safety analysis.

### Graph of Thoughts Formalism (Besta et al. 2024)

Most rigorously formalized reasoning topology. Defines:
- A **thought** as a partial solution to a problem
- **Transformations** as operations on thoughts: Generate (T_G), Aggregate (T_A), Refine (T_R), Score (T_S)
- The reasoning process as a directed graph G = (V, E) where V = thoughts, E = dependencies
- Different topologies (chain, tree, graph) as restrictions on the allowed edge structures

---

## 3. Primitive Vocabulary for Agentic Reasoning

Across all patterns, these primitives recur. Organized by category:

### Perception
- `perceive(env)` — observe the environment
- `detect(condition)` — check for specific state
- `scene(env)` — get structured description

### Belief Management
- `assert(claim)` — commit to a belief
- `retract(claim)` — withdraw a belief
- `update(claim, evidence)` — revise confidence
- `decay(claim, factor)` — degrade stale belief

### Planning
- `decompose(goal) -> [subgoal]` — break down
- `prioritize([subgoal]) -> [subgoal]` — order by importance
- `select(candidates, strategy)` — pick best option
- `replan(goal, feedback)` — revise plan

### Execution
- `execute(action) -> result` — act on environment
- `invoke(tool, args) -> result` — call external tool
- `delegate(subgoal, agent)` — assign to sub-agent

### Evaluation
- `verify(result, expectation)` — check correctness
- `score(thought)` — rate quality
- `critique(result, criteria)` — structured assessment
- `compare(a, b)` — relative evaluation

### Memory
- `store(item, memory_type)` — persist
- `retrieve(query, memory_type)` — recall
- `forget(item)` — explicit removal
- `refresh(item, new_evidence)` — update stored belief

### Control Flow
- `loop { ... } until condition` — iterate
- `branch(condition, if_true, if_false)` — conditional
- `backtrack(to_state)` — undo and retry
- `escalate(problem)` — pass to higher authority

### Composition (Connectives)
- `|>` — sequential pipe (already in RLang)
- `||>` — parallel fan-out (generate multiple)
- `<|` — aggregate (merge multiple into one)
- `->` — transform/resolve (already in RLang)
- `~>` — tentative/exploratory step
- `!>` — error/failure channel
- `@>` — store to memory
- `<@` — retrieve from memory

---

## 4. What RLang Is Missing for Agentic Reasoning

Based on this analysis, the current RLang spec (v0.1) is a strong epistemic reasoning language but lacks the following for full agentic reasoning:

| Gap | Current State | Needed |
|-----|--------------|--------|
| **Action primitives** | No concept of acting on environment | `execute`, `invoke`, `delegate` |
| **Goal/Desire types** | Only `blf` (belief) | `goal<T>`, `intent<T>`, `desire<T>` |
| **Loop/cycle structure** | No iteration | `loop { observe; think; act } until done` |
| **Decomposition** | Flat reasoning | `decompose(goal) -> [subgoal]` |
| **Memory operations** | Only `src:` tag | `store`, `retrieve`, `forget`, `refresh` |
| **Error recovery** | `Err(reason)` but no retry | `backtrack`, `replan`, `retry_with(reflection)` |
| **Environmental feedback** | No perception | `perceive`, `detect`, feedback injection |
| **Branching search** | Single-path reasoning | `generate(n)`, fan-out, `select` |
| **Temporal reasoning** | `'fresh`/`'stale` only | Sequencing, before/after, deadlines |
| **Multi-agent** | Single agent only | `delegate`, `request`, `coordinate` |

---

## 5. Suggested Type Extensions for RLang v0.2

```rust
// Goal type — what the agent wants to achieve
type goal<T> = {
    target: T,
    priority: f32,       // 0.0-1.0
    deadline: lifetime,   // 'urgent, 'normal, 'background
    status: pending | active | achieved | failed | abandoned,
}

// Intent type — committed goal with plan
type intent<T> = {
    goal: goal<T>,
    plan: [step],
    progress: usize,     // current step index
}

// Action type — interaction with environment
type action<T> = {
    tool: tool_id,
    args: T,
    expected: blf<f32>,  // expected outcome
}

// Observation type — environmental feedback
type obs_feed<T> = {
    data: T,
    source: env | tool | agent,
    timestamp: lifetime,
}

// Reflection type — structured self-critique
type reflection = {
    attempt: trace_id,
    outcome: Ok<T> | Err<reason>,
    diagnosis: str,
    revision: option<plan>,
}
```

---

## 6. Sources

### Core Papers
- Yao et al. (2022) — ReAct: Synergizing Reasoning and Acting in Language Models — https://arxiv.org/abs/2210.03629
- Besta et al. (2024) — Demystifying Chains, Trees, and Graphs of Thoughts — https://arxiv.org/abs/2401.14295
- Shinn et al. (2023) — Reflexion: Language Agents with Verbal Reinforcement Learning
- Huang et al. (2022) — Inner Monologue: Embodied Reasoning through Planning with Language Models — https://innermonologue.github.io/
- Rao & Georgeff (1995) — BDI Agents: From Theory to Practice

### Surveys and Overviews
- Masterman et al. (2024) — The Landscape of Emerging AI Agent Architectures — https://arxiv.org/html/2404.11584v1
- HuggingFace Agents Course — https://huggingface.co/learn/agents-course/en/unit1/agent-steps-and-structure
- IBM — What is a ReAct Agent? — https://www.ibm.com/think/topics/react-agent
- IBM — What Is Agentic Reasoning? — https://www.ibm.com/think/topics/agentic-reasoning
- Oracle — The AI Agent Loop — https://blogs.oracle.com/developers/what-is-the-ai-agent-loop-the-core-architecture-behind-autonomous-ai-systems

### Formal Frameworks
- Formal-LLM (2024) — https://github.com/agiresearch/Formal-LLM
- CodeAgents (2025) — https://arxiv.org/html/2507.03254v1
- AgentSpec (2026) — https://cposkitt.github.io/files/publications/agentspec_llm_enforcement_icse26.pdf
- A-MEM: Agentic Memory (2025) — https://arxiv.org/abs/2502.12110

### Additional References
- AutoDSL (2024) — https://aclanthology.org/2024.acl-long.659.pdf
- TDAG Multi-Agent Framework — https://arxiv.org/html/2402.10178v2
- STEP Planner (2025) — https://arxiv.org/html/2506.21030
- Adaptive Graph of Thoughts (2025) — https://arxiv.org/html/2502.05078v1
- Reasoning Topology Matters (2025) — https://arxiv.org/html/2603.20730
