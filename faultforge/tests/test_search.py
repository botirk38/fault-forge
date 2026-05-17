"""Tests for FaultForge bounded search loop."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from faultforge.oracle import Oracle, OracleResult
from faultforge.search import (
    ExhaustiveSearchStrategy,
    SearchConfig,
    SearchSpace,
)

# ---------------------------------------------------------------------------
# SearchSpace
# ---------------------------------------------------------------------------


class TestSearchSpace:
    def test_default_combinations(self):
        space = SearchSpace(
            nodes=["node1"],
            fault_models=["network_delay"],
            magnitudes_ms=[100],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        combos = space.combinations()
        assert len(combos) == 1
        assert combos[0] == {
            "node": "node1",
            "fault_model": "network_delay",
            "delay_ms": 100,
            "start_s": 0.0,
            "duration_s": 30.0,
        }

    def test_multiple_combinations(self):
        space = SearchSpace(
            nodes=["leader", "follower"],
            fault_models=["network_delay"],
            magnitudes_ms=[50, 100],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        combos = space.combinations()
        assert len(combos) == 4  # 2 nodes * 1 model * 2 magnitudes

    def test_default_values(self):
        space = SearchSpace()
        assert "leader" in space.nodes
        assert "network_delay" in space.fault_models
        assert 100 in space.magnitudes_ms


# ---------------------------------------------------------------------------
# Recipe building
# ---------------------------------------------------------------------------


class TestBuildRecipe:
    def test_builds_recipe_with_single_fault(self):
        params = {
            "node": "leader",
            "fault_model": "network_delay",
            "delay_ms": 100,
            "start_s": 10.0,
            "duration_s": 60.0,
        }
        recipe = ExhaustiveSearchStrategy()._build_recipe(
            params, issue_id="ZK-001", trial_id="t1"
        )

        assert recipe.issue_id == "ZK-001"
        assert recipe.trial_id == "t1"
        assert len(recipe.faults) == 1

        fault = recipe.faults[0]
        assert fault.provider == "xinda"
        assert fault.model == "network_delay"
        assert fault.target.node == "leader"
        assert fault.timing.start_s == 10.0
        assert fault.timing.duration_s == 60.0
        assert fault.params.delay_ms == 100

    def test_default_trial_id(self):
        params = {
            "node": "follower",
            "fault_model": "disk_delay",
            "delay_ms": 250,
            "start_s": 0.0,
            "duration_s": 30.0,
        }
        recipe = ExhaustiveSearchStrategy()._build_recipe(params)
        assert "follower" in recipe.trial_id
        assert "disk_delay" in recipe.trial_id
        assert "250" in recipe.trial_id


# ---------------------------------------------------------------------------
# Search (mocked)
# ---------------------------------------------------------------------------


class TestSearch:
    def test_search_runs_all_combinations(self):
        space = SearchSpace(
            nodes=["n1"],
            fault_models=["network_delay"],
            magnitudes_ms=[50],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        config = SearchConfig(max_trials=10)
        strategy = ExhaustiveSearchStrategy()

        results = strategy.run(space, config, issue_id="TEST-1")

        assert len(results) == 1
        assert results[0].recipe.issue_id == "TEST-1"
        assert results[0].symptom_score == 0.0  # no oracle/system config

    def test_search_respects_max_trials(self):
        space = SearchSpace(
            nodes=["n1", "n2"],
            fault_models=["network_delay", "disk_delay"],
            magnitudes_ms=[50, 100],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        # 2 * 2 * 2 * 1 * 1 = 8 combos, limit to 3
        config = SearchConfig(max_trials=3)
        strategy = ExhaustiveSearchStrategy()

        results = strategy.run(space, config)

        assert len(results) == 3

    def test_search_ranked_by_score(self):
        space = SearchSpace(
            nodes=["n1", "n2"],
            fault_models=["network_delay"],
            magnitudes_ms=[50, 100],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        config = SearchConfig(max_trials=10)

        # Mock run_recipe to return different results per trial
        call_count = 0

        def mock_run_recipe(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            mock_result = MagicMock()
            mock_result.log_path = f"/tmp/trial-{call_count}.log"
            return [mock_result]

        def mock_oracle_evaluate(*args, **kwargs):
            nonlocal call_count
            # Simulate: trial 2 has highest score
            if call_count == 2:
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
        config.oracle = mock_oracle
        config.system_config = MagicMock()
        config.benchmark_config = MagicMock()
        strategy = ExhaustiveSearchStrategy()

        with patch("faultforge.search.run_recipe", side_effect=mock_run_recipe):
            results = strategy.run(space, config)

        # Results should be sorted by score descending
        assert results[0].symptom_score >= results[1].symptom_score
        assert results[0].symptom_score == 0.9

    def test_search_without_system_config(self):
        """Search should work without system/benchmark config (recipe-only mode)."""
        space = SearchSpace(
            nodes=["n1"],
            fault_models=["network_delay"],
            magnitudes_ms=[100],
            start_times_s=[0.0],
            durations_s=[30.0],
        )
        config = SearchConfig(max_trials=5)
        strategy = ExhaustiveSearchStrategy()

        results = strategy.run(space, config)

        assert len(results) == 1
        assert results[0].details["trials_run"] == 0
