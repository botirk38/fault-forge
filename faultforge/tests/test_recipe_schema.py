"""Recipe schema validation and discriminated-union serialization."""

from __future__ import annotations

import json

from pydantic import TypeAdapter

from faultforge.fault_provider import (
    Fault,
    InProcessFault,
    Recipe,
    SlowFault,
)


def test_discriminated_union_round_trip_through_json() -> None:
    adapter: TypeAdapter[Fault] = TypeAdapter(Fault)
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

    for f in faults:
        round_trip = adapter.validate_python(adapter.dump_python(f))
        assert isinstance(round_trip, type(f))

    recipe = Recipe(issue_id="i1", trial_id="t1", faults=faults)
    blob = recipe.model_dump_json()
    Recipe.model_validate(json.loads(blob))
