# Issue / Oracle File Format (Draft)

> **Status:** Draft — describes the planned config shape only. No implementation exists yet.

This document specifies the file format for describing a known bug (issue) and its expected symptom (oracle). FaultForge will use these files to know *what* to reproduce and *how* to verify that a reproduction attempt succeeded.

---

## Overview

Each bug is described by a single YAML file. The file contains two logical sections:

1. **Issue** — metadata about the bug: which system, what went wrong, references.
2. **Oracle** — how to detect the symptom: log patterns, exit codes, exceptions.

A minimal example:

```yaml
# zookeeper-2247.yaml

issue:
  id: "ZOOKEEPER-2247"
  system: "zookeeper"
  title: "Slow follower connection attempt can cause leader to go into
         ReadOnlyMode"
  source: "https://issues.apache.org/jira/browse/ZOOKEEPER-2247"
  versions_affected:
    - "3.4.8"
  category: "slow-fault"

fault:
  provider: "xinda"
  fault_type: "nw"
  severity: "slow-100"
  target_node: "follower1"
  start_s: 10
  duration_s: 30

oracle:
  type: "log-symptom"
  node: 0
  pattern:
    log_level: "ERROR"
    exception: "ConnectionLossException"
    exception_msg_contains: "KeeperErrorCode = ConnectionLoss"
    class_name: "QuorumPeer"
  verdict: "symptom_present"
```

---

## `issue` Section

Describes the bug being reproduced.

| Field | Type | Required | Description |
|---|---|---|---|
| `id` | string | yes | Bug tracker ID (e.g. `ZOOKEEPER-2247`, `HDFS-15032`) |
| `system` | string | yes | Target system registry key (must match Xinda's system registry) |
| `title` | string | yes | One-line bug summary |
| `source` | string | no | URL to the original bug report |
| `versions_affected` | list[string] | no | System versions known to exhibit the bug |
| `category` | string | no | Fault category: `slow-fault`, `crash-fault`, `byzantine`, `config-error` |
| `notes` | string | no | Free-form notes about the bug |

---

## `fault` Section

Describes the fault injection configuration needed to trigger the bug.

| Field | Type | Required | Description |
|---|---|---|---|
| `provider` | string | yes | Fault provider: `xinda` (environmental) or `anduril` (in-process) |
| `fault_type` | string | yes | Fault type: `nw`, `fs`, `none` (for Xinda); `exception`, `delay` (for Anduril) |
| `severity` | string | no | Provider-specific severity string (e.g. `slow-100`, `flaky-0.5`) |
| `target_node` | string | no | Which node to target (container name or role) |
| `start_s` | int | no | Seconds after workload start to inject fault |
| `duration_s` | int | no | Fault duration in seconds (-1 for unbounded/restart) |
| `anduril_spec` | string | no | Path to Anduril injection spec JSON (for Anduril provider) |
| `params` | map | no | Additional provider-specific parameters |

---

## `oracle` Section

Describes how to detect whether the bug symptom was reproduced.

| Field | Type | Required | Description |
|---|---|---|---|
| `type` | string | yes | Oracle type (see below) |
| `verdict` | string | yes | Expected outcome: `symptom_present` or `symptom_absent` |
| `node` | int/string | no | Which node's logs to check (index or name) |
| `pattern` | map | conditional | Log matching pattern (required for `log-symptom` type) |
| `exit_code` | int | conditional | Expected process exit code (required for `exit-code` type) |
| `script` | string | conditional | Path to custom checker script (required for `custom` type) |

### Oracle Types

| Type | Description | Required fields |
|---|---|---|
| `log-symptom` | Match a log entry by level, exception, message, class | `pattern` |
| `exit-code` | Check process/benchmark exit code | `exit_code` |
| `test-result` | Check JUnit test pass/fail | `pattern` (test class/method) |
| `custom` | Run a user-provided script that exits 0 (symptom found) or 1 | `script` |

### `pattern` Fields (for `log-symptom`)

| Field | Type | Description |
|---|---|---|
| `log_level` | string | Log level to match: `ERROR`, `WARN`, `FATAL` |
| `exception` | string | Exception class name (e.g. `ConnectionLossException`) |
| `exception_msg_contains` | string | Substring match on exception message |
| `class_name` | string | Logging class name |
| `thread` | string | Thread name pattern |
| `stack_trace_prefix` | list[string] | Expected top-of-stack method signatures |

### `pattern` Fields (for `test-result`)

| Field | Type | Description |
|---|---|---|
| `test_class` | string | JUnit test class name |
| `test_method` | string | JUnit test method name |
| `expect_fail` | bool | `true` if the symptom is a test failure (default: `true`) |

---

## File Organization

```
cases/
├── zookeeper/
│   ├── ZOOKEEPER-2247.yaml
│   ├── ZOOKEEPER-3006.yaml
│   └── ZOOKEEPER-3157.yaml
├── hbase/
│   ├── HBASE-15252.yaml
│   └── HBASE-16144.yaml
├── cassandra/
│   └── CASSANDRA-17663.yaml
└── kafka/
    └── KAFKA-10048.yaml
```

Each file is named after the bug tracker ID. Files are grouped by system.

---

## Relationship to Existing Code

- **Xinda**: The `fault` section maps to `SlowFault` and `Trial` construction parameters.
- **Anduril**: The `fault` section with `provider: anduril` maps to Anduril's injection spec JSON (referenced via `anduril_spec` field). The `oracle.pattern` fields parallel the `BugCase` trait methods in `anduril/tool/feedback/src/main/scala/feedback/cases/BugCase.scala`.
- **FaultForge**: Will consume these files to orchestrate end-to-end reproduction: read issue → configure fault → run trial → check oracle → report verdict.

---

## Open Questions

1. **Multiple oracles**: Should a single issue support multiple oracle checks (e.g. log pattern AND exit code)?
2. **Timing constraints**: Should the oracle specify a time window for symptom detection?
3. **Retry semantics**: Should the file encode how many trials to attempt before declaring "not reproduced"?
4. **Anduril integration depth**: Should the Anduril injection spec be inlined in the YAML or always referenced as an external JSON file?
5. **Version pinning**: Should the file pin Docker image tags or defer to runtime configuration?
