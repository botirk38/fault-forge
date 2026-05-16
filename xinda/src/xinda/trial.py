"""Trial model and configuration dataclasses for Xinda SDK."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SlowFault:
    """Configuration for a slow fault injection."""

    fault_type: str  # "nw", "fs", "none"
    location: str  # e.g. "leader", "datanode"
    duration_s: int
    severity: str  # e.g. "slow-100ms", "10000"
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


@dataclass
class ResourceLimit:
    """CPU and memory limits for containers."""

    cpu_limit: str
    mem_limit: str


@dataclass
class SystemConfig:
    """Target system configuration."""

    name: str  # cassandra, hbase, hadoop, etcd, crdb, kafka, depfast, copilot
    version: str | None = None
    cluster_size: int = 3
    data_dir: str = "default"
    coverage: bool = False
    change_workload: bool = False
    if_iaso: str = "none"  # "reboot", "shutdown", "none"


@dataclass
class BenchmarkConfig:
    """Benchmark configuration.

    Use one of the factory methods or pass raw kwargs for advanced cases.
    """

    name: str  # ycsb, mrbench, terasort, perf_test, etc.
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
    xinda_software_dir: str = ""
    xinda_tools_dir: str = ""
    charybdefs_mount_dir: str = "/var/lib/docker/cfs_mount/tmp"

    @classmethod
    def defaults(cls, data_dir: str = "default") -> TrialPaths:
        home = Path.home()
        return cls(
            log_root_dir=str(home / "workdir" / "data" / data_dir),
            xinda_software_dir=str(home / "workdir" / "xinda-software"),
            xinda_tools_dir=str(home / "workdir" / "xinda" / "tools"),
        )


@dataclass
class Trial:
    """Complete configuration for a single Xinda trial."""

    system: SystemConfig
    benchmark: BenchmarkConfig
    fault: SlowFault
    resource: ResourceLimit = field(
        default_factory=lambda: ResourceLimit(cpu_limit="4", mem_limit="32G")
    )
    paths: TrialPaths = field(default_factory=TrialPaths.defaults)
    iteration: int = 1
    version: str | None = None

    def data_dir(self) -> str:
        return self.system.data_dir


@dataclass
class TrialResult:
    """Result of a single trial."""

    success: bool
    system: SystemConfig
    benchmark: BenchmarkConfig
    fault: SlowFault
    log_path: str | None = None
    error: str | None = None
    metadata: dict = field(default_factory=dict)
