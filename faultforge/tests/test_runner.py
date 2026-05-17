"""Tests for TrialRunner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from faultforge.runner import TrialRunner
from faultforge.trial import BenchmarkConfig, SlowFault, SystemConfig, Trial


@pytest.fixture()
def etcd_trial() -> Trial:
    sy = SystemConfig(name="etcd")
    bm = BenchmarkConfig.ycsb(workload="a")
    fault = SlowFault.network(location="etcd0", severity="slow-100ms", duration_s=30)
    return Trial(trial_id="t1", system=sy, benchmark=bm, faults=[fault])


def test_runner_rejects_invalid_fault_type(etcd_trial: Trial) -> None:
    etcd_trial.faults[0].fault_type = "garbage"  # type: ignore[assignment]
    with pytest.raises(ValueError, match="Unknown fault type"):
        TrialRunner().run(etcd_trial)


def test_runner_rejects_empty_faults(etcd_trial: Trial) -> None:
    etcd_trial.faults = []
    with pytest.raises(ValueError, match="at least one fault"):
        TrialRunner().run(etcd_trial)


def test_runner_returns_success_on_good_run(etcd_trial: Trial) -> None:
    fake_system = MagicMock()
    fake_system.log.compose = "/tmp/test.log"

    with patch("faultforge.runner.create_system", return_value=fake_system):
        result = TrialRunner().run(etcd_trial)

    assert result.success is True
    assert result.trial is etcd_trial
    assert result.log_path == "/tmp/test.log"
    assert result.error is None


def test_runner_returns_failure_on_exception(etcd_trial: Trial) -> None:
    with patch("faultforge.runner.create_system", side_effect=RuntimeError("boom")):
        result = TrialRunner().run(etcd_trial)

    assert result.success is False
    assert result.trial is etcd_trial
    assert result.error is not None
    assert "boom" in result.error


def test_runner_passes_multi_fault_trial(etcd_trial: Trial) -> None:
    fault2 = SlowFault.filesystem(location="etcd1", severity="10000", duration_s=60)
    etcd_trial.faults.append(fault2)

    fake_system = MagicMock()
    fake_system.log.compose = "/tmp/multi.log"

    with patch("faultforge.runner.create_system", return_value=fake_system) as mock_create:
        result = TrialRunner().run(etcd_trial)

    assert result.success is True
    assert len(mock_create.call_args[0][0].faults) == 2
