# Build Notes

## env-anduril (Go)

### Requirements

- Go 1.26+
- Linux or macOS (fault operators require Linux for `tc`/cgroup)

### Build

```bash
cd env-anduril
go build ./...
go test ./...
```

### Notes

- The Go module is initialized but has no packages yet. See [PLAN.md](PLAN.md) for the development roadmap.
- Fault operators that use `tc`/`netem` require `NET_ADMIN` capability and a Linux kernel.

## anduril (Java)

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

### Compile a Case

```bash
cd anduril/systems/zookeeper-3006
./compile.sh
```

### Compile All Cases

```bash
cd anduril/systems
./compile-all.sh
```

### Known Blockers

- **JDK version**: This machine has JDK 25. Anduril was developed and tested with JDK 8. Some cases may fail to compile or run with newer JDKs.
- **Platform**: Anduril was tested on Ubuntu 18.04–20.04 (x86_64). This machine is macOS (arm64). System compilation (ZooKeeper, HDFS, HBase) may have platform-specific issues.
- **protobuf 2.5.0**: Required for HDFS. This is an old version that may not build on modern systems without patches.

### Workaround for Development

For now, focus development on `env-anduril/` (Go) which does not depend on JDK 8 or Ubuntu. The Java plane can be validated later in a compatible environment (Linux + JDK 8).
