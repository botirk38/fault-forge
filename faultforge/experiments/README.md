# FaultForge Experiment Configs

Pre-built experiment configurations and oracle definitions for reproducing known
distributed system vulnerabilities under slow faults.

## Directory Structure

```
experiments/
├── oracles/          # Issue + oracle YAML definitions
│   ├── etcd-*.yaml
│   ├── cassandra-*.yaml
│   ├── hbase-*.yaml
│   ├── kafka-*.yaml
│   ├── crdb-*.yaml
│   └── hadoop-*.yaml
├── configs/          # Experiment batch configs
│   ├── <system>-danger-zone.yaml   # Per-system danger-zone sweeps
│   ├── multi-fault-escalation.yaml # Multi-fault combinations
│   └── all-systems-sweep.yaml      # Quick broad coverage
└── README.md
```

## Usage

### Dry-run (plan trials without executing)

```bash
cd faultforge
uv run faultforge experiment experiments/configs/etcd-danger-zone.yaml --dry-run
```

### Execute an experiment

```bash
uv run faultforge experiment experiments/configs/etcd-danger-zone.yaml \
  --runtime runtime.yaml \
  --output-dir results/
```

### Single search with an oracle

```bash
uv run faultforge search \
  --system etcd \
  --benchmark ycsb \
  --oracle experiments/oracles/etcd-leader-lease.yaml \
  --nodes leader \
  --fault-models nw \
  --magnitudes 1 5 10 50 100 \
  --max-trials 50 \
  --strategy shuffled \
  --seed 42
```

## Oracle Definitions

Each oracle YAML follows the `OracleConfig` schema:

```yaml
issue:
  id: "ETCD-LEADER-LEASE"
  system: "etcd"
  title: "..."
  source: "https://..."
  category: "slow-fault"

invalid_if:
  any:
    - file: info
      contains: "docker-compose up failed"

reproduced_if:
  any:
    - file: compose
      regex: "lease expired"
    - file: compose
      contains: "peer became inactive"
```

- `invalid_if` — trial is thrown out (infrastructure failure, not a valid test)
- `reproduced_if` — symptom was detected (vulnerability triggered)
- `severity_threshold` — number of matches needed for `reproduced=True` (default: 1)

## Experiment Configs

Each config YAML has a `name` and a list of `runs`:

```yaml
name: etcd-danger-zone
runs:
  - name: etcd-nw-leader-ycsb
    system: etcd
    benchmark: ycsb
    oracle: experiments/oracles/etcd-leader-lease.yaml
    nodes: ["leader"]
    fault_models: ["nw"]
    magnitudes_ms: [1, 5, 10, 50, 100]
    start_times_s: [0, 10, 30]
    durations_s: [60]
    max_trials: 100
    strategy: shuffled
    seed: 42
```

## Coverage

| System | Oracles | Configs | Fault Types | Known Issues |
|--------|---------|---------|-------------|-------------|
| etcd | 3 | 4 runs | nw, fs | ETCD#15247, ETCD#18109 |
| Cassandra | 2 | 3 runs | nw, fs | CASSANDRA-18120, CASSANDRA-15442 |
| HBase | 2 | 3 runs | nw, fs | HBASE-26347, HBASE-15018 |
| Kafka | 2 | 3 runs | nw, fs | consumer rebalance, under-replication |
| CockroachDB | 2 | 3 runs | nw, fs | disk stall, raft stepdown |
| Hadoop | 2 | 4 runs | nw, fs | limplock, speculative exec |
| **Multi-fault** | — | 4 runs | nw+fs, multi-node | escalation combos |
| **Sweep** | — | 6 runs | nw, fs | broad random sample |

## Design Rationale

Severity ranges are tuned to the **danger zones** identified in the Xinda/NSDI'25
paper (Lu et al.). Key insight: the transition from "tolerable" to "catastrophic"
often happens in a narrow band (e.g., etcd leader at 1-10ms network delay).
The configs concentrate trials in these zones to maximize the probability of
triggering vulnerabilities with minimal trial budget.
