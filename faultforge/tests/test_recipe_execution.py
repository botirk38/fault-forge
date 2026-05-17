"""Tests for executing recipes through wired fault-provider implementations."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from xinda import BenchmarkConfig, SlowFault, SystemConfig, TrialResult

from faultforge.fault_provider import InProcessFault, Recipe
from faultforge.fault_provider import SlowFault as RecipeSlowFault
from faultforge.fault_provider.anduril import Anduril
from faultforge.fault_provider.xinda import Xinda


@pytest.fixture()
def etcd_sysbench() -> tuple[SystemConfig, BenchmarkConfig]:
    return SystemConfig(name="etcd"), BenchmarkConfig.ycsb(workload="a")


@pytest.fixture()
def nw_fault() -> RecipeSlowFault:
    return RecipeSlowFault(
        id="fault-1",
        fault_type="nw",
        location="leader",
        duration_s=30,
        severity="slow-100ms",
        start_s=0,
    )


def test_wrong_fault_type_for_xinda_raises(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
) -> None:
    sy, bm = etcd_sysbench
    recipe = Recipe(
        trial_id="t-bad-kind",
        faults=[
            InProcessFault(id="fault-1", exception_class="java.io.IOException"),
        ],
    )
    with pytest.raises(TypeError):
        Xinda().run(recipe, sy, bm)


def test_xinda_raises_on_unknown_model(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
) -> None:
    sy, bm = etcd_sysbench
    fault = RecipeSlowFault.model_construct(
        id="fault-bad-model",
        kind="slow",
        fault_type="garbage-model",
        location="leader",
        duration_s=60,
        severity="slow-50ms",
        start_s=0,
        if_restart=False,
    )
    recipe = Recipe(trial_id="t3", faults=[fault])
    with pytest.raises(ValueError, match="unsupported Xinda"):
        Xinda().run(recipe, sy, bm)


def test_xinda_execution_patches_client(
    etcd_sysbench: tuple[SystemConfig, BenchmarkConfig],
    nw_fault: RecipeSlowFault,
) -> None:
    sy, bm = etcd_sysbench
    recipe = Recipe(trial_id="t4", faults=[nw_fault])

    mock_tr = TrialResult(
        success=True,
        system=sy,
        benchmark=bm,
        fault=SlowFault.network(location="leader", severity="slow-100ms", duration_s=30),
        log_path="/tmp/xinda.log",
    )

    with patch("faultforge.fault_provider.xinda.XindaClient") as xc:
        xc.return_value.run.return_value = mock_tr
        results = Xinda().run(recipe, sy, bm)

    assert len(results) == 1
    assert results[0].success is True
    assert results[0].log_path == "/tmp/xinda.log"


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
    nw_fault: RecipeSlowFault,
) -> None:
    sy, bm = etcd_sysbench
    recipe = Recipe(trial_id="t6", faults=[nw_fault])
    with pytest.raises(TypeError):
        Anduril().run(recipe, sy, bm)
