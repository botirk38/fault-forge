# Xinda - Agent Development Guide

## Project Overview

Xinda is a slow-fault testing pipeline for distributed systems. It is vendored into the FaultForge monorepo and packaged as a local uv dependency.

## Package Manager: uv

**Always use uv.** Never use pip, pipenv, poetry, or venv directly.

### Essential Commands

```bash
# Install dependencies
uv sync --project xinda

# Run a script
uv run --project xinda python xinda/main.py --sys_name etcd --fault_type nw ...

# Lint
uv run --project xinda ruff check xinda/src/
uv run --project xinda ruff format --check xinda/src/

# Type check
uv run --project xinda --directory xinda ty check

# Fix lint issues
uv run --project xinda ruff check --fix xinda/src/
```

## Non-Negotiable Rules

1. **ruff and ty checks MUST pass before any commit.** No exceptions.
2. Run `uv run --project xinda ruff check xinda/src/` and `uv run --project xinda --directory xinda ty check` before committing.
3. If checks fail, fix the issues. Do not add blanket ignores.
4. Use per-file ignores in `pyproject.toml` only for legacy test/example/data-analysis files that are not part of the core SDK.

## Project Structure

```
xinda/
├── pyproject.toml          # Package config, deps, ruff/ty settings
├── main.py                 # CLI entry point (top-level script)
├── cleanup.py              # Cleanup script (top-level script)
├── src/
│   └── xinda/              # Core package (src layout)
│       ├── __init__.py
│       ├── configs/        # Configuration classes (SlowFault, ResourceLimit, Benchmark, etc.)
│       └── systems/        # System implementations (TestSystem, etcd, hbase, kafka, etc.)
```

## Development Workflow

1. Make changes to `xinda/src/xinda/`
2. Run `uv run --project xinda ruff check xinda/src/`
3. Run `uv run --project xinda --directory xinda ty check`
4. Fix any failures
5. Commit

## Adding Dependencies

```bash
uv add --project xinda <package>
uv add --project xinda --dev <dev-package>
```

## Key Constraints

- Xinda runs on Python 3.12+
- Xinda is a local editable dependency of FaultForge (root `pyproject.toml`)
- `main.py` and `cleanup.py` stay at top level, not under `src/`
- The package uses `uv_build` as build backend with src layout
