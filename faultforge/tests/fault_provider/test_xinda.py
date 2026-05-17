"""Tests for FaultForge ``fault_provider.xinda`` and the Xinda SDK surface it relies on."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from xinda import (
    BenchmarkConfig,
    ResourceLimit,
    SystemConfig,
    Trial,
    TrialPaths,
    TrialResult,
    XindaClient,
)
from xinda import SlowFault as SdkSlowFault
from xinda.systems.registry import SYSTEMS

from faultforge.fault_provider import InProcessFault
from faultforge.fault_provider import SlowFault as RecipeSlowFault
from faultforge.fault_provider.xinda import Xinda
from faultforge.recipe import Recipe

# ---------------------------------------------------------------------------
# FaultForge adapter
# ---------------------------------------------------------------------------


@pytest.fixture()
def etcd_sysbench() -> tuple[SystemConfig, BenchmarkConfig]:
    return SystemConfig(name="etcd"), BenchmarkConfig.ycsb(workload="a")


@pytest.fixture()
def nw_fault() -> RecipeSlowFault:
    return RecipeSlowFault(
        id="fault-1",
        fault_type="nw",
        location="leader",
        duration_s=30,
        severity="slow-100ms",
        start_s=0,
    )


def test_wrong_fault_type_for_xinda_raises(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
) -> None:
    sy, bm = etcd_sysbench
    recipe = Recipe(
        trial_id="t-bad-kind",
        faults=[
            InProcessFault(id="fault-1", exception_class="java.io.IOException"),
        ],
    )
    with pytest.raises(TypeError):
        Xinda().run(recipe, sy, bm)


def test_xinda_raises_on_unknown_model(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
) -> None:
    sy, bm = etcd_sysbench
    fault = RecipeSlowFault.model_construct(
        id="fault-bad-model",
        kind="slow",
        fault_type="garbage-model",
        location="leader",
        duration_s=60,
        severity="slow-50ms",
        start_s=0,
        if_restart=False,
    )
    recipe = Recipe(trial_id="t3", faults=[fault])
    with pytest.raises(ValueError, match="unsupported Xinda"):
        Xinda().run(recipe, sy, bm)


def test_xinda_execution_patches_client(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
    nw_fault: RecipeSlowFault,
) -> None:
    sy, bm = etcd_sysbench
    recipe = Recipe(trial_id="t4", faults=[nw_fault])

    mock_tr = TrialResult(
        success=True,
        system=sy,
        benchmark=bm,
        fault=SdkSlowFault.network(location="leader", severity="slow-100ms", duration_s=30),
        log_path="/tmp/xinda.log",
    )

    with patch("faultforge.fault_provider.xinda.XindaClient") as xc:
        xc.return_value.run.return_value = mock_tr
        results = Xinda().run(recipe, sy, bm)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].log_path == "/tmp/xinda.log"


# ---------------------------------------------------------------------------
# Xinda SDK: SlowFault construction
# ---------------------------------------------------------------------------


class TestSdkSlowFault:
    def test_network(self):
        f = SdkSlowFault.network(location="node1", severity="slow-100ms", duration_s=60)
        assert f.fault_type == "nw"
        assert f.location == "node1"
        assert f.duration_s == 60

    def test_filesystem(self):
        f = SdkSlowFault.filesystem(location="datanode", severity="10000", duration_s=120)
        assert f.fault_type == "fs"
        assert f.location == "datanode"

    def test_baseline(self):
        f = SdkSlowFault(fault_type="none", location="node1", duration_s=-1, severity="none")
        assert f.fault_type == "none"
        assert f.duration_s == -1

    def test_with_restart(self):
        f = SdkSlowFault.network(
            location="leader", severity="slow-50ms", duration_s=30, start_s=10, if_restart=True
        )
        assert f.if_restart is True
        assert f.start_s == 10


# ---------------------------------------------------------------------------
# Xinda SDK: BenchmarkConfig factories
# ---------------------------------------------------------------------------


class TestSdkBenchmarkConfig:
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
# Xinda SDK: SystemConfig
# ---------------------------------------------------------------------------


class TestSdkSystemConfig:
    def test_minimal(self):
        s = SystemConfig(name="etcd")
        assert s.name == "etcd"
        assert s.cluster_size == 3

    def test_with_options(self):
        s = SystemConfig(name="hbase", cluster_size=5, data_dir="test", coverage=True)
        assert s.cluster_size == 5
        assert s.coverage is True


# ---------------------------------------------------------------------------
# Xinda SDK: ResourceLimit / TrialPaths
# ---------------------------------------------------------------------------


class TestSdkResourceLimit:
    def test_defaults(self):
        r = ResourceLimit(cpu_limit="4", mem_limit="32G")
        assert r.cpu_limit == "4"

    def test_custom(self):
        r = ResourceLimit(cpu_limit="2", mem_limit="8G")
        assert r.mem_limit == "8G"


class TestSdkTrialPaths:
    def test_defaults(self):
        p = TrialPaths.defaults()
        assert "workdir" in p.log_root_dir


# ---------------------------------------------------------------------------
# Xinda SDK: Trial construction across registered systems
# ---------------------------------------------------------------------------

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


class TestSdkTrialConstruction:
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
            fault=SdkSlowFault.network(location=location, severity="slow-100ms", duration_s=60),
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
            fault=SdkSlowFault(
                fault_type="none", location=location, duration_s=-1, severity="none"
            ),
        )
        assert trial.fault.fault_type == "none"


# ---------------------------------------------------------------------------
# Xinda SDK: TrialResult
# ---------------------------------------------------------------------------


class TestSdkTrialResult:
    def test_success_result(self):
        r = TrialResult(
            success=True,
            system=SystemConfig(name="etcd"),
            benchmark=BenchmarkConfig.ycsb(workload="a"),
            fault=SdkSlowFault.network(location="etcd0", severity="slow-100ms", duration_s=60),
            log_path="/tmp/log",
        )
        assert r.success is True
        assert r.error is None

    def test_failure_result(self):
        r = TrialResult(
            success=False,
            system=SystemConfig(name="etcd"),
            benchmark=BenchmarkConfig.ycsb(workload="a"),
            fault=SdkSlowFault.network(location="etcd0", severity="slow-100ms", duration_s=60),
            error="connection refused",
        )
        assert r.success is False
        assert r.error == "connection refused"


# ---------------------------------------------------------------------------
# Xinda SDK: XindaClient.validate
# ---------------------------------------------------------------------------


class TestSdkXindaClientValidation:
    def test_rejects_invalid_fault_type(self):
        client = XindaClient()
        trial = Trial(
            system=SystemConfig(name="etcd"),
            benchmark=BenchmarkConfig.ycsb(workload="a"),
            fault=SdkSlowFault(
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
                fault=SdkSlowFault(
                    fault_type=ft, location="etcd0", duration_s=60, severity="slow-100ms"
                ),
            )
            client._validate(trial)
