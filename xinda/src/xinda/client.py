"""Xinda SDK client.

FaultForge and other consumers call Xinda through this client,
never through main.py or subprocess.
"""

from __future__ import annotations

import datetime
import sys
import time
import traceback
from pathlib import Path

from xinda.systems.etcd import Etcd
from xinda.trial import Trial, TrialResult


class XindaClient:
    """Programmatic entry point for running Xinda trials."""

    def run(self, trial: Trial) -> TrialResult:
        """Run a single trial and return structured results."""
        self._validate(trial)
        trial.paths = trial.paths or self._default_paths(trial.system.data_dir)

        try:
            system = self._build_system(trial)
            system.test()
            return TrialResult(
                success=True,
                system=trial.system,
                benchmark=trial.benchmark,
                fault=trial.fault,
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
                system=trial.system,
                benchmark=trial.benchmark,
                fault=trial.fault,
                log_path=log_path,
                error=str(e),
            )

    def _validate(self, trial: Trial) -> None:
        if trial.system.name not in (
            "cassandra",
            "hbase",
            "hadoop",
            "etcd",
            "crdb",
            "kafka",
            "depfast",
            "copilot",
        ):
            raise ValueError(f"Unknown system: {trial.system.name}")

        if trial.fault.fault_type not in ("nw", "fs", "none"):
            raise ValueError(f"Unknown fault type: {trial.fault.fault_type}")

    def _default_paths(self, data_dir: str):
        from xinda.trial import TrialPaths

        return TrialPaths.defaults(data_dir)

    def _build_system(self, trial: Trial):
        """Build the appropriate system instance from a Trial."""
        if trial.system.name == "etcd":
            return Etcd.from_trial(trial)

        raise NotImplementedError(
            f"System {trial.system.name} not yet migrated to SDK Trial API. "
            "Only etcd is supported in this release."
        )
