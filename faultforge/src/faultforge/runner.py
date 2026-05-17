"""Trial execution runner for FaultForge."""

from __future__ import annotations

import datetime
import logging
import sys
import time
import traceback
from pathlib import Path

from faultforge.systems.registry import create_system
from faultforge.trial import Trial, TrialPaths, TrialResult

logger = logging.getLogger(__name__)


class TrialRunner:
    """Execute a Trial against a real distributed system."""

    def run(self, trial: Trial) -> TrialResult:
        self._validate(trial)
        trial.paths = trial.paths or TrialPaths.defaults(trial.system.data_dir)

        try:
            system = create_system(trial)
            system.test()
            return TrialResult(
                success=True,
                trial=trial,
                log_path=system.log.info,
            )
        except (KeyboardInterrupt, Exception) as e:
            error_msg = traceback.format_exc()
            log_path = str(Path.cwd() / "stderr.log")
            with open(log_path, "a") as f:
                f.write("#" * 50 + "\n")
                f.write(f"[{int(time.time() * 1e9)}, {datetime.datetime.now()}]\n")
                f.write(f"{' '.join(sys.argv)}\n")
                f.write(error_msg)
                f.write("#" * 50 + "\n")
            return TrialResult(
                success=False,
                trial=trial,
                log_path=log_path,
                error=str(e),
            )

    def _validate(self, trial: Trial) -> None:
        for fault in trial.faults:
            if fault.fault_type not in ("nw", "fs", "none"):
                raise ValueError(f"Unknown fault type: {fault.fault_type}")
        if not trial.faults:
            raise ValueError("Trial must have at least one fault")
