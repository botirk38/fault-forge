"""Xinda: A slow-fault testing pipeline for distributed systems."""

__version__ = "0.2.0"

from xinda.client import XindaClient
from xinda.trial import (
    BenchmarkConfig,
    ResourceLimit,
    SlowFault,
    SystemConfig,
    Trial,
    TrialPaths,
    TrialResult,
)

__all__ = [
    "BenchmarkConfig",
    "ResourceLimit",
    "SlowFault",
    "SystemConfig",
    "Trial",
    "TrialPaths",
    "TrialResult",
    "XindaClient",
]
