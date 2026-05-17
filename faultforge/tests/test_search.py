"""Tests for FaultForge bounded search loop."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from faultforge.oracle import Oracle, OracleResult
from faultforge.runner import TrialRunner
from faultforge.search import (
    RANDOM_SUBSET_GRID,
    SHUFFLED_GRID,
    SearchConfig,
    Searcher,
)
from faultforge.trial import BenchmarkConfig, SlowFault, SystemConfig, Trial, TrialResult


class _FakeRunner:
    """Test double: emits synthetic trial results for oracle scoring."""

    def __init__(self) -> None:
        self.completed_runs = 0

    def run(self, trial: Trial) -> TrialResult:
        self.completed_runs += 1
        return TrialResult(
            success=True,
            trial=trial,
            log_path=f"/tmp/trial-{self.completed_runs}.log",
        )


class TestTrialEnumeration:
    def test_single_trial_from_grid(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=["node1"],
            fault_models=["nw"],
            magnitudes_ms=[100],
            start_times_s=[0],
            durations_s=[30],
        )
        outs = cfg.full_grid_trials(issue_id="iss")
        assert len(outs) == 1
        trial = outs[0]
        assert trial.issue_id == "iss"
        assert len(trial.faults) == 1
        f = trial.faults[0]
        assert isinstance(f, SlowFault)
        assert f.location == "node1"
        assert f.fault_type == "nw"
        assert f.duration_s == 30
        assert f.severity == "slow-100ms"
        assert f.start_s == 0

    def test_multiple_trials_from_grid(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=["leader", "follower"],
            fault_models=["nw"],
            magnitudes_ms=[50, 100],
            start_times_s=[0],
            durations_s=[30],
        )
        assert len(cfg.full_grid_trials()) == 4

    def test_default_grid_values(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(system=sy, benchmark=bm)
        assert "leader" in cfg.nodes
        assert "nw" in cfg.fault_models
        assert "fs" in cfg.fault_models
        assert 100 in cfg.magnitudes_ms


class TestSearchStrategies:
    def test_random_subset_respects_seed(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=["a", "b"],
            fault_models=["nw"],
            magnitudes_ms=[10, 20],
            start_times_s=[0],
            durations_s=[30],
            max_trials=2,
            strategy=RANDOM_SUBSET_GRID,
            strategy_seed=42,
        )
        run1 = [t.trial_id for t in cfg.bounded_trials(issue_id="x")]
        run2 = [t.trial_id for t in cfg.bounded_trials(issue_id="x")]
        assert run1 == run2

    def test_shuffled_differs_from_exhaustive_prefix(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=["n1"],
            fault_models=["nw"],
            magnitudes_ms=[1, 2, 3],
            start_times_s=[0],
            durations_s=[30],
            max_trials=3,
        )
        ex = [t.trial_id for t in cfg.bounded_trials(issue_id="")]
        cf2 = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=cfg.nodes,
            fault_models=cfg.fault_models,
            magnitudes_ms=cfg.magnitudes_ms,
            start_times_s=cfg.start_times_s,
            durations_s=cfg.durations_s,
            max_trials=3,
            strategy=SHUFFLED_GRID,
            strategy_seed=123,
        )
        sh = [t.trial_id for t in cf2.bounded_trials(issue_id="")]
        assert ex != sh


class TestSearchRunner:
    def test_search_runs_all_trials_when_small_grid(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=["n1"],
            fault_models=["nw"],
            magnitudes_ms=[50],
            start_times_s=[0],
            durations_s=[30],
            max_trials=10,
        )
        runner = TrialRunner()

        with patch.object(runner, "run") as mock_run:
            mock_run.return_value = TrialResult(
                success=True,
                trial=cfg.bounded_trials(issue_id="TEST-1")[0],
                log_path="/tmp/test.log",
            )
            results = Searcher(runner).run(cfg, issue_id="TEST-1")

        assert len(results) == 1
        assert results[0].trial.issue_id == "TEST-1"
        assert results[0].symptom_score == 0.0

    def test_search_respects_max_trials(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=["n1", "n2"],
            fault_models=["nw", "fs"],
            magnitudes_ms=[50, 100],
            start_times_s=[0],
            durations_s=[30],
            max_trials=3,
        )
        runner = TrialRunner()

        with patch.object(runner, "run") as mock_run:
            mock_run.return_value = TrialResult(
                success=True,
                trial=cfg.bounded_trials()[0],
                log_path="/tmp/test.log",
            )
            results = Searcher(runner).run(cfg)

        assert len(results) == 3

    def test_search_ranked_by_score(self):
        sy = SystemConfig(name="etcd")
        bm = BenchmarkConfig.ycsb(workload="a")
        cfg = SearchConfig(
            system=sy,
            benchmark=bm,
            nodes=["n1", "n2"],
            fault_models=["nw"],
            magnitudes_ms=[50, 100],
            start_times_s=[0],
            durations_s=[30],
            max_trials=10,
        )

        fake = _FakeRunner()

        def mock_oracle_evaluate(*args, **kwargs):
            if fake.completed_runs == 2:
                return OracleResult(
                    issue_id="TEST",
                    symptom_score=0.9,
                    success=True,
                )
            return OracleResult(
                issue_id="TEST",
                symptom_score=0.3,
                success=False,
            )

        mock_oracle = MagicMock(spec=Oracle)
        mock_oracle.evaluate.side_effect = mock_oracle_evaluate
        cfg.oracle = mock_oracle

        results = Searcher(fake).run(cfg)

        assert results[0].symptom_score >= results[1].symptom_score
        assert results[0].symptom_score == 0.9
