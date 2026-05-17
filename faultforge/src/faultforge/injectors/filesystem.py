"""Filesystem fault injection via CharybdeFS."""

from __future__ import annotations

import logging
import subprocess

from faultforge.injectors.base import FaultInjector

logger = logging.getLogger(__name__)


class FilesystemFaultInjector(FaultInjector):
    """Inject filesystem faults via CharybdeFS inject_client.

    CharybdeFS is a FUSE-based fault injection filesystem that intercepts
    syscalls and adds configurable delays or failures.

    Usage requires:
    - CharybdeFS source built and available at cfs_source path
    - CharybdeFS running and mounted for the target container's volume
    - Container data directory accessible through the FUSE mount
    """

    def __init__(self, docker_bin: str = "docker", cfs_source: str = "") -> None:
        super().__init__(docker_bin)
        self._cfs_source = cfs_source

    def inject(self, target: str, **params: object) -> None:
        delay = params.get("delay")
        pattern = params.get("pattern")
        if delay is None:
            raise ValueError("Filesystem fault requires 'delay' parameter (microseconds)")
        self._run_inject(delay=str(delay), pattern=str(pattern) if pattern else None)

    def clear(self, target: str, **params: object) -> None:
        self._run_clear()

    def _run_inject(self, delay: str, pattern: str | None = None) -> None:
        cmd = ["./inject_client", "--delay", delay]
        if pattern:
            cmd += ["--pattern", pattern]
        logger.info("Running CharybdeFS inject: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, cwd=self._cfs_source)

    def _run_clear(self) -> None:
        cmd = ["./inject_client", "--clear"]
        logger.info("Running CharybdeFS clear: %s", " ".join(cmd))
        subprocess.run(cmd, check=True, cwd=self._cfs_source)
