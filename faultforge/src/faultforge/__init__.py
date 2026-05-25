"""FaultForge: symptom-guided fault reproduction orchestrator."""

__version__ = "0.1.0"

from faultforge.minimizer import (
    MinimizationConfig,
    MinimizationResult,
    Minimizer,
    ReductionStep,
)
from faultforge.runner import RunTrial
from faultforge.severity import build_severity, parse_severity_ms
from faultforge.trial import (
    BenchmarkConfig,
    ResourceLimit,
    SlowFault,
    SlowFaultKind,
    SystemConfig,
    Trial,
    TrialPaths,
    TrialResult,
)

__all__ = [
    "BenchmarkConfig",
    "MinimizationConfig",
    "MinimizationResult",
    "Minimizer",
    "ReductionStep",
    "ResourceLimit",
    "RunTrial",
    "SlowFault",
    "SlowFaultKind",
    "SystemConfig",
    "Trial",
    "TrialPaths",
    "TrialResult",
    "build_severity",
    "parse_severity_ms",
]
