"""Fault recipe minimizer for FaultForge.

Given a reproducing trial (one where the oracle confirms the symptom),
iteratively reduces fault parameters to find the minimal fault recipe —
the simplest combination that still triggers the vulnerability.

Algorithm: greedy dimensional reduction.
  1. Eliminate unnecessary faults (fault count)
  2. Binary-search minimum severity per remaining fault
  3. Binary-search minimum duration per remaining fault
  4. Binary-search latest start time per remaining fault

Noise-tolerance is handled by the injected ProbeStrategy (see probe.py).
The minimizer delegates all evaluation decisions to the strategy, keeping
the binary search logic independent of the noise-handling policy.
"""

from __future__ import annotations

import copy
import logging
from dataclasses import dataclass

from faultforge.confidence import BoundaryInterval, BoundaryValidator
from faultforge.oracle import Oracle, OracleResult
from faultforge.probe import ProbeStrategy, SingleShotProbe
from faultforge.runner import RunTrial
from faultforge.severity import build_severity, parse_severity_magnitude
from faultforge.trial import SlowFault, Trial, fault_info

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MinimizationConfig:
    """Controls the minimization budget and behavior."""

    max_iterations: int = 50
    score_threshold: float = 0.5
    magnitude_steps: int = 8
    duration_steps: int = 5
    timing_steps: int = 5
    validate_boundary: bool = True
    validation_probes: int = 5


@dataclass(frozen=True)
class ReductionStep:
    """Record of one successful reduction."""

    dimension: str
    fault_index: int
    before: str
    after: str
    score: float


@dataclass(frozen=True)
class MinimizationResult:
    """Output of the minimization process."""

    original: Trial
    minimized: Trial
    iterations_used: int
    reductions: tuple[ReductionStep, ...] = ()
    final_score: float = 0.0
    boundary_intervals: tuple[BoundaryInterval, ...] = ()


class Minimizer:
    """Greedy fault recipe minimizer.

    Takes a reproducing Trial and reduces fault parameters (count,
    magnitude, duration, timing) to find the smallest recipe that
    still triggers the oracle symptom.

    Evaluation decisions are delegated to the injected ProbeStrategy,
    which controls noise-handling policy (single-shot, majority-vote,
    etc.) independently of the search algorithm.
    """

    def __init__(
        self,
        runner: RunTrial,
        oracle: Oracle,
        config: MinimizationConfig | None = None,
        probe: ProbeStrategy | None = None,
    ) -> None:
        self._runner = runner
        self._oracle = oracle
        self._config = config or MinimizationConfig()
        self._probe = probe or SingleShotProbe(
            runner, oracle, threshold=self._config.score_threshold
        )

    def minimize(self, trial: Trial) -> MinimizationResult:
        """Run the full minimization pipeline on a reproducing trial."""
        original = copy.deepcopy(trial)
        budget = _Budget(self._config.max_iterations)
        reductions: list[ReductionStep] = []

        initial_result = self._evaluate(trial, budget)
        if not initial_result.reproduced:
            logger.warning(
                "Trial does not reproduce (score=%.2f). Returning as-is.",
                initial_result.score,
            )
            return MinimizationResult(
                original=original,
                minimized=trial,
                iterations_used=budget.used,
                final_score=initial_result.score,
            )

        trial, count_steps = self._reduce_fault_count(trial, budget)
        reductions.extend(count_steps)

        magnitude_bounds: list[tuple[int, float, float]] = []

        for fault_idx in range(len(trial["faults"])):
            if budget.exhausted:
                break
            trial, steps, bounds = self._reduce_magnitude(trial, fault_idx, budget)
            reductions.extend(steps)
            if bounds is not None:
                magnitude_bounds.append((fault_idx, bounds[0], bounds[1]))

            if budget.exhausted:
                break
            trial, steps = self._reduce_duration(trial, fault_idx, budget)
            reductions.extend(steps)

            if budget.exhausted:
                break
            trial, steps = self._reduce_timing(trial, fault_idx, budget)
            reductions.extend(steps)

        # Validate boundary confidence if configured and budget allows
        intervals = self._validate_boundaries(trial, magnitude_bounds, budget)

        final_result = self._evaluate(trial, budget)

        return MinimizationResult(
            original=original,
            minimized=trial,
            iterations_used=budget.used,
            reductions=tuple(reductions),
            final_score=final_result.score,
            boundary_intervals=tuple(intervals),
        )

    def _validate_boundaries(
        self,
        trial: Trial,
        bounds: list[tuple[int, float, float]],
        budget: _Budget,
    ) -> list[BoundaryInterval]:
        """Run boundary validation for converged magnitude dimensions."""
        if not self._config.validate_boundary or not bounds:
            return []

        min_budget_per_validation = self._config.validation_probes * 2
        intervals: list[BoundaryInterval] = []

        for fault_idx, lo, hi in bounds:
            if budget.remaining < min_budget_per_validation:
                break
            validator = BoundaryValidator(
                self._probe, validation_probes=self._config.validation_probes
            )
            interval = validator.validate(trial, fault_idx, lo, hi)
            intervals.append(interval)
            # Account for probes consumed by the validator
            probes_used = self._config.validation_probes * 2
            for _ in range(probes_used):
                if not budget.exhausted:
                    budget.spend()

        return intervals

    # ------------------------------------------------------------------
    # Reduction phases
    # ------------------------------------------------------------------

    def _reduce_fault_count(
        self, trial: Trial, budget: _Budget
    ) -> tuple[Trial, list[ReductionStep]]:
        """Try removing each fault; keep removals that preserve reproduction."""
        reductions: list[ReductionStep] = []
        if len(trial["faults"]) <= 1:
            return trial, reductions

        idx = 0
        while idx < len(trial["faults"]) and len(trial["faults"]) > 1 and not budget.exhausted:
            candidate = copy.deepcopy(trial)
            removed = candidate["faults"].pop(idx)

            result = self._evaluate(candidate, budget)
            if self._is_reproduced(result):
                info = fault_info(removed)
                logger.info(
                    "Removed fault %d (%s) — still reproduces (score=%.2f)",
                    idx,
                    info,
                    result.score,
                )
                reductions.append(
                    ReductionStep(
                        dimension="fault_count",
                        fault_index=idx,
                        before=info,
                        after="removed",
                        score=result.score,
                    )
                )
                trial = candidate
            else:
                idx += 1

        return trial, reductions

    def _reduce_magnitude(
        self, trial: Trial, fault_idx: int, budget: _Budget
    ) -> tuple[Trial, list[ReductionStep], tuple[float, float] | None]:
        """Binary search for minimum severity on a single fault.

        Returns (trial, reductions, bounds) where bounds is (lo, hi) --
        the final binary search interval for boundary validation.
        Returns None for bounds if the fault type is not reducible.
        """
        fault = trial["faults"][fault_idx]
        original_severity = fault["severity"]

        current_ms = parse_severity_magnitude(fault["fault_type"], fault["severity"])
        if current_ms is None:
            return trial, [], None

        lo = 0.0
        hi = current_ms
        best_severity = original_severity
        best_score = 1.0

        steps = min(self._config.magnitude_steps, budget.remaining)
        for _ in range(steps):
            if budget.exhausted:
                break
            mid = (lo + hi) / 2
            if mid <= 0:
                break

            new_severity = build_severity(fault["fault_type"], mid)
            candidate = self._with_severity(trial, fault_idx, new_severity)

            probe_result = self._probe.probe(candidate)
            budget.spend()
            if probe_result.reproduced:
                hi = mid
                best_severity = new_severity
                best_score = 1.0
            else:
                lo = mid

        reductions: list[ReductionStep] = []
        if best_severity != original_severity:
            trial = self._with_severity(trial, fault_idx, best_severity)
            reductions.append(
                ReductionStep(
                    dimension="magnitude",
                    fault_index=fault_idx,
                    before=original_severity,
                    after=best_severity,
                    score=best_score,
                )
            )

        return trial, reductions, (lo, hi)

    def _reduce_duration(
        self, trial: Trial, fault_idx: int, budget: _Budget
    ) -> tuple[Trial, list[ReductionStep]]:
        """Binary search for minimum duration on a single fault."""
        fault = trial["faults"][fault_idx]
        original_duration = fault["duration_s"]

        if original_duration <= 1:
            return trial, []

        lo = 1
        hi = original_duration
        best_duration = original_duration
        best_score = 1.0

        steps = min(self._config.duration_steps, budget.remaining)
        for _ in range(steps):
            if budget.exhausted:
                break
            mid = (lo + hi) // 2
            if mid <= 0 or mid >= hi:
                break

            candidate = self._with_duration(trial, fault_idx, mid)

            result = self._evaluate(candidate, budget)
            if self._is_reproduced(result):
                hi = mid
                best_duration = mid
                best_score = result.score
            else:
                lo = mid + 1

        reductions: list[ReductionStep] = []
        if best_duration != original_duration:
            trial = self._with_duration(trial, fault_idx, best_duration)
            reductions.append(
                ReductionStep(
                    dimension="duration",
                    fault_index=fault_idx,
                    before=str(original_duration),
                    after=str(best_duration),
                    score=best_score,
                )
            )

        return trial, reductions

    def _reduce_timing(
        self, trial: Trial, fault_idx: int, budget: _Budget
    ) -> tuple[Trial, list[ReductionStep]]:
        """Binary search for latest start time that still reproduces."""
        fault = trial["faults"][fault_idx]
        original_start = fault["start_s"]

        exec_time = trial["benchmark"].get("exec_time_s", 150)
        max_start = exec_time - fault["duration_s"]
        if max_start <= original_start:
            return trial, []

        lo = original_start
        hi = max_start
        best_start = original_start
        best_score = 1.0

        steps = min(self._config.timing_steps, budget.remaining)
        for _ in range(steps):
            if budget.exhausted:
                break
            mid = (lo + hi) // 2
            if mid <= lo:
                break

            candidate = self._with_start(trial, fault_idx, mid)

            result = self._evaluate(candidate, budget)
            if self._is_reproduced(result):
                lo = mid
                best_start = mid
                best_score = result.score
            else:
                hi = mid

        reductions: list[ReductionStep] = []
        if best_start != original_start:
            trial = self._with_start(trial, fault_idx, best_start)
            reductions.append(
                ReductionStep(
                    dimension="timing",
                    fault_index=fault_idx,
                    before=str(original_start),
                    after=str(best_start),
                    score=best_score,
                )
            )

        return trial, reductions

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _with_severity(trial: Trial, fault_idx: int, severity: str) -> Trial:
        new_faults: list[SlowFault] = [
            {**f, "severity": severity} if i == fault_idx else {**f}
            for i, f in enumerate(trial["faults"])
        ]
        result: Trial = {**trial, "faults": new_faults}
        return result

    @staticmethod
    def _with_duration(trial: Trial, fault_idx: int, duration_s: int) -> Trial:
        new_faults: list[SlowFault] = [
            {**f, "duration_s": duration_s} if i == fault_idx else {**f}
            for i, f in enumerate(trial["faults"])
        ]
        result: Trial = {**trial, "faults": new_faults}
        return result

    @staticmethod
    def _with_start(trial: Trial, fault_idx: int, start_s: int) -> Trial:
        new_faults: list[SlowFault] = [
            {**f, "start_s": start_s} if i == fault_idx else {**f}
            for i, f in enumerate(trial["faults"])
        ]
        result: Trial = {**trial, "faults": new_faults}
        return result

    def _evaluate(self, trial: Trial, budget: _Budget) -> OracleResult:
        """Run trial and evaluate oracle. Consumes one iteration from budget."""
        budget.spend()
        trial_result = self._runner.run(trial)

        if not trial_result["success"] or not trial_result.get("artifacts"):
            return OracleResult(
                issue_id=self._oracle.configured_issue_id,
                valid=False,
                reproduced=False,
                score=0.0,
                details={"error": trial_result.get("error") or "trial failed"},
            )

        return self._oracle.evaluate(artifacts=trial_result["artifacts"])

    def _is_reproduced(self, result: OracleResult) -> bool:
        return result.reproduced and result.score >= self._config.score_threshold


class _Budget:
    """Tracks iteration budget consumption."""

    __slots__ = ("_limit", "_used")

    def __init__(self, limit: int) -> None:
        self._limit = limit
        self._used = 0

    @property
    def remaining(self) -> int:
        return self._limit - self._used

    @property
    def exhausted(self) -> bool:
        return self._used >= self._limit

    @property
    def used(self) -> int:
        return self._used

    def spend(self) -> None:
        self._used += 1
