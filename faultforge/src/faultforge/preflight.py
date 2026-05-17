"""Preflight checks for FaultForge experiments."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from faultforge.runtime import ResolvedRuntime


@dataclass
class CheckResult:
    name: str
    passed: bool
    message: str = ""


@dataclass
class PreflightReport:
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def failed(self) -> list[CheckResult]:
        return [c for c in self.checks if not c.passed]

    def add(self, name: str, passed: bool, message: str = "") -> None:
        self.checks.append(CheckResult(name, passed, message))


class Preflight:
    """Validate the runtime environment before executing trials."""

    def __init__(self, runtime: ResolvedRuntime) -> None:
        self._runtime = runtime

    def run(self) -> PreflightReport:
        report = PreflightReport()
        self._check_docker_cli(report)
        self._check_docker_daemon(report)
        self._check_docker_compose(report)
        self._check_compose_root(report)
        self._check_nsenter(report)
        return report

    def _check_docker_cli(self, report: PreflightReport) -> None:
        path = shutil.which(self._runtime.docker_bin)
        if path:
            report.add("docker CLI", True, f"found at {path}")
        else:
            report.add("docker CLI", False, f"{self._runtime.docker_bin} not found in PATH")

    def _check_docker_daemon(self, report: PreflightReport) -> None:
        try:
            result = subprocess.run(
                [self._runtime.docker_bin, "info", "--format", "{{.ServerVersion}}"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                report.add("Docker daemon", True, f"version {result.stdout.strip()}")
            else:
                report.add("Docker daemon", False, result.stderr.strip())
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
            report.add("Docker daemon", False, str(e))

    def _check_docker_compose(self, report: PreflightReport) -> None:
        path = shutil.which(self._runtime.docker_compose_bin)
        if path:
            report.add("docker-compose", True, f"found at {path}")
        else:
            report.add(
                "docker-compose",
                False,
                f"{self._runtime.docker_compose_bin} not found in PATH",
            )

    def _check_compose_root(self, report: PreflightReport) -> None:
        p = Path(self._runtime.compose_root)
        if p.is_dir():
            report.add("compose root", True, f"{self._runtime.compose_root}")
        else:
            report.add("compose root", False, f"{self._runtime.compose_root} does not exist")

    def _check_nsenter(self, report: PreflightReport) -> None:
        path = shutil.which("nsenter")
        if path:
            report.add("nsenter", True, f"found at {path}")
        else:
            report.add(
                "nsenter",
                False,
                "nsenter not found; network faults require nsenter for host-side tc injection",
            )
