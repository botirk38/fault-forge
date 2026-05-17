"""Smoke tests for Xinda SDK Trial construction.

These tests verify that Trial objects can be constructed for every registered
system/benchmark combination without requiring Docker or any runtime toolchain.
"""

from __future__ import annotations

import pytest

from xinda import (
    BenchmarkConfig,
    ResourceLimit,
    SlowFault,
    SystemConfig,
    Trial,
    TrialPaths,
    TrialResult,
    XindaClient,
)
from xinda.systems.registry import SYSTEMS


# ---------------------------------------------------------------------------
# SlowFault construction
# ---------------------------------------------------------------------------


class TestSlowFault:
    def test_network(self):
        f = SlowFault.network(location="node1", severity="slow-100ms", duration_s=60)
        assert f.fault_type == "nw"
        assert f.location == "node1"
        assert f.duration_s == 60

    def test_filesystem(self):
        f = SlowFault.filesystem(location="datanode", severity="10000", duration_s=120)
        assert f.fault_type == "fs"
        assert f.location == "datanode"

    def test_baseline(self):
        f = SlowFault(fault_type="none", location="node1", duration_s=-1, severity="none")
        assert f.fault_type == "none"
        assert f.duration_s == -1

    def test_with_restart(self):
        f = SlowFault.network(
            location="leader", severity="slow-50ms", duration_s=30, start_s=10, if_restart=True
        )
        assert f.if_restart is True
        assert f.start_s == 10


# ---------------------------------------------------------------------------
# BenchmarkConfig construction (one test per factory method)
# ---------------------------------------------------------------------------


class TestBenchmarkConfig:
    def test_ycsb(self):
        b = BenchmarkConfig.ycsb(workload="a", exec_time_s=100)
        assert b.name == "ycsb"
        assert b.kwargs["workload"] == "a"

    def test_mrbench(self):
        b = BenchmarkConfig.mrbench(num_iter=5)
        assert b.name == "mrbench"
        assert b.kwargs["num_iter"] == 5

    def test_terasort(self):
        b = BenchmarkConfig.terasort()
        assert b.name == "terasort"

    def test_perf_test(self):
        b = BenchmarkConfig.perf_test(num_msg=1000)
        assert b.name == "perf_test"
        assert b.kwargs["num_msg"] == 1000

    def test_openmsg(self):
        b = BenchmarkConfig.openmsg(driver="kafka-latency")
        assert b.name == "openmsg"

    def test_sysbench(self):
        b = BenchmarkConfig.sysbench(lua_scheme="oltp_read_only")
        assert b.name == "sysbench"

    def test_etcd_official(self):
        b = BenchmarkConfig.etcd_official(workload="lease-keepalive", total=100)
        assert b.name == "etcd-official"

    def test_depfast(self):
        b = BenchmarkConfig.depfast(concurrency=50, scheme="fpga_raft")
        assert b.name == "depfast"

    def test_copilot(self):
        b = BenchmarkConfig.copilot(concurrency=10, scheme="copilot")
        assert b.name == "copilot"

    def test_raw_kwargs(self):
        b = BenchmarkConfig(name="custom", exec_time_s=60, kwargs={"k": "v"})
        assert b.name == "custom"
        assert b.kwargs["k"] == "v"


# ---------------------------------------------------------------------------
# SystemConfig construction
# ---------------------------------------------------------------------------


class TestSystemConfig:
    def test_minimal(self):
        s = SystemConfig(name="etcd")
        assert s.name == "etcd"
        assert s.cluster_size == 3

    def test_with_options(self):
        s = SystemConfig(name="hbase", cluster_size=5, data_dir="test", coverage=True)
        assert s.cluster_size == 5
        assert s.coverage is True


# ---------------------------------------------------------------------------
# ResourceLimit and TrialPaths
# ---------------------------------------------------------------------------


class TestResourceLimit:
    def test_defaults(self):
        r = ResourceLimit(cpu_limit="4", mem_limit="32G")
        assert r.cpu_limit == "4"

    def test_custom(self):
        r = ResourceLimit(cpu_limit="2", mem_limit="8G")
        assert r.mem_limit == "8G"


class TestTrialPaths:
    def test_defaults(self):
        p = TrialPaths.defaults()
        assert "workdir" in p.log_root_dir


# ---------------------------------------------------------------------------
# Trial construction for all registered systems
# ---------------------------------------------------------------------------

# Map each system to a valid (benchmark, location) pair.
SYSTEM_BENCHMARKS: list[tuple[str, BenchmarkConfig, str]] = [
    ("cassandra", BenchmarkConfig.ycsb(workload="a"), "cas1"),
    ("hbase", BenchmarkConfig.ycsb(workload="a"), "hbase-master"),
    ("hadoop", BenchmarkConfig.mrbench(), "namenode"),
    ("etcd", BenchmarkConfig.ycsb(workload="a"), "etcd0"),
    ("crdb", BenchmarkConfig.ycsb(workload="a"), "roach1"),
    ("kafka", BenchmarkConfig.perf_test(), "kafka1"),
    ("depfast", BenchmarkConfig.depfast(), "server1"),
    ("copilot", BenchmarkConfig.copilot(), "control"),
]


class TestTrialConstruction:
    """Verify Trial objects can be built for every registered system."""

    def test_registry_has_all_expected_systems(self):
        expected = {"cassandra", "copilot", "crdb", "depfast", "etcd", "hbase", "hadoop", "kafka"}
        assert set(SYSTEMS.keys()) == expected

    @pytest.mark.parametrize(
        "system_name,benchmark,location",
        SYSTEM_BENCHMARKS,
        ids=[s[0] for s in SYSTEM_BENCHMARKS],
    )
    def test_trial_construction(self, system_name: str, benchmark: BenchmarkConfig, location: str):
        trial = Trial(
            system=SystemConfig(name=system_name),
            benchmark=benchmark,
            fault=SlowFault.network(location=location, severity="slow-100ms", duration_s=60),
        )
        assert trial.system.name == system_name
        assert trial.benchmark.name == benchmark.name
        assert trial.fault.fault_type == "nw"

    @pytest.mark.parametrize(
        "system_name,benchmark,location",
        SYSTEM_BENCHMARKS,
        ids=[s[0] for s in SYSTEM_BENCHMARKS],
    )
    def test_trial_with_baseline_fault(
        self, system_name: str, benchmark: BenchmarkConfig, location: str
    ):
        trial = Trial(
            system=SystemConfig(name=system_name),
            benchmark=benchmark,
            fault=SlowFault(fault_type="none", location=location, duration_s=-1, severity="none"),
        )
        assert trial.fault.fault_type == "none"


# ---------------------------------------------------------------------------
# TrialResult construction
# ---------------------------------------------------------------------------


class TestTrialResult:
    def test_success_result(self):
        r = TrialResult(
            success=True,
            system=SystemConfig(name="etcd"),
            benchmark=BenchmarkConfig.ycsb(workload="a"),
            fault=SlowFault.network(location="etcd0", severity="slow-100ms", duration_s=60),
            log_path="/tmp/log",
        )
        assert r.success is True
        assert r.error is None

    def test_failure_result(self):
        r = TrialResult(
            success=False,
            system=SystemConfig(name="etcd"),
            benchmark=BenchmarkConfig.ycsb(workload="a"),
            fault=SlowFault.network(location="etcd0", severity="slow-100ms", duration_s=60),
            error="connection refused",
        )
        assert r.success is False
        assert r.error == "connection refused"


# ---------------------------------------------------------------------------
# XindaClient validation
# ---------------------------------------------------------------------------


class TestXindaClientValidation:
    def test_rejects_invalid_fault_type(self):
        client = XindaClient()
        trial = Trial(
            system=SystemConfig(name="etcd"),
            benchmark=BenchmarkConfig.ycsb(workload="a"),
            fault=SlowFault(
                fault_type="invalid", location="etcd0", duration_s=60, severity="slow-100ms"
            ),
        )
        with pytest.raises(ValueError, match="Unknown fault type"):
            client._validate(trial)

    def test_accepts_valid_fault_types(self):
        client = XindaClient()
        for ft in ("nw", "fs", "none"):
            trial = Trial(
                system=SystemConfig(name="etcd"),
                benchmark=BenchmarkConfig.ycsb(workload="a"),
                fault=SlowFault(
                    fault_type=ft, location="etcd0", duration_s=60, severity="slow-100ms"
                ),
            )
            client._validate(trial)
