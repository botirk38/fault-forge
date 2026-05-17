"""Trial recipe: declarative assembled faults (no orchestration)."""

from __future__ import annotations

from pydantic import BaseModel, Field

from faultforge.fault_provider.fault import Fault


class Recipe(BaseModel):
    """A complete trial recipe with zero or more faults."""

    issue_id: str = ""
    trial_id: str
    faults: list[Fault] = Field(default_factory=list)
