# FaultForge - Agent Development Guide

## Project Overview

FaultForge is a symptom-guided fault reproduction orchestrator for distributed systems. It coordinates Xinda (environmental slow-fault provider) and Anduril (Java in-process provider) to search for minimal fault recipes that reproduce production issues.

## Package Manager: uv

**Always use uv.** Never use pip, pipenv, poetry, or venv directly.

### Essential Commands

```bash
cd faultforge

uv sync

# Run FaultForge CLI (when implemented)
uv run faultforge --help

# Lint
uv run ruff check src/faultforge/
uv run ruff format --check src/faultforge/

# Type check
uv run ty check

# Fix lint issues
uv run ruff check --fix src/faultforge/
```

## Non-Negotiable Rules

1. **ruff and ty checks MUST pass before any commit.** No exceptions.
2. Run FaultForge lint and `ty check` inside `faultforge/` before committing.
3. If checks fail, fix the issues. Do not add blanket ignores.
4. Legacy per-file ignores in `xinda/pyproject.toml` follow `xinda/AGENTS.md` rules.

## Project Structure

```
fault-forge/
├── .python-version         # Python version pin
├── .github/workflows/ci.yml
├── faultforge/             # FaultForge uv project (`faultforge-sdk`)
│   ├── pyproject.toml      # FaultForge deps, ruff, ty
│   ├── uv.lock
│   └── src/faultforge/     # oracle.py, search.py, fault_provider/ (fault.py, recipe.py, …)
├── xinda/                  # Local uv package (environmental fault provider)
│   ├── pyproject.toml
│   ├── AGENTS.md           # Xinda-specific dev guide
│   ├── main.py
│   ├── cleanup.py
│   └── src/xinda/
│       ├── __init__.py
│       ├── client.py       # XindaClient SDK entry point
│       ├── trial.py        # Trial, SlowFault, BenchmarkConfig dataclasses
│       ├── configs/        # Legacy config classes
│       └── systems/        # System implementations + registry
├── anduril/                # Java in-process provider (vendored, Java 25)
│   ├── tool/               # Maven multi-module build
│   ├── evaluation/
│   └── systems/
├── README.md
└── PLAN.md
```

## Development Workflow

1. Change files under `faultforge/src/faultforge/`.
2. From `faultforge/`, run ruff + `ty check`.
3. Fix any failures, then commit.

## Working on Xinda

See `xinda/AGENTS.md` for Xinda-specific commands. Key difference: use `--project xinda` flag for xinda operations.

```bash
uv run --project xinda ruff check xinda/src/
uv run --project xinda --directory xinda ty check
```

## Adding Dependencies

```bash
cd faultforge
uv add <package>
uv add --dev <dev-package>

# Xinda sub-project
uv add --project xinda <package>
```

## Git Workflow

- Work on feature branches: `pr<N>-<description>`
- Create PRs via `gh pr create`
- Merge into main after review
- Never push directly to main

## Key Constraints

- Python 3.12+
- Xinda is declared in FaultForge via `[tool.uv.sources] xinda = { path = "../xinda", editable = true }` inside `faultforge/pyproject.toml`
- No backward compatibility baggage — refactor aggressively when it improves clarity
- Keep code simple and readable. Best practices over clever architecture.
