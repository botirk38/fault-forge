"""Normalized provider execution primitives and contract."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from xinda import BenchmarkConfig, SystemConfig

from faultforge.fault_provider.recipe import Recipe


@dataclass(frozen=True, slots=True)
class ProviderRunResult:
    """Normalized outcome after running faults for one recipe slice."""

    success: bool
    fault_id: str
    log_path: str | None = None
    error: str | None = None
    note: str | None = None


class FaultProvider(Protocol):
    """Execute declarative trials; backends know only ``Recipe`` and Xinda configs."""

    def run(
        self,
        recipe: Recipe,
        system_config: SystemConfig,
        benchmark_config: BenchmarkConfig,
    ) -> Sequence[ProviderRunResult]:
        """Run fault execution for ``recipe`` and return normalized results."""
