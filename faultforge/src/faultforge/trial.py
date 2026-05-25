"""Canonical trial model and configuration for FaultForge.

All data structures are TypedDicts — plain dicts with type annotations.
JSON serialization is trivial: json.loads() produces them directly.
"""

from __future__ import annotations

import json
from typing import Literal, NotRequired, TypedDict, cast

type SlowFaultKind = Literal["nw", "fs", "cpu", "mem", "process", "none"]


# ---------------------------------------------------------------------------
# Core types
# ---------------------------------------------------------------------------


class SlowFault(TypedDict):
    """Single environmental slow fault."""

    fault_type: SlowFaultKind
    location: str
    duration_s: int
    severity: str
    start_s: int
    if_restart: bool


class ResourceLimit(TypedDict):
    """CPU and memory limits for containers."""

    cpu_limit: str
    mem_limit: str


class SystemConfig(TypedDict):
    """Target system configuration."""

    name: str
    version: NotRequired[str | None]
    cluster_size: NotRequired[int]
    data_dir: NotRequired[str]
    coverage: NotRequired[bool]
    change_workload: NotRequired[bool]
    if_iaso: NotRequired[str]


class BenchmarkConfig(TypedDict):
    """Benchmark configuration."""

    name: str
    exec_time_s: NotRequired[int]
    kwargs: NotRequired[dict[str, str | int]]


class TrialPaths(TypedDict, total=False):
    """Directory paths used during a trial."""

    log_root_dir: str
    install_root: str
    tooling_root: str
    software_dir: str
    tools_dir: str
    charybdefs_mount_dir: str


class Trial(TypedDict):
    """Executable fault trial emitted by search and run by TrialRunner."""

    trial_id: str
    system: SystemConfig
    benchmark: BenchmarkConfig
    faults: list[SlowFault]
    issue_id: NotRequired[str]
    resource: NotRequired[ResourceLimit]
    paths: NotRequired[TrialPaths | None]
    iteration: NotRequired[int]
    version: NotRequired[str | None]


class TrialResult(TypedDict):
    """Result of executing a single trial."""

    success: bool
    trial: Trial
    log_path: NotRequired[str | None]
    artifacts: NotRequired[dict[str, str]]
    error: NotRequired[str | None]
    metadata: NotRequired[dict[str, object]]


# ---------------------------------------------------------------------------
# Factory functions
# ---------------------------------------------------------------------------


def make_fault(
    fault_type: SlowFaultKind,
    location: str,
    duration_s: int,
    severity: str,
    start_s: int = 0,
    if_restart: bool = False,
) -> SlowFault:
    """Create a SlowFault with defaults filled in."""
    return {
        "fault_type": fault_type,
        "location": location,
        "duration_s": duration_s,
        "severity": severity,
        "start_s": start_s,
        "if_restart": if_restart,
    }


def make_nw_fault(
    location: str,
    severity: str,
    duration_s: int,
    start_s: int = 0,
    if_restart: bool = False,
) -> SlowFault:
    return make_fault("nw", location, duration_s, severity, start_s, if_restart)


def make_fs_fault(
    location: str,
    severity: str,
    duration_s: int,
    start_s: int = 0,
    if_restart: bool = False,
) -> SlowFault:
    return make_fault("fs", location, duration_s, severity, start_s, if_restart)


def make_cpu_fault(
    location: str,
    cpus: str,
    duration_s: int,
    start_s: int = 0,
    if_restart: bool = False,
) -> SlowFault:
    return make_fault("cpu", location, duration_s, f"cpus-{cpus}", start_s, if_restart)


def make_mem_fault(
    location: str,
    memory: str,
    duration_s: int,
    start_s: int = 0,
    if_restart: bool = False,
) -> SlowFault:
    return make_fault("mem", location, duration_s, f"memory-{memory}", start_s, if_restart)


def make_process_fault(
    location: str,
    action: str = "restart",
    duration_s: int = 0,
    start_s: int = 0,
    if_restart: bool = False,
) -> SlowFault:
    return make_fault("process", location, duration_s, action, start_s, if_restart)


def make_trial(
    trial_id: str,
    system: SystemConfig,
    benchmark: BenchmarkConfig,
    faults: list[SlowFault],
    issue_id: str = "",
) -> Trial:
    """Create a Trial with required fields."""
    return {
        "trial_id": trial_id,
        "system": system,
        "benchmark": benchmark,
        "faults": faults,
        "issue_id": issue_id,
    }


def make_result(
    success: bool,
    trial: Trial,
    log_path: str | None = None,
    artifacts: dict[str, str] | None = None,
    error: str | None = None,
) -> TrialResult:
    """Create a TrialResult."""
    result: TrialResult = {"success": success, "trial": trial}
    if log_path is not None:
        result["log_path"] = log_path
    if artifacts is not None:
        result["artifacts"] = artifacts
    if error is not None:
        result["error"] = error
    return result


# ---------------------------------------------------------------------------
# Benchmark presets
# ---------------------------------------------------------------------------


def bench_ycsb(
    workload: str = "mixed",
    exec_time_s: int = 150,
    recordcount: str = "10000",
    operationcount: str = "500000000",
    **extra: str | int,
) -> BenchmarkConfig:
    return {
        "name": "ycsb",
        "exec_time_s": exec_time_s,
        "kwargs": {
            "workload": workload,
            "recordcount": recordcount,
            "operationcount": operationcount,
            **extra,
        },
    }


def bench_mrbench(
    exec_time_s: int = 150,
    num_iter: int = 10,
    num_reduces: str = "3",
) -> BenchmarkConfig:
    return {
        "name": "mrbench",
        "exec_time_s": exec_time_s,
        "kwargs": {"num_iter": num_iter, "num_reduces": num_reduces},
    }


def bench_terasort(
    exec_time_s: int = 150,
    num_rows: str = "10737418",
    input_dir: str = "/input",
    output_dir: str = "/output",
) -> BenchmarkConfig:
    return {
        "name": "terasort",
        "exec_time_s": exec_time_s,
        "kwargs": {
            "num_of_100_byte_rows": num_rows,
            "input_dir": input_dir,
            "output_dir": output_dir,
        },
    }


def bench_perf_test(
    exec_time_s: int = 150,
    replication_factor: str = "3",
    topic_partition: str = "10",
    throughput_upper_bound: int = 10000,
    num_msg: int = 14000000,
) -> BenchmarkConfig:
    return {
        "name": "perf_test",
        "exec_time_s": exec_time_s,
        "kwargs": {
            "replication_factor": replication_factor,
            "topic_partition": topic_partition,
            "throughput_upper_bound": throughput_upper_bound,
            "num_msg": num_msg,
        },
    }


def bench_openmsg(
    exec_time_s: int = 150,
    driver: str = "kafka-latency",
    workload_file: str = "simple-workload",
) -> BenchmarkConfig:
    return {
        "name": "openmsg",
        "exec_time_s": exec_time_s,
        "kwargs": {"driver": driver, "workload_file": workload_file},
    }


def bench_sysbench(
    exec_time_s: int = 150,
    lua_scheme: str = "oltp_write_only",
    table_size: int = 10000,
    num_table: int = 1,
    num_thread: int = 1,
    report_interval: int = 1,
) -> BenchmarkConfig:
    return {
        "name": "sysbench",
        "exec_time_s": exec_time_s,
        "kwargs": {
            "lua_scheme": lua_scheme,
            "table_size": table_size,
            "num_table": num_table,
            "num_thread": num_thread,
            "report_interval": report_interval,
        },
    }


def bench_etcd_official(
    workload: str = "lease-keepalive",
    total: int = 800000,
    max_execution_time: int = 600,
    isolation: str = "r",
    stm_locker: str = "stm",
    num_watchers: int = 1000000,
) -> BenchmarkConfig:
    return {
        "name": "etcd-official",
        "exec_time_s": max_execution_time,
        "kwargs": {
            "workload": workload,
            "total": total,
            "isolation": isolation,
            "stm_locker": stm_locker,
            "num_watchers": num_watchers,
        },
    }


def bench_depfast(
    exec_time_s: int = 150,
    concurrency: int = 100,
    scheme: str = "fpga_raft",
    nclient: int = 1,
) -> BenchmarkConfig:
    return {
        "name": "depfast",
        "exec_time_s": exec_time_s,
        "kwargs": {"concurrency": concurrency, "scheme": scheme, "nclient": nclient},
    }


def bench_copilot(
    exec_time_s: int = 150,
    concurrency: int = 10,
    scheme: str = "copilot",
    nclient: int = 1,
    trim_ratio: str = "0",
) -> BenchmarkConfig:
    return {
        "name": "copilot",
        "exec_time_s": exec_time_s,
        "kwargs": {
            "concurrency": concurrency,
            "scheme": scheme,
            "nclient": nclient,
            "trim_ratio": trim_ratio,
        },
    }


# ---------------------------------------------------------------------------
# Computed helpers (replacements for former @property methods)
# ---------------------------------------------------------------------------


def fault_end_s(fault: SlowFault) -> int:
    """End time in seconds."""
    return fault["start_s"] + fault["duration_s"] if fault["duration_s"] != -1 else -1


def fault_info(fault: SlowFault) -> str:
    """Human-readable fault summary string."""
    if fault["fault_type"] == "none":
        return "none"
    if fault["duration_s"] == -1:
        return f"{fault['fault_type']}-{fault['severity']}-none"
    prefix = "restart-" if fault["if_restart"] else ""
    end = fault_end_s(fault)
    return (
        f"{prefix}{fault['fault_type']}-{fault['severity']}"
        f"-dur{fault['duration_s']}-{fault['start_s']}-{end}"
    )


def fault_get_info(fault: SlowFault) -> str:
    """JSON representation of fault."""
    return json.dumps(fault, indent=4)


# ---------------------------------------------------------------------------
# JSON loading (fills defaults for optional fields)
# ---------------------------------------------------------------------------


def load_trial(data: dict[str, object]) -> Trial:
    """Normalize a raw JSON dict into a Trial (fill missing defaults)."""
    sys_raw = cast(dict[str, object], data.get("system") or {})
    bm_raw = cast(dict[str, object], data.get("benchmark") or {})
    faults_raw = cast(list[dict[str, object]], data.get("faults") or [])

    system: SystemConfig = {"name": cast(str, sys_raw.get("name", "unknown"))}
    if "version" in sys_raw:
        system["version"] = cast(str | None, sys_raw["version"])
    if "cluster_size" in sys_raw:
        system["cluster_size"] = cast(int, sys_raw["cluster_size"])
    if "data_dir" in sys_raw:
        system["data_dir"] = cast(str, sys_raw["data_dir"])

    benchmark: BenchmarkConfig = {
        "name": cast(str, bm_raw.get("name", "ycsb")),
    }
    if "exec_time_s" in bm_raw:
        benchmark["exec_time_s"] = cast(int, bm_raw["exec_time_s"])
    if "kwargs" in bm_raw:
        benchmark["kwargs"] = cast(dict[str, str | int], bm_raw["kwargs"])

    faults: list[SlowFault] = [
        make_fault(
            fault_type=cast(SlowFaultKind, f.get("fault_type", "nw")),
            location=cast(str, f.get("location", "node1")),
            duration_s=cast(int, f.get("duration_s", 30)),
            severity=cast(str, f.get("severity", "slow-100ms")),
            start_s=cast(int, f.get("start_s", 0)),
            if_restart=cast(bool, f.get("if_restart", False)),
        )
        for f in faults_raw
    ]

    trial: Trial = {
        "trial_id": cast(str, data.get("trial_id", "trial")),
        "system": system,
        "benchmark": benchmark,
        "faults": faults,
    }
    if "issue_id" in data:
        trial["issue_id"] = cast(str, data["issue_id"])
    return trial
