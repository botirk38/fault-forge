"""Run the FaultForge minimizer against a live Docker cluster.

This is the experiment script — it uses the library's Minimizer + LiveRunner
with a concrete SystemSpec to produce minimized fault recipes.

Usage:
    python experiments/run_minimizer.py --spec experiments/systems/etcd.yaml \
        --oracle experiments/oracles/etcd-raft-election.yaml --json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "faultforge" / "src"))

from faultforge.live.runner import LiveRunner
from faultforge.live.systems import SystemSpec
from faultforge.minimizer import MinimizationConfig, Minimizer
from faultforge.oracle import Oracle
from faultforge.trial import SlowFault, SlowFaultKind, Trial

logger = logging.getLogger(__name__)


def run_minimization(
    spec: SystemSpec,
    oracle_path: str | Path,
    *,
    fault_type: str = "nw",
    location: str = "node1",
    initial_severity: str = "slow-5s",
    initial_duration_s: int = 30,
    max_iterations: int = 30,
    log_dir: str | None = None,
) -> dict[str, object]:
    """Run a single minimization experiment end-to-end."""
    oracle = Oracle.from_file(oracle_path)
    runner = LiveRunner(spec, log_dir=log_dir)
    config = MinimizationConfig(
        max_iterations=max_iterations,
        score_threshold=0.5,
        magnitude_steps=8,
        duration_steps=5,
        timing_steps=3,
    )
    minimizer = Minimizer(runner=runner, oracle=oracle, config=config)

    fault: SlowFault = {
        "fault_type": cast(SlowFaultKind, fault_type),
        "location": location,
        "duration_s": initial_duration_s,
        "severity": initial_severity,
        "start_s": 0,
        "if_restart": False,
    }
    trial: Trial = {
        "trial_id": f"{spec.name}-minimize-{int(time.time())}",
        "system": {"name": spec.name},
        "benchmark": {"name": "default"},
        "faults": [fault],
    }

    logger.info(
        "Starting minimization: system=%s oracle=%s severity=%s",
        spec.name,
        oracle.configured_issue_id,
        initial_severity,
    )

    start = time.time()
    result = minimizer.minimize(trial)
    wall_time = time.time() - start

    logger.info(
        "Minimization complete: %d iterations, %d reductions, score=%.2f",
        result.iterations_used,
        len(result.reductions),
        result.final_score,
    )

    return {
        "system": spec.name,
        "oracle_id": oracle.configured_issue_id,
        "initial_severity": initial_severity,
        "minimized_severity": (
            result.minimized["faults"][0]["severity"]
            if result.minimized["faults"]
            else None
        ),
        "iterations_used": result.iterations_used,
        "reductions": len(result.reductions),
        "final_score": result.final_score,
        "wall_time_s": wall_time,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run FaultForge minimizer")
    parser.add_argument("--spec", required=True, help="Path to system spec YAML")
    parser.add_argument("--oracle", required=True, help="Path to oracle YAML")
    parser.add_argument("--location", default="node1")
    parser.add_argument("--fault-type", default="nw")
    parser.add_argument("--initial-severity", default="slow-5s")
    parser.add_argument("--initial-duration", type=int, default=30)
    parser.add_argument("--max-iterations", type=int, default=30)
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    spec = SystemSpec.from_file(args.spec)
    result = run_minimization(
        spec,
        args.oracle,
        fault_type=args.fault_type,
        location=args.location,
        initial_severity=args.initial_severity,
        initial_duration_s=args.initial_duration,
        max_iterations=args.max_iterations,
        log_dir=args.log_dir,
    )

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"System: {result['system']}")
        print(f"Oracle: {result['oracle_id']}")
        print(f"Iterations: {result['iterations_used']}")
        print(f"Initial: {result['initial_severity']}")
        print(f"Minimized: {result['minimized_severity']}")
        print(f"Wall time: {result['wall_time_s']:.1f}s")


if __name__ == "__main__":
    main()
