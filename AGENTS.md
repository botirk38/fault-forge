# FaultForge - Agent Development Guide

## Project Overview

FaultForge is a symptom-guided fault reproduction orchestrator for distributed systems. It directly integrates the Xinda-derived runtime to search for minimal fault trials that reproduce production issues.

## Package Manager: uv

**Always use uv.** Never use pip, pipenv, poetry, or venv directly.

### Essential Commands

```bash
cd faultforge

uv sync

# Run FaultForge CLI
uv run faultforge --help
uv run faultforge search --help

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
├── faultforge/             # FaultForge uv project
│   ├── pyproject.toml      # FaultForge deps, ruff, ty
│   ├── uv.lock
│   └── src/faultforge/
│       ├── __init__.py     # exports: Trial, SlowFault, SystemConfig, etc.
│       ├── cli.py          # faultforge CLI (search subcommand)
│       ├── oracle.py       # symptom oracle (log-pattern, exit-code)
│       ├── trial.py        # canonical Trial, SlowFault, configs
│       ├── runner.py       # TrialRunner executes trials
│       ├── search.py       # SearchConfig, SearchStrategy, Searcher
│       ├── systems/        # Docker/Blockade/CharybdeFS lifecycle
│       └── configs/        # legacy runtime configs
├── xinda/                  # Reference copy for result comparison
│   ├── pyproject.toml
│   ├── AGENTS.md
│   ├── main.py
│   └── src/xinda/
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
- FaultForge directly owns the integrated runtime; no external `xinda` dependency
- The canonical execution unit is `Trial` (not `Recipe`)
- `Trial.faults: list[SlowFault]` supports multi-fault trials
- No backward compatibility baggage — refactor aggressively when it improves clarity
- Keep code simple and readable. Best practices over clever architecture.
