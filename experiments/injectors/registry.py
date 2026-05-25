"""Registry mapping fault domain to injector instance."""

from __future__ import annotations

from injectors.base import FaultInjector
from injectors.filesystem import FilesystemFaultInjector
from injectors.network import NetworkFaultInjector
from injectors.process import ProcessFaultInjector
from injectors.resource import ResourceFaultInjector

DOMAIN_MAP: dict[str, type[FaultInjector]] = {
    "nw": NetworkFaultInjector,
    "fs": FilesystemFaultInjector,
    "cpu": ResourceFaultInjector,
    "mem": ResourceFaultInjector,
    "process": ProcessFaultInjector,
}


class InjectorRegistry:
    """Create and cache injector instances per domain."""

    def __init__(
        self,
        docker_bin: str = "docker",
        cfs_source: str = "",
    ) -> None:
        self._docker = docker_bin
        self._cfs_source = cfs_source
        self._injectors: dict[str, FaultInjector] = {}

    def get(self, domain: str) -> FaultInjector:
        cls = DOMAIN_MAP.get(domain)
        if cls is None:
            raise ValueError(f"Unknown fault domain: {domain}")
        if domain not in self._injectors:
            if cls is FilesystemFaultInjector:
                self._injectors[domain] = cls(self._docker, self._cfs_source)
            else:
                self._injectors[domain] = cls(self._docker)
        return self._injectors[domain]

    def inject(self, domain: str, target: str, **params: object) -> None:
        self.get(domain).inject(target, **params)

    def clear(self, domain: str, target: str, **params: object) -> None:
        self.get(domain).clear(target, **params)
