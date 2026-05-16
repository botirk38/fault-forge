# Env-Anduril Plan

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
│         env-anduril controller      │
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

### PR 1: Repo Hygiene and Build Notes

- [x] Move Anduril to `anduril/` subdirectory
- [x] Init `env-anduril/` Go module
- [x] Update README with two-project structure
- [x] Add BUILD.md with build notes and known blockers
- [x] Update PLAN.md with composable PR plan

### PR 2: Baseline Build and Smoke Test

- [ ] Document build dependencies (Java, Maven, Soot)
- [ ] Add build script or Makefile target
- [ ] Try building one existing case (e.g. zookeeper-3006)
- [ ] Record blockers and environment requirements
- [ ] No conceptual changes yet

## Phase 2: Core Abstractions

### PR 3: Shared Recipe Schema

Define the minimum recipe structure that both planes consume. **A trial can contain multiple concurrent faults**:

```json
{
  "trial_id": "string",
  "faults": [
    {
      "id": "string",
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

- [ ] Add `env-anduril/internal/recipe/` with Go structs
- [ ] Add schema validation tests
- [ ] Add equivalent minimal Java model under `anduril/tool/runtime/recipe/` only if needed

### PR 4: Fault Operator Interface

Clean interface, no plugin framework, just a simple dispatch:

```java
interface FaultOperator {
    void apply(FaultSpec spec);
    void clear(FaultSpec spec);
}
```

- [ ] Add `anduril/tool/runtime/fault/FaultOperator.java`
- [ ] Add `anduril/tool/runtime/fault/FaultSpec.java`
- [ ] Add `anduril/tool/runtime/fault/ExceptionFaultOperator.java` (wraps current Anduril behavior)
- [ ] Add `anduril/tool/runtime/fault/FaultOperatorFactory.java` (simple switch, no reflection)
- [ ] Runtime applies all faults in a trial's recipe concurrently
- [ ] Cleanup guarantees all faults are cleared even if trial fails

### PR 5: Thread Delay Fault Operator

First new fault model. Simplest in-process change:

- [ ] Add `anduril/tool/runtime/fault/ThreadDelayFaultOperator.java`
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

### PR 8: Env-Anduril CLI

Thin CLI for manual fault injection:

- [ ] Add `env-anduril/cmd/cli/`
- [ ] Commands: `apply`, `clear`, `status`
- [ ] HTTP client only, no logic duplication

## Phase 4: Trial Runner and Oracle

### PR 9: Single-Node Trial Runner

Run one workload with one environmental recipe:

- [ ] Add minimal trial runner in Go
- [ ] Flow: load recipe → apply faults → run workload → collect output → clear faults → write result
- [ ] Keep workload command generic
- [ ] Cleanup runs even if workload fails or times out

### PR 10: Basic Symptom Oracle

Score trials instead of only running them:

- [ ] Add simple oracle config
- [ ] Initial signal types: `log_contains`, `exit_code`, `latency_threshold`
- [ ] Output: `symptom_score`, `matched_signals`, `success`

### PR 11: Bounded Search Loop

Automate search over recipe parameters:

- [ ] Simple search over: node, delay_ms, duration_ms
- [ ] Grid or beam search, not complex
- [ ] Input: search space YAML/JSON + workload command + oracle config
- [ ] Output: ranked recipes

## Phase 5: First Fail-Slow Case

### PR 12: ZooKeeper Environmental Case

First real fail-slow end-to-end case:

- [ ] Add Docker Compose ZooKeeper case under `env-anduril/examples/zookeeper/`
- [ ] Containers include `tc` and `NET_ADMIN`
- [ ] Add workload script
- [ ] Add oracle config for first target symptom
- [ ] Prefer one issue-derived case, likely `ZOOKEEPER-2251`

### PR 13: Recipe Minimizer

Convert a successful recipe into a minimal reproduction:

- [ ] Add minimizer in Go
- [ ] Greedy minimize: delay_ms, duration_ms, number of faults
- [ ] Keep recipe if oracle success remains above threshold
- [ ] Output minimal recipe

## Phase 6: Java Provider Integration

### PR 14: Anduril Java Provider Boundary

Connect Java in-process work cleanly without overhauling it:

- [ ] Add small adapter layer around existing Anduril runtime
- [ ] Define how Java in-process faults consume the shared recipe
- [ ] Do not rewrite analyzer yet
- [ ] Start with mapping: recipe fault → injection id → occurrence → operator

### PR 15: Java Thread Delay Operator

First in-process fail-slow fault:

- [ ] Add `thread_delay` operator in Java runtime
- [ ] When selected injection point fires, sleep instead of throw
- [ ] Record event: fault id, injection id, thread name, delay ms, occurrence

### PR 16: Multi-Fault Trial Support

Safely apply multiple simultaneous faults:

- [ ] Environmental plane applies multiple recipe faults
- [ ] Java plane applies matching in-process faults
- [ ] Trial runner coordinates lifecycle
- [ ] Cleanup is deterministic

## Phase 7: Evaluation

### PR 17: Evaluation Harness

Make experiments reproducible:

- [ ] Compare: original Anduril, random injection, Env-Anduril search
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
BUILD.md               # Build notes for both projects
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
