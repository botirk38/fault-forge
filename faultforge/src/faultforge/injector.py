"""Network fault injection via tc netem in Docker containers."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


class NetworkFaultInjector:
    """Inject network faults into Docker containers using tc netem.

    Replaces Blockade. Uses ``nsenter`` to run ``tc`` in the container's
    network namespace from the host, avoiding the need for ``tc`` inside
    the container image.
    """

    def __init__(self, docker_bin: str = "docker") -> None:
        self._docker = docker_bin

    def inject_delay(self, container: str, delay_ms: int) -> None:
        """Add a fixed delay to all egress traffic on eth0."""
        self._run_tc(container, f"qdisc add dev eth0 root netem delay {delay_ms}ms")

    def inject_loss(self, container: str, loss_pct: float) -> None:
        """Add random packet loss to all egress traffic on eth0."""
        self._run_tc(container, f"qdisc add dev eth0 root netem loss {loss_pct}%")

    def clear(self, container: str) -> None:
        """Remove all tc qdisc rules from eth0."""
        try:
            self._run_tc(container, "qdisc del dev eth0 root")
        except subprocess.CalledProcessError:
            pass

    def _get_pid(self, container: str) -> str:
        result = subprocess.run(
            [self._docker, "inspect", "-f", "{{.State.Pid}}", container],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _run_tc(self, container: str, tc_args: str) -> None:
        pid = self._get_pid(container)
        cmd = ["nsenter", "-t", pid, "-n", "tc"] + tc_args.split()
        logger.info("Running: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, capture_output=True, text=True)


def parse_severity(severity: str) -> tuple[str, int | float]:
    """Parse a severity string like 'slow-100ms' or 'loss-5pct'.

    Returns (fault_kind, value).
    """
    if severity.startswith("slow-"):
        val = severity.replace("slow-", "").replace("ms", "")
        return ("delay", int(val))
    if severity.startswith("loss-"):
        val = severity.replace("loss-", "").replace("pct", "")
        return ("loss", float(val))
    raise ValueError(f"Unknown severity format: {severity}")
