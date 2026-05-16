# Anduril Tool Module Inventory

The Anduril tool suite lives under `anduril/tool/` and is built as a Maven multi-module project. This document lists each module, its entrypoint, key classes, inputs, and outputs.

---

## Module Overview

| Module | Entrypoint | Role |
|---|---|---|
| **analyzer** | `analyzer.AnalyzerMain.main()` | Static analysis via Soot: call-graph construction, exception/return analysis, injection point identification |
| **index** | (library) | Indexing support for analysis results; consumed by other modules |
| **runtime** | `runtime.TraceAgent` (Java agent) | In-process fault injection at runtime via bytecode instrumentation |
| **feedback** | `feedback.CommandLine.main()` | Post-trial log diffing and feedback-guided injection refinement |
| **reporter** | `reporter.CommandLine.main()` | Validates injection locations against distributed logs; reports trial outcomes |
| **driver** | `driver.Driver.main()` | Top-level orchestrator: loops over trials, invokes single-trial script, runs feedback |

---

## analyzer

**Entrypoint:** `analyzer.AnalyzerMain.main(String[] args)`

**What it does:** Runs Soot-based static analysis on target system bytecode to identify candidate injection points (exception sites, thread scheduling points, etc.).

**Key classes:**
- `AnalyzerMain` — CLI entry, option parsing, phase orchestration
- `AnalyzerOptions` / `OptionParser` — CLI flag definitions
- `PhaseManager` / `PhaseInfo` — manages analysis phases
- `AnalysisManager` — coordinates individual analyses
- `GlobalCallGraphAnalysis` — builds inter-procedural call graph
- `GlobalExceptionAnalysis` — identifies exception propagation paths
- `GlobalSlicingAnalysis` — program slicing for fault impact
- `ThreadSchedulingAnalysis` — thread interleaving analysis
- `TraceInstrumentor` / `ThreadInstrumentor` — bytecode instrumentation for tracing
- `FlakyTestAnalyzer` — analysis variant for flaky test reproduction
- `StackTraceAnalyzer` — stack-trace-guided analysis
- `FateAnalyzer` / `CrashTunerAnalyzer` — specialized analysis modes

**Inputs:** Target system class files / JARs, analysis configuration

**Outputs:** Injection spec JSON (candidate injection points), Soot intermediate files (`sootOutput/`, `jimpleOutput/`)

**Shell scripts:** `anduril/tool/bin/analyzer.sh` and per-bug scripts like `analyzer-zookeeper-2247.sh` wrap the analyzer with system-specific classpaths and options.

---

## index

**Entrypoint:** Library module (no `main` method)

**What it does:** Provides indexing utilities consumed by the analyzer and feedback modules.

---

## runtime

**Entrypoint:** `runtime.TraceAgent` (loaded as a `-javaagent`)

**What it does:** Attaches to the target JVM process and performs in-process fault injection (exception throwing, thread delays) at points identified by the analyzer.

**Key classes:**
- `TraceAgent` — Java agent `premain` entry point
- `InjectionIndex` — maps injection IDs to code locations
- `Config` / `Hash` — experiment configuration and hashing
- `ExceptionBuilder` — constructs exceptions to throw at injection sites
- `PriorityGraph` — injection priority ordering
- `FeedbackManager` — runtime feedback collection
- `DistributedInjectionManager` — coordinates injection across distributed processes
- `BaselineAgent` / `BaselineRemote` / `BaselineStub` — baseline (no-fault) run support
- `StacktraceAgent` — stack-trace collection mode
- `TimePriorityTable` / `TimeFeedbackManager` — timing-based injection

**Inputs:** Injection spec JSON, experiment config properties

**Outputs:** Runtime traces, stack traces (`stack_trace.txt`), injection feedback data

---

## feedback

**Entrypoint:** `feedback.CommandLine.main(String[] args)`

**CLI flags:**
- `--location-feedback` — enable location-based feedback
- `-g <path>` — good-run (baseline) log directory
- `-b <path>` — bad-run (buggy) log directory
- `-t <path>` — trial output directory
- `-s <path>` — injection spec JSON
- `-a <path>` — injection file (current trial)

**What it does:** Compares trial output logs against good/bad baselines to compute feedback signals that guide the next injection point selection.

**Key classes:**
- `CommandLine` — CLI entry point
- `FastDiff` / `LogFileDiff` / `ThreadDiff` — log diffing algorithms
- `DiffDump` — serializes diff results
- `NativeAlgorithms` — optimized diff computations
- `Timeline` — temporal log analysis
- `BugCase` (Scala) — per-system bug case definitions (HBase, Cassandra, Kafka subclasses)

**Inputs:** Good-run logs, bad-run logs, trial output, injection spec JSON

**Outputs:** Updated injection file with refined injection points for the next trial

---

## reporter

**Entrypoint:** `reporter.CommandLine.main(String[] args)`

**What it does:** Post-experiment validation. Loads distributed logs, checks whether the injection actually hit the intended location, and reports outcomes.

**Key classes:**
- `CommandLine` — CLI entry point
- `DistributedLogLoader` — parses logs from multiple nodes
- `InjectionLocationMatcher` — verifies injection site was reached
- `Checker` — validation logic

**Inputs:** Trial output logs, injection spec

**Outputs:** Validation report (pass/fail per injection point)

---

## driver

**Entrypoint:** `driver.Driver.main(String[] args)`

**CLI flags:**
- `-c, --config <file>` — experiment config properties file (required)
- `-b, --baseline` — run in baseline mode (no injection)
- `-e, --experiment` — run in experiment mode (with injection)
- `-n, --nodes <N>` — number of distributed nodes
- `-p, --path <dir>` — directory for trial outputs (required)
- `-s, --spec <file>` — injection spec JSON (required for experiment mode)
- `-t, --trial-limit <N>` — max trials (default: 2000)

**What it does:** Top-level loop that orchestrates the full Anduril workflow:
1. Reads experiment config and injection spec
2. For each trial: runs `single-trial.sh`, monitors for timeout/size limits
3. Collects trial output and stack traces
4. Runs feedback to refine the next injection
5. Repeats until trial limit or convergence

**Key classes:**
- `Driver` — main loop, process management, monitoring
- `Spec` — CLI argument parsing and validation

**Inputs:** Experiment config, injection spec JSON, `single-trial.sh` script

**Outputs:** Per-trial directories (`<N>.out/`) containing logs, injection files (`injection-<N>.json`), stack traces

---

## Non-Module Directories

| Directory | Contents |
|---|---|
| `bin/` | Shell scripts that invoke the analyzer with per-bug classpaths (e.g., `analyzer-zookeeper-2247.sh`) |
| `conf/` | Runtime configuration (`log4j.properties`) |
| `server/` | Auxiliary server utilities (not a Maven module) |
| `move/` | File-moving utilities (not a Maven module) |
