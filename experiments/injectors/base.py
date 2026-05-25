"""Base fault injector interface."""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class FaultInjector(ABC):
    """Base class for domain-specific fault injectors."""

    def __init__(self, docker_bin: str = "docker") -> None:
        self._docker = docker_bin

    @abstractmethod
    def inject(self, target: str, **params: object) -> None:
        """Inject a fault into the given target container."""

    @abstractmethod
    def clear(self, target: str, **params: object) -> None:
        """Remove the fault from the given target container."""

    def _run(
        self,
        cmd: list[str],
        *,
        check: bool = True,
        capture_output: bool = True,
        text: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a subprocess command with consistent logging."""
        logger.debug("Running: %s", " ".join(cmd))
        return subprocess.run(
            cmd,
            check=check,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
        )

    def _exec(
        self,
        container: str,
        inner_cmd: list[str],
        *,
        check: bool = True,
        capture_output: bool = True,
        text: bool = True,
        timeout: int | None = None,
    ) -> subprocess.CompletedProcess:
        """Run a command inside a container via docker exec."""
        return self._run(
            [self._docker, "exec", container] + inner_cmd,
            check=check,
            capture_output=capture_output,
            text=text,
            timeout=timeout,
        )
