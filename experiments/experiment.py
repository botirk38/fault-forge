"""Experiment orchestration for FaultForge."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from trial_runner import TrialRunner
from faultforge.search import SearchConfig, Searcher, SearchResult

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Aggregated results from running a single search config."""

    name: str
    search_config: SearchConfig
    search_results: list[SearchResult]
    issue_id: str = ""

    @property
    def top_match(self) -> SearchResult | None:
        """Highest-scoring trial, or None if no results."""
        return self.search_results[0] if self.search_results else None

    @property
    def any_symptom(self) -> bool:
        """Whether any trial triggered the oracle symptom."""
        return any(r.oracle_success for r in self.search_results)

    def summary(self) -> dict:
        return {
            "name": self.name,
            "issue_id": self.issue_id,
            "total_trials": len(self.search_results),
            "any_symptom": self.any_symptom,
            "top_score": self.top_match.symptom_score if self.top_match else 0.0,
            "top_trial": self.top_match.trial["trial_id"] if self.top_match else None,
        }


@dataclass
class Experiment:
    """Collection of search configs to run as a batch."""

    name: str
    configs: list[tuple[str, SearchConfig]]
    output_dir: Path = Path("experiments")
    issue_ids: dict[str, str] = field(default_factory=dict)

    def add(self, name: str, config: SearchConfig, *, issue_id: str = "") -> None:
        self.configs.append((name, config))
        if issue_id:
            self.issue_ids[name] = issue_id


class ExperimentRunner:
    """Execute an experiment and write structured results."""

    def __init__(self, runner: TrialRunner | None = None) -> None:
        self._runner = runner or TrialRunner()

    def run(self, experiment: Experiment) -> list[ExperimentResult]:
        results: list[ExperimentResult] = []
        for name, config in experiment.configs:
            issue_id = experiment.issue_ids.get(name, "")
            logger.info("Running experiment config: %s", name)
            search_results = Searcher(self._runner).run(config, issue_id=issue_id)
            exp_result = ExperimentResult(
                name=name,
                search_config=config,
                search_results=search_results,
                issue_id=issue_id,
            )
            results.append(exp_result)

        self._write_results(experiment, results)
        return results

    def _write_results(
        self,
        experiment: Experiment,
        results: list[ExperimentResult],
    ) -> None:
        out = experiment.output_dir / experiment.name
        out.mkdir(parents=True, exist_ok=True)

        summary = [r.summary() for r in results]
        (out / "summary.json").write_text(
            json.dumps(summary, indent=2, default=str),
            encoding="utf-8",
        )

        for r in results:
            trial_rows = [
                {
                    "trial_id": sr.trial["trial_id"],
                    "symptom_score": sr.symptom_score,
                    "oracle_success": sr.oracle_success,
                    "trial_index": sr.trial_index,
                }
                for sr in r.search_results
            ]
            safe_name = r.name.replace("/", "_").replace(" ", "_")
            (out / f"{safe_name}.jsonl").write_text(
                "".join(json.dumps(row, default=str) + "\n" for row in trial_rows),
                encoding="utf-8",
            )
