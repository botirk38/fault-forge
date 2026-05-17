"""Fault-provider backends (run-only adapters + trial schema)."""

from faultforge.fault_provider.base import FaultProvider, ProviderRunResult
from faultforge.fault_provider.fault import Fault, InProcessFault, SlowFault, SlowFaultKind
from faultforge.fault_provider.recipe import Recipe

__all__ = [
    "Fault",
    "FaultProvider",
    "InProcessFault",
    "ProviderRunResult",
    "Recipe",
    "SlowFault",
    "SlowFaultKind",
]
