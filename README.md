# FaultForge

A symptom-guided fault reproduction orchestrator for distributed systems.

## Overview

FaultForge directly integrates the Xinda-derived runtime to automatically search for and minimize fault trials that reproduce known production issues. Search emits executable `Trial` objects, which are run against real distributed systems and scored by a symptom oracle.

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
                  network/disk/cpu slow faults
```

## Components

| Component | Role |
|---|---|
| `faultforge/src/faultforge/` | Symptom oracle, search, minimization, experiment control |
| `faultforge/src/faultforge/trial.py` | Canonical `Trial`, `SlowFault`, `SystemConfig`, `BenchmarkConfig` |
| `faultforge/src/faultforge/runner.py` | `TrialRunner` executes trials against real systems |
| `faultforge/src/faultforge/systems/` | Docker/Blockade/CharybdeFS lifecycle for 8 distributed systems |
| `xinda/` | Reference copy for result comparison (not imported by FaultForge) |

## Motivation

Existing slow-fault testing systems such as Xinda explore the impact of configured slow faults under benchmarks. FaultForge targets a complementary problem: given a production issue symptom, automatically search for and minimize a fault trial that reproduces that symptom.

## Quick Start

```bash
cd faultforge
uv sync
uv run faultforge --help
uv run faultforge search --help
```

## Roadmap

See [PLAN.md](PLAN.md) for the full development plan.

## Acknowledgments

This project integrates two prior systems:

- [Xinda](https://github.com/OrderLab/xinda) - Automated slow-fault testing pipeline (NSDI 2025)
- [Anduril](https://github.com/OrderLab/Anduril) - Feedback-guided fault reproduction (ATC 2025)

See [Xinda](https://github.com/OrderLab/xinda) and [Anduril](https://github.com/OrderLab/Anduril) upstream repositories for original project documentation.
