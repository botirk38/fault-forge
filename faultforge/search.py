"""Bounded search loop for fault reproduction.

Searches over fault parameters, runs trials, scores against oracle,
and returns ranked recipes.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass, field
from typing import Any

from faultforge.oracle import Oracle
from faultforge.recipe import Fault, FaultParams, FaultTarget, FaultTiming, Recipe
from faultforge.xinda_runner import run_recipe
from xinda import BenchmarkConfig, SystemConfig

logger = logging.getLogger(__name__)


@dataclass
class SearchSpace:
    """Bounded parameter space for fault search."""

    nodes: list[str] = field(default_factory=lambda: ["leader", "follower"])
    fault_models: list[str] = field(default_factory=lambda: ["network_delay", "disk_delay"])
    magnitudes_ms: list[int] = field(default_factory=lambda: [10, 50, 100, 250, 500])
    start_times_s: list[float] = field(default_factory=lambda: [0.0, 10.0, 30.0])
    durations_s: list[float] = field(default_factory=lambda: [30.0, 60.0])

    def combinations(self) -> list[dict[str, Any]]:
        """Generate all parameter combinations."""
        return [
            {
                "node": node,
                "fault_model": model,
                "delay_ms": mag,
                "start_s": start,
                "duration_s": dur,
            }
            for node, model, mag, start, dur in itertools.product(
                self.nodes,
                self.fault_models,
                self.magnitudes_ms,
                self.start_times_s,
                self.durations_s,
            )
        ]


@dataclass
class SearchResult:
    """Result of a single search trial."""

    recipe: Recipe
    symptom_score: float
    oracle_success: bool
    trial_index: int
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchConfig:
    """Search execution configuration."""

    max_trials: int = 100
    oracle: Oracle | None = None
    system_config: SystemConfig | None = None
    benchmark_config: BenchmarkConfig | None = None


def _build_recipe(
    params: dict[str, Any],
    issue_id: str = "",
    trial_id: str = "",
) -> Recipe:
    """Build a Recipe from search parameters."""
    default_id = f"trial-{params['node']}-{params['fault_model']}-{params['delay_ms']}ms"
    return Recipe(
        issue_id=issue_id,
        trial_id=trial_id or default_id,
        faults=[
            Fault(
                id="fault-1",
                provider="xinda",
                model=params["fault_model"],
                target=FaultTarget(node=params["node"]),
                timing=FaultTiming(
                    start_s=params["start_s"],
                    duration_s=params["duration_s"],
                ),
                params=FaultParams(delay_ms=params["delay_ms"]),
            ),
        ],
    )


def search(
    search_space: SearchSpace,
    config: SearchConfig,
    issue_id: str = "",
) -> list[SearchResult]:
    """Run bounded search over fault parameters.

    Iterates through parameter combinations, runs each trial via Xinda,
    scores against the oracle, and returns results ranked by symptom_score.

    Stops early if max_trials is reached.
    """
    all_combos = search_space.combinations()
    combos = all_combos[: config.max_trials]

    if len(all_combos) > config.max_trials:
        logger.info(
            "Search space has %d combinations, limiting to %d",
            len(all_combos),
            config.max_trials,
        )

    results: list[SearchResult] = []

    for i, params in enumerate(combos):
        recipe = _build_recipe(params, issue_id=issue_id)

        logger.info(
            "Trial %d/%d: node=%s model=%s delay=%dms start=%.1fs duration=%.1fs",
            i + 1,
            len(combos),
            params["node"],
            params["fault_model"],
            params["delay_ms"],
            params["start_s"],
            params["duration_s"],
        )

        if config.system_config and config.benchmark_config:
            trial_results = run_recipe(recipe, config.system_config, config.benchmark_config)

            if trial_results and config.oracle:
                log_path = trial_results[0].log_path if trial_results else None
                oracle_result = config.oracle.evaluate(log_path=log_path)
                symptom_score = oracle_result.symptom_score
                oracle_success = oracle_result.success
            else:
                symptom_score = 0.0
                oracle_success = False
        else:
            logger.info("No system/benchmark config, building recipe only")
            symptom_score = 0.0
            oracle_success = False

        results.append(
            SearchResult(
                recipe=recipe,
                symptom_score=symptom_score,
                oracle_success=oracle_success,
                trial_index=i,
                details={
                    "params": params,
                    "trials_run": len(trial_results) if config.system_config else 0,
                },
            )
        )

    results.sort(key=lambda r: r.symptom_score, reverse=True)
    return results
