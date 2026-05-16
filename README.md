# Env-Anduril

An extensible feedback-guided fault reproduction framework for distributed systems.

## Overview

Env-Anduril extends the [Anduril](https://github.com/OrderLab/Anduril) framework to support generalized fault models beyond exception injection. The core thesis: given a production failure symptom, automatically search over fault site, node, fault type, parameters, and timing to reproduce the symptom and output a minimal root-cause recipe.

## Motivation

Original Anduril reproduces exception/partial-failure bugs via feedback-guided search over injection points. Env-Anduril generalizes this to:

- **Fail-slow faults**: thread delays, network degradation, disk slowdowns
- **Multi-fault trials**: multiple concurrent faults across planes and nodes
- **Quantitative oracles**: latency thresholds, timeout rates, election churn, retry storms
- **Recipe minimization**: smallest delay magnitude, duration, and occurrence that reproduces a symptom

## Architecture

Two projects under one repo:

- **`anduril/`**: Java in-process fault plane (Soot static analysis, bytecode instrumentation, TraceAgent)
- **`env-anduril/`**: Go environmental fault plane (node-local agent, tc/netem, cgroup, OS-level controls)

Both consume a shared multi-fault recipe schema. Trials can activate multiple faults concurrently across planes and nodes.

## Quick Start

See [BUILD.md](BUILD.md) for build instructions for both projects.

## Roadmap

See [PLAN.md](PLAN.md) for the full development plan.

## Acknowledgments

This project extends [Anduril](https://github.com/OrderLab/Anduril) by OrderLab. See [README-Anduril.md](README-Anduril.md) for the original project documentation.
