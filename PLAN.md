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

### Xinda follow-on work

- [ ] Modernize `xinda/src/xinda/configs/` and align naming with **`trial.py`**
- [ ] Consolidate **`SlowFault`** usage so legacy YAML paths share one canonical model
- [ ] Extract **`main.py`** orchestration into `xinda/src/xinda/runner.py`; CLI is a thin `runner.run_trial` wrapper
- [ ] Modernize **`TestSystem`** into a typed base while preserving Docker / Blockade / CharybdeFS behavior
- [ ] Extend **`ruff` / `ty`** coverage to maintained Xinda SDK modules; tighten per-file excludes as code is ported

### FaultForge ⇄ Xinda execution

Implemented as **`faultforge/fault_provider/xinda.py`**: **`Xinda.run(recipe, system_config, benchmark_config)`** maps **`faultforge.recipe.Recipe`** and **`fault_provider.fault.SlowFault`** into Xinda **`Trial`** / **`XindaClient`**.

Search builds recipes (**`SearchConfig`** → **`recipe.Recipe`**) and calls **`FaultProvider.run`** directly (no standalone top-level **`xinda_runner`** module).

### First Xinda case (ZooKeeper compose)

- [ ] Add Docker Compose ZooKeeper workload
- [ ] Configure network delay faults for ZooKeeper topology
- [ ] Run single trial end-to-end with artifact collection verified

## Phase 3: Oracle and Search

### Symptom oracle

- [x] Add [`faultforge/oracle.py`](faultforge/src/faultforge/oracle.py) (**Phase 3 baseline**)
- [x] Initial signal types: **log-pattern** and **exit-code** YAML-driven oracles (**`Oracle.from_file`**)
- [ ] Extend signal types when needed (**latency thresholds, error aggregates**)
- [x] Score trial output → **`symptom_score`**, **`matched_signals`**, **`success`**

### Bounded search loop

- [x] Add [`faultforge/search.py`](faultforge/src/faultforge/search.py)
- [x] **Cartesian grid** over: node, fault model (**`SlowFaultKind`**), magnitude (ms delay), timing (**`SearchConfig`**)
- [x] **`SearchConfig`** materializes **`faultforge.recipe.Recipe`** with Xinda-aligned **`SlowFault`** payloads; traversal obeys **`SearchStrategy`** and **`max_trials`**
- [x] **`SearchStrategy`**: exhaustive, shuffled-with-seed, random-subset-with-seed (**`Searcher`** uses **`config.bounded_recipes()`** / strategy **`select_recipes`**)
- [ ] Directed search (**beam**, bandits, heuristic ordering) once grid-first path is gated on real workloads
- [x] **`Searcher(provider)`** → **`FaultProvider.run(recipe)`** once per bounded recipe slice → oracle on **first non-empty `log_path`**
- [x] Output: **`SearchResult`** sorted descending by **`symptom_score`** (recipe is source of truth; no standalone **`SearchParams`** layer)

### CLI

- [x] Click entrypoint **`faultforge`** (see **`pyproject.toml`** **`[project.scripts]`**) with **`faultforge search`** (**`faultforge/cli.py`**: **`--oracle`**, **`--issue-id`**, **`--max-trials`**, **`--strategy`**, **`--seed`**)

### Fault / provider layering (baseline)

- [x] **Fault models** (**`SlowFault`**, **`InProcessFault`**, discriminated **`Fault`**): [`faultforge/fault_provider/fault.py`](faultforge/src/faultforge/fault_provider/fault.py)
- [x] **`Recipe`** lives in [`faultforge/recipe.py`](faultforge/src/faultforge/recipe.py) (hooks for Phase 4 minimizer)
- [x] **`FaultProvider`** contract is **run-only** in [`faultforge/fault_provider/base.py`](faultforge/src/faultforge/fault_provider/base.py); **`Xinda`** / stub **`Anduril`** adapters do **not** import **`search`**

### Anduril provider (today)

[`faultforge/fault_provider/anduril.py`](faultforge/src/faultforge/fault_provider/anduril.py) validates **`InProcessFault`** recipes and returns **`ProviderRunResult`** with **`note="execution_not_implemented"`** until [**Phase 5**](#phase-5-anduril-integration) wires the Java tool.

## Phase 4: Minimization

### Recipe minimizer

- [ ] Add `faultforge/minimizer.py` (or submodule under **`faultforge/recipe`** when types grow)
- [ ] Consume / emit **`faultforge.recipe.Recipe`** (fault shapes via **`fault_provider.fault`**)
- [ ] Greedy reduce: magnitude, duration, fault count
- [ ] Keep recipe if oracle score stays above threshold
- [ ] Emit minimal **`Recipe`** for hand-off

## Phase 5: Anduril Integration

### Anduril Java Provider

- [ ] Replace **`Anduril.run`** stub paths with subprocess / JNI bridge to **`anduril/tool`**
- [ ] Map **`InProcessFault`** recipe entries to Anduril injection points
- [ ] Execute trials with structured logs / artifacts surfaced through **`ProviderRunResult`**

### Multi-Provider Trial

- [ ] Coordinate Xinda + Anduril faults in one trial
- [ ] Apply environmental faults first
- [ ] Activate in-process faults from the same **`Recipe`**
- [ ] Tear down faults deterministically

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
    cli.py                       # faultforge CLI (search subcommand)
    oracle.py
    recipe.py
    search.py                    # SearchConfig, SearchStrategy, Searcher, SearchResult
    fault_provider/
      __init__.py
      base.py                    # FaultProvider (run-only), ProviderRunResult
      fault.py
      xinda.py
      anduril.py                 # validates InProcessFault; Java bridge Phase 5
    minimizer.py                 # Phase 4

xinda/
  src/xinda/
    __init__.py
    client.py
    trial.py
    configs/
    systems/

anduril/
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
- **`faultforge/recipe.py`**: declarative **`Recipe`**
- **`fault_provider/`**: **`Fault`** schema + **`Xinda`/`Anduril`** run adapters
- **Search**: Cartesian **`SearchStrategy`**, oracle-ranked **`SearchResult`** list, **`faultforge search`**
- **`Oracle.configured_issue_id`** for tooling that loads issue YAML (`cli`, tests)
- Recipe minimization (Phase 4)
- Multi-provider coordination (Phase 5)

## Risks

- Over-engineering abstractions before concrete integrations
- Trying to support too many fault classes at once
- Breaking existing Anduril/Xinda cases before new path works

## Mitigations

- Build concrete wrappers first, extract interfaces later
- Add one fault class at a time
- Keep existing cases working until new path is proven
