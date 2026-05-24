"""Tests for FaultForge fault recipe minimizer."""

from __future__ import annotations

import copy
import tempfile
from pathlib import Path

from faultforge.minimizer import (
    MinimizationConfig,
    Minimizer,
    build_severity,
    parse_severity_ms,
)
from faultforge.oracle import Oracle
from faultforge.trial import BenchmarkConfig, SlowFault, SystemConfig, Trial, TrialResult


# --- Test helpers ---


class _MockRunner:
    """Mock runner that tracks calls and returns configurable results."""

    def __init__(self, always_reproduces: bool = True) -> None:
        self.runs: list[Trial] = []
        self.always_reproduces = always_reproduces
        self._fail_below_ms: float | None = None
        self._fail_below_duration: int | None = None

    def set_magnitude_threshold(self, min_ms: float) -> None:
        """Trials with severity below this won't produce the symptom."""
        self._fail_below_ms = min_ms

    def set_duration_threshold(self, min_duration: int) -> None:
        """Trials with duration below this won't produce the symptom."""
        self._fail_below_duration = min_duration

    def run(self, trial: Trial) -> TrialResult:
        self.runs.append(copy.deepcopy(trial))

        # Check if this trial would produce the symptom
        produces_symptom = self.always_reproduces

        if self._fail_below_ms is not None:
            for fault in trial.faults:
                ms = parse_severity_ms(fault.fault_type, fault.severity)
                if ms is not None and ms < self._fail_below_ms:
                    produces_symptom = False

        if self._fail_below_duration is not None:
            for fault in trial.faults:
                if fault.duration_s < self._fail_below_duration:
                    produces_symptom = False

        if produces_symptom:
            log_content = "WARN: leader election timeout\nElection triggered\n"
        else:
            log_content = "INFO: normal operation\n"

        # Write a temp log file
        log_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, prefix="trial-"
        )
        log_file.write(log_content)
        log_file.close()

        return TrialResult(
            success=True,
            trial=trial,
            log_path=log_file.name,
            artifacts={"compose": log_file.name},
        )


def _make_oracle() -> Oracle:
    """Create an oracle that detects 'Election triggered'."""
    return Oracle.from_dict(
        {
            "issue": {"id": "TEST-001", "system": "etcd"},
            "reproduced_if": {
                "any": [
                    {"file": "compose", "contains": "Election triggered"},
                ]
            },
        }
    )


def _make_trial(
    severity: str = "slow-100ms",
    duration_s: int = 60,
    start_s: int = 0,
    fault_type: str = "nw",
    num_faults: int = 1,
) -> Trial:
    """Create a standard test trial."""
    faults = [
        SlowFault(
            fault_type=fault_type,
            location=f"node{i + 1}",
            duration_s=duration_s,
            severity=severity,
            start_s=start_s,
        )
        for i in range(num_faults)
    ]
    return Trial(
        trial_id="test-trial",
        system=SystemConfig(name="etcd"),
        benchmark=BenchmarkConfig(name="ycsb", exec_time_s=150),
        faults=faults,
        issue_id="TEST-001",
    )


# --- Severity parsing tests ---


class TestSeverityParsing:
    def test_parse_nw_ms(self):
        assert parse_severity_ms("nw", "slow-100ms") == 100.0

    def test_parse_nw_us(self):
        assert parse_severity_ms("nw", "slow-500us") == 0.5

    def test_parse_nw_s(self):
        assert parse_severity_ms("nw", "slow-2s") == 2000.0

    def test_parse_nw_flaky(self):
        assert parse_severity_ms("nw", "flaky-p10") == 10.0

    def test_parse_nw_flaky_decimal(self):
        assert parse_severity_ms("nw", "flaky-p0.5") == 0.5

    def test_parse_fs(self):
        assert parse_severity_ms("fs", "100000") == 100000.0

    def test_parse_cpu_returns_none(self):
        assert parse_severity_ms("cpu", "cpus-0.5") is None

    def test_parse_mem_returns_none(self):
        assert parse_severity_ms("mem", "memory-512m") is None

    def test_parse_process_returns_none(self):
        assert parse_severity_ms("process", "restart") is None

    def test_parse_invalid_nw(self):
        assert parse_severity_ms("nw", "partition") is None


class TestSeverityBuilding:
    def test_build_nw_ms(self):
        assert build_severity("nw", 100.0) == "slow-100ms"

    def test_build_nw_us(self):
        assert build_severity("nw", 0.5) == "slow-500us"

    def test_build_nw_s(self):
        assert build_severity("nw", 2000.0) == "slow-2s"

    def test_build_nw_fractional_ms(self):
        assert build_severity("nw", 12.5) == "slow-12.5ms"

    def test_build_fs(self):
        assert build_severity("fs", 50000.0) == "50000"

    def test_roundtrip_nw_100ms(self):
        sev = "slow-100ms"
        ms = parse_severity_ms("nw", sev)
        assert ms is not None
        rebuilt = build_severity("nw", ms)
        assert rebuilt == sev

    def test_roundtrip_nw_1s(self):
        sev = "slow-1s"
        ms = parse_severity_ms("nw", sev)
        assert ms is not None
        rebuilt = build_severity("nw", ms)
        assert rebuilt == sev

    def test_roundtrip_fs(self):
        sev = "100000"
        ms = parse_severity_ms("fs", sev)
        assert ms is not None
        rebuilt = build_severity("fs", ms)
        assert rebuilt == sev


# --- Minimizer tests ---


class TestMinimizerBasic:
    def test_non_reproducing_trial_returns_unchanged(self):
        runner = _MockRunner(always_reproduces=False)
        oracle = _make_oracle()
        minimizer = Minimizer(runner, oracle)
        trial = _make_trial()

        result = minimizer.minimize(trial)

        assert result.iterations_used == 1
        assert result.reductions == []
        assert result.final_score == 0.0
        assert result.minimized.faults[0].severity == "slow-100ms"

    def test_reproducing_trial_attempts_reductions(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        minimizer = Minimizer(runner, oracle)
        trial = _make_trial()

        result = minimizer.minimize(trial)

        assert result.iterations_used > 1
        assert result.final_score >= 0.5

    def test_respects_iteration_budget(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(max_iterations=5)
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial()

        result = minimizer.minimize(trial)

        # Budget controls reduction iterations; +1 for initial verify, +1 for final score
        # So total can be at most max_iterations + 2 (initial + final bookkeeping)
        assert result.iterations_used <= config.max_iterations + 2
        # But the reduction iterations (between initial and final) should respect budget
        reduction_iters = result.iterations_used - 2  # subtract initial + final
        assert reduction_iters <= config.max_iterations


class TestFaultCountReduction:
    def test_removes_unnecessary_fault(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=20, magnitude_steps=0, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(num_faults=3)

        result = minimizer.minimize(trial)

        # Should reduce from 3 faults to 1 (since all reproduce individually)
        assert len(result.minimized.faults) == 1
        reductions = [r for r in result.reductions if r.dimension == "fault_count"]
        assert len(reductions) == 2

    def test_keeps_necessary_fault(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=20, magnitude_steps=0, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(num_faults=1)

        result = minimizer.minimize(trial)

        assert len(result.minimized.faults) == 1


class TestMagnitudeReduction:
    def test_reduces_magnitude_to_threshold(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(20.0)  # Below 20ms fails
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=8,
            duration_steps=0,
            timing_steps=0,
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(severity="slow-100ms")

        result = minimizer.minimize(trial)

        # Should reduce from 100ms to somewhere around 20-30ms
        mag_reductions = [r for r in result.reductions if r.dimension == "magnitude"]
        assert len(mag_reductions) == 1
        final_ms = parse_severity_ms("nw", result.minimized.faults[0].severity)
        assert final_ms is not None
        assert final_ms < 100.0
        assert final_ms >= 20.0

    def test_no_reduction_if_already_minimal(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(95.0)  # Threshold just below current
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=8,
            duration_steps=0,
            timing_steps=0,
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(severity="slow-100ms")

        result = minimizer.minimize(trial)

        final_ms = parse_severity_ms("nw", result.minimized.faults[0].severity)
        assert final_ms is not None
        # Should be close to 100ms since threshold is 95ms
        assert final_ms >= 95.0

    def test_skips_non_reducible_severity(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=8,
            duration_steps=0,
            timing_steps=0,
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(severity="restart", fault_type="process")

        result = minimizer.minimize(trial)

        # Process fault severity can't be reduced numerically
        mag_reductions = [r for r in result.reductions if r.dimension == "magnitude"]
        assert len(mag_reductions) == 0
        assert result.minimized.faults[0].severity == "restart"


class TestDurationReduction:
    def test_reduces_duration(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_duration_threshold(10)  # Below 10s fails
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=0,
            duration_steps=5,
            timing_steps=0,
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(duration_s=60)

        result = minimizer.minimize(trial)

        dur_reductions = [r for r in result.reductions if r.dimension == "duration"]
        assert len(dur_reductions) == 1
        assert result.minimized.faults[0].duration_s < 60
        assert result.minimized.faults[0].duration_s >= 10

    def test_skips_duration_1(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=0,
            duration_steps=5,
            timing_steps=0,
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(duration_s=1)

        result = minimizer.minimize(trial)

        dur_reductions = [r for r in result.reductions if r.dimension == "duration"]
        assert len(dur_reductions) == 0


class TestTimingReduction:
    def test_finds_later_start_time(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=0,
            duration_steps=0,
            timing_steps=5,
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(start_s=0, duration_s=30)

        result = minimizer.minimize(trial)

        time_reductions = [r for r in result.reductions if r.dimension == "timing"]
        assert len(time_reductions) == 1
        assert result.minimized.faults[0].start_s > 0

    def test_no_timing_reduction_when_no_room(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=0,
            duration_steps=0,
            timing_steps=5,
        )
        minimizer = Minimizer(runner, oracle, config)
        # Duration equals exec time, so no room for later start
        trial = _make_trial(start_s=0, duration_s=150)

        result = minimizer.minimize(trial)

        time_reductions = [r for r in result.reductions if r.dimension == "timing"]
        assert len(time_reductions) == 0


class TestFullMinimization:
    def test_full_pipeline_reduces_all_dimensions(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(10.0)
        runner.set_duration_threshold(5)
        oracle = _make_oracle()
        config = MinimizationConfig(max_iterations=50)
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(severity="slow-100ms", duration_s=60, start_s=0)

        result = minimizer.minimize(trial)

        # Should have reductions in multiple dimensions
        dimensions = {r.dimension for r in result.reductions}
        assert "magnitude" in dimensions
        assert "duration" in dimensions
        assert "timing" in dimensions
        assert result.final_score >= 0.5

    def test_multi_fault_reduces_count_then_dimensions(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(10.0)
        oracle = _make_oracle()
        config = MinimizationConfig(max_iterations=50)
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(severity="slow-100ms", duration_s=60, num_faults=3)

        result = minimizer.minimize(trial)

        # Should first reduce fault count, then reduce remaining fault
        assert len(result.minimized.faults) < 3
        # Magnitude should be reduced on remaining faults
        for f in result.minimized.faults:
            ms = parse_severity_ms("nw", f.severity)
            assert ms is not None
            assert ms < 100.0


class TestMinimizationResult:
    def test_preserves_original(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        minimizer = Minimizer(runner, oracle)
        trial = _make_trial(severity="slow-100ms", duration_s=60)

        result = minimizer.minimize(trial)

        # Original should be unchanged
        assert result.original.faults[0].severity == "slow-100ms"
        assert result.original.faults[0].duration_s == 60

    def test_fs_severity_reduction(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(20000.0)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30,
            magnitude_steps=8,
            duration_steps=0,
            timing_steps=0,
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_trial(severity="100000", fault_type="fs")

        result = minimizer.minimize(trial)

        mag_reductions = [r for r in result.reductions if r.dimension == "magnitude"]
        assert len(mag_reductions) == 1
        final_ms = parse_severity_ms("fs", result.minimized.faults[0].severity)
        assert final_ms is not None
        assert final_ms < 100000.0
        assert final_ms >= 20000.0
