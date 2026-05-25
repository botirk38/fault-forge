"""RunTrial protocol — the interface for executing trials."""

from __future__ import annotations

from typing import Protocol

from faultforge.trial import Trial, TrialResult


class RunTrial(Protocol):
    """Protocol for anything that can execute a Trial."""

    def run(self, trial: Trial) -> TrialResult: ...
