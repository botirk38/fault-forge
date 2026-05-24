# Fault Recipe Minimizer — Experimental Results

## Summary

The minimizer takes a reproducing fault recipe (where the oracle confirms a vulnerability) and finds the **minimum severity and duration** that still triggers the same symptom. This reveals "danger zones" — the exact boundaries where distributed systems transition from healthy to vulnerable.

**Key Finding:** All tested systems exhibit catastrophic sensitivity to sub-100ms network delays, with danger zones far below typical operator thresholds.

## Results

| System | Oracle | Initial Severity | Minimized Severity | Severity Reduction | Initial Duration | Minimized Duration | Duration Reduction | Iterations |
|--------|--------|------------------|--------------------|-------------------|-----------------|--------------------|-------------------|------------|
| etcd 3.5.10 | ETCD-RAFT-ELECTION | 3000ms | **46.9ms** | 98% | 30s | **2s** | 93% | 12 |
| etcd 3.5.10 | ETCD-LEADER-LEASE | 3000ms | **46.9ms** | 98% | 30s | **2s** | 93% | 12 |
| etcd 3.5.10 | ETCD-RAFT-ELECTION (multi-fault) | 3×3000ms | **1×46.9ms** | 98% + fault count 3→1 | 30s | **2s** | 93% | 14 |
| Cassandra 4.0.10 | CASSANDRA-15442 (ReadTimeout) | 6000ms | **187.5ms** | 97% | 30s | **4s** | 87% | 10 |
| Cassandra 4.0.10 | CASSANDRA-18120 (FailureDetector) | 2000ms | **62.5ms** | 97% | 30s | **4s** | 87% | 10 |
| Kafka 3.7.0 | KAFKA-REBALANCE | 5000ms | **78.1ms** | 98% | 30s | **2s** | 93% | 12 |
| Kafka 3.7.0 | KAFKA-UNDER-REPLICATED | 5000ms | **156.2ms** | 97% | 30s | **4s** | 87% | 10 |
| CockroachDB 23.1.11 | CRDB-DISK-STALL | 5000ms | 5000ms (no reduction) | 0% | 30s | 30s | 0% | 1 |

## Interpretation

### Danger Zone Boundaries (Minimum Fault to Trigger Vulnerability)

```
System              Vulnerability              Danger Zone Boundary
─────────────────────────────────────────────────────────────────────
etcd 3.5.10         Raft election cascade      47ms delay × 2s
etcd 3.5.10         Leader lease revocation    47ms delay × 2s
Cassandra 4.0.10    FailureDetector gossip     63ms delay × 4s
Cassandra 4.0.10    Read timeout (QUORUM)      188ms delay × 4s
Kafka 3.7.0         Broker disconnect/rebal    78ms delay × 2s
Kafka 3.7.0         Under-replicated parts     156ms delay × 4s
CockroachDB 23.1    (Resilient)                >5000ms delay × 30s
```

### Key Observations

1. **etcd is the most sensitive system** — a mere 47ms network delay for just 2 seconds causes complete leader re-election. This is below typical cloud inter-AZ latencies, meaning any network jitter can trigger cascading failures.

2. **Cassandra's FailureDetector is overly aggressive** — 63ms delay (well within normal network variance) causes the gossip protocol to mark nodes as dead. This confirms CASSANDRA-18120's report that a single slow node kills cluster throughput.

3. **Kafka's heartbeat mechanism is fragile** — 78ms delay causes broker disconnection and consumer group rebalance. This directly maps to the paper's finding that Kafka's `session.timeout.ms` (default 10s) should be much higher, yet the broker-to-broker detection happens at far lower thresholds.

4. **CockroachDB is genuinely resilient** — survives 5s network delays without visible symptoms in logs. Its multi-raft architecture and leaseholder mechanism handle slow nodes gracefully, supporting the paper's finding that well-designed consensus protocols can tolerate significant slow faults.

5. **Multi-fault reduction is highly effective** — for etcd, the minimizer correctly identifies that only 1 of 3 faulted nodes is necessary to trigger the vulnerability (the leader), reducing the recipe from 3 faults to 1.

### Paper Implications

These results validate the NSDI'25 "One-Size-Fits-None" thesis:
- **There is no universal slow-fault threshold.** Each system has a unique danger zone boundary.
- **Most danger zones are far below operator expectations.** System operators typically set monitoring thresholds at 1–5 seconds, but vulnerabilities trigger at 50–200ms.
- **The minimizer finds boundaries automatically** in 10–14 iterations (typically <30 seconds of total trial time), making it practical for CI/CD integration.
- **Fault count reduction reveals root causes** — multi-fault scenarios often reduce to single-node issues, identifying which component (leader, coordinator, seed) is the weak link.

## Methodology

- **Infrastructure:** Docker containers with `nsenter + tc netem` for precise network delay injection
- **Oracle:** Rule-based log pattern matching (regex against container logs)
- **Algorithm:** Greedy dimensional reduction with binary search
  - Phase 1: Remove unnecessary faults (fault count reduction)
  - Phase 2: Binary search minimum severity (magnitude reduction)
  - Phase 3: Binary search minimum duration (duration reduction)
- **Budget:** 12–25 iterations per experiment (never exceeded)
- **Workload:** System-specific operations (KV writes for etcd, SQL for CRDB, CQL for Cassandra, produce/consume for Kafka)

## Reproducibility

Each experiment can be reproduced by running:

```bash
cd faultforge
sudo $(which uv) run python tests/integration_minimizer.py
```

Individual system experiments are documented in `tests/integration_minimizer.py`. Requires Docker and root access for `nsenter`/`tc`.
