"""FaultForge: symptom-guided fault reproduction orchestrator."""

__version__ = "0.1.0"

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
    "ResourceLimit",
    "SlowFault",
    "SlowFaultKind",
    "SystemConfig",
    "Trial",
    "TrialPaths",
    "TrialResult",
]
