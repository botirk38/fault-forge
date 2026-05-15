# Slow-Anduril

An extensible feedback-guided fault reproduction framework for distributed systems.

## Overview

Slow-Anduril extends the [Anduril](https://github.com/OrderLab/Anduril) framework to support generalized fault models beyond exception injection. The core thesis: given a production failure symptom, automatically search over fault site, node, fault type, parameters, and timing to reproduce the symptom and output a minimal root-cause recipe.

## Motivation

Original Anduril reproduces exception/partial-failure bugs via feedback-guided search over injection points. Slow-Anduril generalizes this to:
- **Fail-slow faults**: thread delays, network degradation, disk slowdowns
- **Quantitative oracles**: latency thresholds, timeout rates, election churn, retry storms
- **Recipe minimization**: smallest delay magnitude, duration, and occurrence that reproduces a symptom

## Architecture

- **Candidate Discovery**: Static analysis (Soot) identifies injection points across I/O, RPC, synchronization, and resource paths
- **Fault Operators**: Pluggable fault models (exception, thread delay, network delay, disk delay, etc.)
- **Feedback-Guided Search**: Prioritizes injection points using good/bad/trial log comparison
- **Symptom Oracle**: Evaluates whether a trial reproduces target symptoms
- **Recipe Minimization**: Reduces fault parameters to minimal reproducing configuration

## Getting Started

See [README-Anduril.md](README-Anduril.md) for the original Anduril build and usage instructions.

## Roadmap

1. [x] Adopt Anduril baseline
2. [ ] Baseline build and smoke test
3. [ ] Fault model abstraction
4. [ ] Thread delay fault operator
5. [ ] Generalized trial recipe format
6. [ ] Symptom oracle abstraction
7. [ ] First fail-slow case (ZOOKEEPER-2251)
8. [ ] Search over delay parameters
9. [ ] Recipe minimization

## Acknowledgments

This project extends [Anduril](https://github.com/OrderLab/Anduril) by OrderLab. See [README-Anduril.md](README-Anduril.md) for the original project documentation.
