"""Smoke tests for the FaultForge CLI (provider calls patched)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from click.testing import CliRunner

from faultforge.cli import main
from faultforge.recipe import Recipe
from faultforge.search import SearchConfig, SearchResult

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
    recipe = Recipe(issue_id="x", trial_id="trial-a-nw-10ms", faults=[])
    fake_results = [
        SearchResult(
            recipe=recipe,
            symptom_score=0.0,
            oracle_success=False,
            trial_index=0,
            trials_run=0,
        )
    ]

    runner = CliRunner()

    fake_search = MagicMock()
    fake_search.run.return_value = fake_results

    with patch("faultforge.cli.Xinda", return_value=MagicMock()):
        with patch("faultforge.cli.Searcher", return_value=fake_search):
            result = runner.invoke(main, ["search", "--issue-id", "x", "--max-trials", "1"])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert "trial-a-nw-10ms" in result.output
    fake_search.run.assert_called_once()


def test_search_pulls_issue_id_from_oracle_file(tmp_path: Path) -> None:
    path = tmp_path / "o.yaml"
    path.write_text(_ISSUE_ORACLE_YAML.strip(), encoding="utf-8")

    captured: dict[str, object] = {}

    class _CaptureSearcher:
        def __init__(self, _provider: object) -> None:
            pass

        def run(self, config: SearchConfig, issue_id: str = "") -> tuple[()]:
            captured["oracle"] = config.oracle
            captured["issue_id"] = issue_id
            return ()

    runner = CliRunner()

    with patch("faultforge.cli.Xinda", return_value=MagicMock()):
        with patch("faultforge.cli.Searcher", _CaptureSearcher):
            result = runner.invoke(main, ["search", "--oracle", str(path)])

    assert result.exit_code == 0, result.stdout + result.stderr
    assert captured["issue_id"] == "CLI-TEST-1"
    assert captured["oracle"] is not None
