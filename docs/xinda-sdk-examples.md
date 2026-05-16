# Xinda SDK Usage Examples

Typed Python examples for the Xinda SDK surface (`Trial`, `SlowFault`, `BenchmarkConfig`, `XindaClient`).

> These examples construct SDK objects only. Running a trial requires Docker, Blockade, and the Xinda toolchain installed on the host.

---

## SlowFault

```python
from xinda import SlowFault

# Network delay on the leader node, 100 ms for 60 s starting at t=10 s
nw = SlowFault.network(
    location="leader",
    severity="slow-100ms",
    duration_s=60,
    start_s=10,
)

# Filesystem delay on a datanode, 10 000 us for 120 s
fs = SlowFault.filesystem(
    location="datanode",
    severity="10000",
    duration_s=120,
)

# No-fault baseline
baseline = SlowFault(fault_type="none", location="leader", duration_s=-1, severity="none")
```

---

## BenchmarkConfig

```python
from xinda import BenchmarkConfig

# YCSB (Cassandra, HBase, etcd, CRDB)
ycsb = BenchmarkConfig.ycsb(workload="a", exec_time_s=150)

# etcd official benchmark
etcd_bench = BenchmarkConfig.etcd_official(workload="lease-keepalive", total=800000)

# Kafka perf_test
kafka = BenchmarkConfig.perf_test(exec_time_s=150, num_msg=14000000)

# Kafka OpenMessaging
openmsg = BenchmarkConfig.openmsg(driver="kafka-latency", workload_file="simple-workload")

# Hadoop MRBench
mrbench = BenchmarkConfig.mrbench(num_iter=10)

# Hadoop TeraSort
terasort = BenchmarkConfig.terasort(num_rows="10737418")

# CockroachDB sysbench
sysbench = BenchmarkConfig.sysbench(lua_scheme="oltp_write_only", table_size=10000)

# DepFast
depfast = BenchmarkConfig.depfast(concurrency=100, scheme="fpga_raft")

# Copilot
copilot = BenchmarkConfig.copilot(concurrency=10, scheme="copilot")

# Raw kwargs for custom benchmarks
custom = BenchmarkConfig(name="my_bench", exec_time_s=300, kwargs={"key": "value"})
```

---

## SystemConfig

```python
from xinda import SystemConfig

# Minimal
sys = SystemConfig(name="etcd")

# With options
sys = SystemConfig(
    name="hbase",
    cluster_size=5,
    data_dir="hbase-nw-test",
    coverage=True,
)
```

---

## Trial

A `Trial` ties system, benchmark, fault, resource limits, and paths together.

```python
from xinda import Trial, SystemConfig, BenchmarkConfig, SlowFault, ResourceLimit

trial = Trial(
    system=SystemConfig(name="etcd"),
    benchmark=BenchmarkConfig.ycsb(workload="a"),
    fault=SlowFault.network(location="etcd1", severity="slow-100ms", duration_s=60),
)

# Override resource limits
trial = Trial(
    system=SystemConfig(name="cassandra"),
    benchmark=BenchmarkConfig.ycsb(workload="mixed"),
    fault=SlowFault.network(location="cassandra1", severity="slow-50ms", duration_s=120),
    resource=ResourceLimit(cpu_limit="2", mem_limit="16G"),
    iteration=3,
)
```

---

## XindaClient

```python
from xinda import XindaClient, Trial, SystemConfig, BenchmarkConfig, SlowFault

client = XindaClient()

trial = Trial(
    system=SystemConfig(name="kafka"),
    benchmark=BenchmarkConfig.perf_test(),
    fault=SlowFault.network(location="kafka1", severity="slow-200ms", duration_s=90),
)

# Run the trial (requires Docker + toolchain)
result = client.run(trial)

print(result.success)    # True / False
print(result.log_path)   # path to trial log
print(result.error)      # None on success, error message on failure
```

---

## TrialResult

`XindaClient.run()` always returns a `TrialResult`, even on failure.

```python
from xinda import TrialResult

# result.success   -- bool
# result.system    -- SystemConfig echo
# result.benchmark -- BenchmarkConfig echo
# result.fault     -- SlowFault echo
# result.log_path  -- str | None
# result.error     -- str | None
# result.metadata  -- dict (extra data)
```
