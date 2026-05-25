"""Tests for experiment orchestration."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from faultforge.experiment import Experiment, ExperimentResult, ExperimentRunner
from faultforge.search import SearchConfig, SearchResult
from faultforge.trial import Trial, make_trial


def _make_search_result(trial_id: str, score: float, success: bool, index: int) -> SearchResult:
    trial: Trial = make_trial(
        trial_id=trial_id,
        system={"name": "etcd"},  # type: ignore[arg-type]
        benchmark={"name": "ycsb"},  # type: ignore[arg-type]
        faults=[],
    )
    return SearchResult(
        trial=trial,
        trial_result=MagicMock(),
        symptom_score=score,
        oracle_success=success,
        trial_index=index,
    )


class TestExperimentResult:
    def test_top_match_returns_first(self) -> None:
        results = [
            _make_search_result("t1", 0.9, True, 0),
            _make_search_result("t2", 0.3, False, 1),
        ]
        exp = ExperimentResult(
            name="test",
            search_config=MagicMock(),
            search_results=results,
        )
        assert exp.top_match is not None
        assert exp.top_match.trial["trial_id"] == "t1"

    def test_top_match_none_when_empty(self) -> None:
        exp = ExperimentResult(
            name="test",
            search_config=MagicMock(),
            search_results=[],
        )
        assert exp.top_match is None

    def test_any_symptom_true(self) -> None:
        results = [
            _make_search_result("t1", 0.0, False, 0),
            _make_search_result("t2", 0.5, True, 1),
        ]
        exp = ExperimentResult(
            name="test",
            search_config=MagicMock(),
            search_results=results,
        )
        assert exp.any_symptom is True

    def test_any_symptom_false(self) -> None:
        results = [
            _make_search_result("t1", 0.0, False, 0),
            _make_search_result("t2", 0.1, False, 1),
        ]
        exp = ExperimentResult(
            name="test",
            search_config=MagicMock(),
            search_results=results,
        )
        assert exp.any_symptom is False

    def test_summary(self) -> None:
        results = [_make_search_result("t1", 0.7, True, 0)]
        exp = ExperimentResult(
            name="exp1",
            search_config=MagicMock(),
            search_results=results,
            issue_id="ISSUE-1",
        )
        s = exp.summary()
        assert s["name"] == "exp1"
        assert s["issue_id"] == "ISSUE-1"
        assert s["total_trials"] == 1
        assert s["any_symptom"] is True
        assert s["top_score"] == 0.7
        assert s["top_trial"] == "t1"


class TestExperiment:
    def test_add_config(self) -> None:
        exp = Experiment(name="my-exp", configs=[])
        cfg = SearchConfig(
            system={"name": "etcd"},  # type: ignore[arg-type]
            benchmark={"name": "ycsb"},  # type: ignore[arg-type]
        )
        exp.add("baseline", cfg, issue_id="BUG-1")
        assert len(exp.configs) == 1
        assert exp.configs[0][0] == "baseline"
        assert exp.issue_ids["baseline"] == "BUG-1"


class TestExperimentRunner:
    def test_run_writes_files(self, tmp_path: Path) -> None:
        cfg = SearchConfig(
            system={"name": "etcd"},  # type: ignore[arg-type]
            benchmark={"name": "ycsb"},  # type: ignore[arg-type]
            max_trials=1,
        )
        exp = Experiment(
            name="test-exp",
            configs=[("baseline", cfg)],
            output_dir=tmp_path,
        )

        fake_result = _make_search_result("t1", 0.5, False, 0)

        with patch("faultforge.experiment.Searcher") as mock_searcher_cls:
            mock_searcher = MagicMock()
            mock_searcher.run.return_value = [fake_result]
            mock_searcher_cls.return_value = mock_searcher

            runner = ExperimentRunner()
            results = runner.run(exp)

        assert len(results) == 1
        assert results[0].name == "baseline"

        summary_path = tmp_path / "test-exp" / "summary.json"
        assert summary_path.exists()
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        assert len(summary) == 1
        assert summary[0]["total_trials"] == 1

        trials_path = tmp_path / "test-exp" / "baseline.jsonl"
        assert trials_path.exists()
        lines = trials_path.read_text(encoding="utf-8").strip().split("\n")
        assert len(lines) == 1
        row = json.loads(lines[0])
        assert row["trial_id"] == "t1"
        assert row["symptom_score"] == 0.5
