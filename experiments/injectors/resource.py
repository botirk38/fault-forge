"""Resource fault injection via Docker cgroup controls."""

from __future__ import annotations

import logging

from injectors.base import FaultInjector

logger = logging.getLogger(__name__)


class ResourceFaultInjector(FaultInjector):
    """Inject CPU/memory faults using docker update."""

    def __init__(self, docker_bin: str = "docker") -> None:
        super().__init__(docker_bin)
        self._baselines: dict[str, dict[str, str]] = {}

    def inject(self, target: str, **params: object) -> None:
        kind = params.get("kind")
        value = params.get("value")
        if kind == "cpu":
            self.inject_cpu(target, str(value))
        elif kind == "mem":
            self.inject_mem(target, str(value))
        else:
            raise ValueError(f"Unknown resource fault kind: {kind}")

    def clear(self, target: str, **params: object) -> None:
        baseline = self._baselines.pop(target, {})
        if "cpu" in baseline:
            self._run([self._docker, "update", f"--cpus={baseline['cpu']}", target])
        if "mem" in baseline:
            self._run([self._docker, "update", f"--memory={baseline['mem']}", target])

    def inject_cpu(self, container: str, cpus: str) -> None:
        """Throttle container CPU to the given limit."""
        self._capture_baseline(container, "cpu")
        self._run([self._docker, "update", f"--cpus={cpus}", container])

    def inject_mem(self, container: str, memory: str) -> None:
        """Limit container memory to the given value."""
        self._capture_baseline(container, "mem")
        self._run([self._docker, "update", f"--memory={memory}", container])

    def _capture_baseline(self, container: str, kind: str) -> None:
        """Record the current resource setting for later restoration."""
        if container not in self._baselines:
            self._baselines[container] = {}
        if kind in self._baselines[container]:
            return
        try:
            result = self._run(
                [self._docker, "inspect", "--format", "{{.HostConfig.Cpus}}", container],
                check=False,
            )
            cpus = result.stdout.strip()
            if cpus and cpus != "0":
                self._baselines[container]["cpu"] = cpus
        except Exception:
            pass
        try:
            result = self._run(
                [self._docker, "inspect", "--format", "{{.HostConfig.Memory}}", container],
                check=False,
            )
            mem = result.stdout.strip()
            if mem and mem != "0":
                self._baselines[container]["mem"] = f"{mem}"
        except Exception:
            pass
