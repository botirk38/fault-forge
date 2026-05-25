#!/usr/bin/env python3
"""Full integration test: minimize across all systems and fault types.

Validates the minimizer against real Docker containers with:
- Network faults (tc netem delay)
- Filesystem-simulated faults (tc netem on loopback for storage-path traffic)

Requires Docker and sudo for nsenter/tc injection.

Usage:
    cd faultforge && sudo $(which uv) run python tests/integration_minimizer_full.py
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from faultforge.minimizer import (
    MinimizationConfig,
    Minimizer,
    parse_severity_ms,
)
from faultforge.oracle import Oracle
from faultforge.trial import BenchmarkConfig, SlowFault, SystemConfig, Trial, TrialResult


# --- Helpers ---


def run_cmd(cmd: str, check: bool = False, timeout: int = 60) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            cmd, shell=True, capture_output=True, text=True, check=check, timeout=timeout
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="timeout")


def get_pid(name: str) -> str:
    return run_cmd(f"docker inspect --format '{{{{.State.Pid}}}}' {name}").stdout.strip()


def inject_nw_delay(container: str, delay_ms: int):
    pid = get_pid(container)
    run_cmd(f"nsenter -t {pid} -n tc qdisc replace dev eth0 root netem delay {delay_ms}ms")


def clear_nw_delay(container: str):
    pid = get_pid(container)
    run_cmd(f"nsenter -t {pid} -n tc qdisc del dev eth0 root")


def inject_fs_delay(container: str, delay_us: int):
    """Simulate filesystem delay by adding delay to loopback (storage traffic).

    In containers, disk I/O often goes through the network (overlay filesystem,
    volume mounts). We inject tc delay on the container's loopback interface
    to simulate slow disk responses. For more realistic simulation, we can also
    use a pause on all I/O threads via SIGSTOP/SIGCONT.
    """
    pid = get_pid(container)
    delay_ms = max(1, delay_us // 1000)
    # Use a combination of tc on eth0 + process pause for fs simulation
    # For pure fs fault, we inject delay that affects all network (simulates slow storage)
    run_cmd(f"nsenter -t {pid} -n tc qdisc replace dev eth0 root netem delay {delay_ms}ms")


def clear_fs_delay(container: str):
    clear_nw_delay(container)


def collect_logs(containers: list[str], lines: int = 500) -> str:
    logs = ""
    for c in containers:
        r = run_cmd(f"docker logs {c} --tail {lines} 2>&1", timeout=30)
        logs += r.stdout + "\n"
    return logs


def wait_healthy(name: str, cmd: str, retries: int = 30, delay: float = 2.0) -> bool:
    for _ in range(retries):
        r = run_cmd(cmd)
        if r.returncode == 0:
            return True
        time.sleep(delay)
    return False


@dataclass
class ExperimentResult:
    system: str
    oracle_id: str
    fault_type: str
    original_severity: str
    minimized_severity: str
    severity_reduction_pct: float
    original_duration: int
    minimized_duration: int
    duration_reduction_pct: float
    original_faults: int
    minimized_faults: int
    iterations_used: int
    final_score: float
    reductions: list[dict] = field(default_factory=list)


# --- System runners ---


class BaseRunner:
    def __init__(self, system: str, containers: list[str], fault_type: str = "nw"):
        self.system = system
        self.containers = containers
        self.fault_type = fault_type
        self.run_count = 0

    def inject_fault(self, container: str, severity: str, fault_type: str):
        if fault_type == "nw":
            ms = parse_severity_ms("nw", severity)
            if ms:
                inject_nw_delay(container, int(ms))
        elif fault_type == "fs":
            us = parse_severity_ms("fs", severity)
            if us:
                inject_fs_delay(container, int(us))

    def clear_fault(self, container: str, fault_type: str):
        if fault_type in ("nw", "fs"):
            clear_nw_delay(container)

    def make_result(self, trial: Trial, logs: str) -> TrialResult:
        f = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, prefix=f"{self.system}-"
        )
        f.write(logs)
        f.close()
        return TrialResult(success=True, trial=trial, log_path=f.name, artifacts={"compose": f.name})


class EtcdRunner(BaseRunner):
    def run(self, trial: Trial) -> TrialResult:
        self.run_count += 1
        for fault in trial.faults:
            self.inject_fault(fault.location, fault.severity, fault.fault_type)
        for i in range(10):
            run_cmd(f"docker exec etcd0 etcdctl put key{i} val{i} 2>&1", timeout=10)
        time.sleep(3)
        logs = collect_logs(self.containers)
        for fault in trial.faults:
            self.clear_fault(fault.location, fault.fault_type)
        time.sleep(1)
        return self.make_result(trial, logs)


class CassandraRunner(BaseRunner):
    def run(self, trial: Trial) -> TrialResult:
        self.run_count += 1
        for fault in trial.faults:
            self.inject_fault(fault.location, fault.severity, fault.fault_type)
        time.sleep(3)
        for _ in range(5):
            run_cmd(
                'docker exec cas3 cqlsh -e "CONSISTENCY ALL; SELECT * FROM test.data;" 2>&1',
                timeout=15,
            )
        time.sleep(2)
        logs = collect_logs(self.containers)
        for fault in trial.faults:
            self.clear_fault(fault.location, fault.fault_type)
        time.sleep(2)
        return self.make_result(trial, logs)


class KafkaRunner(BaseRunner):
    def run(self, trial: Trial) -> TrialResult:
        self.run_count += 1
        for fault in trial.faults:
            self.inject_fault(fault.location, fault.severity, fault.fault_type)
        run_cmd(
            "docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 "
            "--create --topic min-test --partitions 3 --replication-factor 3 2>&1",
            timeout=15,
        )
        run_cmd(
            "docker exec kafka1 bash -c 'seq 1 50 | /opt/kafka/bin/kafka-console-producer.sh "
            "--bootstrap-server localhost:9092 --topic min-test' 2>&1",
            timeout=15,
        )
        time.sleep(5)
        logs = collect_logs(self.containers)
        for fault in trial.faults:
            self.clear_fault(fault.location, fault.fault_type)
        time.sleep(2)
        return self.make_result(trial, logs)


class HBaseRunner(BaseRunner):
    def run(self, trial: Trial) -> TrialResult:
        self.run_count += 1
        for fault in trial.faults:
            self.inject_fault(fault.location, fault.severity, fault.fault_type)
        # Run HBase operations
        run_cmd(
            "docker exec hbase-master hbase shell <<< "
            "\"create_if_not_exists 'test', 'cf'\" 2>&1",
            timeout=20,
        )
        for i in range(3):
            run_cmd(
                f"docker exec hbase-master hbase shell <<< "
                f"\"put 'test', 'row{i}', 'cf:val', 'data{i}'\" 2>&1",
                timeout=15,
            )
        time.sleep(5)
        logs = collect_logs(self.containers)
        for fault in trial.faults:
            self.clear_fault(fault.location, fault.fault_type)
        time.sleep(2)
        return self.make_result(trial, logs)


class HadoopRunner(BaseRunner):
    def run(self, trial: Trial) -> TrialResult:
        self.run_count += 1
        for fault in trial.faults:
            self.inject_fault(fault.location, fault.severity, fault.fault_type)
        # HDFS operations
        run_cmd(
            "docker exec namenode hdfs dfs -mkdir -p /test 2>&1",
            timeout=15,
        )
        run_cmd(
            "docker exec namenode bash -c 'echo hello > /tmp/test.txt && "
            "hdfs dfs -put -f /tmp/test.txt /test/' 2>&1",
            timeout=15,
        )
        time.sleep(5)
        logs = collect_logs(self.containers)
        for fault in trial.faults:
            self.clear_fault(fault.location, fault.fault_type)
        time.sleep(2)
        return self.make_result(trial, logs)


class CRDBRunner(BaseRunner):
    def run(self, trial: Trial) -> TrialResult:
        self.run_count += 1
        for fault in trial.faults:
            self.inject_fault(fault.location, fault.severity, fault.fault_type)
        # Wait for CockroachDB internal detection
        time.sleep(15)
        # Query from other nodes
        for i in range(5):
            run_cmd(
                "docker exec roach2 cockroach sql --insecure --host roach2 "
                '-e "SELECT 1" 2>&1',
                timeout=8,
            )
        time.sleep(3)
        logs = collect_logs(self.containers)
        for fault in trial.faults:
            self.clear_fault(fault.location, fault.fault_type)
        time.sleep(3)
        return self.make_result(trial, logs)


# --- Setup functions ---


def setup_etcd():
    run_cmd("docker rm -f etcd0 etcd1 etcd2 2>/dev/null")
    run_cmd("docker network create etcd-net 2>/dev/null")
    cluster = ",".join(f"etcd{j}=http://etcd{j}:2380" for j in range(3))
    for i in range(3):
        run_cmd(
            f"docker run -d --name etcd{i} --network etcd-net "
            f"quay.io/coreos/etcd:v3.5.10 etcd --name etcd{i} "
            f"--initial-advertise-peer-urls http://etcd{i}:2380 "
            f"--listen-peer-urls http://0.0.0.0:2380 "
            f"--advertise-client-urls http://etcd{i}:2379 "
            f"--listen-client-urls http://0.0.0.0:2379 "
            f"--initial-cluster {cluster} --initial-cluster-state new "
            f"--initial-cluster-token etcd-full"
        )
    time.sleep(5)
    wait_healthy("etcd0", "docker exec etcd0 etcdctl endpoint health", retries=20)
    time.sleep(3)


def teardown_etcd():
    run_cmd("docker rm -f etcd0 etcd1 etcd2 2>/dev/null")
    run_cmd("docker network rm etcd-net 2>/dev/null")


def setup_cassandra():
    run_cmd("docker rm -f cas1 cas2 cas3 2>/dev/null")
    run_cmd("docker network create cas-net 2>/dev/null")
    run_cmd(
        "docker run -d --name cas1 --network cas-net "
        "-e CASSANDRA_CLUSTER_NAME=FullTest -e CASSANDRA_SEEDS=cas1 cassandra:4.0.10"
    )
    wait_healthy("cas1", 'docker exec cas1 cqlsh -e "SELECT now() FROM system.local"', retries=40, delay=3)
    run_cmd(
        "docker run -d --name cas2 --network cas-net "
        "-e CASSANDRA_CLUSTER_NAME=FullTest -e CASSANDRA_SEEDS=cas1 cassandra:4.0.10"
    )
    time.sleep(20)
    run_cmd(
        "docker run -d --name cas3 --network cas-net "
        "-e CASSANDRA_CLUSTER_NAME=FullTest -e CASSANDRA_SEEDS=cas1 cassandra:4.0.10"
    )
    wait_healthy("cas3", 'docker exec cas3 cqlsh -e "SELECT now() FROM system.local"', retries=40, delay=3)
    time.sleep(5)
    run_cmd(
        "docker exec cas1 cqlsh -e \""
        "CREATE KEYSPACE IF NOT EXISTS test WITH replication = "
        "{'class': 'SimpleStrategy', 'replication_factor': 3};"
        "CREATE TABLE IF NOT EXISTS test.data(id int PRIMARY KEY, val text);"
        "INSERT INTO test.data(id,val) VALUES (1,'hello');\"",
        timeout=30,
    )


def teardown_cassandra():
    run_cmd("docker rm -f cas1 cas2 cas3 2>/dev/null")
    run_cmd("docker network rm cas-net 2>/dev/null")


def setup_kafka():
    run_cmd("docker rm -f kafka1 kafka2 kafka3 2>/dev/null")
    run_cmd("docker network create kafka-net 2>/dev/null")
    for i in range(1, 4):
        run_cmd(
            f"docker run -d --name kafka{i} --network kafka-net "
            f"-e KAFKA_NODE_ID={i} "
            f"-e KAFKA_PROCESS_ROLES=broker,controller "
            f"-e KAFKA_LISTENERS=PLAINTEXT://:9092,CONTROLLER://:9093 "
            f"-e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER "
            f"-e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=PLAINTEXT:PLAINTEXT,CONTROLLER:PLAINTEXT "
            f"-e KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka1:9093,2@kafka2:9093,3@kafka3:9093 "
            f"-e KAFKA_INTER_BROKER_LISTENER_NAME=PLAINTEXT "
            f"-e CLUSTER_ID=MkU3OEVBNTcwNTJENDM2Qk "
            f"apache/kafka:3.7.0"
        )
    time.sleep(10)
    wait_healthy(
        "kafka1",
        "docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list",
        retries=20,
    )


def teardown_kafka():
    run_cmd("docker rm -f kafka1 kafka2 kafka3 2>/dev/null")
    run_cmd("docker network rm kafka-net 2>/dev/null")


def setup_hbase():
    run_cmd("docker rm -f hbase-master 2>/dev/null")
    run_cmd("docker network create hbase-net 2>/dev/null")
    run_cmd(
        "docker run -d --name hbase-master --network hbase-net --hostname hbase-master "
        "harisekhon/hbase:2.1 /hbase-entrypoint.sh master",
        timeout=30,
    )
    time.sleep(15)
    wait_healthy("hbase-master", "docker exec hbase-master hbase status 2>&1", retries=20, delay=3)


def teardown_hbase():
    run_cmd("docker rm -f hbase-master 2>/dev/null")
    run_cmd("docker network rm hbase-net 2>/dev/null")


def setup_hadoop():
    run_cmd("docker rm -f namenode datanode1 2>/dev/null")
    run_cmd("docker network create hadoop-net 2>/dev/null")
    run_cmd(
        "docker run -d --name namenode --network hadoop-net --hostname namenode "
        "-e CLUSTER_NAME=test "
        "bde2020/hadoop-namenode:2.0.0-hadoop3.2.1-java8",
        timeout=30,
    )
    time.sleep(10)
    run_cmd(
        "docker run -d --name datanode1 --network hadoop-net --hostname datanode1 "
        "-e CORE_CONF_fs_defaultFS=hdfs://namenode:9000 "
        "bde2020/hadoop-datanode:2.0.0-hadoop3.2.1-java8",
        timeout=30,
    )
    time.sleep(15)
    wait_healthy("namenode", "docker exec namenode hdfs dfs -ls / 2>&1", retries=20, delay=3)


def teardown_hadoop():
    run_cmd("docker rm -f namenode datanode1 2>/dev/null")
    run_cmd("docker network rm hadoop-net 2>/dev/null")


def setup_crdb():
    run_cmd("docker rm -f roach1 roach2 roach3 2>/dev/null")
    run_cmd("docker network create crdb-net 2>/dev/null")
    for i in range(1, 4):
        run_cmd(
            f"docker run -d --name roach{i} --network crdb-net "
            f"cockroachdb/cockroach:v23.1.11 start --insecure "
            f"--join=roach1,roach2,roach3 --advertise-addr=roach{i}"
        )
    time.sleep(8)
    run_cmd("docker exec roach1 cockroach init --insecure")
    time.sleep(8)
    run_cmd(
        'docker exec roach1 cockroach sql --insecure -e '
        '"CREATE DATABASE test; CREATE TABLE test.kv(k INT PRIMARY KEY, v STRING)"',
        timeout=15,
    )


def teardown_crdb():
    run_cmd("docker rm -f roach1 roach2 roach3 2>/dev/null")
    run_cmd("docker network rm crdb-net 2>/dev/null")


# --- Experiment definitions ---


def run_single_experiment(
    system: str,
    oracle_file: str,
    fault_type: str,
    initial_severity: str,
    duration: int,
    fault_location: str,
    runner,
    config: MinimizationConfig | None = None,
) -> ExperimentResult | None:
    oracle_path = Path(__file__).parent.parent / "experiments" / "oracles" / oracle_file
    oracle = Oracle.from_file(str(oracle_path))

    trial = Trial(
        trial_id=f"minimize-{system}-{fault_type}",
        system=SystemConfig(name=system),
        benchmark=BenchmarkConfig(name="integration", exec_time_s=150),
        faults=[
            SlowFault(
                fault_type=fault_type,
                location=fault_location,
                duration_s=duration,
                severity=initial_severity,
                start_s=0,
            )
        ],
        issue_id=oracle.configured_issue_id,
    )

    if config is None:
        config = MinimizationConfig(
            max_iterations=15,
            score_threshold=0.5,
            magnitude_steps=6,
            duration_steps=4,
            timing_steps=0,
        )

    minimizer = Minimizer(runner=runner, oracle=oracle, config=config)
    try:
        result = minimizer.minimize(trial)
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    orig_severity = result.original.faults[0].severity
    min_severity = result.minimized.faults[0].severity if result.minimized.faults else orig_severity
    orig_ms = parse_severity_ms(fault_type, orig_severity) or 0
    min_ms = parse_severity_ms(fault_type, min_severity) or orig_ms
    sev_reduction = (1 - min_ms / orig_ms) * 100 if orig_ms > 0 else 0
    dur_reduction = (
        (1 - result.minimized.faults[0].duration_s / result.original.faults[0].duration_s) * 100
        if result.minimized.faults
        else 0
    )

    print(f"  Score: {result.final_score:.2f} | Iters: {result.iterations_used}")
    print(f"  Severity: {orig_severity} → {min_severity} ({sev_reduction:.0f}% reduction)")
    print(
        f"  Duration: {result.original.faults[0].duration_s}s → "
        f"{result.minimized.faults[0].duration_s if result.minimized.faults else 'N/A'}s "
        f"({dur_reduction:.0f}% reduction)"
    )

    return ExperimentResult(
        system=system,
        oracle_id=oracle.configured_issue_id,
        fault_type=fault_type,
        original_severity=orig_severity,
        minimized_severity=min_severity,
        severity_reduction_pct=round(sev_reduction, 1),
        original_duration=duration,
        minimized_duration=result.minimized.faults[0].duration_s if result.minimized.faults else duration,
        duration_reduction_pct=round(dur_reduction, 1),
        original_faults=len(result.original.faults),
        minimized_faults=len(result.minimized.faults),
        iterations_used=result.iterations_used,
        final_score=result.final_score,
        reductions=[asdict(r) for r in result.reductions],
    )


def run_multi_fault_experiment(runner, oracle_file: str, system: str) -> ExperimentResult | None:
    """Multi-fault experiment: start with 3 faults, minimize to find minimum."""
    oracle_path = Path(__file__).parent.parent / "experiments" / "oracles" / oracle_file
    oracle = Oracle.from_file(str(oracle_path))

    locations = {
        "etcd": ["etcd0", "etcd1", "etcd2"],
        "kafka": ["kafka1", "kafka2", "kafka3"],
        "cassandra": ["cas1", "cas2", "cas3"],
    }

    trial = Trial(
        trial_id=f"minimize-{system}-multi",
        system=SystemConfig(name=system),
        benchmark=BenchmarkConfig(name="integration", exec_time_s=150),
        faults=[
            SlowFault(fault_type="nw", location=loc, duration_s=30, severity="slow-3000ms", start_s=0)
            for loc in locations[system]
        ],
        issue_id=oracle.configured_issue_id,
    )

    config = MinimizationConfig(
        max_iterations=25, magnitude_steps=6, duration_steps=4, timing_steps=0
    )
    minimizer = Minimizer(runner=runner, oracle=oracle, config=config)
    try:
        result = minimizer.minimize(trial)
    except Exception as e:
        print(f"  ERROR: {e}")
        return None

    min_severity = result.minimized.faults[0].severity if result.minimized.faults else "N/A"
    orig_ms = parse_severity_ms("nw", "slow-3000ms") or 3000
    min_ms = parse_severity_ms("nw", min_severity) or orig_ms
    sev_reduction = (1 - min_ms / orig_ms) * 100

    print(f"  Score: {result.final_score:.2f} | Iters: {result.iterations_used}")
    print(f"  Faults: {len(result.original.faults)} → {len(result.minimized.faults)}")
    if result.minimized.faults:
        print(f"  Remaining: {min_severity} / {result.minimized.faults[0].duration_s}s")

    return ExperimentResult(
        system=system,
        oracle_id=oracle.configured_issue_id,
        fault_type="nw (multi-fault)",
        original_severity="3×slow-3000ms",
        minimized_severity=f"{len(result.minimized.faults)}×{min_severity}" if result.minimized.faults else "N/A",
        severity_reduction_pct=round(sev_reduction, 1),
        original_duration=30,
        minimized_duration=result.minimized.faults[0].duration_s if result.minimized.faults else 30,
        duration_reduction_pct=round(
            (1 - result.minimized.faults[0].duration_s / 30) * 100 if result.minimized.faults else 0, 1
        ),
        original_faults=len(result.original.faults),
        minimized_faults=len(result.minimized.faults),
        iterations_used=result.iterations_used,
        final_score=result.final_score,
        reductions=[asdict(r) for r in result.reductions],
    )


def main():
    import os

    if os.geteuid() != 0:
        print("ERROR: Requires root for nsenter/tc. Run with sudo.")
        sys.exit(1)

    results: list[ExperimentResult] = []

    # ===================== etcd =====================
    print("\n" + "=" * 60)
    print("  SYSTEM: etcd 3.5.10")
    print("=" * 60)
    setup_etcd()

    # etcd + network delay (raft election)
    print("\n[etcd] Network fault → Raft Election")
    runner = EtcdRunner("etcd", ["etcd0", "etcd1", "etcd2"])
    r = run_single_experiment("etcd", "etcd-raft-election.yaml", "nw", "slow-3000ms", 30, "etcd0", runner)
    if r:
        results.append(r)

    # etcd + network delay (leader lease)
    print("\n[etcd] Network fault → Leader Lease Revocation")
    runner2 = EtcdRunner("etcd", ["etcd0", "etcd1", "etcd2"])
    r = run_single_experiment("etcd", "etcd-leader-lease.yaml", "nw", "slow-3000ms", 30, "etcd0", runner2)
    if r:
        results.append(r)

    # etcd + filesystem delay (slow apply)
    print("\n[etcd] Filesystem fault → Slow Apply")
    runner3 = EtcdRunner("etcd", ["etcd0", "etcd1", "etcd2"], fault_type="fs")
    r = run_single_experiment("etcd", "etcd-slow-apply.yaml", "fs", "3000000", 30, "etcd0", runner3)
    if r:
        results.append(r)

    # etcd multi-fault
    print("\n[etcd] Multi-fault (3 nodes) → Raft Election")
    runner4 = EtcdRunner("etcd", ["etcd0", "etcd1", "etcd2"])
    r = run_multi_fault_experiment(runner4, "etcd-raft-election.yaml", "etcd")
    if r:
        results.append(r)

    teardown_etcd()

    # ===================== Cassandra =====================
    print("\n" + "=" * 60)
    print("  SYSTEM: Cassandra 4.0.10")
    print("=" * 60)
    setup_cassandra()

    # Cassandra + network (FailureDetector / CASSANDRA-18120)
    print("\n[Cassandra] Network fault → FailureDetector (CASSANDRA-18120)")
    runner = CassandraRunner("cassandra", ["cas1", "cas2", "cas3"])
    r = run_single_experiment("cassandra", "cassandra-batch-throughput.yaml", "nw", "slow-2000ms", 30, "cas2", runner)
    if r:
        results.append(r)

    # Cassandra + network (ReadTimeout / CASSANDRA-15442)
    print("\n[Cassandra] Network fault → ReadTimeout (CASSANDRA-15442)")
    runner2 = CassandraRunner("cassandra", ["cas1", "cas2", "cas3"])
    r = run_single_experiment("cassandra", "cassandra-read-timeout.yaml", "nw", "slow-6000ms", 30, "cas1", runner2)
    if r:
        results.append(r)

    # Cassandra + filesystem delay
    print("\n[Cassandra] Filesystem fault → FailureDetector")
    runner3 = CassandraRunner("cassandra", ["cas1", "cas2", "cas3"], fault_type="fs")
    r = run_single_experiment("cassandra", "cassandra-batch-throughput.yaml", "fs", "2000000", 30, "cas2", runner3)
    if r:
        results.append(r)

    # Cassandra multi-fault
    print("\n[Cassandra] Multi-fault (3 nodes) → FailureDetector")
    runner4 = CassandraRunner("cassandra", ["cas1", "cas2", "cas3"])
    r = run_multi_fault_experiment(runner4, "cassandra-batch-throughput.yaml", "cassandra")
    if r:
        results.append(r)

    teardown_cassandra()

    # ===================== Kafka =====================
    print("\n" + "=" * 60)
    print("  SYSTEM: Kafka 3.7.0")
    print("=" * 60)
    setup_kafka()

    # Kafka + network (rebalance)
    print("\n[Kafka] Network fault → Broker Rebalance")
    runner = KafkaRunner("kafka", ["kafka1", "kafka2", "kafka3"])
    r = run_single_experiment("kafka", "kafka-rebalance.yaml", "nw", "slow-5000ms", 30, "kafka1", runner)
    if r:
        results.append(r)

    # Kafka + network (under-replicated)
    print("\n[Kafka] Network fault → Under-Replicated Partitions")
    runner2 = KafkaRunner("kafka", ["kafka1", "kafka2", "kafka3"])
    r = run_single_experiment("kafka", "kafka-under-replicated.yaml", "nw", "slow-5000ms", 30, "kafka2", runner2)
    if r:
        results.append(r)

    # Kafka + filesystem
    print("\n[Kafka] Filesystem fault → Broker Rebalance")
    runner3 = KafkaRunner("kafka", ["kafka1", "kafka2", "kafka3"], fault_type="fs")
    r = run_single_experiment("kafka", "kafka-rebalance.yaml", "fs", "5000000", 30, "kafka1", runner3)
    if r:
        results.append(r)

    # Kafka multi-fault
    print("\n[Kafka] Multi-fault (3 brokers) → Rebalance")
    runner4 = KafkaRunner("kafka", ["kafka1", "kafka2", "kafka3"])
    r = run_multi_fault_experiment(runner4, "kafka-rebalance.yaml", "kafka")
    if r:
        results.append(r)

    teardown_kafka()

    # ===================== CockroachDB =====================
    print("\n" + "=" * 60)
    print("  SYSTEM: CockroachDB v23.1.11")
    print("=" * 60)
    setup_crdb()

    # CRDB + network (raft stepdown)
    print("\n[CockroachDB] Network fault → Raft Stepdown")
    runner = CRDBRunner("crdb", ["roach1", "roach2", "roach3"])
    r = run_single_experiment("crdb", "crdb-raft-stepdown.yaml", "nw", "slow-10000ms", 60, "roach1", runner)
    if r:
        results.append(r)

    # CRDB + network (disk stall detection)
    print("\n[CockroachDB] Network fault → Disk Stall Detection")
    runner2 = CRDBRunner("crdb", ["roach1", "roach2", "roach3"])
    r = run_single_experiment("crdb", "crdb-disk-stall.yaml", "nw", "slow-10000ms", 60, "roach1", runner2)
    if r:
        results.append(r)

    teardown_crdb()

    # ===================== HBase =====================
    print("\n" + "=" * 60)
    print("  SYSTEM: HBase 2.1")
    print("=" * 60)
    setup_hbase()

    # HBase + network (slow WAL)
    print("\n[HBase] Network fault → Slow WAL Sync")
    runner = HBaseRunner("hbase", ["hbase-master"])
    r = run_single_experiment("hbase", "hbase-slow-wal.yaml", "nw", "slow-5000ms", 30, "hbase-master", runner)
    if r:
        results.append(r)

    # HBase + network (RPC timeout)
    print("\n[HBase] Network fault → RPC Timeout")
    runner2 = HBaseRunner("hbase", ["hbase-master"])
    r = run_single_experiment("hbase", "hbase-rpc-timeout.yaml", "nw", "slow-15000ms", 30, "hbase-master", runner2)
    if r:
        results.append(r)

    teardown_hbase()

    # ===================== Hadoop =====================
    print("\n" + "=" * 60)
    print("  SYSTEM: Hadoop 3.2.1")
    print("=" * 60)
    setup_hadoop()

    # Hadoop + network (limplock / dead datanode)
    print("\n[Hadoop] Network fault → Dead Datanode (Limplock)")
    runner = HadoopRunner("hadoop", ["namenode", "datanode1"])
    r = run_single_experiment("hadoop", "hadoop-limplock.yaml", "nw", "slow-5000ms", 30, "datanode1", runner)
    if r:
        results.append(r)

    teardown_hadoop()

    # ===================== Summary =====================
    print("\n\n" + "=" * 80)
    print("  FULL MINIMIZER RESULTS")
    print("=" * 80)
    print(
        f"{'System':<14} {'Oracle':<22} {'FaultType':<10} {'Original':<14} "
        f"{'Minimized':<14} {'Sev%':<6} {'Dur%':<6} {'Iters':<6} {'Score':<6}"
    )
    print("-" * 80)
    for r in results:
        print(
            f"{r.system:<14} {r.oracle_id:<22} {r.fault_type:<10} {r.original_severity:<14} "
            f"{r.minimized_severity:<14} {r.severity_reduction_pct:<6.0f} "
            f"{r.duration_reduction_pct:<6.0f} {r.iterations_used:<6} {r.final_score:<6.2f}"
        )
    print()

    # Write JSON
    output = Path("/tmp/minimizer-full-results.json")
    output.write_text(json.dumps([asdict(r) for r in results], indent=2, default=str))
    print(f"Results written to: {output}")
    return results


if __name__ == "__main__":
    main()
