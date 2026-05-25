"""End-to-end experiment orchestrator.

Connects the Minimizer to LiveRunner to produce minimized fault recipes
from real Docker container experiments.

Usage:
    from faultforge.live.orchestrator import run_minimization
    results = run_minimization("etcd", oracle_path="path/to/oracle.yaml")
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

from faultforge.live.runner import LiveRunner
from faultforge.minimizer import MinimizationConfig, MinimizationResult, Minimizer
from faultforge.oracle import Oracle
from faultforge.trial import SlowFault, SlowFaultKind, Trial

logger = logging.getLogger(__name__)


@dataclass
class ExperimentResult:
    """Result of a single end-to-end minimization experiment."""

    system: str
    oracle_id: str
    initial_trial: Trial
    minimization: MinimizationResult
    wall_time_s: float
    error: str | None = None


@dataclass
class ExperimentSuite:
    """Collection of experiment results across systems/oracles."""

    results: list[ExperimentResult] = field(default_factory=list)

    def summary_table(self) -> str:
        """Generate a markdown summary table."""
        lines = [
            "| System | Oracle | Initial Severity | Minimized Severity"
            " | Iterations | Reductions | Time |",
            "|--------|--------|-----------------|-------------------|"
            "------------|------------|------|",
        ]
        for r in self.results:
            if r.error:
                lines.append(
                    f"| {r.system} | {r.oracle_id} | — | ERROR: {r.error}"
                    f" | — | — | {r.wall_time_s:.1f}s |"
                )
                continue

            orig_faults = r.minimization.original["faults"]
            mini_faults = r.minimization.minimized["faults"]
            orig_sev = orig_faults[0]["severity"] if orig_faults else "—"
            mini_sev = mini_faults[0]["severity"] if mini_faults else "—"
            n_reductions = len(r.minimization.reductions)

            lines.append(
                f"| {r.system} | {r.oracle_id} | {orig_sev}"
                f" | {mini_sev} | {r.minimization.iterations_used}"
                f" | {n_reductions} | {r.wall_time_s:.1f}s |"
            )
        return "\n".join(lines)

    def to_json(self) -> str:
        """Serialize results to JSON."""
        records = []
        for r in self.results:
            records.append(
                {
                    "system": r.system,
                    "oracle_id": r.oracle_id,
                    "initial_severity": (
                        r.initial_trial["faults"][0]["severity"]
                        if r.initial_trial["faults"]
                        else None
                    ),
                    "minimized_severity": (
                        r.minimization.minimized["faults"][0]["severity"]
                        if r.minimization.minimized["faults"]
                        else None
                    ),
                    "initial_duration_s": (
                        r.initial_trial["faults"][0]["duration_s"]
                        if r.initial_trial["faults"]
                        else None
                    ),
                    "minimized_duration_s": (
                        r.minimization.minimized["faults"][0]["duration_s"]
                        if r.minimization.minimized["faults"]
                        else None
                    ),
                    "iterations_used": r.minimization.iterations_used,
                    "reductions": len(r.minimization.reductions),
                    "final_score": r.minimization.final_score,
                    "wall_time_s": r.wall_time_s,
                    "error": r.error,
                }
            )
        return json.dumps(records, indent=2)


def make_initial_trial(
    system: str,
    fault_type: str = "nw",
    location: str = "node1",
    severity: str = "slow-5s",
    duration_s: int = 30,
    start_s: int = 0,
) -> Trial:
    """Construct an initial trial at high severity for minimization."""
    fault: SlowFault = {
        "fault_type": cast(SlowFaultKind, fault_type),
        "location": location,
        "duration_s": duration_s,
        "severity": severity,
        "start_s": start_s,
        "if_restart": False,
    }
    return {
        "trial_id": f"{system}-minimize-{int(time.time())}",
        "system": {"name": system},
        "benchmark": {"name": "default"},
        "faults": [fault],
    }


def run_minimization(
    system: str,
    oracle_path: str | Path,
    *,
    fault_type: str = "nw",
    location: str = "node1",
    initial_severity: str = "slow-5s",
    initial_duration_s: int = 30,
    max_iterations: int = 30,
    log_dir: str | None = None,
) -> ExperimentResult:
    """Run a single minimization experiment end-to-end.

    1. Constructs an initial high-severity trial
    2. Spins up the system in Docker
    3. Runs the minimizer (binary search over severity/duration)
    4. Returns the minimized recipe
    """
    oracle = Oracle.from_file(oracle_path)
    runner = LiveRunner(log_dir=log_dir)
    config = MinimizationConfig(
        max_iterations=max_iterations,
        score_threshold=0.5,
        magnitude_steps=8,
        duration_steps=5,
        timing_steps=3,
    )
    minimizer = Minimizer(runner=runner, oracle=oracle, config=config)

    trial = make_initial_trial(
        system=system,
        fault_type=fault_type,
        location=location,
        severity=initial_severity,
        duration_s=initial_duration_s,
    )

    logger.info(
        "Starting minimization: system=%s oracle=%s severity=%s",
        system,
        oracle.configured_issue_id,
        initial_severity,
    )

    start = time.time()
    try:
        result = minimizer.minimize(trial)
        wall_time = time.time() - start

        logger.info(
            "Minimization complete: %d iterations, %d reductions, score=%.2f",
            result.iterations_used,
            len(result.reductions),
            result.final_score,
        )

        return ExperimentResult(
            system=system,
            oracle_id=oracle.configured_issue_id,
            initial_trial=trial,
            minimization=result,
            wall_time_s=wall_time,
        )
    except Exception as e:
        wall_time = time.time() - start
        logger.error("Minimization failed: %s", e)
        from faultforge.minimizer import MinimizationResult

        return ExperimentResult(
            system=system,
            oracle_id=oracle.configured_issue_id,
            initial_trial=trial,
            minimization=MinimizationResult(
                original=trial,
                minimized=trial,
                iterations_used=0,
            ),
            wall_time_s=wall_time,
            error=str(e),
        )


def run_suite(
    experiments: list[dict[str, str]],
    *,
    log_dir: str | None = None,
    max_iterations: int = 30,
) -> ExperimentSuite:
    """Run multiple minimization experiments sequentially.

    Each experiment dict must have keys: system, oracle_path, location.
    Optional: fault_type, initial_severity, initial_duration_s.
    """
    suite = ExperimentSuite()

    for exp in experiments:
        result = run_minimization(
            system=exp["system"],
            oracle_path=exp["oracle_path"],
            fault_type=exp.get("fault_type", "nw"),
            location=exp.get("location", "node1"),
            initial_severity=exp.get("initial_severity", "slow-5s"),
            initial_duration_s=int(exp.get("initial_duration_s", "30")),
            max_iterations=max_iterations,
            log_dir=log_dir,
        )
        suite.results.append(result)
        logger.info("Completed %s/%s", exp["system"], result.oracle_id)

    return suite
