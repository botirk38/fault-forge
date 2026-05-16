# FaultForge

A symptom-guided fault reproduction orchestrator for distributed systems.

## Overview

FaultForge composes environmental slow-fault providers (Xinda) with in-process fault providers (Anduril) to automatically search for and minimize the fault recipe that reproduces a known production issue.

## Architecture

```text
                 production issue / oracle
                           │
                           ▼
                 orchestrator/ (Python)
                 search │ oracle │ minimize
                    │              │
                    ▼              ▼
        xinda/                anduril/
        environmental         Java in-process
        slow-fault provider   static analysis + TraceAgent
        network/disk/cpu      thread delay / exception
```

## Components

| Component | Role |
|---|---|
| `faultforge/` | Symptom oracle, search, minimization, experiment control |
| `xinda/` | Environmental slow-fault SDK (`xinda-sdk`), cluster lifecycle, benchmarks |
| `anduril/` | Java in-process fault injection, static analysis, feedback-guided search |

Xinda is packaged as a local uv dependency (`xinda-sdk`) and consumed directly by FaultForge.

## Motivation

Existing slow-fault testing systems such as Xinda explore the impact of configured slow faults under benchmarks. FaultForge targets a complementary problem: given a production issue symptom, automatically search for and minimize a fault recipe that reproduces that symptom.

## Quick Start

```bash
uv sync
uv run faultforge --help
```

See [BUILD.md](BUILD.md) for build instructions for each component.

## Roadmap

See [PLAN.md](PLAN.md) for the full development plan.

## Acknowledgments

This project integrates two prior systems:

- [Xinda](https://github.com/OrderLab/xinda) - Automated slow-fault testing pipeline (NSDI 2025)
- [Anduril](https://github.com/OrderLab/Anduril) - Feedback-guided fault reproduction (ATC 2025)

See [README-Xinda.md](README-Xinda.md) and [README-Anduril.md](README-Anduril.md) for original project documentation.
