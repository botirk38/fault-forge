"""Network fault injection via tc netem in Docker containers."""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


class NetworkFaultInjector:
    """Inject network faults into Docker containers using tc netem.

    Replaces Blockade. Installs ``iproute2`` (provides ``tc``) in the
    target container if not present, then runs ``tc`` via ``docker exec``.
    """

    def __init__(self, docker_bin: str = "docker") -> None:
        self._docker = docker_bin
        self._tc_installed: set[str] = set()

    def inject_delay(self, container: str, delay_ms: int) -> None:
        """Add a fixed delay to all egress traffic on eth0."""
        self._ensure_tc(container)
        self._run_tc(container, f"qdisc add dev eth0 root netem delay {delay_ms}ms")

    def inject_loss(self, container: str, loss_pct: float) -> None:
        """Add random packet loss to all egress traffic on eth0."""
        self._ensure_tc(container)
        self._run_tc(container, f"qdisc add dev eth0 root netem loss {loss_pct}%")

    def clear(self, container: str) -> None:
        """Remove all tc qdisc rules from eth0."""
        try:
            self._run_tc(container, "qdisc del dev eth0 root")
        except subprocess.CalledProcessError:
            pass

    def _ensure_tc(self, container: str) -> None:
        """Install tc in the container if not already present."""
        if container in self._tc_installed:
            return
        result = subprocess.run(
            [self._docker, "exec", container, "sh", "-c", "which tc"],
            capture_output=True,
        )
        if result.returncode == 0:
            self._tc_installed.add(container)
            return
        logger.info("Installing iproute2 (tc) in container %s", container)
        # Try apt-get first (Debian/Ubuntu), then apk (Alpine)
        for cmd in [
            ["apt-get", "update", "-qq", "&&", "apt-get", "install", "-y", "-qq", "iproute2"],
            ["apk", "add", "--no-cache", "iproute2"],
        ]:
            result = subprocess.run(
                [self._docker, "exec", container, "sh", "-c", " ".join(cmd)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                self._tc_installed.add(container)
                return
        raise RuntimeError(
            f"Failed to install tc in container {container}. "
            f"Tried apt-get and apk. stderr: {result.stderr}"
        )

    def _run_tc(self, container: str, tc_args: str) -> None:
        cmd = [self._docker, "exec", container, "tc"] + tc_args.split()
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
