"""Search grid + trial orchestration."""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field

from xinda import BenchmarkConfig, SystemConfig

from faultforge.fault_provider import (
    FaultProvider,
    ProviderRunResult,
    Recipe,
    SlowFault,
    SlowFaultKind,
)
from faultforge.oracle import Oracle

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    """Cartesian knob grid plus how trials run (Xinda ``SlowFault`` recipes)."""

    nodes: list[str] = field(default_factory=lambda: ["leader", "follower"])
    fault_models: list[SlowFaultKind] = field(default_factory=lambda: ["nw", "fs"])
    magnitudes_ms: list[int] = field(default_factory=lambda: [10, 50, 100, 250, 500])
    start_times_s: list[float] = field(default_factory=lambda: [0.0, 10.0, 30.0])
    durations_s: list[float] = field(default_factory=lambda: [30.0, 60.0])
    max_trials: int = 100
    oracle: Oracle | None = None
    system_config: SystemConfig | None = None
    benchmark_config: BenchmarkConfig | None = None

    def recipes(self, *, issue_id: str = "") -> list[Recipe]:
        """Enumerate ``SlowFault`` trial recipes over the Cartesian product."""
        return [
            Recipe(
                issue_id=issue_id,
                trial_id=f"trial-{node}-{fault_model}-{delay_ms}ms",
                faults=[
                    SlowFault(
                        id="fault-1",
                        fault_type=fault_model,
                        location=node,
                        duration_s=int(duration_s),
                        severity=f"slow-{delay_ms}ms",
                        start_s=int(start_s),
                        if_restart=False,
                    ),
                ],
            )
            for node, fault_model, delay_ms, start_s, duration_s in itertools.product(
                self.nodes,
                self.fault_models,
                self.magnitudes_ms,
                self.start_times_s,
                self.durations_s,
            )
        ]


@dataclass
class SearchResult:
    recipe: Recipe
    symptom_score: float
    oracle_success: bool
    trial_index: int
    trials_run: int = 0


class Searcher:
    def __init__(self, provider: FaultProvider) -> None:
        self._provider = provider

    def run(self, config: SearchConfig, issue_id: str = "") -> list[SearchResult]:
        all_recipes = config.recipes(issue_id=issue_id)
        recipes_slice = all_recipes[: config.max_trials]
        if len(all_recipes) > config.max_trials:
            logger.info(
                "Search space %d combos, using first %d",
                len(all_recipes),
                config.max_trials,
            )

        results: list[SearchResult] = []
        sy, bm = config.system_config, config.benchmark_config
        oracle = config.oracle

        for trial_index, recipe in enumerate(recipes_slice):
            symptom_score = 0.0
            oracle_success = False
            trials_run = 0

            if sy is not None and bm is not None:
                outcomes: tuple[ProviderRunResult, ...] = tuple(self._provider.run(recipe, sy, bm))
                trials_run = len(outcomes)
                log_path = next((o.log_path for o in outcomes if o.log_path is not None), None)
                if oracle is not None and log_path is not None:
                    verdict = oracle.evaluate(log_path=log_path)
                    symptom_score = verdict.symptom_score
                    oracle_success = verdict.success

            results.append(
                SearchResult(
                    recipe=recipe,
                    symptom_score=symptom_score,
                    oracle_success=oracle_success,
                    trial_index=trial_index,
                    trials_run=trials_run,
                )
            )

        results.sort(key=lambda r: r.symptom_score, reverse=True)
        return results
