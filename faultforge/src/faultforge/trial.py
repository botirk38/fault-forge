"""Canonical trial model and configuration for FaultForge."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal

type SlowFaultKind = Literal["nw", "fs", "cpu", "mem", "process", "none"]


@dataclass
class SlowFault:
    """Single environmental slow fault (network/filesystem/baseline)."""

    fault_type: SlowFaultKind
    location: str
    duration_s: int
    severity: str
    start_s: int = 0
    if_restart: bool = False

    @classmethod
    def network(
        cls,
        location: str,
        severity: str,
        duration_s: int,
        start_s: int = 0,
        if_restart: bool = False,
    ) -> SlowFault:
        return cls(
            fault_type="nw",
            location=location,
            duration_s=duration_s,
            severity=severity,
            start_s=start_s,
            if_restart=if_restart,
        )

    @classmethod
    def filesystem(
        cls,
        location: str,
        severity: str,
        duration_s: int,
        start_s: int = 0,
        if_restart: bool = False,
    ) -> SlowFault:
        return cls(
            fault_type="fs",
            location=location,
            duration_s=duration_s,
            severity=severity,
            start_s=start_s,
            if_restart=if_restart,
        )

    @classmethod
    def cpu(
        cls,
        location: str,
        cpus: str,
        duration_s: int,
        start_s: int = 0,
        if_restart: bool = False,
    ) -> SlowFault:
        return cls(
            fault_type="cpu",
            location=location,
            duration_s=duration_s,
            severity=f"cpus-{cpus}",
            start_s=start_s,
            if_restart=if_restart,
        )

    @classmethod
    def memory(
        cls,
        location: str,
        memory: str,
        duration_s: int,
        start_s: int = 0,
        if_restart: bool = False,
    ) -> SlowFault:
        return cls(
            fault_type="mem",
            location=location,
            duration_s=duration_s,
            severity=f"memory-{memory}",
            start_s=start_s,
            if_restart=if_restart,
        )

    @classmethod
    def process(
        cls,
        location: str,
        action: str = "restart",
        duration_s: int = 0,
        start_s: int = 0,
        if_restart: bool = False,
    ) -> SlowFault:
        return cls(
            fault_type="process",
            location=location,
            duration_s=duration_s,
            severity=action,
            start_s=start_s,
            if_restart=if_restart,
        )

    @property
    def end_s(self) -> int:
        return self.start_s + self.duration_s if self.duration_s != -1 else -1

    @property
    def info(self) -> str:
        if self.fault_type == "none":
            return self.fault_type
        if self.duration_s == -1:
            return f"{self.fault_type}-{self.severity}-none"
        prefix = "restart-" if self.if_restart else ""
        return (
            f"{prefix}{self.fault_type}-{self.severity}"
            f"-dur{self.duration_s}-{self.start_s}-{self.end_s}"
        )

    def get_info(self) -> str:
        return json.dumps(self.__dict__, indent=4)


@dataclass
class ResourceLimit:
    """CPU and memory limits for containers."""

    cpu_limit: str
    mem_limit: str


@dataclass
class SystemConfig:
    """Target system configuration."""

    name: str
    version: str | None = None
    cluster_size: int = 3
    data_dir: str = "default"
    coverage: bool = False
    change_workload: bool = False
    if_iaso: str = "none"


@dataclass
class BenchmarkConfig:
    """Benchmark configuration."""

    name: str
    exec_time_s: int = 150
    kwargs: dict[str, str | int] = field(default_factory=dict)

    @classmethod
    def ycsb(
        cls,
        workload: str = "mixed",
        exec_time_s: int = 150,
        recordcount: str = "10000",
        operationcount: str = "500000000",
        **extra: str | int,
    ) -> BenchmarkConfig:
        return cls(
            name="ycsb",
            exec_time_s=exec_time_s,
            kwargs={
                "workload": workload,
                "recordcount": recordcount,
                "operationcount": operationcount,
                **extra,
            },
        )

    @classmethod
    def mrbench(
        cls,
        exec_time_s: int = 150,
        num_iter: int = 10,
        num_reduces: str = "3",
    ) -> BenchmarkConfig:
        return cls(
            name="mrbench",
            exec_time_s=exec_time_s,
            kwargs={"num_iter": num_iter, "num_reduces": num_reduces},
        )

    @classmethod
    def terasort(
        cls,
        exec_time_s: int = 150,
        num_rows: str = "10737418",
        input_dir: str = "/input",
        output_dir: str = "/output",
    ) -> BenchmarkConfig:
        return cls(
            name="terasort",
            exec_time_s=exec_time_s,
            kwargs={
                "num_of_100_byte_rows": num_rows,
                "input_dir": input_dir,
                "output_dir": output_dir,
            },
        )

    @classmethod
    def perf_test(
        cls,
        exec_time_s: int = 150,
        replication_factor: str = "3",
        topic_partition: str = "10",
        throughput_upper_bound: int = 10000,
        num_msg: int = 14000000,
    ) -> BenchmarkConfig:
        return cls(
            name="perf_test",
            exec_time_s=exec_time_s,
            kwargs={
                "replication_factor": replication_factor,
                "topic_partition": topic_partition,
                "throughput_upper_bound": throughput_upper_bound,
                "num_msg": num_msg,
            },
        )

    @classmethod
    def openmsg(
        cls,
        exec_time_s: int = 150,
        driver: str = "kafka-latency",
        workload_file: str = "simple-workload",
    ) -> BenchmarkConfig:
        return cls(
            name="openmsg",
            exec_time_s=exec_time_s,
            kwargs={"driver": driver, "workload_file": workload_file},
        )

    @classmethod
    def sysbench(
        cls,
        exec_time_s: int = 150,
        lua_scheme: str = "oltp_write_only",
        table_size: int = 10000,
        num_table: int = 1,
        num_thread: int = 1,
        report_interval: int = 1,
    ) -> BenchmarkConfig:
        return cls(
            name="sysbench",
            exec_time_s=exec_time_s,
            kwargs={
                "lua_scheme": lua_scheme,
                "table_size": table_size,
                "num_table": num_table,
                "num_thread": num_thread,
                "report_interval": report_interval,
            },
        )

    @classmethod
    def etcd_official(
        cls,
        workload: str = "lease-keepalive",
        total: int = 800000,
        max_execution_time: int = 600,
        isolation: str = "r",
        stm_locker: str = "stm",
        num_watchers: int = 1000000,
    ) -> BenchmarkConfig:
        return cls(
            name="etcd-official",
            exec_time_s=max_execution_time,
            kwargs={
                "workload": workload,
                "total": total,
                "isolation": isolation,
                "stm_locker": stm_locker,
                "num_watchers": num_watchers,
            },
        )

    @classmethod
    def depfast(
        cls,
        exec_time_s: int = 150,
        concurrency: int = 100,
        scheme: str = "fpga_raft",
        nclient: int = 1,
    ) -> BenchmarkConfig:
        return cls(
            name="depfast",
            exec_time_s=exec_time_s,
            kwargs={
                "concurrency": concurrency,
                "scheme": scheme,
                "nclient": nclient,
            },
        )

    @classmethod
    def copilot(
        cls,
        exec_time_s: int = 150,
        concurrency: int = 10,
        scheme: str = "copilot",
        nclient: int = 1,
        trim_ratio: str = "0",
    ) -> BenchmarkConfig:
        return cls(
            name="copilot",
            exec_time_s=exec_time_s,
            kwargs={
                "concurrency": concurrency,
                "scheme": scheme,
                "nclient": nclient,
                "trim_ratio": trim_ratio,
            },
        )


@dataclass
class TrialPaths:
    """Directory paths used during a trial."""

    log_root_dir: str = ""
    install_root: str = ""
    tooling_root: str = ""
    software_dir: str = ""
    tools_dir: str = ""
    charybdefs_mount_dir: str = "/var/lib/docker/cfs_mount/tmp"


@dataclass
class Trial:
    """Executable fault trial emitted by search and run by TrialRunner."""

    trial_id: str
    system: SystemConfig
    benchmark: BenchmarkConfig
    faults: list[SlowFault]
    issue_id: str = ""
    resource: ResourceLimit = field(
        default_factory=lambda: ResourceLimit(cpu_limit="4", mem_limit="32G")
    )
    paths: TrialPaths | None = None
    iteration: int = 1
    version: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Trial:
        """Deserialize a Trial from a JSON-compatible dict."""
        sys_data: dict[str, Any] = data.get("system") or {}
        system = SystemConfig(
            name=sys_data.get("name", "unknown"),
            version=sys_data.get("version"),
            cluster_size=sys_data.get("cluster_size", 3),
        )
        bm_data: dict[str, Any] = data.get("benchmark") or {}
        benchmark = BenchmarkConfig(
            name=bm_data.get("name", "ycsb"),
            exec_time_s=bm_data.get("exec_time_s", 150),
            kwargs=bm_data.get("kwargs", {}),
        )
        raw_faults: list[dict[str, Any]] = data.get("faults") or []
        faults = [
            SlowFault(
                fault_type=f["fault_type"],
                location=f["location"],
                duration_s=f["duration_s"],
                severity=f["severity"],
                start_s=f.get("start_s", 0),
                if_restart=f.get("if_restart", False),
            )
            for f in raw_faults
        ]
        res_data: dict[str, Any] = data.get("resource") or {}
        resource = ResourceLimit(
            cpu_limit=res_data.get("cpu_limit", "4"),
            mem_limit=res_data.get("mem_limit", "32G"),
        )
        return cls(
            trial_id=data.get("trial_id", "trial"),
            system=system,
            benchmark=benchmark,
            faults=faults,
            issue_id=data.get("issue_id", ""),
            resource=resource,
        )


@dataclass
class TrialResult:
    """Result of executing a single trial."""

    success: bool
    trial: Trial
    log_path: str | None = None
    artifacts: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)
