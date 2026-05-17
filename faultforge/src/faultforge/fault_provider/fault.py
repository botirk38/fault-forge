"""Declarative fault shapes for backends."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field

# Matches Xinda slow-fault vocabulary.
type SlowFaultKind = Literal["nw", "fs", "none"]


class SlowFault(BaseModel):
    """Environmental slow fault (Xinda-aligned)."""

    kind: Literal["slow"] = Field(default="slow", repr=False)
    id: str
    fault_type: SlowFaultKind
    location: str
    duration_s: int
    severity: str
    start_s: int = 0
    if_restart: bool = False


class InProcessFault(BaseModel):
    """Instrumented in-process fault (Anduril-aligned)."""

    kind: Literal["in_process"] = Field(default="in_process", repr=False)
    id: str
    injection_id: int | None = None
    component: str = ""
    phase: str = ""
    occurrence: int | None = None
    exception_class: str = ""


Fault = Annotated[SlowFault | InProcessFault, Field(discriminator="kind")]
