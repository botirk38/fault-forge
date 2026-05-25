"""System specification for live Docker-based trial execution."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass(frozen=True)
class SystemSpec:
    """Defines the Docker lifecycle for a distributed system.

    Generic data model — users define specs for their own systems
    either in code or in YAML files.
    """

    name: str
    image: str
    cluster_size: int = 3
    network_name: str = ""
    start_commands: list[str] = field(default_factory=list)
    init_command: str = ""
    workload_command: str = ""
    stop_commands: list[str] = field(default_factory=list)
    node_map: dict[str, str] = field(default_factory=dict)
    startup_wait_s: int = 10
    post_inject_wait_s: int = 15

    def network(self) -> str:
        return self.network_name or f"{self.name}-net"

    @staticmethod
    def from_file(path: str | Path) -> SystemSpec:
        data = yaml.safe_load(Path(path).read_text())
        return SystemSpec.from_dict(data)

    @staticmethod
    def from_dict(data: dict[str, object]) -> SystemSpec:
        return SystemSpec(
            name=str(data["name"]),
            image=str(data["image"]),
            cluster_size=int(data.get("cluster_size", 3)),  # type: ignore[arg-type]
            network_name=str(data.get("network_name", "")),
            start_commands=list(data.get("start_commands", [])),  # type: ignore[arg-type]
            init_command=str(data.get("init_command", "")),
            workload_command=str(data.get("workload_command", "")),
            stop_commands=list(data.get("stop_commands", [])),  # type: ignore[arg-type]
            node_map=dict(data.get("node_map", {})),  # type: ignore[arg-type]
            startup_wait_s=int(data.get("startup_wait_s", 10)),  # type: ignore[arg-type]
            post_inject_wait_s=int(data.get("post_inject_wait_s", 15)),  # type: ignore[arg-type]
        )
