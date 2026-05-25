"""Smoke tests for the FaultForge CLI (runner calls patched)."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from cli import main  # noqa: E402
from click.testing import CliRunner

from faultforge.search import SearchConfig
from faultforge.trial import Trial, make_trial

_ISSUE_ORACLE_YAML = """
issue:
  id: "CLI-TEST-1"
  system: "zookeeper"
  title: ""
oracle:
  type: "exit-code"
  verdict: "symptom_present"
  exit_code: 0
"""


def test_search_command_runs_without_oracle() -> None:
    trial: Trial = make_trial(
        trial_id="trial-a-nw-10ms",
        faults=[],
        system={"name": "etcd"},  # type: ignore[arg-type]
        benchmark={"name": "ycsb"},  # type: ignore[arg-type]
    )
    fake_results = [
        MagicMock(
            trial=trial,
            symptom_score=0.0,
            oracle_success=False,
            trial_index=0,
        )
    ]

    runner = CliRunner()

    fake_search = MagicMock()
    fake_search.run.return_value = fake_results

    with patch("cli.TrialRunner", return_value=MagicMock()):
        with patch("cli.Searcher", return_value=fake_search):
            result = runner.invoke(
                main,
                [
                    "search",
                    "--issue-id",
                    "x",
                    "--max-trials",
                    "1",
                    "--system",
                    "etcd",
                    "--benchmark",
                    "ycsb",
                ],
            )

    assert result.exit_code == 0, result.output
    assert "trial-a-nw-10ms" in result.output
    fake_search.run.assert_called_once()


def test_search_pulls_issue_id_from_oracle_file(tmp_path: Path) -> None:
    path = tmp_path / "o.yaml"
    path.write_text(_ISSUE_ORACLE_YAML.strip(), encoding="utf-8")

    captured: dict[str, object] = {}

    class _CaptureSearcher:
        def __init__(self, _runner: object) -> None:
            pass

        def run(self, config: SearchConfig, issue_id: str = "") -> tuple[()]:
            captured["oracle"] = config.oracle
            captured["issue_id"] = issue_id
            return ()

    runner = CliRunner()

    with patch("cli.TrialRunner", return_value=MagicMock()):
        with patch("cli.Searcher", _CaptureSearcher):
            result = runner.invoke(
                main,
                [
                    "search",
                    "--oracle",
                    str(path),
                    "--system",
                    "etcd",
                    "--benchmark",
                    "ycsb",
                ],
            )

    assert result.exit_code == 0, result.output
    assert captured["issue_id"] == "CLI-TEST-1"
    assert captured["oracle"] is not None


def test_search_dry_run_plans_without_executing() -> None:
    runner = CliRunner()

    with patch("cli.Searcher") as mock_searcher_cls:
        result = runner.invoke(
            main,
            [
                "search",
                "--dry-run",
                "--max-trials",
                "2",
                "--system",
                "etcd",
                "--benchmark",
                "ycsb",
                "--nodes",
                "leader",
                "--magnitudes",
                "10",
            ],
        )

    mock_searcher_cls.assert_not_called()
    assert result.exit_code == 0, result.output
    assert "trial(s) planned" in result.output


def test_search_dry_run_json_output() -> None:
    runner = CliRunner()

    result = runner.invoke(
        main,
        [
            "search",
            "--dry-run",
            "--json",
            "--max-trials",
            "1",
            "--system",
            "etcd",
            "--benchmark",
            "ycsb",
            "--nodes",
            "leader",
            "--magnitudes",
            "10",
        ],
    )

    assert result.exit_code == 0, result.output
    lines = [line for line in result.output.strip().split("\n") if line.startswith("{")]
    for line in lines:
        parsed = json.loads(line)
        assert "trial_id" in parsed
        assert "faults" in parsed


def test_search_custom_fault_knobs() -> None:
    captured: dict[str, object] = {}

    class _CaptureSearcher:
        def __init__(self, _runner: object) -> None:
            pass

        def run(self, config: SearchConfig, issue_id: str = "") -> tuple[()]:
            captured["config"] = config
            return ()

    runner = CliRunner()

    with patch("cli.TrialRunner", return_value=MagicMock()):
        with patch("cli.Searcher", _CaptureSearcher):
            result = runner.invoke(
                main,
                [
                    "search",
                    "--nodes",
                    "node1",
                    "--nodes",
                    "node2",
                    "--fault-models",
                    "nw",
                    "--magnitudes",
                    "25",
                    "--magnitudes",
                    "50",
                    "--start-times",
                    "5",
                    "--durations",
                    "45",
                    "--max-faults-per-trial",
                    "2",
                ],
            )

    assert result.exit_code == 0, result.output
    cfg = captured["config"]
    assert cfg.nodes == ["node1", "node2"]
    assert cfg.fault_models == ["nw"]
    assert cfg.magnitudes_ms == [25, 50]
    assert cfg.start_times_s == [5]
    assert cfg.durations_s == [45]
    assert cfg.max_faults_per_trial == 2


_EXP_YAML = """
name: "quick-test"
runs:
  - name: baseline
    system: etcd
    benchmark: ycsb
    max_trials: 1
    nodes:
      - leader
    magnitudes_ms:
      - 10
"""


def test_experiment_dry_run(tmp_path: Path) -> None:
    cfg_file = tmp_path / "exp.yaml"
    cfg_file.write_text(_EXP_YAML.strip(), encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["experiment", str(cfg_file), "--dry-run"],
    )

    assert result.exit_code == 0, result.output
    assert "[baseline]" in result.output
    assert "dry-run complete" in result.output


def test_experiment_runs_and_writes_files(tmp_path: Path) -> None:
    cfg_file = tmp_path / "exp.yaml"
    cfg_file.write_text(_EXP_YAML.strip(), encoding="utf-8")
    out_dir = tmp_path / "out"

    runner = CliRunner()

    with patch("experiment.ExperimentRunner") as mock_runner_cls:
        mock_runner = MagicMock()
        mock_result = MagicMock()
        mock_result.name = "baseline"
        mock_result.any_symptom = False
        mock_result.top_match.trial.__getitem__ = lambda self, key: (
            "trial-nw-leader-slow-10ms" if key == "trial_id" else None
        )
        mock_runner.run.return_value = [mock_result]
        mock_runner_cls.return_value = mock_runner

        result = runner.invoke(
            main,
            ["experiment", str(cfg_file), "--output-dir", str(out_dir)],
        )

    assert result.exit_code == 0, result.output
    mock_runner.run.assert_called_once()
    assert "baseline" in result.output
