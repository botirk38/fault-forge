"""Probe strategies for fault trial evaluation.

A probe strategy determines how a single binary-search decision is made.
The simplest strategy evaluates a trial once; noise-tolerant strategies
repeat the evaluation and apply a voting rule to handle non-determinism
at boundary severities.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from faultforge.oracle import Oracle, OracleResult
from faultforge.runner import RunTrial
from faultforge.trial import Trial


class ProbeStrategy(Protocol):
    """Decides whether a trial reproduces the target symptom."""

    def probe(self, trial: Trial) -> ProbeResult: ...

    @property
    def probes_consumed(self) -> int: ...


@dataclass(frozen=True)
class ProbeResult:
    """Outcome of a single probe decision."""

    reproduced: bool
    repro_rate: float
    evaluations: int


class SingleShotProbe:
    """Evaluate once. Fast, but vulnerable to non-determinism at boundaries."""

    def __init__(self, runner: RunTrial, oracle: Oracle, threshold: float = 0.5) -> None:
        self._runner = runner
        self._oracle = oracle
        self._threshold = threshold
        self._consumed = 0

    @property
    def probes_consumed(self) -> int:
        return self._consumed

    def probe(self, trial: Trial) -> ProbeResult:
        self._consumed += 1
        result = self._evaluate(trial)
        reproduced = result.reproduced and result.score >= self._threshold
        return ProbeResult(
            reproduced=reproduced,
            repro_rate=1.0 if reproduced else 0.0,
            evaluations=1,
        )

    def _evaluate(self, trial: Trial) -> OracleResult:
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


class MajorityVoteProbe:
    """Repeat evaluation k times; require majority to reproduce.

    Provides resilience against transient non-determinism at boundary
    severities. The majority threshold controls the trade-off between
    false positives (threshold too low) and false negatives (too high).
    """

    def __init__(
        self,
        runner: RunTrial,
        oracle: Oracle,
        repeats: int = 3,
        majority: float = 0.66,
        threshold: float = 0.5,
    ) -> None:
        self._runner = runner
        self._oracle = oracle
        self._repeats = repeats
        self._majority = majority
        self._threshold = threshold
        self._consumed = 0

    @property
    def probes_consumed(self) -> int:
        return self._consumed

    def probe(self, trial: Trial) -> ProbeResult:
        repro_count = 0
        for _ in range(self._repeats):
            self._consumed += 1
            result = self._evaluate(trial)
            if result.reproduced and result.score >= self._threshold:
                repro_count += 1

        rate = repro_count / self._repeats
        return ProbeResult(
            reproduced=rate >= self._majority,
            repro_rate=rate,
            evaluations=self._repeats,
        )

    def _evaluate(self, trial: Trial) -> OracleResult:
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
