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

from faultforge.live.systems import SystemSpec
from faultforge.severity import parse_severity_ms
from faultforge.trial import Trial, TrialResult

logger = logging.getLogger(__name__)


class LiveRunner:
    """Execute trials against real Docker containers.

    Requires a SystemSpec defining the cluster lifecycle. The runner is
    generic — it works with any system that can be expressed as a SystemSpec.

    Usage:
        spec = SystemSpec.from_file("etcd.yaml")
        runner = LiveRunner(spec)
        result = runner.run(trial)
    """

    def __init__(self, spec: SystemSpec, *, log_dir: str | None = None) -> None:
        self._spec = spec
        self._log_dir = log_dir

    def run(self, trial: Trial) -> TrialResult:
        """Execute trial: start cluster, inject fault, run workload, collect logs."""
        spec = self._spec

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
            cmd = spec.init_command.format(network=network, image=spec.image)
            _sh(cmd, timeout=30)
            time.sleep(5)

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

            if fault["fault_type"] in ("nw", "fs"):
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
        """Map a fault location to a container name using the spec's node_map."""
        container = spec.node_map.get(location, location)
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
