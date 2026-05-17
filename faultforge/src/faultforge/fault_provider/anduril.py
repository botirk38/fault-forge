"""Anduril in-process fault execution (stub until wired to the Java tool)."""

from __future__ import annotations

import logging

from xinda import BenchmarkConfig, SystemConfig

from faultforge.fault_provider.base import ProviderRunResult
from faultforge.fault_provider.fault import InProcessFault
from faultforge.recipe import Recipe

logger = logging.getLogger(__name__)


class Anduril:
    """In-process instrumentation faults (stub)."""

    def run(
        self,
        recipe: Recipe,
        system_config: SystemConfig,
        benchmark_config: BenchmarkConfig,
    ) -> tuple[ProviderRunResult, ...]:
        logger.warning("Anduril execution is not implemented yet")
        _ = system_config, benchmark_config
        results = []
        for fault in recipe.faults:
            if not isinstance(fault, InProcessFault):
                msg = f"expected InProcessFault faults for Anduril, got {type(fault).__name__}"
                raise TypeError(msg)
            results.append(
                ProviderRunResult(
                    success=False,
                    fault_id=fault.id,
                    note="execution_not_implemented",
                )
            )
        return tuple(results)
