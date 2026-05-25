"""Tests for experiment configs and oracle definitions."""

from __future__ import annotations

from pathlib import Path

import yaml

from faultforge.oracle import Oracle, OracleConfig, RuleGroup, RuleLeaf
from faultforge.search import SearchConfig

EXPERIMENTS_DIR = Path(__file__).parent.parent
ORACLES_DIR = EXPERIMENTS_DIR / "oracles"
CONFIGS_DIR = EXPERIMENTS_DIR / "configs"


class TestOracleFiles:
    """Every oracle YAML under experiments/oracles/ must load and validate."""

    def _oracle_files(self) -> list[Path]:
        return sorted(ORACLES_DIR.glob("*.yaml"))

    def test_oracle_dir_exists(self) -> None:
        assert ORACLES_DIR.is_dir()

    def test_at_least_10_oracles(self) -> None:
        assert len(self._oracle_files()) >= 10

    def test_all_oracles_load(self) -> None:
        for path in self._oracle_files():
            oracle = Oracle.from_file(path)
            assert oracle.configured_issue_id, f"{path.name} missing issue id"

    def test_all_oracles_have_reproduced_if(self) -> None:
        for path in self._oracle_files():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert "reproduced_if" in data, f"{path.name} missing reproduced_if"

    def test_all_oracles_have_invalid_if(self) -> None:
        for path in self._oracle_files():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert "invalid_if" in data, f"{path.name} missing invalid_if"

    def test_etcd_leader_lease_oracle(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "etcd-leader-lease.yaml")
        assert oracle.configured_issue_id == "ETCD-LEADER-LEASE"

    def test_cassandra_batch_oracle(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "cassandra-batch-throughput.yaml")
        assert oracle.configured_issue_id == "CASSANDRA-18120"

    def test_crdb_disk_stall_oracle(self) -> None:
        oracle = Oracle.from_file(ORACLES_DIR / "crdb-disk-stall.yaml")
        assert oracle.configured_issue_id == "CRDB-DISK-STALL"


class TestExperimentConfigFiles:
    """Every experiment config YAML must be valid and parseable."""

    def _config_files(self) -> list[Path]:
        return sorted(CONFIGS_DIR.glob("*.yaml"))

    def test_config_dir_exists(self) -> None:
        assert CONFIGS_DIR.is_dir()

    def test_at_least_6_configs(self) -> None:
        assert len(self._config_files()) >= 6

    def test_all_configs_parse(self) -> None:
        for path in self._config_files():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert "name" in data, f"{path.name} missing name"
            assert "runs" in data, f"{path.name} missing runs"
            assert len(data["runs"]) > 0, f"{path.name} has no runs"

    def test_all_runs_have_required_fields(self) -> None:
        required = {"name", "system", "benchmark", "fault_models"}
        for path in self._config_files():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            for run in data["runs"]:
                missing = required - set(run.keys())
                assert not missing, f"{path.name}/{run.get('name')}: missing {missing}"

    def test_oracle_paths_exist(self) -> None:
        base = Path(__file__).parent.parent.parent
        for path in self._config_files():
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
            for run in data["runs"]:
                oracle_path = run.get("oracle")
                if oracle_path:
                    full = base / oracle_path
                    assert full.exists(), (
                        f"{path.name}/{run['name']}: oracle {oracle_path} not found"
                    )

    def test_etcd_danger_zone_has_multiple_runs(self) -> None:
        data = yaml.safe_load((CONFIGS_DIR / "etcd-danger-zone.yaml").read_text(encoding="utf-8"))
        assert len(data["runs"]) >= 3


class TestSeverityOverrides:
    """SearchConfig supports nw_flaky_pcts and severity overrides."""

    def test_nw_flaky_pcts_generates_flaky_faults(self) -> None:
        cfg = SearchConfig(
            system={"name": "etcd"},
            benchmark={"name": "ycsb"},
            nodes=["n1"],
            fault_models=["nw"],
            magnitudes_ms=[10],
            start_times_s=[0],
            durations_s=[30],
            nw_flaky_pcts=[0.1, 1.0, 10.0],
        )
        trials = cfg.full_grid_trials()
        severities = {t["faults"][0]["severity"] for t in trials}
        assert "slow-10ms" in severities
        assert "flaky-p0.1" in severities
        assert "flaky-p1.0" in severities
        assert "flaky-p10.0" in severities

    def test_nw_severity_overrides_replaces_defaults(self) -> None:
        cfg = SearchConfig(
            system={"name": "etcd"},
            benchmark={"name": "ycsb"},
            nodes=["n1"],
            fault_models=["nw"],
            magnitudes_ms=[10, 50],
            start_times_s=[0],
            durations_s=[30],
            nw_severity_overrides=["slow-1ms", "partition"],
        )
        trials = cfg.full_grid_trials()
        severities = {t["faults"][0]["severity"] for t in trials}
        assert severities == {"slow-1ms", "partition"}

    def test_fs_severity_overrides_replaces_defaults(self) -> None:
        cfg = SearchConfig(
            system={"name": "etcd"},
            benchmark={"name": "ycsb"},
            nodes=["n1"],
            fault_models=["fs"],
            magnitudes_ms=[1000, 5000],
            start_times_s=[0],
            durations_s=[30],
            fs_severity_overrides=["slow-999us", "slow-12345us"],
        )
        trials = cfg.full_grid_trials()
        severities = {t["faults"][0]["severity"] for t in trials}
        assert severities == {"slow-999us", "slow-12345us"}

    def test_empty_overrides_use_defaults(self) -> None:
        cfg = SearchConfig(
            system={"name": "etcd"},
            benchmark={"name": "ycsb"},
            nodes=["n1"],
            fault_models=["nw"],
            magnitudes_ms=[100],
            start_times_s=[0],
            durations_s=[30],
        )
        trials = cfg.full_grid_trials()
        assert trials[0]["faults"][0]["severity"] == "slow-100ms"


class TestOracleSeverityThreshold:
    """OracleConfig severity_threshold enables graduated scoring."""

    def test_default_threshold_is_one(self) -> None:
        cfg = OracleConfig(issue={"id": "T"})
        assert cfg.severity_threshold == 1

    def test_threshold_two_requires_two_matches(self) -> None:
        oracle = Oracle(
            OracleConfig(
                issue={"id": "T"},
                reproduced_if=RuleGroup(
                    any=[
                        RuleLeaf(file="compose", regex="i/o timeout"),
                        RuleLeaf(file="compose", regex="peer became inactive"),
                    ]
                ),
                severity_threshold=2,
            )
        )
        fixture = Path(__file__).parent / "fixtures" / "oracle" / "compose-error.log"
        result = oracle.evaluate(artifacts={"compose": str(fixture)})
        assert result.valid is True
        # compose-error.log has "i/o timeout" and "peer became inactive" → 2 matches
        assert result.reproduced is True
        assert result.score == 1.0

    def test_threshold_higher_than_matches_not_reproduced(self) -> None:
        oracle = Oracle(
            OracleConfig(
                issue={"id": "T"},
                reproduced_if=RuleGroup(
                    any=[
                        RuleLeaf(file="compose", regex="i/o timeout"),
                    ]
                ),
                severity_threshold=5,
            )
        )
        fixture = Path(__file__).parent / "fixtures" / "oracle" / "compose-error.log"
        result = oracle.evaluate(artifacts={"compose": str(fixture)})
        assert result.valid is True
        assert result.reproduced is False
        assert 0.0 < result.score < 1.0

    def test_score_gradient(self) -> None:
        oracle = Oracle(
            OracleConfig(
                issue={"id": "T"},
                reproduced_if=RuleGroup(
                    any=[
                        RuleLeaf(file="compose", regex="i/o timeout"),
                        RuleLeaf(file="compose", regex="peer became inactive"),
                    ]
                ),
                severity_threshold=4,
            )
        )
        fixture = Path(__file__).parent / "fixtures" / "oracle" / "compose-error.log"
        result = oracle.evaluate(artifacts={"compose": str(fixture)})
        assert result.score == 0.5  # 2 matches / 4 threshold
