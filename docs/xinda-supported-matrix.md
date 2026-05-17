# Xinda Supported Matrix

Reference for the systems, benchmarks, fault types, and runtime tools supported by the Xinda SDK.

---

## Supported Systems

| System | Registry key | Container nodes | SDK class |
|---|---|---|---|
| Apache Cassandra | `cassandra` | `cas1`, `cas2`, `cas3` | `Cassandra` |
| Apache HBase | `hbase` | `hbase-master`, `hbase-regionserver`, `hbase-regionserver1`, `hbase-regionserver2`, `datanode`, `namenode` | `HBase` |
| Apache Hadoop (MapReduce) | `hadoop` | `namenode`, `datanode`, `datanode1`, `datanode2` | `Mapred` |
| etcd | `etcd` | `etcd0`, `etcd1`, `etcd2` | `Etcd` |
| CockroachDB | `crdb` | `roach1`, `roach2`, `roach3` | `Crdb` |
| Apache Kafka | `kafka` | `kafka1`, `kafka2`, `kafka3` | `Kafka` |
| DepFast | `depfast` | `server1`..`server5`, `client` | `Depfast` |
| Copilot | `copilot` | `control`, `master`, `replica1`..`replica3`, `client` | `Copilot` |

Default cluster size is 3 nodes. Larger clusters (10-node, 20-node) are supported via alternate container YAML files.

---

## Benchmark Names

Each system has one or more valid benchmark names. The `BenchmarkConfig` factory method and the benchmark name passed to the SDK must match the system.

| Benchmark name | Factory method | Valid systems | Description |
|---|---|---|---|
| `ycsb` | `BenchmarkConfig.ycsb()` | cassandra, hbase, etcd, crdb | Yahoo! Cloud Serving Benchmark |
| `etcd-official` | `BenchmarkConfig.etcd_official()` | etcd | etcd built-in benchmark (lease-keepalive, range, stm, txn-put, watch, watch-get) |
| `mrbench` | `BenchmarkConfig.mrbench()` | hadoop | MapReduce benchmark |
| `terasort` | `BenchmarkConfig.terasort()` | hadoop | TeraSort (large-scale sorting) |
| `perf_test` | `BenchmarkConfig.perf_test()` | kafka | Kafka producer performance test |
| `openmsg` | `BenchmarkConfig.openmsg()` | kafka | OpenMessaging benchmark for Kafka |
| `sysbench` | `BenchmarkConfig.sysbench()` | crdb | Sysbench OLTP workloads for CockroachDB |
| `depfast` | `BenchmarkConfig.depfast()` | depfast | DepFast built-in benchmark |
| `copilot` | `BenchmarkConfig.copilot()` | copilot | Copilot built-in benchmark |

---

## Fault Types

| `fault_type` | Description | Injection mechanism | Factory method |
|---|---|---|---|
| `nw` | Network fault | Blockade (tc/netem) | `SlowFault.network()` |
| `fs` | Filesystem fault | CharybdeFS (FUSE) | `SlowFault.filesystem()` |
| `none` | No fault (baseline) | N/A | `SlowFault(fault_type="none", ...)` |

### Network fault severities (Blockade)

| Severity pattern | Blockade command | Effect |
|---|---|---|
| `slow-<delay>` | `blockade slow <node>` | Adds network delay via tc/netem |
| `flaky-*` | `blockade flaky <node>` | Introduces packet loss |
| `partition-*` | `blockade partition <node>` | Network partition |

### Filesystem fault severities (CharybdeFS)

The `severity` field is passed directly to CharybdeFS `inject_client --delay <severity>`.

### Special cases

- **DepFast** with `nw` + `slow-*`: Uses direct `tc qdisc` injection inside the container instead of Blockade.
- **Baseline** (`duration_s=-1`): No fault is injected; used for collecting reference behavior.
- **Restart** (`if_restart=True`, `duration_s=-1`): Restarts the target container after `start_s` seconds instead of injecting a fault.

---

## Required Runtime Tools

Running Xinda trials (not just constructing SDK objects) requires the following tools on the host:

| Tool | Purpose | Required for |
|---|---|---|
| Docker + Docker Compose | Container cluster lifecycle | All systems |
| Blockade | Network fault injection (tc/netem) | `nw` faults |
| CharybdeFS | Filesystem fault injection (FUSE) | `fs` faults |
| System-specific Docker images | Target system binaries | Each system |
| Xinda tools directory | Benchmark runners, compose files, blockade configs | All systems |
| Xinda software directory | Pre-built system binaries and dependencies | All systems |

### Directory layout expected at runtime

```
~/workdir/
├── data/<data_dir>/     # Trial logs and results
├── xinda-software/      # Pre-built system images/binaries
└── xinda/
    └── tools/           # Compose files, blockade configs, benchmark scripts
```

These paths are configured via `TrialPaths` (defaults based on `$HOME/workdir/`).
