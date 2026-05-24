"""Search grid + trial orchestration."""

from __future__ import annotations

import itertools
import logging
import random
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from faultforge.oracle import Oracle
from faultforge.runner import TrialRunner
from faultforge.trial import (
    BenchmarkConfig,
    SlowFault,
    SlowFaultKind,
    SystemConfig,
    Trial,
    TrialResult,
)

logger = logging.getLogger(__name__)


class SearchStrategy(ABC):
    """Pluggable traversal of the Cartesian knob grid."""

    @abstractmethod
    def select_trials(self, config: SearchConfig, *, issue_id: str = "") -> list[Trial]:
        """Produce trials to evaluate, honoring ``max_trials``."""

    def __repr__(self) -> str:
        return f"{type(self).__name__}()"


class ExhaustiveGridStrategy(SearchStrategy):
    """Lexicographic ``itertools.product`` order; take first ``max_trials``."""

    def select_trials(self, config: SearchConfig, *, issue_id: str = "") -> list[Trial]:
        full = config.full_grid_trials(issue_id=issue_id)
        cap = config.max_trials
        if len(full) > cap:
            logger.info(
                "Search space %d trials (exhaustive order), bounded to max_trials=%d",
                len(full),
                cap,
            )
        return full[:cap]


class ShuffledGridStrategy(SearchStrategy):
    """Deterministic shuffle (``strategy_seed``), then first ``max_trials``."""

    def select_trials(self, config: SearchConfig, *, issue_id: str = "") -> list[Trial]:
        full = config.full_grid_trials(issue_id=issue_id)
        cap = config.max_trials
        rng = random.Random(config.strategy_seed)
        dup = full.copy()
        rng.shuffle(dup)
        if len(dup) > cap:
            logger.info(
                "Shuffled grid %d trials, bounded to max_trials=%d",
                len(dup),
                cap,
            )
        return dup[:cap]


class RandomSubsetGridStrategy(SearchStrategy):
    """Uniform random sample without replacement; size ``min(max_trials, grid_size)``."""

    def select_trials(self, config: SearchConfig, *, issue_id: str = "") -> list[Trial]:
        full = config.full_grid_trials(issue_id=issue_id)
        rng = random.Random(config.strategy_seed)
        k = min(config.max_trials, len(full))
        return rng.sample(full, k=k)


EXHAUSTIVE_GRID = ExhaustiveGridStrategy()
SHUFFLED_GRID = ShuffledGridStrategy()
RANDOM_SUBSET_GRID = RandomSubsetGridStrategy()


@dataclass
class SearchConfig:
    """Cartesian knob grid plus how trials run."""

    system: SystemConfig
    benchmark: BenchmarkConfig
    nodes: list[str] = field(default_factory=lambda: ["leader", "follower"])
    fault_models: list[SlowFaultKind] = field(default_factory=lambda: ["nw", "fs"])
    magnitudes_ms: list[int] = field(default_factory=lambda: [10, 50, 100, 250, 500])
    start_times_s: list[int] = field(default_factory=lambda: [0, 10, 30])
    durations_s: list[int] = field(default_factory=lambda: [30, 60])
    max_faults_per_trial: int = 1
    max_trials: int = 100
    strategy: SearchStrategy = EXHAUSTIVE_GRID
    strategy_seed: int | None = None
    oracle: Oracle | None = None
    nw_flaky_pcts: list[float] = field(default_factory=list)
    nw_severity_overrides: list[str] = field(default_factory=list)
    fs_severity_overrides: list[str] = field(default_factory=list)

    def _single_fault_candidates(self) -> list[SlowFault]:
        faults: list[SlowFault] = []
        for node, fault_model, start_s, duration_s in itertools.product(
            self.nodes,
            self.fault_models,
            self.start_times_s,
            self.durations_s,
        ):
            if fault_model == "nw":
                if self.nw_severity_overrides:
                    severities = self.nw_severity_overrides
                else:
                    severities = [f"slow-{ms}ms" for ms in self.magnitudes_ms]
                    for pct in self.nw_flaky_pcts:
                        severities.append(f"flaky-p{pct}")
                for sev in severities:
                    faults.append(
                        SlowFault(
                            fault_type="nw",
                            location=node,
                            duration_s=int(duration_s),
                            severity=sev,
                            start_s=int(start_s),
                            if_restart=False,
                        )
                    )
            elif fault_model == "fs":
                if self.fs_severity_overrides:
                    severities = self.fs_severity_overrides
                else:
                    severities = [f"slow-{us}us" for us in self.magnitudes_ms]
                for sev in severities:
                    faults.append(
                        SlowFault(
                            fault_type="fs",
                            location=node,
                            duration_s=int(duration_s),
                            severity=sev,
                            start_s=int(start_s),
                            if_restart=False,
                        )
                    )
            elif fault_model == "cpu":
                for cpus in ["0.25", "0.5", "1.0"]:
                    faults.append(
                        SlowFault(
                            fault_type="cpu",
                            location=node,
                            duration_s=int(duration_s),
                            severity=f"cpus-{cpus}",
                            start_s=int(start_s),
                            if_restart=False,
                        )
                    )
            elif fault_model == "mem":
                for mem in ["256m", "512m", "1g"]:
                    faults.append(
                        SlowFault(
                            fault_type="mem",
                            location=node,
                            duration_s=int(duration_s),
                            severity=f"memory-{mem}",
                            start_s=int(start_s),
                            if_restart=False,
                        )
                    )
            elif fault_model == "process":
                for action in ["restart", "stop"]:
                    faults.append(
                        SlowFault(
                            fault_type="process",
                            location=node,
                            duration_s=int(duration_s),
                            severity=action,
                            start_s=int(start_s),
                            if_restart=False,
                        )
                    )
            elif fault_model == "none":
                faults.append(
                    SlowFault(
                        fault_type="none",
                        location=node,
                        duration_s=int(duration_s),
                        severity="none",
                        start_s=int(start_s),
                        if_restart=False,
                    )
                )
        return faults

    def _trial_from_faults(
        self,
        issue_id: str,
        faults: list[SlowFault],
    ) -> Trial:
        labels = "-".join(f"{f.fault_type}-{f.location}-{f.severity}" for f in faults)
        return Trial(
            trial_id=f"trial-{labels}",
            issue_id=issue_id,
            system=self.system,
            benchmark=self.benchmark,
            faults=faults,
            version=self.system.version,
        )

    def full_grid_trials(self, *, issue_id: str = "") -> list[Trial]:
        candidates = self._single_fault_candidates()
        max_k = self.max_faults_per_trial
        faults_combos: list[list[SlowFault]] = []
        for k in range(1, max_k + 1):
            for combo in itertools.combinations(candidates, k):
                faults_combos.append(list(combo))
        return [self._trial_from_faults(issue_id, faults) for faults in faults_combos]

    def bounded_trials(self, *, issue_id: str = "") -> list[Trial]:
        return self.strategy.select_trials(self, issue_id=issue_id)


@dataclass
class SearchResult:
    trial: Trial
    trial_result: TrialResult | None
    symptom_score: float
    oracle_success: bool
    trial_index: int


class Searcher:
    def __init__(self, runner: TrialRunner) -> None:
        self._runner = runner

    def run(self, config: SearchConfig, issue_id: str = "") -> list[SearchResult]:
        trials = config.bounded_trials(issue_id=issue_id)
        oracle = config.oracle
        results: list[SearchResult] = []

        for trial_index, trial in enumerate(trials):
            trial_result = self._runner.run(trial)
            symptom_score = 0.0
            oracle_success = False

            if oracle is not None and trial_result.artifacts:
                verdict = oracle.evaluate(artifacts=trial_result.artifacts)
                symptom_score = verdict.score
                oracle_success = verdict.reproduced

            results.append(
                SearchResult(
                    trial=trial,
                    trial_result=trial_result,
                    symptom_score=symptom_score,
                    oracle_success=oracle_success,
                    trial_index=trial_index,
                )
            )

        results.sort(key=lambda r: r.symptom_score, reverse=True)
        return results
