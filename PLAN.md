# FaultForge Plan

Transform fault reproduction from manual/configured experiments into symptom-guided fault-recipe synthesis for distributed systems.

## Guiding Principles

- Simple first, expand only when needed
- Best practices over clever architecture
- No backward compatibility baggage
- One path end-to-end before adding more
- Fail-slow is the first major evaluation class

## Architecture

```text
                 production issue / oracle
                           │
                           ▼
                 faultforge/ (Python)
                 search │ oracle │ minimize
                    │              │
                    ▼              ▼
        xinda/                anduril/
        environmental         Java in-process
        slow-fault provider   static analysis + TraceAgent
```

## Phase 1: Baseline

### PR 1: Adopt Anduril Baseline

- [x] Move Anduril to `anduril/` subdirectory
- [x] Clean .gitignore
- [x] Project README with fork direction
- [x] Preserve upstream docs as README-Anduril.md

### PR 2: Integrate Xinda and Initialize FaultForge

- [x] Remove `xinda/.git/`, vendored under `xinda/`
- [x] Remove old `env-anduril/` Go-first framing
- [x] Init root `uv` project
- [x] Add `faultforge/` package with recipe schema
- [x] Configure `ruff` + `ty`
- [x] Update docs around FaultForge architecture

## Phase 2: Xinda SDK

### PR 3: Package Xinda As A uv SDK

- [x] Add `xinda/pyproject.toml` targeting Python `>=3.12`
- [x] Add `xinda/README.md`
- [x] Add `xinda/xinda/__init__.py` with version
- [x] Make `uv sync --project xinda` work
- [x] Add local editable dependency from root FaultForge
- [x] Configure `ruff` + `ty` for Xinda (legacy code excluded, SDK boundary checked)
- [x] Update docs

### PR 4: Add Typed Xinda SDK Surface

- [ ] Add `xinda/xinda/sdk.py`
- [ ] Add typed models: `XindaTrialConfig`, `XindaTrialResult`, `SlowFaultConfig`, `BenchmarkConfig`, `SystemConfig`
- [ ] `run_trial(config)` callable SDK function
- [ ] Keep CLI/script behavior secondary

### PR 5: Refactor Xinda Configs

- [ ] Modernize `xinda/xinda/configs/`
- [ ] Replace `SlowFault` with typed config model
- [ ] Normalize field names
- [ ] Remove dead compatibility paths

### PR 6: Refactor Xinda Runner Flow

- [ ] Extract `main.py` orchestration into `xinda/xinda/runner.py`
- [ ] CLI becomes a thin wrapper around `runner.run_trial`
- [ ] Preserve setup → workload → inject → collect → cleanup order

### PR 7: Refactor Xinda System Layer

- [ ] Modernize `TestSystem.py` into a typed base class/module
- [ ] Keep Docker, Blockade, CharybdeFS behavior
- [ ] Rename only where it improves clarity

### PR 8: Make Xinda Package Pass Full ruff/ty

- [ ] Expand checks to all maintained Xinda SDK code
- [ ] Remove broad ignores for modernized Xinda modules
- [ ] Keep exclusions only for generated/data-analysis/legacy scripts

### PR 9: Xinda Trial Runner (FaultForge)

- [ ] Add `faultforge/xinda_runner.py`
- [ ] Wrap Xinda SDK for single-trial execution
- [ ] Pass recipe fault config to Xinda
- [ ] Collect logs/stats output
- [ ] Clean up cluster after trial

### PR 4: First Xinda Case (ZooKeeper)

- [ ] Add Docker Compose ZooKeeper case
- [ ] Configure Xinda for ZK network delay
- [ ] Run single trial end-to-end
- [ ] Verify log/stat collection

## Phase 3: Oracle and Search

### PR 10: First Xinda Case (ZooKeeper)

- [ ] Add Docker Compose ZooKeeper case
- [ ] Configure Xinda for ZK network delay
- [ ] Run single trial end-to-end
- [ ] Verify log/stat collection

### PR 11: Symptom Oracle

- [ ] Add `faultforge/oracle.py`
- [ ] Initial signal types: log patterns, latency thresholds, error counts
- [ ] Score trial output against target symptom
- [ ] Output: `symptom_score`, `matched_signals`, `success`

### PR 12: Bounded Search Loop

- [ ] Add `faultforge/search.py`
- [ ] Search over: node, fault model, magnitude, timing
- [ ] Grid or beam search, simple first
- [ ] Input: search space + oracle config
- [ ] Output: ranked recipes

## Phase 4: Minimization

### PR 13: Recipe Minimizer

- [ ] Add `faultforge/minimizer.py`
- [ ] Greedy reduce: magnitude, duration, fault count
- [ ] Keep recipe if oracle score stays above threshold
- [ ] Output minimal recipe

## Phase 5: Anduril Integration

### PR 14: Anduril Java Provider

- [ ] Add `faultforge/anduril_runner.py`
- [ ] Map recipe faults to Anduril injection points
- [ ] Run Anduril trial with recipe config
- [ ] Collect trial output

### PR 15: Multi-Provider Trial

- [ ] Coordinate Xinda + Anduril faults in one trial
- [ ] Apply environmental faults first
- [ ] Activate in-process faults from recipe
- [ ] Clear all faults deterministically

## Phase 6: Evaluation

### PR 16: First Fail-Slow Case

- [ ] Define ZOOKEEPER-2251 or compatible case
- [ ] Oracle config for target symptom
- [ ] Search space definition
- [ ] Run search, find reproducing recipe

### PR 17: Evaluation Harness

- [ ] Compare: Xinda baseline, random search, FaultForge
- [ ] Run across exception bugs and fail-slow cases
- [ ] Measure: trials to reproduce, recipe quality
- [ ] Generate comparison report

## File Layout

```text
faultforge/
  __init__.py
  recipe.py
  xinda_runner.py
  oracle.py
  search.py
  minimizer.py

xinda/               # vendored Xinda source
anduril/             # vendored Anduril source

PLAN.md
README.md
README-Xinda.md
README-Anduril.md
BUILD.md
pyproject.toml
uv.lock
```

## What We Keep From Prior Systems

- Xinda: environmental faults, cluster lifecycle, benchmarks, data collection
- Anduril: static analysis, instrumentation, feedback-guided search, trial records

## What We Add

- Symptom oracle with scoring
- Recipe schema for multi-fault trials
- Search over fault parameters
- Recipe minimization
- Multi-provider coordination

## Risks

- Over-engineering abstractions before concrete integrations
- Trying to support too many fault classes at once
- Breaking existing Anduril/Xinda cases before new path works

## Mitigations

- Build concrete wrappers first, extract interfaces later
- Add one fault class at a time
- Keep existing cases working until new path is proven
