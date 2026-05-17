# FaultForge Plan

Transform fault reproduction from manual/configured experiments into symptom-guided fault-trial synthesis for distributed systems.

## Guiding Principles

- Simple first, expand only when needed
- Best practices over clever architecture
- No backward compatibility baggage — refactor aggressively
- One path end-to-end before adding more
- Fail-slow is the first major evaluation class

## Architecture

```text
                  production issue / oracle
                            │
                            ▼
                  faultforge/ (Python)
                  search │ oracle │ minimize
                            │
                            ▼
                  TrialRunner (integrated runtime)
                  systems/ configs/
```

## Phase 1: Baseline (Done)

- [x] Vendored Anduril and Xinda under monorepo
- [x] Initialized FaultForge uv package with oracle + search
- [x] Packaged Xinda as uv SDK with typed trial models
- [x] Added CI for FaultForge, Xinda, and Anduril build

## Phase 2: Integrated Runtime (Done)

- [x] Canonical `Trial` model with multi-fault support (`trial.py`)
- [x] `TrialRunner` executes trials directly (`runner.py`)
- [x] `SearchConfig` emits `Trial` objects; `Searcher` runs them
- [x] Refactored `systems/` from single-fault to `trial.faults`
- [x] Removed `fault_provider/`, `Recipe`, `InProcessFault`
- [x] Removed Anduril from active architecture and CI
- [x] Restored `xinda/` as reference copy for result comparison
- [x] All checks pass: ruff, format, ty, pytest (57 tests)

## Phase 3: CLI For Real Experiments

### CLI Flags

- [ ] Add `--system`, `--benchmark`, `--data-dir`
- [ ] Add `--nodes`, `--fault-models`, `--magnitudes-ms`, `--start-times-s`, `--durations-s`
- [ ] Add `--max-faults-per-trial`
- [ ] Add `--dry-run` to print planned trials without execution
- [ ] Add `--output` for JSONL results

### Output

- [ ] Structured output: trial index, trial id, faults, score, success, log path
- [ ] `--output results.jsonl` writes machine-readable results

## Phase 4: Experiment Configs

### First Fail-Slow Case

- [ ] Choose target system (etcd recommended)
- [ ] Define oracle YAML (exit-code + log-symptom)
- [ ] Define search space (nodes, fault models, magnitudes, timing)
- [ ] Run bounded search, find reproducing trial

### Experiment Harness

- [ ] Add `experiments/` directory with case configs
- [ ] Add comparison harness: Xinda baseline vs FaultForge
- [ ] Collect: command, trial config, log path, runtime, success/error
- [ ] Result schema: JSONL with issue id, trial id, faults, score, log path, elapsed time

## Phase 5: Minimization

### Trial Minimizer

- [ ] Add `faultforge/minimizer.py`
- [ ] Consume / emit `Trial` objects
- [ ] Greedy reduce: magnitude, duration, fault count
- [ ] Keep trial if oracle score stays above threshold
- [ ] Emit minimal `Trial` for hand-off

## Phase 6: Evaluation

### Comparison Report

- [ ] Compare: Xinda baseline, random search, FaultForge
- [ ] Run across exception bugs and fail-slow cases
- [ ] Measure: trials to reproduce, trial quality
- [ ] Generate comparison report

## File Layout

```text
fault-forge/
├── .github/workflows/ci.yml
├── faultforge/
│   ├── pyproject.toml
│   ├── uv.lock
│   └── src/faultforge/
│       ├── __init__.py
│       ├── cli.py
│       ├── oracle.py
│       ├── trial.py          # canonical Trial, SlowFault, configs
│       ├── runner.py         # TrialRunner
│       ├── search.py         # SearchConfig, Searcher, SearchResult
│       ├── systems/          # integrated runtime internals
│       └── configs/          # legacy runtime configs
├── xinda/                    # reference copy for comparison
├── README.md
└── PLAN.md
```

## What We Keep From Prior Systems

- Xinda: environmental faults, cluster lifecycle, benchmarks, data collection
- Anduril: kept in git history; removed from active architecture

## What We Add

- Symptom oracle with scoring (baseline log + exit-code)
- Canonical `Trial` model with multi-fault support
- `TrialRunner`: direct trial execution boundary
- Search: Cartesian `SearchStrategy`, oracle-ranked `SearchResult` list, `faultforge search`
- Experiment configs and comparison harness
- Trial minimization (Phase 5)

## Risks

- Over-engineering abstractions before concrete integrations
- Trying to support too many fault classes at once
- Breaking existing Xinda cases before new path works

## Mitigations

- Build concrete wrappers first, extract interfaces later
- Add one fault class at a time
- Keep existing cases working until new path is proven
