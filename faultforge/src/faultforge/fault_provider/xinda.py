"""Xinda environmental (slow) fault execution for FaultForge recipes."""

from __future__ import annotations

import logging

from xinda import BenchmarkConfig, SystemConfig, Trial, XindaClient
from xinda import SlowFault as SdkSlowFault

from faultforge.fault_provider.base import ProviderRunResult
from faultforge.fault_provider.fault import SlowFault
from faultforge.recipe import Recipe

logger = logging.getLogger(__name__)


class Xinda:
    """Environmental slow faults via Xinda SDK."""

    def _sdk_slow_fault(self, fault: SlowFault) -> SdkSlowFault:
        match fault.fault_type:
            case "nw":
                return SdkSlowFault.network(
                    location=fault.location,
                    severity=fault.severity,
                    duration_s=fault.duration_s,
                    start_s=fault.start_s,
                    if_restart=fault.if_restart,
                )
            case "fs":
                return SdkSlowFault.filesystem(
                    location=fault.location,
                    severity=fault.severity,
                    duration_s=fault.duration_s,
                    start_s=fault.start_s,
                    if_restart=fault.if_restart,
                )
            case "none":
                return SdkSlowFault(
                    fault_type="none",
                    location=fault.location,
                    duration_s=fault.duration_s,
                    severity="none",
                    start_s=fault.start_s,
                    if_restart=fault.if_restart,
                )
            case _:
                msg = f"unsupported Xinda fault model {fault.fault_type!r}"
                raise ValueError(msg)

    def run(
        self,
        recipe: Recipe,
        system_config: SystemConfig,
        benchmark_config: BenchmarkConfig,
    ) -> tuple[ProviderRunResult, ...]:
        trial_pairs = self._trial_pairs_for_recipe(recipe, system_config, benchmark_config)
        if not trial_pairs:
            logger.info("No Xinda faults in recipe, skipping")
            return ()

        client = XindaClient()
        return tuple(self._trial_result(client, trial, fault) for trial, fault in trial_pairs)

    def _trial_pairs_for_recipe(
        self,
        recipe: Recipe,
        system_config: SystemConfig,
        benchmark_config: BenchmarkConfig,
    ) -> list[tuple[Trial, SlowFault]]:
        pairs: list[tuple[Trial, SlowFault]] = []
        for fault in recipe.faults:
            if not isinstance(fault, SlowFault):
                msg = f"expected SlowFault faults for Xinda, got {type(fault).__name__}"
                raise TypeError(msg)
            pairs.append(
                (
                    Trial(
                        system=system_config,
                        benchmark=benchmark_config,
                        fault=self._sdk_slow_fault(fault),
                        iteration=1,
                        version=system_config.version,
                    ),
                    fault,
                )
            )
        return pairs

    def _trial_result(
        self,
        client: XindaClient,
        trial: Trial,
        fault: SlowFault,
    ) -> ProviderRunResult:
        logger.info(
            "Running Xinda trial: system=%s fault=%s location=%s severity=%s",
            trial.system.name,
            trial.fault.fault_type,
            trial.fault.location,
            trial.fault.severity,
        )
        tr = client.run(trial)
        return ProviderRunResult(
            success=bool(tr.success),
            fault_id=fault.id,
            log_path=tr.log_path,
            error=tr.error,
        )
