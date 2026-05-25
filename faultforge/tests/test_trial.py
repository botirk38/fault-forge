"""Tests for canonical trial models."""

from __future__ import annotations

from faultforge.trial import (
    Trial,
    TrialResult,
    fault_end_s,
    fault_info,
    make_fault,
    make_fs_fault,
    make_nw_fault,
    make_trial,
)


class TestSlowFault:
    def test_network(self):
        f = make_nw_fault(location="node1", severity="slow-100ms", duration_s=60)
        assert f["fault_type"] == "nw"
        assert f["location"] == "node1"
        assert f["duration_s"] == 60

    def test_filesystem(self):
        f = make_fs_fault(location="datanode", severity="10000", duration_s=120)
        assert f["fault_type"] == "fs"
        assert f["location"] == "datanode"

    def test_baseline(self):
        f = make_fault(fault_type="none", location="node1", duration_s=-1, severity="none")
        assert f["fault_type"] == "none"
        assert f["duration_s"] == -1

    def test_with_restart(self):
        f = make_nw_fault(
            location="leader", severity="slow-50ms", duration_s=30, start_s=10, if_restart=True
        )
        assert f["if_restart"] is True
        assert f["start_s"] == 10

    def test_info_function(self):
        f = make_nw_fault(location="n1", severity="slow-100ms", duration_s=30, start_s=0)
        info = fault_info(f)
        assert "nw" in info
        assert "slow-100ms" in info

    def test_end_s(self):
        f = make_fault(
            fault_type="nw", location="n1", duration_s=30, severity="slow-10ms", start_s=5
        )
        assert fault_end_s(f) == 35

    def test_end_s_negative_duration(self):
        f = make_fault(fault_type="none", location="n1", duration_s=-1, severity="none")
        assert fault_end_s(f) == -1


class TestSystemConfig:
    def test_minimal(self):
        s = {"name": "etcd"}
        assert s["name"] == "etcd"

    def test_with_options(self):
        s = {"name": "hbase", "cluster_size": 5, "data_dir": "test", "coverage": True}
        assert s["cluster_size"] == 5
        assert s["coverage"] is True


class TestBenchmarkConfig:
    def test_ycsb(self):
        b = {"name": "ycsb", "workload": "a", "exec_time_s": 100}
        assert b["name"] == "ycsb"
        assert b["workload"] == "a"

    def test_mrbench(self):
        b = {"name": "mrbench", "num_iter": 5}
        assert b["name"] == "mrbench"
        assert b["num_iter"] == 5

    def test_exec_time(self):
        b = {"name": "custom", "exec_time_s": 60}
        assert b["name"] == "custom"
        assert b["exec_time_s"] == 60


class TestResourceLimit:
    def test_defaults(self):
        r = {"cpu_limit": "4", "mem_limit": "32G"}
        assert r["cpu_limit"] == "4"

    def test_custom(self):
        r = {"cpu_limit": "2", "mem_limit": "8G"}
        assert r["mem_limit"] == "8G"


class TestTrialPaths:
    def test_empty_defaults(self):
        p = {}
        assert p.get("log_root_dir", "") == ""
        assert p.get("install_root", "") == ""
        assert p.get("tooling_root", "") == ""

    def test_custom_values(self):
        p = {
            "log_root_dir": "/data",
            "install_root": "/software",
            "tooling_root": "/tools",
        }
        assert p["log_root_dir"] == "/data"
        assert p["install_root"] == "/software"
        assert p["tooling_root"] == "/tools"


class TestTrial:
    def test_single_fault(self):
        fault = make_nw_fault(location="etcd0", severity="slow-100ms", duration_s=60)
        t = make_trial(
            trial_id="t1",
            system={"name": "etcd"},  # type: ignore[arg-type]
            benchmark={"name": "ycsb", "workload": "a"},  # type: ignore[arg-type]
            faults=[fault],
            issue_id="ETCD-1",
        )
        assert t["trial_id"] == "t1"
        assert t["issue_id"] == "ETCD-1"
        assert len(t["faults"]) == 1
        assert t["faults"][0]["fault_type"] == "nw"

    def test_multi_fault(self):
        faults = [
            make_nw_fault(location="etcd0", severity="slow-100ms", duration_s=30),
            make_fs_fault(location="etcd1", severity="10000", duration_s=60),
        ]
        t = make_trial(
            trial_id="t2",
            system={"name": "etcd"},  # type: ignore[arg-type]
            benchmark={"name": "ycsb", "workload": "a"},  # type: ignore[arg-type]
            faults=faults,
        )
        assert len(t["faults"]) == 2
        assert t["faults"][0]["fault_type"] == "nw"
        assert t["faults"][1]["fault_type"] == "fs"

    def test_data_dir(self):
        t = make_trial(
            trial_id="t3",
            system={"name": "etcd", "data_dir": "test"},  # type: ignore[arg-type]
            benchmark={"name": "ycsb"},  # type: ignore[arg-type]
            faults=[],
        )
        assert t["system"]["data_dir"] == "test"


class TestTrialResult:
    def test_success_result(self):
        fault = make_nw_fault(location="etcd0", severity="slow-100ms", duration_s=60)
        trial: Trial = make_trial(
            trial_id="t1",
            system={"name": "etcd"},  # type: ignore[arg-type]
            benchmark={"name": "ycsb", "workload": "a"},  # type: ignore[arg-type]
            faults=[fault],
        )
        r: TrialResult = {
            "success": True,
            "trial": trial,
            "log_path": "/tmp/log",
        }
        assert r["success"] is True
        assert r.get("error") is None
        assert r["trial"] is trial

    def test_failure_result(self):
        fault = make_nw_fault(location="etcd0", severity="slow-100ms", duration_s=60)
        trial: Trial = make_trial(
            trial_id="t1",
            system={"name": "etcd"},  # type: ignore[arg-type]
            benchmark={"name": "ycsb", "workload": "a"},  # type: ignore[arg-type]
            faults=[fault],
        )
        r: TrialResult = {
            "success": False,
            "trial": trial,
            "error": "connection refused",
        }
        assert r["success"] is False
        assert r["error"] == "connection refused"
