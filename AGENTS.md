# FaultForge - Agent Development Guide

## Project Overview

FaultForge is a symptom-guided fault reproduction orchestrator for distributed systems. It coordinates Xinda (environmental slow-fault provider) and Anduril (Java in-process provider) to search for minimal fault recipes that reproduce production issues.

## Package Manager: uv

**Always use uv.** Never use pip, pipenv, poetry, or venv directly.

### Essential Commands

```bash
# Install all dependencies (root + xinda local package)
uv sync

# Run FaultForge CLI (when implemented)
uv run faultforge --help

# Lint
uv run ruff check faultforge/
uv run ruff format --check faultforge/

# Type check
uv run ty check

# Fix lint issues
uv run ruff check --fix faultforge/
```

## Non-Negotiable Rules

1. **ruff and ty checks MUST pass before any commit.** No exceptions.
2. Run `uv run ruff check faultforge/` and `uv run ty check` before committing.
3. If checks fail, fix the issues. Do not add blanket ignores.
4. Per-file ignores in `pyproject.toml` are only for vendored code (`xinda/`, `anduril/`).

## Project Structure

```
fault-forge/
├── pyproject.toml          # Root FaultForge project config
├── uv.lock                 # Lockfile (commit this)
├── .python-version         # Python version pin
├── .github/workflows/ci.yml
├── faultforge/             # Core orchestrator package
│   ├── __init__.py
│   └── recipe.py           # Multi-fault recipe schema (Pydantic)
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

1. Make changes to `faultforge/`
2. Run `uv run ruff check faultforge/`
3. Run `uv run ty check`
4. Fix any failures
5. Commit

## Working on Xinda

See `xinda/AGENTS.md` for Xinda-specific commands. Key difference: use `--project xinda` flag for xinda operations.

```bash
uv run --project xinda ruff check xinda/src/
uv run --project xinda --directory xinda ty check
```

## Adding Dependencies

```bash
# Root FaultForge
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
- Xinda is a local editable dependency: `[tool.uv.sources] xinda = { path = "xinda", editable = true }`
- No backward compatibility baggage — refactor aggressively when it improves clarity
- Keep code simple and readable. Best practices over clever architecture.
