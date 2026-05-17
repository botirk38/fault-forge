"""Search grid + trial orchestration."""

from __future__ import annotations

import itertools
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from xinda import BenchmarkConfig, SystemConfig

from faultforge.fault_provider import FaultProvider, ProviderRunResult, SlowFault, SlowFaultKind
from faultforge.oracle import Oracle
from faultforge.recipe import Recipe

logger = logging.getLogger(__name__)


class SearchStrategy(ABC):
    """Pluggable traversal of the Cartesian knob grid."""

    @abstractmethod
    def select_recipes(self, config: SearchConfig, *, issue_id: str = "") -> list[Recipe]:
        """Produce recipes to evaluate, honoring ``max_trials`` and config timing fields."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class ExhaustiveGridStrategy(SearchStrategy):
    """Lexicographic ``itertools.product`` order; take first ``max_trials``."""

    def select_recipes(self, config: SearchConfig, *, issue_id: str = "") -> list[Recipe]:
        full = grid_recipes_flat(config, issue_id=issue_id)
        cap = config.max_trials
        if len(full) > cap:
            logger.info(
                "Search space %d recipes (exhaustive order), bounded to max_trials=%d",
                len(full),
                cap,
            )
        return full[:cap]


class ShuffledGridStrategy(SearchStrategy):
    """Deterministic shuffle (``strategy_seed``), then first ``max_trials``."""

    def select_recipes(self, config: SearchConfig, *, issue_id: str = "") -> list[Recipe]:
        full = grid_recipes_flat(config, issue_id=issue_id)
        cap = config.max_trials
        rng = random.Random(config.strategy_seed)
        dup = full.copy()
        rng.shuffle(dup)
        if len(dup) > cap:
            logger.info(
                "Shuffled grid %d recipes, bounded to max_trials=%d",
                len(dup),
                cap,
            )
        return dup[:cap]


class RandomSubsetGridStrategy(SearchStrategy):
    """Uniform random sample without replacement; size ``min(max_trials, grid_size)``."""

    def select_recipes(self, config: SearchConfig, *, issue_id: str = "") -> list[Recipe]:
        full = grid_recipes_flat(config, issue_id=issue_id)
        rng = random.Random(config.strategy_seed)
        k = min(config.max_trials, len(full))
        return rng.sample(full, k=k)


EXHAUSTIVE_GRID = ExhaustiveGridStrategy()
SHUFFLED_GRID = ShuffledGridStrategy()
RANDOM_SUBSET_GRID = RandomSubsetGridStrategy()


def _recipe_for_combo(
    issue_id: str,
    *,
    node: str,
    fault_model: SlowFaultKind,
    delay_ms: int,
    start_s: float,
    duration_s: float,
) -> Recipe:
    return Recipe(
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


def grid_recipes_flat(config: SearchConfig, *, issue_id: str = "") -> list[Recipe]:
    """Full Cartesian enumeration (no ``max_trials`` cap); stable product order."""
    return [
        _recipe_for_combo(
            issue_id,
            node=node,
            fault_model=fault_model,
            delay_ms=delay_ms,
            start_s=start_s,
            duration_s=duration_s,
        )
        for node, fault_model, delay_ms, start_s, duration_s in itertools.product(
            config.nodes,
            config.fault_models,
            config.magnitudes_ms,
            config.start_times_s,
            config.durations_s,
        )
    ]


def select_search_recipes(config: SearchConfig, *, issue_id: str = "") -> list[Recipe]:
    """Delegate to ``config.strategy`` (thin helper for callers and tests)."""
    return config.strategy.select_recipes(config, issue_id=issue_id)


@dataclass
class SearchConfig:
    """Cartesian knob grid plus how trials run (Xinda ``SlowFault`` recipes)."""

    nodes: list[str] = field(default_factory=lambda: ["leader", "follower"])
    fault_models: list[SlowFaultKind] = field(default_factory=lambda: ["nw", "fs"])
    magnitudes_ms: list[int] = field(default_factory=lambda: [10, 50, 100, 250, 500])
    start_times_s: list[float] = field(default_factory=lambda: [0.0, 10.0, 30.0])
    durations_s: list[float] = field(default_factory=lambda: [30.0, 60.0])
    max_trials: int = 100
    strategy: SearchStrategy = EXHAUSTIVE_GRID
    strategy_seed: int | None = None
    oracle: Oracle | None = None
    system_config: SystemConfig | None = None
    benchmark_config: BenchmarkConfig | None = None

    def recipes(self, *, issue_id: str = "") -> list[Recipe]:
        """Full Cartesian enumeration (ignores ``max_trials`` and ``strategy``)."""
        return grid_recipes_flat(self, issue_id=issue_id)


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
        recipes_slice = config.strategy.select_recipes(config, issue_id=issue_id)

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
