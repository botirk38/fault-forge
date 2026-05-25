"""Xinda-style exhaustive grid baseline for comparison.

Implements the same severity grid from Xinda's generate.py danger-zone scheme
and runs each severity level sequentially. This measures how many trials Xinda
needs to find the danger-zone boundary vs the minimizer's binary search.

Usage:
    python experiments/baseline.py --spec experiments/systems/etcd.yaml \
        --oracle experiments/oracles/etcd-raft-election.yaml --json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import cast

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "faultforge" / "src"))

from live.runner import LiveRunner
from live.systems import SystemSpec
from faultforge.oracle import Oracle
from faultforge.trial import SlowFault, SlowFaultKind, Trial

logger = logging.getLogger(__name__)

XINDA_NW_DANGER_ZONE_GRID: list[str] = [
    "slow-100us",
    "slow-200us",
    "slow-300us",
    "slow-400us",
    "slow-500us",
    "slow-600us",
    "slow-700us",
    "slow-800us",
    "slow-900us",
    "slow-1ms",
    "slow-2ms",
    "slow-3ms",
    "slow-4ms",
    "slow-5ms",
    "slow-6ms",
    "slow-7ms",
    "slow-8ms",
    "slow-9ms",
    "slow-10ms",
    "slow-20ms",
    "slow-30ms",
    "slow-40ms",
    "slow-50ms",
    "slow-60ms",
    "slow-70ms",
    "slow-80ms",
    "slow-90ms",
    "slow-100ms",
    "slow-200ms",
    "slow-300ms",
    "slow-400ms",
    "slow-500ms",
    "slow-600ms",
    "slow-700ms",
    "slow-800ms",
    "slow-900ms",
    "slow-1s",
]


@dataclass
class BaselineResult:
    """Result of a Xinda-style exhaustive grid search."""

    system: str
    oracle_id: str
    total_grid_size: int
    trials_to_first_hit: int
    first_hit_severity: str | None
    wall_time_s: float
    all_results: list[dict[str, object]] = field(default_factory=list)


def run_xinda_baseline(
    spec: SystemSpec,
    oracle_path: str,
    *,
    location: str = "node1",
    fault_type: str = "nw",
    duration_s: int = 30,
    log_dir: str | None = None,
    max_trials: int | None = None,
) -> BaselineResult:
    """Run Xinda-style exhaustive grid search from lowest to highest severity."""
    oracle = Oracle.from_file(oracle_path)
    runner = LiveRunner(spec, log_dir=log_dir)

    grid = XINDA_NW_DANGER_ZONE_GRID
    cap = max_trials or len(grid)
    grid = grid[:cap]

    logger.info(
        "Starting Xinda baseline: system=%s grid_size=%d",
        spec.name,
        len(grid),
    )

    start = time.time()
    results: list[dict[str, object]] = []
    trials_to_hit = 0
    hit_severity: str | None = None

    for i, severity in enumerate(grid):
        fault: SlowFault = {
            "fault_type": cast(SlowFaultKind, fault_type),
            "location": location,
            "duration_s": duration_s,
            "severity": severity,
            "start_s": 0,
            "if_restart": False,
        }
        trial: Trial = {
            "trial_id": f"{spec.name}-baseline-{i}",
            "system": {"name": spec.name},
            "benchmark": {"name": "default"},
            "faults": [fault],
        }

        trial_result = runner.run(trial)
        reproduced = False

        if trial_result["success"] and trial_result.get("artifacts"):
            oracle_result = oracle.evaluate(artifacts=trial_result["artifacts"])
            reproduced = oracle_result.reproduced
            score = oracle_result.score
        else:
            score = 0.0

        results.append(
            {
                "severity": severity,
                "reproduced": reproduced,
                "score": score,
                "trial_num": i + 1,
            }
        )

        logger.info(
            "Baseline trial %d/%d: %s → %s (score=%.2f)",
            i + 1,
            len(grid),
            severity,
            "HIT" if reproduced else "miss",
            score,
        )

        if reproduced and hit_severity is None:
            trials_to_hit = i + 1
            hit_severity = severity

    wall_time = time.time() - start

    if hit_severity is None:
        trials_to_hit = len(grid)

    return BaselineResult(
        system=spec.name,
        oracle_id=oracle.configured_issue_id,
        total_grid_size=len(grid),
        trials_to_first_hit=trials_to_hit,
        first_hit_severity=hit_severity,
        wall_time_s=wall_time,
        all_results=results,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Xinda-style exhaustive grid baseline")
    parser.add_argument("--spec", required=True, help="Path to system spec YAML")
    parser.add_argument("--oracle", required=True, help="Path to oracle YAML")
    parser.add_argument("--location", default="node1")
    parser.add_argument("--fault-type", default="nw")
    parser.add_argument("--duration", type=int, default=30)
    parser.add_argument("--max-trials", type=int, default=None)
    parser.add_argument("--log-dir", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

    spec = SystemSpec.from_file(args.spec)
    result = run_xinda_baseline(
        spec,
        args.oracle,
        location=args.location,
        fault_type=args.fault_type,
        duration_s=args.duration,
        max_trials=args.max_trials,
        log_dir=args.log_dir,
    )

    if args.json:
        print(
            json.dumps(
                {
                    "system": result.system,
                    "oracle_id": result.oracle_id,
                    "total_grid_size": result.total_grid_size,
                    "trials_to_first_hit": result.trials_to_first_hit,
                    "first_hit_severity": result.first_hit_severity,
                    "wall_time_s": result.wall_time_s,
                },
                indent=2,
            )
        )
    else:
        print(f"System: {result.system}")
        print(f"Oracle: {result.oracle_id}")
        print(f"Grid size: {result.total_grid_size}")
        print(f"Trials to first hit: {result.trials_to_first_hit}")
        print(f"First hit severity: {result.first_hit_severity}")
        print(f"Wall time: {result.wall_time_s:.1f}s")


if __name__ == "__main__":
    main()
