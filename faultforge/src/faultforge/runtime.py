"""Runtime environment configuration for FaultForge."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class RuntimeConfig:
    """Paths and binaries for the experiment runtime.

    All paths are resolved at load time. Missing required paths
    are caught by preflight, not here.
    """

    data_dir: str = "data"
    compose_root: str = "tools"
    software_root: str = "software"
    charybdefs_mount_dir: str = "/var/lib/docker/cfs_mount/tmp"
    docker_bin: str = "docker"
    docker_compose_bin: str = "docker-compose"

    def resolve(self, base: Path | None = None) -> ResolvedRuntime:
        base = base or Path.cwd()
        return ResolvedRuntime(
            data_dir=str((base / self.data_dir).resolve()),
            compose_root=str((base / self.compose_root).resolve()),
            software_root=str((base / self.software_root).resolve()),
            charybdefs_mount_dir=self.charybdefs_mount_dir,
            docker_bin=self.docker_bin,
            docker_compose_bin=self.docker_compose_bin,
        )


@dataclass
class ResolvedRuntime:
    """RuntimeConfig with all paths resolved to absolute strings."""

    data_dir: str
    compose_root: str
    software_root: str
    charybdefs_mount_dir: str
    docker_bin: str
    docker_compose_bin: str


def load_runtime(path: str | Path | None = None) -> ResolvedRuntime:
    """Load a runtime config from YAML, or return defaults."""
    if path is None:
        return RuntimeConfig().resolve()
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    fields = RuntimeConfig.__dataclass_fields__
    cfg = RuntimeConfig(**{k: v for k, v in data.items() if k in fields})
    return cfg.resolve()
