# Xinda SDK

Automated slow-fault testing pipeline for distributed systems.

Originally from the Xinda project (NSDI 2025, "One-Size-Fits-None"), vendored and modernized as a local Python package for FaultForge.

## Quick Start

```bash
uv sync --project xinda
uv run --project xinda python -m xinda.main --help
```

## Package Structure

- `xinda/configs/` - Fault, benchmark, resource limit, and logging configurations
- `xinda/systems/` - System-specific test implementations (Cassandra, HBase, Hadoop, etcd, CRDB, Kafka, DepFast, Copilot)

## Development

```bash
uv run --project xinda ruff check xinda/
uv run --project xinda ty check
uv run --project xinda pytest
```
