"""Trial recipes and future recipe tooling (minimizers, rewriting).

Schemas here stay orchestration-neutral: they reference fault definitions from
backends (`fault_provider.fault`).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from faultforge.fault_provider.fault import Fault


class Recipe(BaseModel):
    """A complete trial recipe with zero or more faults."""

    issue_id: str = ""
    trial_id: str
    faults: list[Fault] = Field(default_factory=list)
