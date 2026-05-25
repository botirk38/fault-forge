"""Tests for TrialRunner."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from faultforge.runner import TrialRunner
from faultforge.trial import Trial, make_fs_fault, make_nw_fault, make_trial


@pytest.fixture()
def etcd_trial() -> Trial:
    fault = make_nw_fault(location="etcd0", severity="slow-100ms", duration_s=30)
    return make_trial(
        trial_id="t1",
        system={"name": "etcd"},  # type: ignore[arg-type]
        benchmark={"name": "ycsb", "workload": "a"},  # type: ignore[arg-type]
        faults=[fault],
    )


def test_runner_rejects_invalid_fault_type(etcd_trial: Trial) -> None:
    etcd_trial["faults"][0]["fault_type"] = "garbage"  # type: ignore[typeddict-item]
    with pytest.raises(ValueError, match="Unknown fault type"):
        TrialRunner().run(etcd_trial)


def test_runner_rejects_empty_faults(etcd_trial: Trial) -> None:
    etcd_trial["faults"] = []
    with pytest.raises(ValueError, match="at least one fault"):
        TrialRunner().run(etcd_trial)


def test_runner_returns_success_on_good_run(etcd_trial: Trial) -> None:
    fake_system = MagicMock()
    fake_system.log.compose = "/tmp/test.log"
    fake_system.log.artifacts.return_value = {}

    with patch("faultforge.runner.create_system", return_value=fake_system):
        result = TrialRunner().run(etcd_trial)

    assert result["success"] is True
    assert result["trial"] is etcd_trial
    assert result["log_path"] == "/tmp/test.log"
    assert result.get("error") is None


def test_runner_returns_failure_on_exception(etcd_trial: Trial) -> None:
    with patch("faultforge.runner.create_system", side_effect=RuntimeError("boom")):
        result = TrialRunner().run(etcd_trial)

    assert result["success"] is False
    assert result["trial"] is etcd_trial
    assert result.get("error") is not None
    assert "boom" in result["error"]


def test_runner_passes_multi_fault_trial(etcd_trial: Trial) -> None:
    fault2 = make_fs_fault(location="etcd1", severity="10000", duration_s=60)
    etcd_trial["faults"].append(fault2)

    fake_system = MagicMock()
    fake_system.log.compose = "/tmp/multi.log"
    fake_system.log.artifacts.return_value = {}

    with patch("faultforge.runner.create_system", return_value=fake_system) as mock_create:
        result = TrialRunner().run(etcd_trial)

    assert result["success"] is True
    assert len(mock_create.call_args[0][0]["faults"]) == 2
