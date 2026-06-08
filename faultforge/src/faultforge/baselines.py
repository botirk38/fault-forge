"""Baseline search strategies for comparison against the greedy minimizer.

Provides alternative boundary-finding algorithms to demonstrate that
greedy dimensional minimization is competitive with more sophisticated
approaches while being simpler and more interpretable.

Strategies:
  - AdaptiveGridSearch: Refines a coarse grid around the first reproduction.
  - BayesianBoundarySearch: GP-UCB model of the reproduction function.
  - BisectionWithRepetition: Binary search with k-repeat confirmation.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from faultforge.probe import ProbeStrategy
from faultforge.severity import build_severity
from faultforge.trial import SlowFault, Trial


@dataclass(frozen=True)
class BoundaryEstimate:
    """Result of a baseline boundary search."""

    boundary: float
    trials_used: int
    severity_str: str
    converged: bool
    history: tuple[tuple[float, bool], ...] = ()


# ---------------------------------------------------------------------------
# Adaptive Grid Refinement
# ---------------------------------------------------------------------------


class AdaptiveGridSearch:
    """Two-phase grid search: coarse scan then local refinement.

    Phase 1: Evaluate a coarse grid (e.g., 8 points spanning the range).
    Phase 2: Refine around the lowest reproducing point with a finer grid.

    This models a reasonable human heuristic: start broad, zoom in.
    """

    def __init__(
        self,
        probe: ProbeStrategy,
        coarse_points: int = 8,
        refine_points: int = 10,
    ) -> None:
        self._probe = probe
        self._coarse_points = coarse_points
        self._refine_points = refine_points

    def find_boundary(
        self,
        trial: Trial,
        fault_index: int,
        max_severity: float,
    ) -> BoundaryEstimate:
        """Search for the minimum reproducing severity."""
        fault = trial["faults"][fault_index]
        history: list[tuple[float, bool]] = []
        trials_used = 0

        # Phase 1: coarse grid
        coarse_step = max_severity / self._coarse_points
        lowest_repro: float | None = None

        for i in range(self._coarse_points, 0, -1):
            severity_val = i * coarse_step
            candidate = _with_severity_val(trial, fault_index, fault, severity_val)
            result = self._probe.probe(candidate)
            trials_used += 1
            reproduced = result.reproduced
            history.append((severity_val, reproduced))
            if reproduced:
                lowest_repro = severity_val

        if lowest_repro is None:
            return BoundaryEstimate(
                boundary=max_severity,
                trials_used=trials_used,
                severity_str=build_severity(fault["fault_type"], max_severity),
                converged=False,
                history=tuple(history),
            )

        # Phase 2: refine around lowest reproducing point
        refine_lo = max(0.0, lowest_repro - coarse_step)
        refine_hi = lowest_repro
        refine_step = (refine_hi - refine_lo) / self._refine_points

        for i in range(self._refine_points):
            severity_val = refine_lo + i * refine_step
            if severity_val <= 0:
                continue
            candidate = _with_severity_val(trial, fault_index, fault, severity_val)
            result = self._probe.probe(candidate)
            trials_used += 1
            reproduced = result.reproduced
            history.append((severity_val, reproduced))
            if reproduced and severity_val < lowest_repro:
                lowest_repro = severity_val

        return BoundaryEstimate(
            boundary=lowest_repro,
            trials_used=trials_used,
            severity_str=build_severity(fault["fault_type"], lowest_repro),
            converged=True,
            history=tuple(history),
        )


# ---------------------------------------------------------------------------
# Bayesian Boundary Search (GP-UCB inspired)
# ---------------------------------------------------------------------------


@dataclass
class _Observation:
    severity: float
    reproduced: bool


class BayesianBoundarySearch:
    """Gaussian-process-inspired boundary search.

    Uses a simplified acquisition function: probe the point that
    maximally reduces uncertainty about the boundary location.
    Maintains a sorted list of observations and targets the largest
    gap between a non-reproducing and reproducing point.

    This is a lightweight proxy for full GP-UCB (which would require
    scipy/sklearn) that captures the key benefit: intelligent point
    selection based on observed data.
    """

    def __init__(
        self,
        probe: ProbeStrategy,
        budget: int = 18,
        initial_samples: int = 4,
    ) -> None:
        self._probe = probe
        self._budget = budget
        self._initial_samples = initial_samples

    def find_boundary(
        self,
        trial: Trial,
        fault_index: int,
        max_severity: float,
    ) -> BoundaryEstimate:
        """Search for boundary using uncertainty-guided sampling."""
        fault = trial["faults"][fault_index]
        observations: list[_Observation] = []
        history: list[tuple[float, bool]] = []
        trials_used = 0

        # Initial space-filling samples (log-spaced for better coverage)
        initial_points = _log_space(0.1, max_severity, self._initial_samples)
        for severity_val in initial_points:
            if trials_used >= self._budget:
                break
            candidate = _with_severity_val(trial, fault_index, fault, severity_val)
            result = self._probe.probe(candidate)
            trials_used += 1
            reproduced = result.reproduced
            observations.append(_Observation(severity_val, reproduced))
            history.append((severity_val, reproduced))

        # Iterative refinement: target the largest uncertain gap
        while trials_used < self._budget:
            next_point = self._select_next(observations, max_severity)
            if next_point is None:
                break

            candidate = _with_severity_val(trial, fault_index, fault, next_point)
            result = self._probe.probe(candidate)
            trials_used += 1
            reproduced = result.reproduced
            observations.append(_Observation(next_point, reproduced))
            history.append((next_point, reproduced))

        # Extract boundary: lowest reproducing severity observed
        repro_severities = [o.severity for o in observations if o.reproduced]
        if not repro_severities:
            return BoundaryEstimate(
                boundary=max_severity,
                trials_used=trials_used,
                severity_str=build_severity(fault["fault_type"], max_severity),
                converged=False,
                history=tuple(history),
            )

        boundary = min(repro_severities)
        return BoundaryEstimate(
            boundary=boundary,
            trials_used=trials_used,
            severity_str=build_severity(fault["fault_type"], boundary),
            converged=True,
            history=tuple(history),
        )

    def _select_next(self, observations: list[_Observation], max_severity: float) -> float | None:
        """Select next probe point: midpoint of largest boundary-crossing gap."""
        sorted_obs = sorted(observations, key=lambda o: o.severity)

        # Find the boundary-crossing gap (last non-repro before first repro)
        best_gap = 0.0
        best_midpoint: float | None = None

        # Check gap from 0 to first observation
        if sorted_obs and sorted_obs[0].reproduced:
            gap = sorted_obs[0].severity
            if gap > best_gap:
                best_gap = gap
                best_midpoint = gap / 2

        # Check gaps between adjacent observations with different outcomes
        for i in range(len(sorted_obs) - 1):
            curr = sorted_obs[i]
            nxt = sorted_obs[i + 1]
            if not curr.reproduced and nxt.reproduced:
                gap = nxt.severity - curr.severity
                if gap > best_gap:
                    best_gap = gap
                    best_midpoint = (curr.severity + nxt.severity) / 2

        # Check gap from last observation to max (if last doesn't reproduce)
        if sorted_obs and not sorted_obs[-1].reproduced:
            gap = max_severity - sorted_obs[-1].severity
            if gap > best_gap:
                best_gap = gap
                best_midpoint = (sorted_obs[-1].severity + max_severity) / 2

        # Stop if gap is negligible
        if best_gap < max_severity * 0.001:
            return None

        return best_midpoint


# ---------------------------------------------------------------------------
# Bisection with Repetition
# ---------------------------------------------------------------------------


class BisectionWithRepetition:
    """Standard binary search with k-repeat confirmation at each midpoint.

    At each step, probes the midpoint k times and uses majority vote.
    This is the most natural noise-tolerant extension of binary search,
    and serves as the direct comparison for the greedy minimizer's
    single-shot approach.
    """

    def __init__(
        self,
        probe: ProbeStrategy,
        steps: int = 8,
        repeats_per_step: int = 3,
    ) -> None:
        self._probe = probe
        self._steps = steps
        self._repeats = repeats_per_step

    def find_boundary(
        self,
        trial: Trial,
        fault_index: int,
        max_severity: float,
    ) -> BoundaryEstimate:
        """Binary search with repeated probing at each midpoint."""
        fault = trial["faults"][fault_index]
        history: list[tuple[float, bool]] = []
        trials_used = 0

        lo = 0.0
        hi = max_severity

        for _ in range(self._steps):
            mid = (lo + hi) / 2
            if mid <= 0:
                break

            # Probe k times and take majority
            repro_count = 0
            for _ in range(self._repeats):
                candidate = _with_severity_val(trial, fault_index, fault, mid)
                result = self._probe.probe(candidate)
                trials_used += 1
                if result.reproduced:
                    repro_count += 1

            reproduced = repro_count > self._repeats // 2
            history.append((mid, reproduced))

            if reproduced:
                hi = mid
            else:
                lo = mid

        severity_str = build_severity(fault["fault_type"], hi)
        return BoundaryEstimate(
            boundary=hi,
            trials_used=trials_used,
            severity_str=severity_str,
            converged=True,
            history=tuple(history),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _with_severity_val(trial: Trial, fault_idx: int, fault: SlowFault, value: float) -> Trial:
    """Return trial copy with one fault's severity set to a numeric value."""
    severity_str = build_severity(fault["fault_type"], value)
    new_faults: list[SlowFault] = [
        {**f, "severity": severity_str} if i == fault_idx else {**f}
        for i, f in enumerate(trial["faults"])
    ]
    result: Trial = {**trial, "faults": new_faults}
    return result


def _log_space(lo: float, hi: float, n: int) -> list[float]:
    """Generate n log-spaced points between lo and hi."""
    if n <= 0:
        return []
    if n == 1:
        return [(lo + hi) / 2]
    log_lo = math.log(max(lo, 0.01))
    log_hi = math.log(hi)
    step = (log_hi - log_lo) / (n - 1)
    return [math.exp(log_lo + i * step) for i in range(n)]
