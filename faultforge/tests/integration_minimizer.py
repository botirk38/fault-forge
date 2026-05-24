#!/usr/bin/env python3
"""Integration test: run the minimizer against real Docker containers.

Demonstrates the minimizer finding danger-zone boundaries for each system.
Requires Docker and sudo for tc netem injection.

Usage:
    sudo python tests/integration_minimizer.py
"""

from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from faultforge.minimizer import (
    MinimizationConfig,
    MinimizationResult,
    Minimizer,
    parse_severity_ms,
)
from faultforge.oracle import Oracle
from faultforge.trial import BenchmarkConfig, SlowFault, SystemConfig, Trial, TrialResult


# --- Docker infrastructure helpers ---


def run_cmd(cmd: str, check: bool = True, timeout: int = 60) -> subprocess.CompletedProcess:
    """Run a shell command."""
    return subprocess.run(
        cmd, shell=True, capture_output=True, text=True, check=check, timeout=timeout
    )


def wait_for_container(name: str, check_cmd: str, retries: int = 30, delay: float = 2.0):
    """Wait until a container is healthy."""
    for _ in range(retries):
        r = subprocess.run(check_cmd, shell=True, capture_output=True, text=True)
        if r.returncode == 0:
            return True
        time.sleep(delay)
    return False


def get_container_pid(name: str) -> str:
    """Get the PID of a running container."""
    r = run_cmd(f"docker inspect --format '{{{{.State.Pid}}}}' {name}")
    return r.stdout.strip()


def inject_delay(container: str, delay_ms: int):
    """Inject network delay using tc netem via nsenter."""
    pid = get_container_pid(container)
    run_cmd(
        f"nsenter -t {pid} -n tc qdisc replace dev eth0 root netem delay {delay_ms}ms",
        check=False,
    )


def clear_delay(container: str):
    """Clear network delay."""
    pid = get_container_pid(container)
    run_cmd(f"nsenter -t {pid} -n tc qdisc del dev eth0 root", check=False)


def collect_logs(container: str, lines: int = 500) -> str:
    """Collect container logs."""
    r = run_cmd(f"docker logs {container} --tail {lines} 2>&1", check=False, timeout=30)
    return r.stdout


# --- Real TrialRunner for integration ---


class DockerTrialRunner:
    """Executes trials against real Docker containers.

    For each trial:
    1. Ensures the system cluster is running
    2. Injects the fault (tc netem delay)
    3. Runs a workload
    4. Collects logs
    5. Clears the fault
    """

    def __init__(self, system_name: str, setup_fn, workload_fn, containers: list[str]):
        self.system_name = system_name
        self.setup_fn = setup_fn
        self.workload_fn = workload_fn
        self.containers = containers
        self._setup_done = False
        self.run_count = 0

    def ensure_setup(self):
        if not self._setup_done:
            self.setup_fn()
            self._setup_done = True

    def run(self, trial: Trial) -> TrialResult:
        self.run_count += 1
        self.ensure_setup()

        # Inject faults
        for fault in trial.faults:
            ms = parse_severity_ms(fault.fault_type, fault.severity)
            if ms is not None and fault.fault_type == "nw":
                inject_delay(fault.location, int(ms))

        # Run workload
        try:
            self.workload_fn()
        except Exception:
            pass

        # Small wait for logs to flush
        time.sleep(2)

        # Collect logs
        all_logs = ""
        for c in self.containers:
            all_logs += collect_logs(c) + "\n"

        # Clear faults
        for fault in trial.faults:
            if fault.fault_type == "nw":
                clear_delay(fault.location)

        # Write log to temp file
        log_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, prefix=f"minimizer-{self.system_name}-"
        )
        log_file.write(all_logs)
        log_file.close()

        return TrialResult(
            success=True,
            trial=trial,
            log_path=log_file.name,
            artifacts={"compose": log_file.name},
        )

    def teardown(self):
        """Clean up containers."""
        for c in self.containers:
            clear_delay(c)


# --- System-specific setups ---


def setup_etcd():
    """Start 3-node etcd cluster."""
    run_cmd("docker rm -f etcd0 etcd1 etcd2 2>/dev/null", check=False)
    run_cmd("docker network create etcd-net 2>/dev/null", check=False)

    for i in range(3):
        cluster = ",".join(f"etcd{j}=http://etcd{j}:2380" for j in range(3))
        run_cmd(
            f"docker run -d --name etcd{i} --network etcd-net "
            f"quay.io/coreos/etcd:v3.5.10 etcd "
            f"--name etcd{i} "
            f"--initial-advertise-peer-urls http://etcd{i}:2380 "
            f"--listen-peer-urls http://0.0.0.0:2380 "
            f"--advertise-client-urls http://etcd{i}:2379 "
            f"--listen-client-urls http://0.0.0.0:2379 "
            f"--initial-cluster {cluster} "
            f"--initial-cluster-state new "
            f"--initial-cluster-token etcd-minimize"
        )

    wait_for_container(
        "etcd0",
        "docker exec etcd0 etcdctl endpoint health",
        retries=20,
    )
    time.sleep(3)


def workload_etcd():
    """Run etcd benchmark writes."""
    run_cmd(
        "docker exec etcd0 etcdctl put testkey testvalue 2>&1",
        check=False,
        timeout=15,
    )
    # Run a batch of writes
    for i in range(20):
        run_cmd(
            f"docker exec etcd0 etcdctl put key{i} value{i} 2>&1",
            check=False,
            timeout=10,
        )


def setup_crdb():
    """Start 3-node CockroachDB cluster."""
    run_cmd("docker rm -f roach1 roach2 roach3 2>/dev/null", check=False)
    run_cmd("docker network create crdb-net 2>/dev/null", check=False)

    run_cmd(
        "docker run -d --name roach1 --network crdb-net "
        "cockroachdb/cockroach:v23.1.11 start "
        "--insecure --join=roach1,roach2,roach3 --advertise-addr=roach1"
    )
    run_cmd(
        "docker run -d --name roach2 --network crdb-net "
        "cockroachdb/cockroach:v23.1.11 start "
        "--insecure --join=roach1,roach2,roach3 --advertise-addr=roach2"
    )
    run_cmd(
        "docker run -d --name roach3 --network crdb-net "
        "cockroachdb/cockroach:v23.1.11 start "
        "--insecure --join=roach1,roach2,roach3 --advertise-addr=roach3"
    )
    time.sleep(5)
    run_cmd("docker exec roach1 cockroach init --insecure", check=False)
    wait_for_container(
        "roach1",
        "docker exec roach1 cockroach sql --insecure -e 'SELECT 1'",
        retries=20,
    )
    time.sleep(3)


def workload_crdb():
    """Run CockroachDB SQL workload."""
    run_cmd(
        "docker exec roach1 cockroach sql --insecure -e "
        "\"CREATE TABLE IF NOT EXISTS test(id INT PRIMARY KEY, val STRING)\" 2>&1",
        check=False,
        timeout=15,
    )
    for i in range(10):
        run_cmd(
            f"docker exec roach1 cockroach sql --insecure -e "
            f"\"UPSERT INTO test VALUES ({i}, 'val{i}')\" 2>&1",
            check=False,
            timeout=15,
        )


def setup_cassandra():
    """Start 3-node Cassandra cluster."""
    run_cmd("docker rm -f cas1 cas2 cas3 2>/dev/null", check=False)
    run_cmd("docker network create cas-net 2>/dev/null", check=False)

    run_cmd(
        "docker run -d --name cas1 --network cas-net "
        "-e CASSANDRA_CLUSTER_NAME=TestCluster "
        "-e CASSANDRA_SEEDS=cas1 "
        "cassandra:4.0.10"
    )
    wait_for_container(
        "cas1",
        "docker exec cas1 cqlsh -e 'SELECT now() FROM system.local'",
        retries=40,
        delay=3.0,
    )

    run_cmd(
        "docker run -d --name cas2 --network cas-net "
        "-e CASSANDRA_CLUSTER_NAME=TestCluster "
        "-e CASSANDRA_SEEDS=cas1 "
        "cassandra:4.0.10"
    )
    time.sleep(15)
    run_cmd(
        "docker run -d --name cas3 --network cas-net "
        "-e CASSANDRA_CLUSTER_NAME=TestCluster "
        "-e CASSANDRA_SEEDS=cas1 "
        "cassandra:4.0.10"
    )
    wait_for_container(
        "cas3",
        "docker exec cas3 cqlsh -e 'SELECT now() FROM system.local'",
        retries=40,
        delay=3.0,
    )
    time.sleep(5)


def workload_cassandra():
    """Run Cassandra read workload."""
    run_cmd(
        "docker exec cas3 cqlsh -e \""
        "CREATE KEYSPACE IF NOT EXISTS test WITH replication = "
        "{'class': 'SimpleStrategy', 'replication_factor': 3};"
        "CREATE TABLE IF NOT EXISTS test.data(id int PRIMARY KEY, val text);"
        "INSERT INTO test.data(id,val) VALUES (1,'hello');"
        "\" 2>&1",
        check=False,
        timeout=30,
    )
    # Read with CONSISTENCY ALL to trigger timeout on slow replicas
    for _ in range(5):
        run_cmd(
            "docker exec cas3 cqlsh -e \"CONSISTENCY ALL; SELECT * FROM test.data;\" 2>&1",
            check=False,
            timeout=15,
        )


def setup_kafka():
    """Start Kafka cluster (KRaft mode)."""
    run_cmd("docker rm -f kafka1 kafka2 kafka3 2>/dev/null", check=False)
    run_cmd("docker network create kafka-net 2>/dev/null", check=False)

    for i in range(1, 4):
        node_id = i
        run_cmd(
            f"docker run -d --name kafka{i} --network kafka-net "
            f"-e KAFKA_NODE_ID={node_id} "
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
    wait_for_container(
        "kafka1",
        "docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list",
        retries=20,
    )


def workload_kafka():
    """Run Kafka produce/consume workload."""
    run_cmd(
        "docker exec kafka1 /opt/kafka/bin/kafka-topics.sh "
        "--bootstrap-server localhost:9092 --create --topic minimize-test "
        "--partitions 3 --replication-factor 3 2>&1",
        check=False,
        timeout=15,
    )
    # Produce messages
    run_cmd(
        "docker exec kafka1 bash -c 'seq 1 100 | "
        "/opt/kafka/bin/kafka-console-producer.sh "
        "--bootstrap-server localhost:9092 --topic minimize-test' 2>&1",
        check=False,
        timeout=15,
    )


# --- Main experiment runner ---


@dataclass
class ExperimentResult:
    system: str
    oracle_id: str
    original_severity: str
    minimized_severity: str
    original_duration: int
    minimized_duration: int
    original_faults: int
    minimized_faults: int
    iterations_used: int
    final_score: float
    reductions: list[dict] = field(default_factory=list)


def run_experiment(
    system_name: str,
    oracle_path: str,
    initial_severity: str,
    initial_duration: int,
    fault_location: str,
    setup_fn,
    workload_fn,
    containers: list[str],
    config: MinimizationConfig | None = None,
) -> ExperimentResult | None:
    """Run one minimizer experiment against a real system."""
    print(f"\n{'='*60}")
    print(f"  MINIMIZING: {system_name} ({oracle_path})")
    print(f"  Initial: severity={initial_severity}, duration={initial_duration}s")
    print(f"{'='*60}")

    oracle = Oracle.from_file(oracle_path)
    runner = DockerTrialRunner(system_name, setup_fn, workload_fn, containers)

    trial = Trial(
        trial_id=f"minimize-{system_name}",
        system=SystemConfig(name=system_name),
        benchmark=BenchmarkConfig(name="integration", exec_time_s=150),
        faults=[
            SlowFault(
                fault_type="nw",
                location=fault_location,
                duration_s=initial_duration,
                severity=initial_severity,
                start_s=0,
            )
        ],
        issue_id=oracle.configured_issue_id,
    )

    if config is None:
        config = MinimizationConfig(
            max_iterations=20,
            score_threshold=0.5,
            magnitude_steps=6,
            duration_steps=4,
            timing_steps=0,  # Skip timing for integration (would need longer exec)
        )

    minimizer = Minimizer(runner=runner, oracle=oracle, config=config)

    try:
        result = minimizer.minimize(trial)
    except Exception as e:
        print(f"  ERROR: {e}")
        runner.teardown()
        return None
    finally:
        runner.teardown()

    # Print results
    print(f"\n  Results:")
    print(f"    Iterations used: {result.iterations_used}")
    print(f"    Final score: {result.final_score:.2f}")
    print(f"    Original: {result.original.faults[0].severity} / {result.original.faults[0].duration_s}s")
    if result.minimized.faults:
        print(f"    Minimized: {result.minimized.faults[0].severity} / {result.minimized.faults[0].duration_s}s")
    print(f"    Reductions:")
    for step in result.reductions:
        print(f"      [{step.dimension}] {step.before} → {step.after} (score={step.score:.2f})")

    return ExperimentResult(
        system=system_name,
        oracle_id=oracle.configured_issue_id,
        original_severity=initial_severity,
        minimized_severity=result.minimized.faults[0].severity if result.minimized.faults else "N/A",
        original_duration=initial_duration,
        minimized_duration=result.minimized.faults[0].duration_s if result.minimized.faults else 0,
        original_faults=len(result.original.faults),
        minimized_faults=len(result.minimized.faults),
        iterations_used=result.iterations_used,
        final_score=result.final_score,
        reductions=[asdict(r) for r in result.reductions],
    )


def main():
    oracle_dir = Path(__file__).parent.parent / "faultforge" / "experiments" / "oracles"
    if not oracle_dir.exists():
        oracle_dir = Path(__file__).parent.parent / "experiments" / "oracles"

    results: list[ExperimentResult] = []

    # --- etcd: find minimum delay that triggers raft election ---
    r = run_experiment(
        system_name="etcd",
        oracle_path=str(oracle_dir / "etcd-raft-election.yaml"),
        initial_severity="slow-3000ms",
        initial_duration=30,
        fault_location="etcd0",
        setup_fn=setup_etcd,
        workload_fn=workload_etcd,
        containers=["etcd0", "etcd1", "etcd2"],
    )
    if r:
        results.append(r)

    # --- CockroachDB: find minimum delay for raft stepdown ---
    r = run_experiment(
        system_name="crdb",
        oracle_path=str(oracle_dir / "crdb-raft-stepdown.yaml"),
        initial_severity="slow-3000ms",
        initial_duration=30,
        fault_location="roach1",
        setup_fn=setup_crdb,
        workload_fn=workload_crdb,
        containers=["roach1", "roach2", "roach3"],
    )
    if r:
        results.append(r)

    # --- Kafka: find minimum delay for rebalance ---
    r = run_experiment(
        system_name="kafka",
        oracle_path=str(oracle_dir / "kafka-rebalance.yaml"),
        initial_severity="slow-5000ms",
        initial_duration=30,
        fault_location="kafka1",
        setup_fn=setup_kafka,
        workload_fn=workload_kafka,
        containers=["kafka1", "kafka2", "kafka3"],
    )
    if r:
        results.append(r)

    # --- Print summary ---
    print("\n" + "=" * 70)
    print("  MINIMIZER RESULTS SUMMARY")
    print("=" * 70)
    print(f"{'System':<12} {'Oracle':<20} {'Original':<15} {'Minimized':<15} {'Reduction':<12} {'Iters':<6}")
    print("-" * 70)
    for r in results:
        orig_ms = parse_severity_ms("nw", r.original_severity)
        min_ms = parse_severity_ms("nw", r.minimized_severity)
        if orig_ms and min_ms:
            reduction_pct = f"{(1 - min_ms / orig_ms) * 100:.0f}%"
        else:
            reduction_pct = "N/A"
        print(
            f"{r.system:<12} {r.oracle_id:<20} {r.original_severity:<15} "
            f"{r.minimized_severity:<15} {reduction_pct:<12} {r.iterations_used}"
        )
    print()

    # Write JSON results
    output_path = Path("/tmp/minimizer-results.json")
    output_path.write_text(json.dumps([asdict(r) for r in results], indent=2, default=str))
    print(f"Results written to: {output_path}")

    return results


if __name__ == "__main__":
    if os.geteuid() != 0:
        print("ERROR: This script requires root for nsenter/tc. Run with sudo.")
        sys.exit(1)
    main()
