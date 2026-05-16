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

## Xinda (Environmental Fault Provider)

### Requirements

- Ubuntu 18.04–20.04 (tested environment)
- Python 3.6.13 (Xinda requirement)
- Docker
- Blockade (network faults)
- CharybdeFS (filesystem faults)
- CloudLab c220g2 nodes recommended

### Build

See [README-Xinda.md](README-Xinda.md) for full instructions.

Quick start:

```bash
cd xinda
pip install -r requirements.txt  # if exists
python3 main.py --help
```

### Notes

- Xinda is vendored as-is. We will wrap it behind `faultforge/xinda_runner.py`.
- Xinda's Python version requirement (3.6) differs from FaultForge (3.12+). They run as separate processes.

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
