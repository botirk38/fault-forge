"""Tests for faultforge.fault_provider.base."""

from faultforge.fault_provider.base import ProviderRunResult


def test_provider_run_result_defaults() -> None:
    res = ProviderRunResult(success=False, fault_id="f1")
    assert res.log_path is None
    assert res.error is None
    assert res.note is None
