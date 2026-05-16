# Anduril Build Notes

## Requirements

| Dependency | Version | Notes |
|---|---|---|
| Java (JDK) | **25** | Temurin recommended (`actions/setup-java` uses `distribution: temurin`) |
| Maven | 3.9+ | Ships with most JDK distributions; `mvn --version` to check |
| Scala | 2.13.18 | Pulled automatically by Maven via `scala-maven-plugin` |

Anduril was migrated from Java 8 to Java 25 in PR #4. The parent POM sets `<java.version>25</java.version>` and uses `maven-compiler-plugin 3.14.0` with `<release>${java.version}</release>`.

## Build Command

```bash
# From repo root
mvn install -DskipTests -B -q -f anduril/tool/pom.xml

# Or from the tool directory
cd anduril/tool
mvn install -DskipTests -B -q
```

Flags:
- `-DskipTests` skips test execution (tests require runtime infrastructure)
- `-B` batch mode (no interactive prompts, CI-friendly)
- `-q` quiet output (suppress info-level Maven logs)

## Maven Modules

The parent POM (`anduril/tool/pom.xml`) builds six modules in order:

| Module | Directory | Artifact |
|---|---|---|
| analyzer | `anduril/tool/analyzer/` | Static analysis / Soot-based call-graph construction |
| index | `anduril/tool/index/` | Indexing support for analysis results |
| runtime | `anduril/tool/runtime/` | TraceAgent for in-process fault injection |
| feedback | `anduril/tool/feedback/` | Feedback-guided search state |
| reporter | `anduril/tool/reporter/` | Trial result reporting |
| driver | `anduril/tool/driver/` | Orchestrates analysis + injection + feedback loop |

## Native Build Behavior

- The Scala compiler (`scala-maven-plugin 4.9.2`) handles all `.scala` source compilation. The standard `maven-compiler-plugin` default-compile phase is disabled (`<phase>none</phase>`), so Java compilation only runs through Scala's mixed-mode compiler.
- Scala incremental compilation is enabled (`<recompileMode>incremental</recompileMode>`).
- Soot (used by the analyzer) generates intermediate Jimple files under `sootOutput/` and `jimpleOutput/`. These directories are gitignored.
- Build artifacts go to the standard `target/` directory in each module (also gitignored).

## CI

The CI workflow (`.github/workflows/ci.yml`) runs the Anduril build on every push/PR to `main`:

```yaml
anduril-build:
  name: "Anduril: Build"
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v6
    - uses: actions/setup-java@v5
      with:
        distribution: temurin
        java-version: "25"
    - run: mvn install -DskipTests -B -q
      working-directory: anduril/tool
```

## Known Issues

- Tests are skipped in CI because they require a running target system (e.g., ZooKeeper, HDFS) with Anduril's TraceAgent attached.
- The `server/` and `move/` directories under `anduril/tool/` are not Maven modules and are not built. They contain auxiliary scripts/configs.
- The `bin/` and `conf/` directories contain runtime shell scripts and configuration templates used during evaluation, not during the Maven build.
