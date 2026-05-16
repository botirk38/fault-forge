# Build Notes

## FaultForge (Python Orchestrator)

### Requirements

- Python 3.12+
- `uv` package manager

### Build

```bash
uv sync
uv run ruff check faultforge/
uv run ruff format --check faultforge/
uv run ty check
uv run pytest
```

## Xinda SDK (Environmental Fault Provider)

### Requirements

- Python 3.12+
- `uv` package manager
- Ubuntu 18.04–20.04 (for runtime: Docker, Blockade, CharybdeFS)

### Build

```bash
uv sync --project xinda
uv run --project xinda ruff check xinda/
uv run --project xinda ruff format --check xinda/
uv run --project xinda --directory xinda ty check
uv run --project xinda pytest
```

### Notes

- Xinda is now a local uv package (`xinda-sdk`) consumed by FaultForge via `[tool.uv.sources]`.
- Legacy Xinda internals (`configs/`, `systems/`) are excluded from strict type checks and will be modernized incrementally.
- The SDK layer provides typed config objects and a callable trial API.
- Runtime requires Linux with Docker, Blockade, and CharybdeFS.

## Anduril (Java In-Process Provider)

### Requirements

- **JDK 8** (OpenJDK recommended). Newer JDKs may work but are untested.
- Apache Maven 3.6+
- Apache Ant 1.10+ (for ZooKeeper compilation)
- protobuf 2.5.0 (for HDFS compilation)
- Ubuntu 18.04–20.04 (tested environment)

### Build

```bash
cd anduril/tool
mvn install -DskipTests
```

### Known Blockers

- **JDK version**: This machine has JDK 25. Anduril was developed and tested with JDK 8.
- **Platform**: Anduril was tested on Ubuntu 18.04–20.04 (x86_64). This machine is macOS (arm64).
- **protobuf 2.5.0**: Old version that may not build on modern systems.

### Workaround

Focus development on `faultforge/` (Python) first. The Java plane can be validated later in a compatible environment (Linux + JDK 8).
