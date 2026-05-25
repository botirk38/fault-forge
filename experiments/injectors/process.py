"""Process fault injection via Docker container lifecycle."""

from __future__ import annotations

import logging

from injectors.base import FaultInjector

logger = logging.getLogger(__name__)


class ProcessFaultInjector(FaultInjector):
    """Inject process faults via Docker stop/restart/kill."""

    def inject(self, target: str, **params: object) -> None:
        kind = str(params.get("kind", "restart"))
        if kind == "restart":
            self.restart(target)
        elif kind == "stop":
            self.stop(target)
        elif kind == "kill":
            signal = str(params.get("signal", "SIGKILL"))
            self.kill(target, signal=signal)
        else:
            raise ValueError(f"Unknown process fault kind: {kind}")

    def clear(self, target: str, **params: object) -> None:
        """Start the container if it was stopped."""
        try:
            self._run([self._docker, "start", target])
        except Exception:
            pass

    def restart(self, container: str) -> None:
        self._run([self._docker, "restart", container])

    def stop(self, container: str) -> None:
        self._run([self._docker, "stop", container])

    def kill(self, container: str, signal: str = "SIGKILL") -> None:
        self._run([self._docker, "kill", f"--signal={signal}", container])
