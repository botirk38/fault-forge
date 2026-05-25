#!/usr/bin/env python3
"""Integration test: verify experiment configs reproduce real faults.

Spins up actual Docker containers, injects faults via tc netem (using nsenter
to reach the container network namespace), collects logs, and evaluates oracles.

Requires: Docker, iproute2 (tc), nsenter, root/sudo access.

Validated systems (images available):
  - etcd 3.5.10 (matt12313/xinda-etcd:3.5.10)
  - CockroachDB v23.1.11 (cockroachdb/cockroach:v23.1.11)
  - Cassandra 4.0.10 (cassandra:4.0.10)
  - HBase 2.5.6 (rmlu/hbase-master:testing, rmlu/hbase-regionserver:testing)

Not yet validated (images unavailable or require extended setup):
  - Kafka (bitnami/kafka:3.5 removed from registry)
  - Hadoop (requires 10+ min for dead-node detection thresholds)
"""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from faultforge.oracle import Oracle  # noqa: E402

TOOLS_DIR = Path(__file__).parent.parent.parent / "xinda" / "tools"
ORACLES_DIR = Path(__file__).parent.parent.parent / "experiments" / "oracles"
RESULTS_DIR = Path("/tmp/fault-reproduction-results")
RESULTS_DIR.mkdir(exist_ok=True)


def run(cmd: str, **kwargs: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kwargs)


def get_container_pid(container_name: str) -> int:
    result = run(f"docker inspect --format '{{{{.State.Pid}}}}' {container_name}")
    return int(result.stdout.strip())


def inject_delay(container_name: str, delay_ms: int) -> bool:
    """Inject network delay into a container using nsenter + tc."""
    try:
        pid = get_container_pid(container_name)
        result = run(
            f"sudo nsenter -t {pid} -n tc qdisc add dev eth0 root netem delay {delay_ms}ms"
        )
        if result.returncode != 0:
            print(f"  [WARN] tc inject failed: {result.stderr.strip()}")
            return False
        return True
    except Exception as e:
        print(f"  [WARN] inject_delay failed: {e}")
        return False


def clear_delay(container_name: str) -> None:
    """Clear network delay from a container."""
    try:
        pid = get_container_pid(container_name)
        run(f"sudo nsenter -t {pid} -n tc qdisc del dev eth0 root")
    except Exception:
        pass


def collect_docker_logs(containers: list[str], output_file: Path) -> None:
    """Collect Docker logs from all containers."""
    with open(output_file, "w") as f:
        for c in containers:
            result = run(f"docker logs {c} 2>&1")
            f.write(result.stdout)


def collect_crdb_internal_logs(containers: list[str], output_file: Path) -> None:
    """CRDB logs internally, not to stdout. Extract from container filesystem."""
    with open(output_file, "w") as f:
        for c in containers:
            result = run(f"docker exec {c} cat /cockroach/cockroach-data/logs/cockroach.log 2>&1")
            f.write(result.stdout)


def docker_compose_up(compose_file: Path) -> bool:
    """Start containers via docker compose."""
    result = run(f"docker compose -f {compose_file} up -d")
    if result.returncode != 0:
        print(f"  [ERROR] docker compose up failed: {result.stderr[:200]}")
        return False
    return True


def docker_compose_down(compose_file: Path) -> None:
    """Tear down containers."""
    run(f"docker compose -f {compose_file} down -v")


def wait_for_healthy(containers: list[str], timeout: int = 30) -> bool:
    """Wait until all containers are running."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        all_running = True
        for c in containers:
            result = run(f"docker inspect --format '{{{{.State.Status}}}}' {c}")
            if result.stdout.strip() != "running":
                all_running = False
                break
        if all_running:
            return True
        time.sleep(1)
    return False


def ensure_env(compose_file: Path) -> None:
    """Create .env with default resource limits if missing."""
    env_file = compose_file.parent / ".env"
    if not env_file.exists():
        env_file.write_text("CPU_LIMIT=2\nMEM_LIMIT=4g\nUID=1000\nGID=1000\n")


def find_etcd_leader(containers: list[str]) -> str | None:
    """Find which etcd container is the current leader."""
    result = run(
        "docker exec etcd0 etcdctl "
        "--endpoints=etcd0:2379,etcd1:2379,etcd2:2379 "
        "endpoint status --write-out=json"
    )
    if result.returncode != 0:
        return None
    import json

    try:
        data = json.loads(result.stdout)
        leader_id = data[0]["Status"]["leader"]
        for ep in data:
            if ep["Status"]["header"]["member_id"] == leader_id:
                host = ep["Endpoint"].split(":")[0]
                return host
    except (json.JSONDecodeError, KeyError, IndexError):
        pass
    return None


# ─── Etcd Tests ──────────────────────────────────────────────────────────────


def test_etcd_raft_election() -> tuple[str, bool]:
    """Network partition on a node triggers new leader election."""
    name = "ETCD-RAFT-ELECTION"
    compose = TOOLS_DIR / "docker-etcd" / "3.5.10" / "docker-compose.yaml"
    containers = ["etcd0", "etcd1", "etcd2"]
    log_file = RESULTS_DIR / "etcd-raft-election.log"
    ensure_env(compose)

    print(f"\n{'=' * 60}")
    print(f"  Testing: {name}")
    print(f"{'=' * 60}")

    docker_compose_up(compose)
    if not wait_for_healthy(containers, timeout=30):
        print("  [FAIL] Containers didn't start")
        docker_compose_down(compose)
        return name, False

    time.sleep(10)

    # Find leader and inject delay on it
    leader = find_etcd_leader(containers)
    target = leader if leader else "etcd0"
    print(f"  Leader: {leader}, injecting 3000ms delay on {target}...")
    inject_delay(target, 3000)
    time.sleep(15)
    clear_delay(target)
    time.sleep(5)

    collect_docker_logs(containers, log_file)
    oracle = Oracle.from_file(ORACLES_DIR / "etcd-raft-election.yaml")
    result = oracle.evaluate(artifacts={"compose": str(log_file)})
    print(
        f"  Result: reproduced={result.reproduced}, "
        f"score={result.score}, matches={len(result.matched_signals)}"
    )

    docker_compose_down(compose)
    return name, result.reproduced


def test_etcd_leader_lease() -> tuple[str, bool]:
    """Slow network on leader causes i/o timeout and lease issues."""
    name = "ETCD-LEADER-LEASE"
    compose = TOOLS_DIR / "docker-etcd" / "3.5.10" / "docker-compose.yaml"
    containers = ["etcd0", "etcd1", "etcd2"]
    log_file = RESULTS_DIR / "etcd-leader-lease.log"
    ensure_env(compose)

    print(f"\n{'=' * 60}")
    print(f"  Testing: {name}")
    print(f"{'=' * 60}")

    docker_compose_up(compose)
    if not wait_for_healthy(containers, timeout=30):
        docker_compose_down(compose)
        return name, False

    time.sleep(10)

    leader = find_etcd_leader(containers)
    target = leader if leader else "etcd1"
    print(f"  Leader: {leader}, injecting 3000ms delay on {target}...")
    inject_delay(target, 3000)
    time.sleep(20)
    clear_delay(target)
    time.sleep(5)

    collect_docker_logs(containers, log_file)
    oracle = Oracle.from_file(ORACLES_DIR / "etcd-leader-lease.yaml")
    result = oracle.evaluate(artifacts={"compose": str(log_file)})
    print(
        f"  Result: reproduced={result.reproduced}, "
        f"score={result.score}, matches={len(result.matched_signals)}"
    )

    docker_compose_down(compose)
    return name, result.reproduced


def test_etcd_slow_apply() -> tuple[str, bool]:
    """Network delay causes 'prober detected unhealthy' and clock drift."""
    name = "ETCD-SLOW-APPLY"
    compose = TOOLS_DIR / "docker-etcd" / "3.5.10" / "docker-compose.yaml"
    containers = ["etcd0", "etcd1", "etcd2"]
    log_file = RESULTS_DIR / "etcd-slow-apply.log"
    ensure_env(compose)

    print(f"\n{'=' * 60}")
    print(f"  Testing: {name}")
    print(f"{'=' * 60}")

    docker_compose_up(compose)
    if not wait_for_healthy(containers, timeout=30):
        docker_compose_down(compose)
        return name, False

    time.sleep(10)

    leader = find_etcd_leader(containers)
    target = leader if leader else "etcd2"
    print(f"  Injecting 500ms delay on {target} + benchmark load...")
    inject_delay(target, 500)

    # Run benchmark for load
    run(
        "docker exec etcd-benchmark benchmark "
        "--endpoints=etcd0:2379,etcd1:2379,etcd2:2379 "
        "--conns=5 --clients=50 put --key-size=8 --total=2000 --val-size=256"
    )

    time.sleep(10)
    clear_delay(target)
    time.sleep(5)

    collect_docker_logs(containers, log_file)
    oracle = Oracle.from_file(ORACLES_DIR / "etcd-slow-apply.yaml")
    result = oracle.evaluate(artifacts={"compose": str(log_file)})
    print(
        f"  Result: reproduced={result.reproduced}, "
        f"score={result.score}, matches={len(result.matched_signals)}"
    )

    docker_compose_down(compose)
    return name, result.reproduced


# ─── CockroachDB Tests ───────────────────────────────────────────────────────


def test_crdb_raft_stepdown() -> tuple[str, bool]:
    """Network delay on CRDB node causes range unavailability."""
    name = "CRDB-RAFT-STEPDOWN"
    compose = TOOLS_DIR / "docker-crdb" / "docker-compose.yaml"
    containers = ["roach1", "roach2", "roach3"]
    log_file = RESULTS_DIR / "crdb-raft-stepdown.log"
    ensure_env(compose)

    print(f"\n{'=' * 60}")
    print(f"  Testing: {name}")
    print(f"{'=' * 60}")

    docker_compose_up(compose)
    if not wait_for_healthy(containers, timeout=30):
        docker_compose_down(compose)
        return name, False

    time.sleep(10)
    # Initialize cluster
    run("docker exec roach1 cockroach init --insecure --host=roach1:26357")
    time.sleep(10)

    print("  Injecting 3000ms delay on roach1...")
    inject_delay("roach1", 3000)
    time.sleep(20)
    clear_delay("roach1")
    time.sleep(5)

    collect_crdb_internal_logs(containers, log_file)
    oracle = Oracle.from_file(ORACLES_DIR / "crdb-raft-stepdown.yaml")
    result = oracle.evaluate(artifacts={"compose": str(log_file)})
    print(
        f"  Result: reproduced={result.reproduced}, "
        f"score={result.score}, matches={len(result.matched_signals)}"
    )

    docker_compose_down(compose)
    return name, result.reproduced


def test_crdb_disk_stall() -> tuple[str, bool]:
    """Network delay triggers slow heartbeat (liveness failure indicator)."""
    name = "CRDB-DISK-STALL"
    compose = TOOLS_DIR / "docker-crdb" / "docker-compose.yaml"
    containers = ["roach1", "roach2", "roach3"]
    log_file = RESULTS_DIR / "crdb-disk-stall.log"
    ensure_env(compose)

    print(f"\n{'=' * 60}")
    print(f"  Testing: {name}")
    print(f"{'=' * 60}")

    docker_compose_up(compose)
    if not wait_for_healthy(containers, timeout=30):
        docker_compose_down(compose)
        return name, False

    time.sleep(10)
    run("docker exec roach1 cockroach init --insecure --host=roach1:26357")
    time.sleep(10)

    print("  Injecting 3000ms delay on roach1...")
    inject_delay("roach1", 3000)
    time.sleep(20)
    clear_delay("roach1")
    time.sleep(5)

    collect_crdb_internal_logs(containers, log_file)
    oracle = Oracle.from_file(ORACLES_DIR / "crdb-disk-stall.yaml")
    result = oracle.evaluate(artifacts={"compose": str(log_file)})
    print(
        f"  Result: reproduced={result.reproduced}, "
        f"score={result.score}, matches={len(result.matched_signals)}"
    )

    docker_compose_down(compose)
    return name, result.reproduced


# ─── Cassandra Tests ─────────────────────────────────────────────────────────


def test_cassandra_batch_throughput() -> tuple[str, bool]:
    """Network delay on seed node triggers gossip failure detection."""
    name = "CASSANDRA-18120"
    compose = TOOLS_DIR / "docker-cassandra" / "docker-compose.yaml"
    containers = ["cas1", "cas2"]
    log_file = RESULTS_DIR / "cassandra-batch-throughput.log"
    ensure_env(compose)

    print(f"\n{'=' * 60}")
    print(f"  Testing: {name}")
    print(f"{'=' * 60}")

    docker_compose_up(compose)
    # Cassandra takes longer to start
    if not wait_for_healthy(containers[:2], timeout=120):
        docker_compose_down(compose)
        return name, False

    time.sleep(30)  # Extra stabilization for Cassandra

    print("  Injecting 2000ms delay on cas1 (seed node)...")
    inject_delay("cas1", 2000)
    time.sleep(30)
    clear_delay("cas1")
    time.sleep(5)

    collect_docker_logs(containers, log_file)
    oracle = Oracle.from_file(ORACLES_DIR / "cassandra-batch-throughput.yaml")
    result = oracle.evaluate(artifacts={"compose": str(log_file)})
    print(
        f"  Result: reproduced={result.reproduced}, "
        f"score={result.score}, matches={len(result.matched_signals)}"
    )

    docker_compose_down(compose)
    return name, result.reproduced


# ─── HBase Tests ─────────────────────────────────────────────────────────────


def test_hbase_slow_wal() -> tuple[str, bool]:
    """Network delay on regionserver triggers StreamSlowMonitor warnings."""
    name = "HBASE-26347"
    compose = TOOLS_DIR / "docker-hbase" / "docker-compose.yaml"
    containers = ["hbase-regionserver", "hbase-master"]
    log_file = RESULTS_DIR / "hbase-slow-wal.log"
    ensure_env(compose)

    print(f"\n{'=' * 60}")
    print(f"  Testing: {name}")
    print(f"{'=' * 60}")

    docker_compose_up(compose)
    # HBase needs extended startup time (ZooKeeper + HDFS + HBase)
    time.sleep(60)

    if not wait_for_healthy(containers, timeout=30):
        docker_compose_down(compose)
        return name, False

    print("  Injecting 5000ms delay on hbase-regionserver...")
    inject_delay("hbase-regionserver", 5000)
    time.sleep(60)
    clear_delay("hbase-regionserver")
    time.sleep(5)

    collect_docker_logs(containers, log_file)
    oracle = Oracle.from_file(ORACLES_DIR / "hbase-slow-wal.yaml")
    result = oracle.evaluate(artifacts={"compose": str(log_file)})
    print(
        f"  Result: reproduced={result.reproduced}, "
        f"score={result.score}, matches={len(result.matched_signals)}"
    )

    docker_compose_down(compose)
    return name, result.reproduced


# ─── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("  FAULT REPRODUCTION INTEGRATION TESTS")
    print("  Spinning up real containers and injecting faults")
    print("=" * 60)

    results: list[tuple[str, bool]] = []

    # Etcd tests
    results.append(test_etcd_raft_election())
    results.append(test_etcd_leader_lease())
    results.append(test_etcd_slow_apply())

    # CockroachDB tests
    results.append(test_crdb_raft_stepdown())
    results.append(test_crdb_disk_stall())

    # Cassandra tests
    results.append(test_cassandra_batch_throughput())

    # HBase tests
    results.append(test_hbase_slow_wal())

    # Summary
    print(f"\n{'=' * 60}")
    print("  RESULTS SUMMARY")
    print(f"{'=' * 60}")
    passed = 0
    for name, reproduced in results:
        status = "REPRODUCED" if reproduced else "NOT REPRODUCED"
        symbol = "[+]" if reproduced else "[-]"
        print(f"  {symbol} {name}: {status}")
        if reproduced:
            passed += 1

    total = len(results)
    failed = total - passed
    print(f"\n  Total: {passed} reproduced, {failed} not reproduced out of {total}")
    print(f"  Logs saved to: {RESULTS_DIR}")

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
