# Complete Examples

[Back to Dictionary Index](./README.md) | [Previous: Grammar](./13-grammar.md)

---

## Overview

Five fully annotated RLang traces demonstrating different reasoning scenarios. Each example includes the English question, the complete RLang trace with inline comments, the rendered English output, and a token comparison.

---

## Example 1: Simple Belief Resolution (Weather Observation)

### English Question

"Is it going to rain? I see dark clouds and the sensor says it's raining."

### RLang Trace

```rust
// Phase 1: Frame the problem -- establish what we observe
#[phase(Frame)]
{
    // Direct observation from a rain sensor -- high confidence, local scope
    let rain: blf<0.95> = obs(rain)
        | p:0.95 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
}

// Phase 2: Explore evidence -- gather and weigh supporting data
#[phase(Explore)]
{
    // Dark clouds support the rain claim with a small positive delta
    let ev = [
        obs(dark_clouds) => sup(rain, +0.05),
    ];
    // Resolve evidence: base 0.95 + 0.05 = effectively confirmed
    rain |> resolve(ev) -> Ok(confirmed);
}

// Phase 3: Verify -- check that our observation holds
#[phase(Verify)]
{
    // Require that the rain observation is backed by sensor data
    req(rain, obs(rain)) |> verify(rain) -> Ok(());
}

// Phase 4: Decide -- commit to our conclusion
#[phase(Decide)]
{
    // Branch on confidence: very high -> assert
    match conf(rain) {
        c if c > 0.85 => assert(rain),
        _ => hedge(rain),
    }
}
```

### Rendered English Output

"Based on direct sensor observation (confidence 0.95) supported by visible dark clouds, it is raining. High confidence -- assertion committed."

### Token Comparison

| Format | Tokens | Ratio |
|--------|--------|-------|
| English CoT | ~120 | 1.0x |
| RLang | ~40 | 3.0x compression |

---

## Example 2: Deployment Decision (Canonical Example)

### English Question

"Should we deploy the bug fix to production? Tests are passing, but there's no rollback plan and traffic is low."

### RLang Trace

```rust
// Phase 1: Frame -- gather all relevant observations
#[phase(Frame)]
impl Deductive {
    // CI pipeline confirms tests pass -- near-certain, direct observation
    let tests: blf<0.99> = obs(tests_pass)
        | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    // Infrastructure check reveals no rollback plan -- this is a risk
    let risk: blf<0.85> = obs(no_rollback)
        | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
    // Monitoring shows low traffic -- favorable for deployment
    let traffic: blf<0.90> = obs(low_traffic)
        | p:0.90 | ep:direct | src:obs(metrics) | scope:loc | t:fresh;
}

// Phase 2: Explore -- evaluate evidence for and against deployment
#[phase(Explore)]
{
    // Build evidence block: tests support, risk weakens, traffic supports
    let ev = [
        tests   => sup(deploy, +0.15),    // Tests passing: moderate support
        risk    => wkn(deploy, -0.25),     // No rollback: significant weakening
        traffic => sup(deploy, +0.10),     // Low traffic: mild support
    ];
    // Resolve: net evidence determines deployment confidence
    deploy |> resolve(ev) -> Ok(ready);
}

// Phase 3: Verify -- check that requirements are met
#[phase(Verify)]
{
    // Ensure deployment depends on passing tests (constraint check)
    req(tests, obs(tests_pass)) |> verify(deploy) -> Ok(());
}

// Phase 4: Decide -- branch on resolved confidence
#[phase(Decide)]
{
    match conf(deploy) {
        // High confidence: commit fully
        c if c > 0.80 => assert(deploy),
        // Moderate confidence: conditional commitment
        c if c > 0.50 => hedge(deploy),
        // Low confidence: hold off
        _ => suspend(deploy),
    }
}
```

### Rendered English Output

"Tests pass and traffic is low, but the lack of a rollback plan significantly weakens the case. Recommend conditional deployment (hedge) -- proceed only with a rollback plan in place."

### Token Comparison

| Format | Tokens | Ratio |
|--------|--------|-------|
| English CoT | ~300 | 1.0x |
| RLang | ~80 | 3.75x compression |

---

## Example 3: Agent Delegation with Trust Check

### English Question

"Can we delegate post-deployment monitoring to Agent-B? Is Agent-B trustworthy enough?"

### RLang Trace

```rust
// Phase 1: Frame -- identify the monitoring need and candidate agent
#[phase(Frame)]
impl Deductive {
    // Define the monitoring goal
    let monitor_goal: goal<Monitor> = goal(self, monitor(deployment))
        | priority:normal | deadline:within(24h);

    // Observe deployment is happening
    let deploy_status: blf<0.90> = obs(deployment_active)
        | p:0.90 | ep:direct | src:obs(deploy_pipeline) | t:fresh;
}

// Phase 2: Explore -- discover agents and evaluate trust
#[phase(Explore)]
{
    // Discover agents with monitoring capability
    let agent_b: AgentCard = discover("monitoring")
        |> match_capability(monitor_goal);

    // Evaluate trust from four sources (FIRE model)
    // Direct interaction history: 0.85
    // Role-based trust: 0.80
    // Witness reports: 0.78
    // Certified credentials: 0.90
    let trust_b: f64 = trust_score(&agent_b.id);
    // trust_b = 0.82 (weighted average)

    // Define the delegation contract
    let monitor_contract = Contract {
        input_spec: "deploy_id, health_endpoint",
        output_spec: "alert_on_failure",
        required_skills: ["health_check", "alerting"],
        resources: ResourceBudget { wall_time: "24h", api_calls: 100 },
        success: "no_alerts_24h OR alert_handled",
        termination: "24h_elapsed OR deploy_rolled_back",
        mode: Balanced,
    };
}

// Phase 3: Verify -- confirm trust meets threshold
#[phase(Verify)]
{
    // Trust threshold for monitoring tasks: 0.6
    req(monitor_goal, trust_b >= 0.6) |> verify(trust_b) -> Ok(());

    // Verify resource conservation: monitoring budget fits within total budget
    let total_budget = self.intent.resources;
    req(monitor_contract.resources <= total_budget) |> verify(budget) -> Ok(());
}

// Phase 4: Decide -- delegate if trust check passes
#[phase(Decide)]
{
    // Trust is 0.82 > 0.6 threshold: safe to delegate
    assert(monitor_goal);

    // Execute delegation with contract
    dlg(agent_b.id, monitor_goal, monitor_contract)
        -> Ok(task_id: "mon-001");

    // Set up monitoring of the delegated task
    subscribe(task_id, "status_changes");

    emit(Delegation {
        to: agent_b.id,
        task: "mon-001",
        trust: 0.82,
        contract: monitor_contract,
    });
}
```

### Rendered English Output

"Agent-B has monitoring capabilities and a trust score of 0.82, which exceeds the 0.6 threshold. Delegating 24-hour post-deployment monitoring under a balanced contract. Subscribed to status updates."

### Token Comparison

| Format | Tokens | Ratio |
|--------|--------|-------|
| English CoT | ~350 | 1.0x |
| RLang | ~110 | 3.2x compression |

---

## Example 4: Multi-Step Goal Decomposition

### English Question

"We need to migrate the database from v1 to v2. What are the steps and how should we prioritize them?"

### RLang Trace

```rust
// Phase 1: Frame -- define the migration goal and constraints
#[phase(Frame)]
impl Deductive {
    // The top-level migration goal
    let migrate_goal: goal<Migration> = goal(self, migrate(database, v1, v2))
        | priority:high | deadline:within(8h)
        | success:obs(v2_schema_active);

    // Observe current state
    let current: blf<0.99> = obs(v1_schema_active)
        | p:0.99 | ep:direct | src:obs(db_status) | t:fresh;
    let data_size: blf<0.95> = obs(data_volume_50gb)
        | p:0.95 | ep:direct | src:obs(db_metrics) | t:fresh;

    // Key constraint: zero downtime required
    req(migrate_goal, obs(zero_downtime));
}

// Phase 2: Explore -- decompose and prioritize
#[phase(Explore)]
{
    // Decompose migration into ordered subgoals
    let subgoals = dcmp(migrate_goal, [
        goal(self, create_backup)         | priority:critical | deadline:within(1h),
        goal(self, create_v2_schema)      | priority:critical | deadline:within(30m),
        goal(self, migrate_data)          | priority:high     | deadline:within(4h) | req:[$0, $1],
        goal(self, validate_migration)    | priority:critical | deadline:within(1h) | req:[$2],
        goal(self, switch_traffic)        | priority:high     | deadline:within(30m) | req:[$3],
        goal(self, monitor_post_switch)   | priority:normal   | deadline:within(2h) | req:[$4],
    ]);

    // Prioritize by dependency order and criticality
    let ranked = prioritize(subgoals, [dependency_order, priority, deadline]);

    // Evaluate feasibility
    let ev = [
        data_size  => wkn(migrate_goal, -0.10),   // 50GB is large but manageable
        current    => sup(migrate_goal, +0.05),    // Current state is clean
    ];
    let feasibility = resolve(ev) -> Ok(blf<0.75>);
}

// Phase 3: Verify -- check constraints
#[phase(Verify)]
{
    // Verify zero-downtime constraint is achievable with this plan
    req(migrate_goal, obs(zero_downtime)) |> verify(subgoals) -> Ok(());

    // Verify total time fits within 8h deadline
    req(migrate_goal, total_time <= 8h) |> verify(ranked) -> Ok(());

    // Verify backup exists before any destructive operation
    req(migrate_data, obs(backup_complete)) |> verify(subgoals) -> Ok(());
}

// Phase 4: Decide -- commit to the plan
#[phase(Decide)]
{
    match conf(feasibility) {
        c if c > 0.60 => assert(migrate_goal),
        _ => suspend(migrate_goal),
    }

    // Select the plan for execution
    select(migrate_goal);

    emit(MigrationPlan {
        steps: ranked,
        total_estimate: "7h",
        risk: "moderate -- 50GB data volume",
        constraint: "zero downtime maintained via blue-green switch",
    });
}
```

### Rendered English Output

"Database migration from v1 to v2 is feasible (confidence 0.75). Plan: (1) backup [critical, 1h], (2) create v2 schema [critical, 30m], (3) migrate 50GB data [high, 4h], (4) validate [critical, 1h], (5) switch traffic [high, 30m], (6) monitor [normal, 2h]. Total estimate: 7h within 8h deadline. Zero downtime maintained via blue-green switching."

### Token Comparison

| Format | Tokens | Ratio |
|--------|--------|-------|
| English CoT | ~450 | 1.0x |
| RLang | ~130 | 3.5x compression |

---

## Example 5: Conflict Resolution Between Agents

### English Question

"Agent-A says the service is healthy but Agent-B says it's degraded. Who's right?"

### RLang Trace

```rust
// Phase 1: Frame -- establish the conflicting claims
#[phase(Frame)]
impl Deductive {
    // Agent-A's claim: service is healthy
    let claim_a: blf<0.80> = obs(service_healthy)
        | p:0.80 | ep:recv | src:agent(agent_a) | scope:loc | t:fresh;

    // Agent-B's claim: service is degraded
    let claim_b: blf<0.75> = obs(service_degraded)
        | p:0.75 | ep:recv | src:agent(agent_b) | scope:loc | t:fresh;

    // These claims conflict
    let conflict = confl(claim_a, claim_b)
        | p:0.95 | ep:direct;
}

// Phase 2: Explore -- gather independent evidence and evaluate trust
#[phase(Explore)]
{
    // Get independent observation
    let metrics: blf<0.90> = obs(response_time_elevated)
        | p:0.90 | ep:direct | src:obs(monitoring_dashboard) | t:fresh;

    // Evaluate trust for each agent
    let trust_a: f64 = trust_score(&agent_a);  // 0.78
    let trust_b: f64 = trust_score(&agent_b);  // 0.85 (monitoring specialist)

    // Build evidence for each position
    let ev_healthy = [
        claim_a => sup(service_healthy, +0.10),
    ];
    let ev_degraded = [
        claim_b          => sup(service_degraded, +0.12),
        metrics          => sup(service_degraded, +0.20),  // Independent evidence supports B
    ];

    let healthy_conf = resolve(ev_healthy) -> Ok(blf<0.55>);
    let degraded_conf = resolve(ev_degraded) -> Ok(blf<0.82>);

    // Attempt resolution by evidence weight
    let resolution = resolve_conflict(
        Conflict::Belief {
            agents: [agent_a, agent_b],
            claims: [(agent_a, "service_healthy"), (agent_b, "service_degraded")],
        },
        ConflictResolver::Evidence
    );
}

// Phase 3: Verify -- confirm the resolution
#[phase(Verify)]
{
    // Verify that independent evidence supports the resolution
    req(resolution, obs(response_time_elevated)) |> verify(metrics) -> Ok(());

    // Verify trust scores were considered
    req(trust_b > trust_a) |> verify(trust_scores) -> Ok(());
}

// Phase 4: Decide -- commit to resolution
#[phase(Decide)]
{
    match resolution {
        Resolved { outcome, justification } => assert(outcome),
        Deadlock { positions } => suspend(conflict),
        Escalated { to, context } => dlg(to, context),
    }

    // Inform both agents of the resolution
    inform(agent_a, resolution);
    inform(agent_b, resolution);

    emit(ConflictResolution {
        winner: agent_b,
        conclusion: "service_degraded",
        justification: "independent metrics confirm elevated response times; "
                      + "Agent-B has higher trust (0.85 vs 0.78) as monitoring specialist",
    });
}
```

### Rendered English Output

"Resolved in favor of Agent-B: the service is degraded. Independent monitoring confirms elevated response times, and Agent-B (trust 0.85, monitoring specialist) has higher trust than Agent-A (trust 0.78). Both agents informed of the resolution."

### Token Comparison

| Format | Tokens | Ratio |
|--------|--------|-------|
| English CoT | ~400 | 1.0x |
| RLang | ~120 | 3.3x compression |

---

## Summary of Token Savings

| Example | English Tokens | RLang Tokens | Compression |
|---------|---------------|-------------|-------------|
| 1. Weather observation | ~120 | ~40 | 3.0x |
| 2. Deployment decision | ~300 | ~80 | 3.75x |
| 3. Agent delegation | ~350 | ~110 | 3.2x |
| 4. Goal decomposition | ~450 | ~130 | 3.5x |
| 5. Conflict resolution | ~400 | ~120 | 3.3x |
| **Average** | **~324** | **~96** | **3.4x** |

The average compression ratio of 3.4x is consistent with the 3-5x range documented in the language specification, with every token in the RLang trace carrying semantic weight.

---

*[Back to Dictionary Index](./README.md)*
