"""Network fault injection via tc netem in Docker containers."""

from __future__ import annotations

import logging

from injectors.base import FaultInjector

logger = logging.getLogger(__name__)


class NetworkFaultInjector(FaultInjector):
    """Inject network faults using tc netem."""

    def __init__(self, docker_bin: str = "docker") -> None:
        super().__init__(docker_bin)
        self._tc_ready: set[str] = set()

    def inject(self, target: str, **params: object) -> None:
        kind = params.get("kind")
        value = params.get("value")
        if kind == "delay":
            self.inject_delay(target, int(str(value)))
        elif kind == "loss":
            self.inject_loss(target, float(str(value)))
        else:
            raise ValueError(f"Unknown network fault kind: {kind}")

    def clear(self, target: str, **params: object) -> None:
        try:
            self._exec(target, ["tc", "qdisc", "del", "dev", "eth0", "root"])
        except Exception:
            pass

    def inject_delay(self, container: str, delay_ms: int) -> None:
        """Add fixed delay to all egress traffic on eth0."""
        self._ensure_tc(container)
        self._exec(
            container,
            [
                "tc",
                "qdisc",
                "add",
                "dev",
                "eth0",
                "root",
                "netem",
                f"delay {delay_ms}ms",
            ],
        )

    def inject_loss(self, container: str, loss_pct: float) -> None:
        """Add random packet loss to all egress traffic on eth0."""
        self._ensure_tc(container)
        self._exec(
            container,
            [
                "tc",
                "qdisc",
                "add",
                "dev",
                "eth0",
                "root",
                "netem",
                f"loss {loss_pct}%",
            ],
        )

    def _ensure_tc(self, container: str) -> None:
        """Verify tc is available in the container."""
        if container in self._tc_ready:
            return
        result = self._exec(container, ["sh", "-c", "which tc"], check=False)
        if result.returncode == 0:
            self._tc_ready.add(container)
            return
        raise RuntimeError(
            f"tc not found in container {container}. "
            "Ensure the image includes iproute2 and the container has NET_ADMIN capability."
        )
