"""Tests for canonical trial models."""

from __future__ import annotations

from faultforge.trial import (
    BenchmarkConfig,
    ResourceLimit,
    SlowFault,
    SystemConfig,
    Trial,
    TrialPaths,
    TrialResult,
)


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

    def test_info_property(self):
        f = SlowFault.network(location="n1", severity="slow-100ms", duration_s=30, start_s=0)
        assert "nw" in f.info
        assert "slow-100ms" in f.info

    def test_end_s(self):
        f = SlowFault(
            fault_type="nw", location="n1", duration_s=30, severity="slow-10ms", start_s=5
        )
        assert f.end_s == 35

    def test_end_s_negative_duration(self):
        f = SlowFault(fault_type="none", location="n1", duration_s=-1, severity="none")
        assert f.end_s == -1


class TestSystemConfig:
    def test_minimal(self):
        s = SystemConfig(name="etcd")
        assert s.name == "etcd"
        assert s.cluster_size == 3

    def test_with_options(self):
        s = SystemConfig(name="hbase", cluster_size=5, data_dir="test", coverage=True)
        assert s.cluster_size == 5
        assert s.coverage is True


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

    def test_has_install_and_tooling_roots(self):
        p = TrialPaths.defaults()
        assert p.install_root != ""
        assert p.tooling_root != ""


class TestTrial:
    def test_single_fault(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        fault = SlowFault.network(location="etcd0", severity="slow-100ms", duration_s=60)
        t = Trial(
            trial_id="t1",
            system=sy,
            benchmark=bm,
            faults=[fault],
            issue_id="ETCD-1",
        )
        assert t.trial_id == "t1"
        assert t.issue_id == "ETCD-1"
        assert len(t.faults) == 1
        assert t.faults[0].fault_type == "nw"

    def test_multi_fault(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        faults = [
            SlowFault.network(location="etcd0", severity="slow-100ms", duration_s=30),
            SlowFault.filesystem(location="etcd1", severity="10000", duration_s=60),
        ]
        t = Trial(trial_id="t2", system=sy, benchmark=bm, faults=faults)
        assert len(t.faults) == 2
        assert t.faults[0].fault_type == "nw"
        assert t.faults[1].fault_type == "fs"

    def test_data_dir(self):
        sy = SystemConfig(name="etcd", data_dir="test")
        bm = BenchmarkConfig.ycsb()
        t = Trial(trial_id="t3", system=sy, benchmark=bm, faults=[])
        assert t.system.data_dir == "test"


class TestTrialResult:
    def test_success_result(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        fault = SlowFault.network(location="etcd0", severity="slow-100ms", duration_s=60)
        trial = Trial(trial_id="t1", system=sy, benchmark=bm, faults=[fault])
        r = TrialResult(success=True, trial=trial, log_path="/tmp/log")
        assert r.success is True
        assert r.error is None
        assert r.trial is trial

    def test_failure_result(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        fault = SlowFault.network(location="etcd0", severity="slow-100ms", duration_s=60)
        trial = Trial(trial_id="t1", system=sy, benchmark=bm, faults=[fault])
        r = TrialResult(success=False, trial=trial, error="connection refused")
        assert r.success is False
        assert r.error == "connection refused"
