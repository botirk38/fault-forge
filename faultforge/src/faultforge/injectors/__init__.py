"""Fault injection primitives for Docker containers."""

from __future__ import annotations

from faultforge.injectors.base import FaultInjector
from faultforge.injectors.filesystem import FilesystemFaultInjector
from faultforge.injectors.network import NetworkFaultInjector
from faultforge.injectors.process import ProcessFaultInjector
from faultforge.injectors.registry import InjectorRegistry
from faultforge.injectors.resource import ResourceFaultInjector

__all__ = [
    "FaultInjector",
    "NetworkFaultInjector",
    "ResourceFaultInjector",
    "ProcessFaultInjector",
    "FilesystemFaultInjector",
    "InjectorRegistry",
]
