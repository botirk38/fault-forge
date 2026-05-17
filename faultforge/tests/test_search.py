"""Tests for FaultForge bounded search loop."""

from __future__ import annotations

from unittest.mock import MagicMock

from faultforge.fault_provider import Recipe
from faultforge.fault_provider import SlowFault as RecipeSlowFault
from faultforge.fault_provider.base import ProviderRunResult
from faultforge.fault_provider.xinda import Xinda
from faultforge.oracle import Oracle, OracleResult
from faultforge.search import SearchConfig, Searcher


class _FakeRankingProvider:
    """Test double: emits synthetic logs for oracle scoring."""

    def __init__(self) -> None:
        self.completed_runs = 0

    def run(self, recipe: Recipe, system_config, benchmark_config):
        assert system_config is not None and benchmark_config is not None
        _ = recipe
        self.completed_runs += 1
        return (
            ProviderRunResult(
                success=True,
                fault_id="fault-1",
                log_path=f"/tmp/trial-{self.completed_runs}.log",
            ),
        )


class TestRecipeEnumeration:
    def test_single_recipe_from_grid(self):
        cfg = SearchConfig(
            nodes=["node1"],
            fault_models=["nw"],
            magnitudes_ms=[100],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        outs = cfg.recipes(issue_id="iss")
        assert len(outs) == 1
        recipe = outs[0]
        assert recipe.issue_id == "iss"
        assert recipe.trial_id == "trial-node1-nw-100ms"
        assert len(recipe.faults) == 1
        f = recipe.faults[0]
        assert isinstance(f, RecipeSlowFault)
        assert f.location == "node1"
        assert f.fault_type == "nw"
        assert f.duration_s == 30
        assert f.severity == "slow-100ms"
        assert f.start_s == 0

    def test_multiple_recipes_from_grid(self):
        cfg = SearchConfig(
            nodes=["leader", "follower"],
            fault_models=["nw"],
            magnitudes_ms=[50, 100],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        assert len(cfg.recipes()) == 4

    def test_default_grid_values(self):
        cfg = SearchConfig()
        assert "leader" in cfg.nodes
        assert "nw" in cfg.fault_models
        assert "fs" in cfg.fault_models
        assert 100 in cfg.magnitudes_ms


class TestSearchRecipes:
    def test_search_config_has_no_provider_field(self):
        cfg = SearchConfig()
        assert not hasattr(cfg, "providers")

    def test_recipe_reflects_leader_nw_slow_100(self):
        cfg = SearchConfig(
            nodes=["leader"],
            fault_models=["nw"],
            magnitudes_ms=[100],
            start_times_s=[10.0],
            durations_s=[60.0],
        )
        recipe = cfg.recipes(issue_id="ZK-001")[0]
        assert recipe.issue_id == "ZK-001"
        assert recipe.trial_id == "trial-leader-nw-100ms"
        assert len(recipe.faults) == 1
        fault = recipe.faults[0]
        assert isinstance(fault, RecipeSlowFault)
        assert fault.fault_type == "nw"
        assert fault.location == "leader"
        assert fault.duration_s == 60
        assert fault.severity == "slow-100ms"
        assert fault.start_s == 10

    def test_trial_id_includes_follower_fs_250(self):
        cfg = SearchConfig(
            nodes=["follower"],
            fault_models=["fs"],
            magnitudes_ms=[250],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        recipe = cfg.recipes()[0]
        assert "follower" in recipe.trial_id
        assert "fs" in recipe.trial_id
        assert "250" in recipe.trial_id


class TestSearchRunner:
    def test_search_runs_all_recipes_when_small_grid(self):
        cfg = SearchConfig(
            nodes=["n1"],
            fault_models=["nw"],
            magnitudes_ms=[50],
            start_times_s=[0.0],
            durations_s=[30.0],
            max_trials=10,
        )
        search = Searcher(Xinda())

        results = search.run(cfg, issue_id="TEST-1")

        assert len(results) == 1
        assert results[0].recipe.issue_id == "TEST-1"
        assert results[0].symptom_score == 0.0

    def test_search_respects_max_trials(self):
        cfg = SearchConfig(
            nodes=["n1", "n2"],
            fault_models=["nw", "fs"],
            magnitudes_ms=[50, 100],
            start_times_s=[0.0],
            durations_s=[30.0],
            max_trials=3,
        )
        search = Searcher(Xinda())

        results = search.run(cfg)

        assert len(results) == 3

    def test_search_ranked_by_score(self):
        cfg = SearchConfig(
            nodes=["n1", "n2"],
            fault_models=["nw"],
            magnitudes_ms=[50, 100],
            start_times_s=[0.0],
            durations_s=[30.0],
            max_trials=10,
        )

        fake = _FakeRankingProvider()

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
        cfg.system_config = MagicMock()
        cfg.benchmark_config = MagicMock()

        results = Searcher(fake).run(cfg)

        assert results[0].symptom_score >= results[1].symptom_score
        assert results[0].symptom_score == 0.9

    def test_search_without_system_config(self):
        cfg = SearchConfig(
            nodes=["n1"],
            fault_models=["nw"],
            magnitudes_ms=[100],
            start_times_s=[0.0],
            durations_s=[30.0],
            max_trials=5,
        )
        search = Searcher(Xinda())

        results = search.run(cfg)

        assert len(results) == 1
        assert results[0].trials_run == 0
