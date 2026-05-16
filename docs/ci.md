# CI Documentation

## Overview

CI runs on every push and pull request to `main` via `.github/workflows/ci.yml`. There are seven jobs split across three component groups.

---

## Jobs

### FaultForge (Python orchestrator)

| Job | What it checks | Command |
|---|---|---|
| **FaultForge: Lint** | Ruff lint + format | `uv run ruff check faultforge/` and `uv run ruff format --check faultforge/` |
| **FaultForge: Type Check** | ty static type checker | `uv run ty check` |
| **FaultForge: Test** | pytest (exit 5 = no tests is OK) | `uv run pytest faultforge/ -v` |

### Xinda SDK (environmental fault provider)

| Job | What it checks | Command |
|---|---|---|
| **Xinda: Lint** | Ruff lint + format | `uv run --project xinda ruff check xinda/` and `uv run --project xinda ruff format --check xinda/src/` |
| **Xinda: Type Check** | ty static type checker | `uv run --project xinda --directory xinda ty check` |
| **Xinda: Test** | pytest (ignores examples/data-analysis) | `uv run --project xinda pytest xinda/ --ignore=xinda/examples --ignore=xinda/data-analysis -v` |

### Anduril (Java in-process fault provider)

| Job | What it checks | Command |
|---|---|---|
| **Anduril: Build** | Maven compile (Java 25, Temurin) | `mvn install -DskipTests -B -q` in `anduril/tool/` |

---

## Required Local Pre-Push Checks

Run these before pushing to avoid CI failures:

### FaultForge

```bash
# Lint
uv run ruff check faultforge/
uv run ruff format --check faultforge/

# Type check
uv run ty check

# Tests
uv run pytest faultforge/ -v
```

### Xinda

```bash
# Lint
uv run --project xinda ruff check xinda/
uv run --project xinda ruff format --check xinda/src/

# Type check
uv run --project xinda --directory xinda ty check

# Tests
uv run --project xinda pytest xinda/ --ignore=xinda/examples --ignore=xinda/data-analysis -v
```

### Anduril

```bash
# Requires Java 25 (Temurin)
cd anduril/tool
mvn install -DskipTests -B -q
```

---

## Auto-Fix

```bash
# Fix FaultForge lint issues
uv run ruff check --fix faultforge/
uv run ruff format faultforge/

# Fix Xinda lint issues
uv run --project xinda ruff check --fix xinda/src/
uv run --project xinda ruff format xinda/src/
```

---

## Environment

- **Python**: 3.12 (pinned in `.python-version`)
- **Java**: 25 (Temurin distribution)
- **Package manager**: uv (astral-sh/setup-uv@v6)
- **Actions**: checkout@v6, setup-java@v5

## Notes

- The `|| test $? -eq 5` suffix on pytest steps allows the job to pass when no tests are collected (exit code 5). This is intentional — FaultForge and Xinda test suites are still being built out.
- Ruff lint and format are separate steps but both must pass.
- ty only checks files under `faultforge/**/*.py` (root) and `src/xinda/**/*.py` (xinda). Legacy code under `xinda/configs/`, `xinda/systems/`, `xinda/examples/`, and `xinda/data-analysis/` is excluded.
- The Anduril build skips tests because they require a running target system with the TraceAgent attached.
