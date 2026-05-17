"""Shared recipe schema for fault reproduction trials."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FaultTarget(BaseModel):
    """Where a fault should be applied."""

    node: str = ""
    component: str = ""
    interface: str = ""
    injection_id: int | None = None


class FaultTiming(BaseModel):
    """When a fault should be applied."""

    occurrence: int | None = None
    phase: str = ""
    start_s: float = 0.0
    duration_s: float = 0.0


class FaultParams(BaseModel):
    """Fault-specific parameters."""

    delay_ms: int | None = None
    loss_pct: float | None = None
    exception_class: str = ""


class Fault(BaseModel):
    """A single fault in a trial recipe."""

    id: str
    provider: str
    model: str
    target: FaultTarget = Field(default_factory=FaultTarget)
    timing: FaultTiming = Field(default_factory=FaultTiming)
    params: FaultParams = Field(default_factory=FaultParams)


class Recipe(BaseModel):
    """A complete trial recipe with zero or more faults."""

    issue_id: str = ""
    trial_id: str
    faults: list[Fault] = Field(default_factory=list)
