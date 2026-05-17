"""Xinda trial runner for FaultForge.

Converts FaultForge recipes into Xinda trials and executes them.
"""

from __future__ import annotations

import logging

from xinda import BenchmarkConfig, SlowFault, SystemConfig, Trial, TrialResult, XindaClient

from faultforge.recipe import Fault, Recipe

logger = logging.getLogger(__name__)

# Mapping from FaultForge fault model names to Xinda fault types.
_MODEL_TO_FAULT_TYPE: dict[str, str] = {
    "network_delay": "nw",
    "disk_delay": "fs",
    "none": "none",
}


def _fault_to_slow_fault(fault: Fault) -> SlowFault | None:
    """Convert a FaultForge Fault to a Xinda SlowFault.

    Returns None if the fault is not a Xinda environmental fault.
    """
    if fault.provider != "xinda":
        return None

    fault_type = _MODEL_TO_FAULT_TYPE.get(fault.model)
    if fault_type is None:
        raise ValueError(
            f"Unknown Xinda fault model {fault.model!r}. Supported: {sorted(_MODEL_TO_FAULT_TYPE)}"
        )

    location = fault.target.node or fault.target.component or "leader"

    delay_ms = fault.params.delay_ms
    if delay_ms is not None:
        severity = f"slow-{delay_ms}ms"
    else:
        severity = "slow-100ms"

    return SlowFault(
        fault_type=fault_type,
        location=location,
        duration_s=int(fault.timing.duration_s) if fault.timing.duration_s else 60,
        severity=severity,
        start_s=int(fault.timing.start_s),
    )


def _build_trials(
    recipe: Recipe,
    system_config: SystemConfig,
    benchmark_config: BenchmarkConfig,
) -> list[Trial]:
    """Build Xinda Trial objects from a FaultForge Recipe.

    Only faults with provider="xinda" are converted. Other provider faults
    are skipped (they will be handled by their own runners).
    """
    xinda_faults = [f for f in recipe.faults if f.provider == "xinda"]

    if not xinda_faults:
        return []

    trials: list[Trial] = []
    for fault in xinda_faults:
        slow_fault = _fault_to_slow_fault(fault)
        if slow_fault is None:
            continue

        trial = Trial(
            system=system_config,
            benchmark=benchmark_config,
            fault=slow_fault,
            iteration=1,
            version=system_config.version,
        )
        trials.append(trial)

    return trials


def run_recipe(
    recipe: Recipe,
    system_config: SystemConfig,
    benchmark_config: BenchmarkConfig,
) -> list[TrialResult]:
    """Run all Xinda faults from a recipe and return results.

    Each Xinda fault becomes its own trial. Results are returned in the
    same order as the faults appear in the recipe.
    """
    trials = _build_trials(recipe, system_config, benchmark_config)

    if not trials:
        logger.info("No Xinda faults in recipe, skipping Xinda runner")
        return []

    client = XindaClient()
    results: list[TrialResult] = []

    for trial in trials:
        logger.info(
            "Running Xinda trial: system=%s fault=%s location=%s severity=%s",
            trial.system.name,
            trial.fault.fault_type,
            trial.fault.location,
            trial.fault.severity,
        )
        result = client.run(trial)
        results.append(result)

    return results
