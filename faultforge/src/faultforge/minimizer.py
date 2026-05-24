"""Fault recipe minimizer for FaultForge.

Given a reproducing trial (one where the oracle confirms the symptom),
iteratively reduces fault parameters to find the minimal fault recipe —
the simplest combination that still triggers the vulnerability.
"""

from __future__ import annotations

import copy
import logging
import re
from dataclasses import dataclass, field

from faultforge.oracle import Oracle, OracleResult
from faultforge.runner import TrialRunner
from faultforge.trial import SlowFaultKind, Trial

logger = logging.getLogger(__name__)


@dataclass
class MinimizationConfig:
    """Controls the minimization budget and behavior."""

    max_iterations: int = 50
    score_threshold: float = 0.5
    magnitude_steps: int = 8
    duration_steps: int = 5
    timing_steps: int = 5
    require_consecutive: int = 1


@dataclass
class ReductionStep:
    """Record of one successful reduction."""

    dimension: str
    fault_index: int
    before: str
    after: str
    score: float


@dataclass
class MinimizationResult:
    """Output of the minimization process."""

    original: Trial
    minimized: Trial
    iterations_used: int
    reductions: list[ReductionStep] = field(default_factory=list)
    final_score: float = 0.0


class Minimizer:
    """Greedy fault recipe minimizer.

    Takes a reproducing Trial and reduces fault parameters (count,
    magnitude, duration, timing) to find the smallest recipe that
    still triggers the oracle symptom.
    """

    def __init__(
        self,
        runner: TrialRunner,
        oracle: Oracle,
        config: MinimizationConfig | None = None,
    ) -> None:
        self._runner = runner
        self._oracle = oracle
        self._config = config or MinimizationConfig()
        self._iterations_used = 0

    @property
    def budget_remaining(self) -> int:
        return self._config.max_iterations - self._iterations_used

    def minimize(self, trial: Trial) -> MinimizationResult:
        """Run the full minimization pipeline on a reproducing trial.

        Returns the minimal trial that still reproduces the symptom,
        along with the reduction log and iteration count.
        """
        self._iterations_used = 0
        original = copy.deepcopy(trial)
        reductions: list[ReductionStep] = []

        # Verify the trial actually reproduces
        initial_result = self._evaluate(trial)
        if not initial_result.reproduced:
            logger.warning(
                "Trial does not reproduce (score=%.2f). Returning as-is.",
                initial_result.score,
            )
            return MinimizationResult(
                original=original,
                minimized=trial,
                iterations_used=self._iterations_used,
                reductions=[],
                final_score=initial_result.score,
            )

        # Phase 1: Reduce fault count
        trial, count_reductions = self._reduce_fault_count(trial)
        reductions.extend(count_reductions)

        # Phase 2: For each remaining fault, reduce dimensions
        for fault_idx in range(len(trial.faults)):
            if self.budget_remaining <= 0:
                break

            # Reduce magnitude
            trial, mag_steps = self._reduce_magnitude(trial, fault_idx)
            reductions.extend(mag_steps)

            if self.budget_remaining <= 0:
                break

            # Reduce duration
            trial, dur_steps = self._reduce_duration(trial, fault_idx)
            reductions.extend(dur_steps)

            if self.budget_remaining <= 0:
                break

            # Narrow timing (find latest start that still works)
            trial, time_steps = self._reduce_timing(trial, fault_idx)
            reductions.extend(time_steps)

        # Get final score
        final_result = self._evaluate(trial)

        return MinimizationResult(
            original=original,
            minimized=trial,
            iterations_used=self._iterations_used,
            reductions=reductions,
            final_score=final_result.score,
        )

    def _reduce_fault_count(self, trial: Trial) -> tuple[Trial, list[ReductionStep]]:
        """Try removing each fault; keep removals that preserve reproduction."""
        reductions: list[ReductionStep] = []
        if len(trial.faults) <= 1:
            return trial, reductions

        idx = 0
        while idx < len(trial.faults) and len(trial.faults) > 1 and self.budget_remaining > 0:
            candidate = copy.deepcopy(trial)
            removed = candidate.faults.pop(idx)

            result = self._evaluate(candidate)
            if result.reproduced and result.score >= self._config.score_threshold:
                logger.info(
                    "Removed fault %d (%s) — still reproduces (score=%.2f)",
                    idx,
                    removed.info,
                    result.score,
                )
                reductions.append(
                    ReductionStep(
                        dimension="fault_count",
                        fault_index=idx,
                        before=removed.info,
                        after="removed",
                        score=result.score,
                    )
                )
                trial = candidate
                # Don't increment idx — next fault shifted down
            else:
                idx += 1

        return trial, reductions

    def _reduce_magnitude(self, trial: Trial, fault_idx: int) -> tuple[Trial, list[ReductionStep]]:
        """Binary search for minimum severity on a single fault."""
        reductions: list[ReductionStep] = []
        fault = trial.faults[fault_idx]
        original_severity = fault.severity

        current_ms = parse_severity_ms(fault.fault_type, fault.severity)
        if current_ms is None:
            return trial, reductions

        lo = 0.0
        hi = current_ms
        best_severity = original_severity
        best_score = 1.0

        steps = min(self._config.magnitude_steps, self.budget_remaining)
        for _ in range(steps):
            if self.budget_remaining <= 0:
                break
            mid = (lo + hi) / 2
            if mid <= 0:
                break

            candidate = copy.deepcopy(trial)
            new_severity = build_severity(fault.fault_type, mid)
            candidate.faults[fault_idx].severity = new_severity

            result = self._evaluate(candidate)
            if result.reproduced and result.score >= self._config.score_threshold:
                hi = mid
                best_severity = new_severity
                best_score = result.score
            else:
                lo = mid

        if best_severity != original_severity:
            trial = copy.deepcopy(trial)
            trial.faults[fault_idx].severity = best_severity
            reductions.append(
                ReductionStep(
                    dimension="magnitude",
                    fault_index=fault_idx,
                    before=original_severity,
                    after=best_severity,
                    score=best_score,
                )
            )

        return trial, reductions

    def _reduce_duration(self, trial: Trial, fault_idx: int) -> tuple[Trial, list[ReductionStep]]:
        """Binary search for minimum duration on a single fault."""
        reductions: list[ReductionStep] = []
        fault = trial.faults[fault_idx]
        original_duration = fault.duration_s

        if original_duration <= 1:
            return trial, reductions

        lo = 1
        hi = original_duration
        best_duration = original_duration
        best_score = 1.0

        steps = min(self._config.duration_steps, self.budget_remaining)
        for _ in range(steps):
            if self.budget_remaining <= 0:
                break
            mid = (lo + hi) // 2
            if mid <= 0 or mid >= hi:
                break

            candidate = copy.deepcopy(trial)
            candidate.faults[fault_idx].duration_s = mid

            result = self._evaluate(candidate)
            if result.reproduced and result.score >= self._config.score_threshold:
                hi = mid
                best_duration = mid
                best_score = result.score
            else:
                lo = mid + 1

        if best_duration != original_duration:
            trial = copy.deepcopy(trial)
            trial.faults[fault_idx].duration_s = best_duration
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

    def _reduce_timing(self, trial: Trial, fault_idx: int) -> tuple[Trial, list[ReductionStep]]:
        """Binary search for latest start time that still reproduces.

        A later start means the system needs less "warm-up" exposure,
        making the recipe more specific about when the vulnerability
        window opens.
        """
        reductions: list[ReductionStep] = []
        fault = trial.faults[fault_idx]
        original_start = fault.start_s

        # Try to push the start time later
        # Use benchmark exec time as upper bound
        max_start = trial.benchmark.exec_time_s - fault.duration_s
        if max_start <= original_start:
            return trial, reductions

        lo = original_start
        hi = max_start
        best_start = original_start
        best_score = 1.0

        steps = min(self._config.timing_steps, self.budget_remaining)
        for _ in range(steps):
            if self.budget_remaining <= 0:
                break
            mid = (lo + hi) // 2
            if mid <= lo:
                break

            candidate = copy.deepcopy(trial)
            candidate.faults[fault_idx].start_s = mid

            result = self._evaluate(candidate)
            if result.reproduced and result.score >= self._config.score_threshold:
                lo = mid
                best_start = mid
                best_score = result.score
            else:
                hi = mid

        if best_start != original_start:
            trial = copy.deepcopy(trial)
            trial.faults[fault_idx].start_s = best_start
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

    def _evaluate(self, trial: Trial) -> OracleResult:
        """Run trial and evaluate oracle. Counts against iteration budget."""
        self._iterations_used += 1
        trial_result = self._runner.run(trial)

        if not trial_result.success or not trial_result.artifacts:
            return OracleResult(
                issue_id=self._oracle.configured_issue_id,
                valid=False,
                reproduced=False,
                score=0.0,
                details={"error": trial_result.error or "trial failed"},
            )

        return self._oracle.evaluate(artifacts=trial_result.artifacts)


# --- Severity parsing utilities ---

_NW_DELAY_RE = re.compile(r"slow-(\d+(?:\.\d+)?)(us|ms|s)$")
_NW_FLAKY_RE = re.compile(r"flaky-p(\d+(?:\.\d+)?)$")
_FS_DELAY_RE = re.compile(r"^(\d+)$")


def parse_severity_ms(fault_type: SlowFaultKind, severity: str) -> float | None:
    """Extract numeric magnitude from a severity string.

    Returns the value normalized to milliseconds for network faults,
    or microseconds for filesystem faults.  Returns None if the
    severity format is not reducible (e.g., cpu/mem/process).
    """
    if fault_type == "nw":
        m = _NW_DELAY_RE.match(severity)
        if m:
            value = float(m.group(1))
            unit = m.group(2)
            if unit == "us":
                return value / 1000.0
            if unit == "ms":
                return value
            if unit == "s":
                return value * 1000.0
        m = _NW_FLAKY_RE.match(severity)
        if m:
            return float(m.group(1))
        return None

    if fault_type == "fs":
        m = _FS_DELAY_RE.match(severity)
        if m:
            return float(m.group(1))
        return None

    return None


def build_severity(fault_type: SlowFaultKind, value: float) -> str:
    """Build severity string from numeric value.

    For network: produces 'slow-Xus', 'slow-Xms', or 'slow-Xs'
    depending on magnitude.  For network flaky: 'flaky-pX'.
    For filesystem: integer microseconds.
    """
    if fault_type == "nw":
        if value < 1.0:
            us = value * 1000.0
            if us == int(us):
                return f"slow-{int(us)}us"
            return f"slow-{us:.1f}us"
        if value >= 1000.0:
            s = value / 1000.0
            if s == int(s):
                return f"slow-{int(s)}s"
            return f"slow-{s:.1f}s"
        if value == int(value):
            return f"slow-{int(value)}ms"
        return f"slow-{value:.1f}ms"

    if fault_type == "fs":
        return str(int(value))

    return str(int(value))
