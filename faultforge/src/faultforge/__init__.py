"""FaultForge: symptom-guided fault reproduction orchestrator."""

__version__ = "0.1.0"

from faultforge.minimizer import (
    MinimizationConfig,
    MinimizationResult,
    Minimizer,
    ReductionStep,
)
from faultforge.oracle import Oracle, OracleConfig, OracleResult
from faultforge.runner import RunTrial
from faultforge.search import SearchConfig, Searcher
from faultforge.severity import build_severity, parse_severity_magnitude
from faultforge.trial import (
    BenchmarkConfig,
    ResourceLimit,
    SlowFault,
    SlowFaultKind,
    SystemConfig,
    Trial,
    TrialPaths,
    TrialResult,
    fault_end_s,
    fault_info,
    load_trial,
    make_fault,
    make_fs_fault,
    make_nw_fault,
    make_result,
    make_trial,
)

__all__ = [
    "BenchmarkConfig",
    "MinimizationConfig",
    "MinimizationResult",
    "Minimizer",
    "Oracle",
    "OracleConfig",
    "OracleResult",
    "ReductionStep",
    "ResourceLimit",
    "RunTrial",
    "SearchConfig",
    "Searcher",
    "SlowFault",
    "SlowFaultKind",
    "SystemConfig",
    "Trial",
    "TrialPaths",
    "TrialResult",
    "build_severity",
    "fault_end_s",
    "fault_info",
    "load_trial",
    "make_fault",
    "make_fs_fault",
    "make_nw_fault",
    "make_result",
    "make_trial",
    "parse_severity_magnitude",
]
