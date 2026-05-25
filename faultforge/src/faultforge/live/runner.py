"""Live trial runner — executes trials against real Docker containers.

Satisfies the RunTrial Protocol. Manages:
  1. Docker cluster lifecycle (start → stop)
  2. Fault injection via nsenter + tc netem
  3. Workload execution
  4. Log collection to temp files for oracle evaluation
"""

from __future__ import annotations

import logging
import subprocess
import tempfile
import time
from pathlib import Path

from faultforge.live.systems import SystemSpec, get_spec
from faultforge.severity import parse_severity_ms
from faultforge.trial import Trial, TrialResult

logger = logging.getLogger(__name__)


class LiveRunner:
    """Execute trials against real Docker containers.

    Usage:
        runner = LiveRunner()
        result = runner.run(trial)
        # result["artifacts"]["compose"] points to collected logs
    """

    def __init__(self, log_dir: str | None = None) -> None:
        self._log_dir = log_dir

    def run(self, trial: Trial) -> TrialResult:
        """Execute trial: start cluster, inject fault, run workload, collect logs."""
        system_name = trial["system"]["name"]
        spec = get_spec(system_name)

        try:
            self._start_cluster(spec)
            self._inject_faults(trial, spec)
            time.sleep(spec.post_inject_wait_s)
            self._run_workload(spec)
            log_path = self._collect_logs(spec, trial)

            return {
                "success": True,
                "trial": trial,
                "log_path": log_path,
                "artifacts": {"compose": log_path},
            }
        except Exception as e:
            logger.error("Trial failed: %s", e)
            return {
                "success": False,
                "trial": trial,
                "log_path": "",
                "error": str(e),
            }
        finally:
            self._stop_cluster(spec)

    def _start_cluster(self, spec: SystemSpec) -> None:
        network = spec.network()
        _sh(f"docker network create {network} 2>/dev/null || true")

        for cmd_template in spec.start_commands:
            cmd = cmd_template.format(network=network, image=spec.image)
            result = _sh(cmd)
            if result.returncode != 0:
                raise RuntimeError(f"Failed to start container: {result.stderr}")

        time.sleep(spec.startup_wait_s)

        if spec.init_command:
            if spec.init_command == "__redis_cluster_create__":
                self._init_redis_cluster(spec)
            else:
                cmd = spec.init_command.format(network=network, image=spec.image)
                _sh(cmd, timeout=30)
                time.sleep(5)

    def _init_redis_cluster(self, spec: SystemSpec) -> None:
        """Create Redis cluster from running nodes."""
        ips = []
        for i in range(1, spec.cluster_size + 1):
            result = _sh(
                f"docker inspect -f '{{{{range.NetworkSettings.Networks}}}}"
                f"{{{{.IPAddress}}}}{{{{end}}}}' redis{i}"
            )
            ip = result.stdout.strip()
            ips.append(f"{ip}:6379")

        ip_list = " ".join(ips)
        _sh(
            f"docker exec redis1 redis-cli --cluster create {ip_list}"
            f" --cluster-replicas 1 --cluster-yes",
            timeout=30,
        )
        time.sleep(3)

    def _inject_faults(self, trial: Trial, spec: SystemSpec) -> None:
        """Inject faults on target containers using nsenter + tc netem."""
        for fault in trial["faults"]:
            if fault["fault_type"] == "none":
                continue

            target = self._resolve_target(fault["location"], spec)
            delay_ms = parse_severity_ms(fault["fault_type"], fault["severity"])

            if delay_ms is None:
                logger.warning("Cannot parse severity %r, skipping", fault["severity"])
                continue

            if fault["fault_type"] == "nw":
                self._inject_network_delay(target, int(delay_ms))
            elif fault["fault_type"] == "fs":
                self._inject_network_delay(target, int(delay_ms))

    def _inject_network_delay(self, container: str, delay_ms: int) -> None:
        """Add tc netem delay to a container's network interface."""
        pid_result = _sh(f"docker inspect --format '{{{{.State.Pid}}}}' {container}")
        pid = pid_result.stdout.strip()
        if not pid or pid == "0":
            raise RuntimeError(f"Container {container} not running (pid={pid})")

        result = _sh(
            f"sudo nsenter -t {pid} -n tc qdisc add dev eth0 root netem delay {delay_ms}ms"
        )
        if result.returncode != 0:
            _sh(f"sudo nsenter -t {pid} -n tc qdisc replace dev eth0 root netem delay {delay_ms}ms")

        logger.info("Injected %dms delay on %s (pid=%s)", delay_ms, container, pid)

    def _resolve_target(self, location: str, spec: SystemSpec) -> str:
        """Map a fault location (e.g., 'node1', 'leader') to container name."""
        name = spec.name
        node_map: dict[str, dict[str, str]] = {
            "etcd": {
                "node1": "etcd1",
                "node2": "etcd2",
                "node3": "etcd3",
                "leader": "etcd1",
                "follower": "etcd2",
            },
            "zookeeper": {
                "node1": "zk1",
                "node2": "zk2",
                "node3": "zk3",
                "leader": "zk1",
                "follower": "zk2",
            },
            "mongodb": {
                "node1": "mongo1",
                "node2": "mongo2",
                "node3": "mongo3",
                "primary": "mongo1",
                "secondary": "mongo2",
            },
            "redis": {
                "node1": "redis1",
                "node2": "redis2",
                "node3": "redis3",
                "master1": "redis1",
                "master2": "redis2",
                "replica1": "redis4",
            },
            "tikv": {
                "node1": "tikv1",
                "node2": "tikv2",
                "node3": "tikv3",
                "leader": "tikv1",
                "follower": "tikv2",
            },
            "cassandra": {"node1": "cass1", "node2": "cass2", "node3": "cass3"},
            "kafka": {
                "node1": "kafka1",
                "node2": "kafka2",
                "node3": "kafka3",
                "broker1": "kafka1",
                "broker2": "kafka2",
            },
        }
        mapping = node_map.get(name, {})
        container = mapping.get(location, location)
        return container

    def _run_workload(self, spec: SystemSpec) -> None:
        """Execute the system's workload command."""
        if spec.workload_command:
            _sh(spec.workload_command, timeout=60)

    def _collect_logs(self, spec: SystemSpec, trial: Trial) -> str:
        """Collect container logs into a single file for oracle evaluation."""
        if self._log_dir:
            log_dir = Path(self._log_dir)
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"{trial['trial_id']}.log"
        else:
            fd, path = tempfile.mkstemp(suffix=".log", prefix=f"live-{spec.name}-")
            log_file = Path(path)

        containers = self._get_running_containers(spec)
        with open(log_file, "w") as f:
            for container in containers:
                result = _sh(f"docker logs {container} 2>&1")
                f.write(f"=== {container} ===\n")
                f.write(result.stdout)
                f.write("\n")

        return str(log_file)

    def _get_running_containers(self, spec: SystemSpec) -> list[str]:
        """List containers belonging to this system's network."""
        network = spec.network()
        result = _sh(
            f"docker network inspect {network}"
            f" --format '{{{{range .Containers}}}}{{{{.Name}}}} {{{{end}}}}'"
        )
        if result.returncode != 0:
            return []
        return result.stdout.strip().split()

    def _stop_cluster(self, spec: SystemSpec) -> None:
        """Tear down all containers and network."""
        network = spec.network()
        for cmd_template in spec.stop_commands:
            cmd = cmd_template.format(network=network, image=spec.image)
            _sh(cmd)


def _sh(cmd: str, timeout: int = 120) -> subprocess.CompletedProcess[str]:
    """Run a shell command, capturing output."""
    return subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
