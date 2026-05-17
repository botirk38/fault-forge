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
- [x] Preserve upstream docs as README-Anduril.md (later removed)

### PR 2: Integrate Xinda and Initialize FaultForge

- [x] Remove `xinda/.git/`, vendored under `xinda/`
- [x] Remove old `env-anduril/` Go-first framing
- [x] Init root `uv` project
- [x] Add `faultforge/` uv package with oracle + search + **`fault_provider/`** backends
- [x] **Recipe / fault schema split**: **`faultforge/recipe.py`** (`Recipe`), **`faultforge/fault_provider/fault.py`** (fault unions)
- [x] Configure `ruff` + `ty`
- [x] Update docs (`AGENTS.md`, etc.) around FaultForge architecture

### PR 4: Migrate Anduril to Java 25

- [x] Update Anduril source to build under Java 25 / Temurin
- [x] Remove stale BUILD.md and README-Anduril.md

### PR 5: CI Workflow

- [x] Add `.github/workflows/ci.yml`
- [x] FaultForge lint + type-check + test jobs
- [x] Xinda lint + type-check + test jobs
- [x] Anduril Maven build job (Java 25)

## Phase 2: Xinda SDK

### PR 3: Package Xinda As A uv SDK

- [x] Add `xinda/pyproject.toml` targeting Python `>=3.12`
- [x] Add `xinda/README.md`
- [x] Add `xinda/xinda/__init__.py` with version
- [x] Make `uv sync --project xinda` work
- [x] Add local editable dependency from root FaultForge
- [x] Configure `ruff` + `ty` for Xinda (legacy code excluded, SDK boundary checked)
- [x] Update docs

### Typed Xinda SDK Surface

- [x] Add `xinda/src/xinda/trial.py` with typed dataclasses
- [x] Add typed models: `Trial`, `TrialResult`, `SlowFault`, `BenchmarkConfig`, `SystemConfig`, `ResourceLimit`, `TrialPaths`
- [x] Add `xinda/src/xinda/client.py` with `XindaClient.run(trial)` callable SDK
- [x] Add `xinda/src/xinda/systems/registry.py` with system dispatch for all 8 systems

### Refactor Xinda Configs (future)

- [ ] Modernize `xinda/src/xinda/configs/`
- [ ] Replace legacy `SlowFault` with typed config model
- [ ] Normalize field names
- [ ] Remove dead compatibility paths

### Refactor Xinda Runner Flow (future)

- [ ] Extract `main.py` orchestration into `xinda/src/xinda/runner.py`
- [ ] CLI becomes a thin wrapper around `runner.run_trial`
- [ ] Preserve setup → workload → inject → collect → cleanup order

### Refactor Xinda System Layer (future)

- [ ] Modernize `TestSystem.py` into a typed base class/module
- [ ] Keep Docker, Blockade, CharybdeFS behavior
- [ ] Rename only where it improves clarity

### Make Xinda Package Pass Full ruff/ty (future)

- [ ] Expand checks to all maintained Xinda SDK code
- [ ] Remove broad ignores for modernized Xinda modules
- [ ] Keep exclusions only for generated/data-analysis/legacy scripts

### FaultForge ⇄ Xinda execution (today)

Implemented as `faultforge/fault_provider/xinda.py`: **`Xinda.run(recipe, system_config, benchmark_config)`** maps `faultforge.recipe.Recipe` / `fault_provider.fault.SlowFault` into Xinda SDK `Trial`/`XindaClient`.

### Xinda Trial Runner in FaultForge (superseded)

- [x] **Superseded** by `fault_provider/xinda.py` + top-level **`faultforge/recipe.py`** pipeline (no separate `xinda_runner.py`; search builds recipes and calls providers directly).

### First Xinda Case — ZooKeeper (future)

- [ ] Add Docker Compose ZooKeeper case
- [ ] Configure Xinda for ZK network delay
- [ ] Run single trial end-to-end
- [ ] Verify log/stat collection

## Phase 3: Oracle and Search

### Symptom Oracle

- [x] Add [`faultforge/oracle.py`](faultforge/src/faultforge/oracle.py) (**Phase 3 baseline** present)
- [x] Initial signal types: **log-pattern** and **exit-code** YAML-driven oracles (`Oracle.from_file`)
- [ ] Extend signals: latency thresholds, error aggregates (explicitly deferred)
- [x] Score trial output → `symptom_score`, `matched_signals`, `success`

### Bounded Search Loop

- [x] Add [`faultforge/search.py`](faultforge/src/faultforge/search.py)
- [x] **Cartesian grid** over: node, fault model (`SlowFaultKind`), magnitude (ms delay), timing (`SearchConfig`)
- [x] `SearchConfig` builds **`faultforge.recipe.Recipe`** with Xinda-aligned **`SlowFault`** payloads; capped by **`max_trials`**
- [ ] Beam / smarter search strategies (explicitly deferred — grid-first)
- [x] Wired path: **`Searcher(provider)`** → `FaultProvider.run(recipe)` once per combo → oracle on **first non-empty `log_path`**
- [x] Output: **`SearchResult`** list sorted descending by **`symptom_score`** (recipe is source of truth; no standalone `SearchParams` type).

### Fault / provider layering (baseline)

- [x] **Fault models** (`SlowFault`, `InProcessFault`, discriminated **`Fault`**): [`faultforge/fault_provider/fault.py`](faultforge/src/faultforge/fault_provider/fault.py)
- [x] **`Recipe`** lives in [`faultforge/recipe.py`](faultforge/src/faultforge/recipe.py) (room for Phase 4 minimizer without pulling search into backends)
- [x] **`FaultProvider`** contract is **run-only** in [`faultforge/fault_provider/base.py`](faultforge/src/faultforge/fault_provider/base.py); concrete **`Xinda` / stub `Anduril`** adapters do not depend on **`search`** (no circular import with orchestration).

### Deferred / stubs

- [ ] **CLI** wrapping `Searcher` config + oracle path (planned)
- [ ] **`Anduril.run`** executes real Java tool (today returns stub **`ProviderRunResult`**)

## Phase 4: Minimization

### Recipe Minimizer

- [ ] Add `faultforge/minimizer.py` (or submodule under **`faultforge/recipe`** when types grow)
- [ ] Consume / emit **`faultforge.recipe.Recipe`** (imports fault shapes from **`fault_provider.fault`**)
- [ ] Greedy reduce: magnitude, duration, fault count
- [ ] Keep recipe if oracle score stays above threshold
- [ ] Output minimal recipe

## Phase 5: Anduril Integration

### Anduril Java Provider

- [ ] Wire real execution in [`faultforge/fault_provider/anduril.py`](faultforge/src/faultforge/fault_provider/anduril.py) (**stub exists** today)
- [ ] Map `InProcessFault` recipe entries to Anduril injection points
- [ ] Run Anduril trial with recipe config; collect structured output (**not** a separate top-level runner module unless ergonomics demand it).

### Multi-Provider Trial

- [ ] Coordinate Xinda + Anduril faults in one trial
- [ ] Apply environmental faults first
- [ ] Activate in-process faults from recipe
- [ ] Clear all faults deterministically

## Phase 6: Evaluation

### First Fail-Slow Case

- [ ] Define ZOOKEEPER-2251 or compatible case
- [ ] Oracle config for target symptom
- [ ] Search space definition
- [ ] Run search, find reproducing recipe

### Evaluation Harness

- [ ] Compare: Xinda baseline, random search, FaultForge
- [ ] Run across exception bugs and fail-slow cases
- [ ] Measure: trials to reproduce, recipe quality
- [ ] Generate comparison report

## File Layout

```text
faultforge/                     # FaultForge uv project (`faultforge-sdk`)
  pyproject.toml
  uv.lock
  src/faultforge/
    __init__.py
    oracle.py
    recipe.py                 # Recipe + future minimizer-related types
    search.py                 # SearchConfig, Searcher, SearchResult
    fault_provider/
      __init__.py
      base.py                # FaultProvider (run-only), ProviderRunResult
      fault.py               # SlowFault, InProcessFault, Fault discriminator
      xinda.py               # Xinda environmental adapter (SDK)
      anduril.py             # Anduril stub / future Java bridge
    minimizer.py             # Phase 4 (not created yet)

xinda/                  # vendored Xinda source + SDK
  src/xinda/
    __init__.py
    client.py
    trial.py
    configs/
    systems/

anduril/                # vendored Anduril source (Java 25)
  tool/
  evaluation/
  systems/

.github/workflows/ci.yml
PLAN.md
README.md
.python-version
```

## What We Keep From Prior Systems

- Xinda: environmental faults, cluster lifecycle, benchmarks, data collection
- Anduril: static analysis, instrumentation, feedback-guided search, trial records

## What We Add

- Symptom oracle with scoring (baseline log + exit-code)
- **`faultforge/recipe.py`**: declarative **`Recipe`** (extensible toward minimization)
- **`fault_provider/`**: **`Fault`** schema + **`Xinda`/`Anduril`** run adapters (`FaultProvider` protocol)
- **Search**: Cartesian grid enumeration + oracle-ranked results (`search.py`)
- Recipe minimization (Phase 4, not started)
- Multi-provider coordination (**Phase 5** future)

## Risks

- Over-engineering abstractions before concrete integrations
- Trying to support too many fault classes at once
- Breaking existing Anduril/Xinda cases before new path works

## Mitigations

- Build concrete wrappers first, extract interfaces later
- Add one fault class at a time
- Keep existing cases working until new path is proven
