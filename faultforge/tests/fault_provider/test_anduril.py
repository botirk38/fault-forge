"""Tests for faultforge.fault_provider.anduril."""

from __future__ import annotations

import pytest
from xinda import BenchmarkConfig, SystemConfig

from faultforge.fault_provider import InProcessFault
from faultforge.fault_provider import SlowFault as RecipeSlowFault
from faultforge.fault_provider.anduril import Anduril
from faultforge.recipe import Recipe


@pytest.fixture()
def etcd_sysbench() -> tuple[SystemConfig, BenchmarkConfig]:
    return SystemConfig(name="etcd"), BenchmarkConfig.ycsb(workload="a")


def test_anduril_recipe_returns_stub_result(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
) -> None:
    sys_c, bm = etcd_sysbench
    recipe = Recipe(
        trial_id="t5",
        faults=[
            InProcessFault(
                id="a1",
                component="srv",
                exception_class="java.io.IOException",
            ),
        ],
    )
    outs = Anduril().run(recipe, sys_c, bm)
    assert len(outs) == 1
    assert outs[0].success is False


def test_anduril_raises_on_slow_fault_slice(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
) -> None:
    sy, bm = etcd_sysbench
    nw_fault = RecipeSlowFault(
        id="fault-1",
        fault_type="nw",
        location="leader",
        duration_s=30,
        severity="slow-100ms",
        start_s=0,
    )
    recipe = Recipe(trial_id="t6", faults=[nw_fault])
    with pytest.raises(TypeError):
        Anduril().run(recipe, sy, bm)
