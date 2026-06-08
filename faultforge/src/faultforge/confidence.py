"""Boundary confidence estimation for converged minimization results.

After binary search converges, the boundary point sits between the last
non-reproducing value (lo) and the last reproducing value (hi). This
module validates that transition by dense probing around the boundary,
producing a confidence interval with measured reproduction rates.
"""

from __future__ import annotations

from dataclasses import dataclass

from faultforge.probe import ProbeStrategy
from faultforge.severity import build_severity
from faultforge.trial import SlowFault, Trial


@dataclass(frozen=True)
class BoundaryInterval:
    """Validated confidence interval for a severity boundary.

    Attributes:
        fault_index: Index of the fault whose severity was minimized.
        lo: Last severity that did NOT reproduce (lower bound).
        hi: Last severity that DID reproduce (upper bound / convergence point).
        repro_rate_above: Reproduction rate at hi over validation probes.
        repro_rate_below: Reproduction rate at lo over validation probes.
        confidence: Separation quality (repro_rate_above - repro_rate_below).
        validation_probes: Number of probes used for validation.
    """

    fault_index: int
    lo: float
    hi: float
    repro_rate_above: float
    repro_rate_below: float
    confidence: float
    validation_probes: int


class BoundaryValidator:
    """Validates a converged boundary by probing above and below.

    Given the binary search result (lo, hi), this validator runs
    additional probes at both points to measure the reproduction
    rate transition. A clean boundary shows ~100% above and ~0% below.
    """

    def __init__(self, probe: ProbeStrategy, validation_probes: int = 5) -> None:
        self._probe = probe
        self._n_probes = validation_probes

    def validate(
        self,
        trial: Trial,
        fault_index: int,
        lo: float,
        hi: float,
    ) -> BoundaryInterval:
        """Probe the boundary and return a validated interval."""
        fault = trial["faults"][fault_index]

        above_repro = self._measure_rate(trial, fault, fault_index, hi)
        below_repro = self._measure_rate(trial, fault, fault_index, lo)

        confidence = max(above_repro - below_repro, 0.0)

        return BoundaryInterval(
            fault_index=fault_index,
            lo=lo,
            hi=hi,
            repro_rate_above=above_repro,
            repro_rate_below=below_repro,
            confidence=confidence,
            validation_probes=self._n_probes,
        )

    def _measure_rate(
        self,
        trial: Trial,
        fault: SlowFault,
        fault_index: int,
        severity_value: float,
    ) -> float:
        """Measure reproduction rate at a specific severity."""
        severity_str = build_severity(fault["fault_type"], severity_value)
        candidate = _with_severity(trial, fault_index, severity_str)

        repro_count = 0
        for _ in range(self._n_probes):
            result = self._probe.probe(candidate)
            if result.reproduced:
                repro_count += 1

        return repro_count / self._n_probes


def _with_severity(trial: Trial, fault_idx: int, severity: str) -> Trial:
    """Return a copy of trial with one fault's severity replaced."""
    new_faults: list[SlowFault] = [
        {**f, "severity": severity} if i == fault_idx else {**f}
        for i, f in enumerate(trial["faults"])
    ]
    result: Trial = {**trial, "faults": new_faults}
    return result
