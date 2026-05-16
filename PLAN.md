# Slow-Anduril Plan

Transform Anduril from exception-only bug reproduction into a dual-plane feedback-guided fault reproduction framework for distributed systems.

## Guiding Principles

- Simple first, expand only when needed
- Best practices over clever architecture
- No backward compatibility baggage
- One path end-to-end before adding more
- Fail-slow is the primary motivating case

## Architecture

Two projects under one repo. **Multiple faults can be active simultaneously** across planes and nodes.

```text
┌─────────────────────────────────────┐
│         slow-anduril controller     │
│                                     │
│  oracle  │  search  │  minimize     │
└──────────┼──────────┼───────────────┘
           │          │
    ┌──────┘          └──────┐
    ▼                        ▼
┌──────────────┐    ┌──────────────────┐
│ anduril/     │    │ env-anduril/     │
│ (Java)       │    │ (Go)             │
│              │    │                  │
│ Soot +       │    │ node-local       │
│ TraceAgent   │    │ fault agent      │
│ in-process   │    │ (tc, cgroup, etc)│
│ faults       │    │ env faults       │
└──────────────┘    └──────────────────┘

Each trial can activate multiple faults concurrently:
  - 2 in-process delays on different sites
  - 1 network delay + 1 disk slowdown
  - 3 nodes with different fault types
  - etc.
```

## Phase 1: Baseline

### PR 1: Adopt Anduril Baseline

- [x] Move Anduril to repo root
- [x] Clean .gitignore
- [x] Project README with fork direction
- [x] Preserve upstream docs as README-Anduril.md

### PR 2: Baseline Build and Smoke Test

- [ ] Document build dependencies (Java, Maven, Soot)
- [ ] Add build script or Makefile target
- [ ] Try building one existing case (e.g. zookeeper-3006)
- [ ] Record blockers and environment requirements
- [ ] No conceptual changes yet

## Phase 2: Core Abstractions

### PR 3: Unified Recipe Schema

Define the minimum recipe structure that both planes consume. **A trial can contain multiple concurrent faults**:

```json
{
  "trial_id": "string",
  "faults": [
    {
      "fault_plane": "in_process | environmental",
      "fault_model": "string",
      "target": {
        "node": "string",
        "component": "string",
        "injection_id": "number (in_process only)"
      },
      "timing": {
        "occurrence": "number (in_process)",
        "phase": "string",
        "start_after_s": "number",
        "duration_s": "number"
      },
      "params": {
        "delay_ms": "number",
        "loss_pct": "number",
        "exception_class": "string (in_process)"
      }
    }
  ]
}
```

- [ ] Add `runtime/recipe/Recipe.java` data class
- [ ] Add `runtime/recipe/FaultSpec.java` data class
- [ ] Add `runtime/recipe/RecipeParser.java` to read from config
- [ ] Update `runtime/config/Config.java` to accept new fields
- [ ] Keep existing `flakyAgent.*` keys working for migration if useful, but new code uses recipe schema

### PR 4: Fault Operator Interface

Clean interface, no plugin framework, just a simple dispatch:

```java
interface FaultOperator {
    void apply(FaultSpec spec);
    void clear(FaultSpec spec);
}
```

- [ ] Add `runtime/fault/FaultOperator.java`
- [ ] Add `runtime/fault/FaultSpec.java`
- [ ] Add `runtime/fault/ExceptionFaultOperator.java` (wraps current Anduril behavior)
- [ ] Add `runtime/fault/FaultOperatorFactory.java` (simple switch, no reflection)
- [ ] Runtime applies all faults in a trial's recipe concurrently
- [ ] Cleanup guarantees all faults are cleared even if trial fails

### PR 5: Thread Delay Fault Operator

First new fault model. Simplest in-process change:

- [ ] Add `runtime/fault/ThreadDelayFaultOperator.java`
- [ ] Selected injection point sleeps instead of throws
- [ ] Config: `fault.delay.ms`, `fault.delay.occurrence`
- [ ] Trial output records: injection_id, delay_ms, occurrence, thread_name

## Phase 3: Environmental Plane

### PR 6: Node-Local Fault Agent (env-anduril)

Small Go binary that runs on each node/container:

- [ ] Add `env-anduril/cmd/agent/` main entry
- [ ] Agent receives commands: apply_fault, clear_fault, status
- [ ] Agent applies faults via OS commands (tc, cgroup, etc)
- [ ] Agent guarantees cleanup on exit
- [ ] Controller communicates via HTTP

### PR 7: Network Delay Operator

First environmental fault in env-anduril:

- [ ] Add `env-anduril/internal/fault/network_delay.go`
- [ ] Uses `tc qdisc add/del dev eth0 root netem delay Xms`
- [ ] Requires NET_ADMIN capability in containers
- [ ] Works with Docker Compose clusters

### PR 8: First Fail-Slow Case

ZOOKEEPER-2251 or compatible:

- [ ] Add `evaluation/zookeeper-2251/` case directory
- [ ] Define oracle: symptom, logs, metrics, events
- [ ] Define search space: fault types, nodes, magnitudes
- [ ] Define workload: sync-heavy, quorum stress
- [ ] Wire into existing driver loop

## Phase 4: Oracle and Search

### PR 9: Symptom Oracle Abstraction

Move beyond binary pass/fail:

- [ ] Add `oracle/Oracle.java` interface
- [ ] Add `oracle/OracleResult.java` with symptom_score, cause_score, matched_signals
- [ ] Port existing `feedback/cases/*` matchers to new oracle interface
- [ ] Add latency-based scoring for fail-slow cases

### PR 10: Feedback Search for Delay Parameters

Extend search beyond injection points:

- [ ] Search over delay magnitudes: 10, 50, 100, 250, 500ms
- [ ] Search over occurrence/timing
- [ ] Search over duration
- [ ] Keep existing feedback-guided prioritization for injection sites
- [ ] Add bounded search for environmental parameters

### PR 11: Recipe Minimizer

After finding a reproducing recipe, shrink it:

- [ ] Add `minimizer/Minimizer.java`
- [ ] Greedy reduction: duration, magnitude, occurrence
- [ ] Stop when symptom score drops below threshold
- [ ] Output minimal recipe

## Phase 5: Evaluation

### PR 12: Evaluation Harness

- [ ] Compare: original Anduril, random injection, Slow-Anduril
- [ ] Run across exception bugs and fail-slow cases
- [ ] Measure: trials to reproduce, recipe quality, false positive rate
- [ ] Generate comparison report

## File Layout (Target)

```text
anduril/               # Original Anduril Java codebase
  tool/
    analyzer/          # Soot static analysis
    runtime/
      recipe/          # NEW: Recipe.java, FaultSpec.java
      fault/           # NEW: FaultOperator interface + operators
      config/          # UPDATED: accept new fields
    driver/            # UPDATED: consume recipe schema
    feedback/          # (keep existing, port to oracle later)
    oracle/            # NEW: Oracle interface
    minimizer/         # NEW: recipe minimization
  evaluation/          # Per-case experiment harnesses
  experiment/          # Per-case oracle/check scripts
  ground_truth/        # Good/bad logs
  systems/             # System source trees
  java-default-parser/

env-anduril/           # Go environmental control plane
  cmd/
    agent/             # Node-local fault agent binary
    cli/               # CLI for manual fault injection
  internal/
    fault/             # Fault operators (network, disk, cpu, etc)
    server/            # HTTP/gRPC command handler
    recipe/            # Recipe parsing
  go.mod

PLAN.md                # This file
README.md              # Fork overview
README-Anduril.md      # Original docs
```

## What We Keep From Anduril

- Static analysis and instrumentation (Soot, TraceAgent)
- Feedback-guided trial selection
- Good/bad/trial log comparison
- Case organization (evaluation/, experiment/)
- Trial record format
- Reporter for results

## What We Replace

- Exception-only fault model -> pluggable fault operators
- Binary pass/fail -> quantitative symptom oracle
- Injection-point-only search -> multi-dimensional search
- No recipe format -> structured recipe JSON
- No minimization -> greedy recipe minimization

## What We Add

- Environmental fault plane (node-local agent)
- Thread delay fault operator
- Network delay fault operator
- Symptom oracle with scoring
- Recipe minimization
- Fail-slow case definitions

## Risks

- Over-engineering the fault operator abstraction
- Trying to support too many fault models at once
- Breaking existing Anduril cases before new ones work
- Complex distributed agent protocol

## Mitigations

- Start with ExceptionFaultOperator wrapping current behavior
- Add one new operator at a time
- Keep existing cases working until new path is proven
- Simple HTTP/local socket for agent communication
- No plugin framework, just a switch statement
