"""Trial execution runner for FaultForge."""

from __future__ import annotations

import datetime
import logging
import sys
import time
import traceback
from pathlib import Path

from faultforge.runtime import ResolvedRuntime
from faultforge.systems.registry import create_system
from faultforge.trial import Trial, TrialPaths, TrialResult

logger = logging.getLogger(__name__)


class TrialRunner:
    """Execute a Trial against a real distributed system.

    Single entry point: ``run(trial) -> TrialResult``.
    Handles system lifecycle, fault injection, and benchmark execution
    through the system implementation.
    """

    def __init__(self, runtime: ResolvedRuntime | None = None) -> None:
        self._runtime = runtime

    def run(self, trial: Trial) -> TrialResult:
        """Execute a trial and return the result.

        On success, returns with the system log path.
        On failure, captures the traceback to stderr.log and returns
        the error message.
        """
        self._validate(trial)
        trial.paths = trial.paths or self._resolve_paths(trial)

        try:
            system = create_system(trial)
            system.test()
            return TrialResult(
                success=True,
                trial=trial,
                log_path=system.log.compose,
                artifacts=system.log.artifacts(),
            )
        except KeyboardInterrupt:
            raise
        except Exception as e:
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

    def _resolve_paths(self, trial: Trial) -> TrialPaths:
        rt = self._runtime
        if rt is None:
            return TrialPaths()
        return TrialPaths(
            log_root_dir=rt.data_dir,
            install_root=rt.software_root,
            tooling_root=rt.compose_root,
            software_dir=rt.software_root,
            tools_dir=rt.compose_root,
            charybdefs_mount_dir=rt.charybdefs_mount_dir,
        )

    def _validate(self, trial: Trial) -> None:
        """Validate trial configuration before execution."""
        for fault in trial.faults:
            if fault.fault_type not in ("nw", "fs", "cpu", "mem", "process", "none"):
                raise ValueError(f"Unknown fault type: {fault.fault_type}")
        if not trial.faults:
            raise ValueError("Trial must have at least one fault")
