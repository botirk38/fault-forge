"""System specification for live Docker-based trial execution.

SystemSpec is the generic data model — users define their own specs
for any distributed system. The library does not ship hardcoded specs.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SystemSpec:
    """Defines the Docker lifecycle for a distributed system.

    This is a generic data model. Users define specs for their own systems
    either in code or in YAML files.

    Attributes:
        name: Human-readable system identifier (e.g., "etcd").
        image: Docker image to use (e.g., "quay.io/coreos/etcd:v3.5.10").
        cluster_size: Number of nodes in the cluster.
        network_name: Docker network name. Defaults to "{name}-net".
        start_commands: Shell commands to start containers.
            Use {network} and {image} placeholders.
        init_command: Optional post-start initialization command.
        workload_command: Command to generate workload during trials.
        stop_commands: Shell commands to tear down containers.
        node_map: Maps logical locations ("node1", "leader") to container names.
        startup_wait_s: Seconds to wait after starting containers.
        post_inject_wait_s: Seconds to wait after fault injection.
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
        """Load a SystemSpec from a YAML file."""
        data = yaml.safe_load(Path(path).read_text())
        return SystemSpec.from_dict(data)

    @staticmethod
    def from_dict(data: dict[str, Any]) -> SystemSpec:
        """Construct a SystemSpec from a dict (e.g., parsed YAML)."""
        return SystemSpec(
            name=data["name"],
            image=data["image"],
            cluster_size=data.get("cluster_size", 3),
            network_name=data.get("network_name", ""),
            start_commands=data.get("start_commands", []),
            init_command=data.get("init_command", ""),
            workload_command=data.get("workload_command", ""),
            stop_commands=data.get("stop_commands", []),
            node_map=data.get("node_map", {}),
            startup_wait_s=data.get("startup_wait_s", 10),
            post_inject_wait_s=data.get("post_inject_wait_s", 15),
        )
