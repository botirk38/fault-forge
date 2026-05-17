"""Tests for faultforge.fault_provider.fault."""

from __future__ import annotations

from pydantic import TypeAdapter

from faultforge.fault_provider import Fault, InProcessFault, SlowFault


def test_discriminated_fault_union_round_trip() -> None:
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
