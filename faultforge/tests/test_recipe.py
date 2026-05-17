"""Tests for faultforge.recipe."""

from __future__ import annotations

import json

from faultforge.fault_provider import Fault, InProcessFault, SlowFault
from faultforge.recipe import Recipe


def test_recipe_json_round_trip_carries_fault_payloads() -> None:
    faults: list[Fault] = [
        SlowFault(
            id="sf1",
            fault_type="nw",
            location="n1",
            duration_s=30,
            severity="slow-10ms",
        ),
        InProcessFault(
            id="ip1",
            component="srv",
            exception_class="java.io.IOException",
        ),
    ]

    recipe = Recipe(issue_id="i1", trial_id="t1", faults=faults)
    blob = recipe.model_dump_json()
    Recipe.model_validate(json.loads(blob))
