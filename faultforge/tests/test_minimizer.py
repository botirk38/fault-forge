"""Tests for FaultForge fault recipe minimizer."""

from __future__ import annotations

import copy
import tempfile

from faultforge.minimizer import MinimizationConfig, Minimizer
from faultforge.oracle import Oracle
from faultforge.severity import build_severity, parse_severity_ms
from faultforge.trial import Trial, TrialResult, load_trial, make_fault, make_trial

# --- Test helpers ---


class _MockRunner:
    """Mock runner satisfying RunTrial protocol."""

    def __init__(self, always_reproduces: bool = True) -> None:
        self.runs: list[Trial] = []
        self.always_reproduces = always_reproduces
        self._fail_below_ms: float | None = None
        self._fail_below_duration: int | None = None

    def set_magnitude_threshold(self, min_ms: float) -> None:
        self._fail_below_ms = min_ms

    def set_duration_threshold(self, min_duration: int) -> None:
        self._fail_below_duration = min_duration

    def run(self, trial: Trial) -> TrialResult:
        self.runs.append(copy.deepcopy(trial))

        produces_symptom = self.always_reproduces

        if self._fail_below_ms is not None:
            for fault in trial["faults"]:
                ms = parse_severity_ms(fault["fault_type"], fault["severity"])
                if ms is not None and ms < self._fail_below_ms:
                    produces_symptom = False

        if self._fail_below_duration is not None:
            for fault in trial["faults"]:
                if fault["duration_s"] < self._fail_below_duration:
                    produces_symptom = False

        if produces_symptom:
            log_content = "WARN: leader election timeout\nElection triggered\n"
        else:
            log_content = "INFO: normal operation\n"

        log_file = tempfile.NamedTemporaryFile(
            mode="w", suffix=".log", delete=False, prefix="trial-"
        )
        log_file.write(log_content)
        log_file.close()

        return {
            "success": True,
            "trial": trial,
            "log_path": log_file.name,
            "artifacts": {"compose": log_file.name},
        }


def _make_oracle() -> Oracle:
    return Oracle.from_dict(
        {
            "issue": {"id": "TEST-001", "system": "etcd"},
            "reproduced_if": {"any": [{"file": "compose", "contains": "Election triggered"}]},
        }
    )


def _make_test_trial(
    severity: str = "slow-100ms",
    duration_s: int = 60,
    start_s: int = 0,
    fault_type: str = "nw",
    num_faults: int = 1,
) -> Trial:
    faults = [
        make_fault(
            fault_type=fault_type,  # type: ignore[arg-type]
            location=f"node{i + 1}",
            duration_s=duration_s,
            severity=severity,
            start_s=start_s,
        )
        for i in range(num_faults)
    ]
    return make_trial(
        trial_id="test-trial",
        system={"name": "etcd"},  # type: ignore[arg-type]
        benchmark={"name": "ycsb", "exec_time_s": 150},  # type: ignore[arg-type]
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
        assert build_severity("nw", ms) == sev

    def test_roundtrip_nw_1s(self):
        sev = "slow-1s"
        ms = parse_severity_ms("nw", sev)
        assert ms is not None
        assert build_severity("nw", ms) == sev

    def test_roundtrip_fs(self):
        sev = "100000"
        ms = parse_severity_ms("fs", sev)
        assert ms is not None
        assert build_severity("fs", ms) == sev


# --- Minimizer tests ---


class TestMinimizerBasic:
    def test_non_reproducing_trial_returns_unchanged(self):
        runner = _MockRunner(always_reproduces=False)
        oracle = _make_oracle()
        minimizer = Minimizer(runner, oracle)
        trial = _make_test_trial()

        result = minimizer.minimize(trial)

        assert result.iterations_used == 1
        assert result.reductions == []
        assert result.final_score == 0.0
        assert result.minimized["faults"][0]["severity"] == "slow-100ms"

    def test_reproducing_trial_attempts_reductions(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        minimizer = Minimizer(runner, oracle)
        trial = _make_test_trial()

        result = minimizer.minimize(trial)

        assert result.iterations_used > 1
        assert result.final_score >= 0.5

    def test_respects_iteration_budget(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(max_iterations=5)
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial()

        result = minimizer.minimize(trial)

        assert result.iterations_used <= config.max_iterations + 2
        reduction_iters = result.iterations_used - 2
        assert reduction_iters <= config.max_iterations


class TestFaultCountReduction:
    def test_removes_unnecessary_fault(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=20, magnitude_steps=0, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(num_faults=3)

        result = minimizer.minimize(trial)

        assert len(result.minimized["faults"]) == 1
        reductions = [r for r in result.reductions if r.dimension == "fault_count"]
        assert len(reductions) == 2

    def test_keeps_necessary_fault(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=20, magnitude_steps=0, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(num_faults=1)

        result = minimizer.minimize(trial)

        assert len(result.minimized["faults"]) == 1


class TestMagnitudeReduction:
    def test_reduces_magnitude_to_threshold(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(20.0)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=8, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(severity="slow-100ms")

        result = minimizer.minimize(trial)

        mag_reductions = [r for r in result.reductions if r.dimension == "magnitude"]
        assert len(mag_reductions) == 1
        final_ms = parse_severity_ms("nw", result.minimized["faults"][0]["severity"])
        assert final_ms is not None
        assert final_ms < 100.0
        assert final_ms >= 20.0

    def test_no_reduction_if_already_minimal(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(95.0)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=8, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(severity="slow-100ms")

        result = minimizer.minimize(trial)

        final_ms = parse_severity_ms("nw", result.minimized["faults"][0]["severity"])
        assert final_ms is not None
        assert final_ms >= 95.0

    def test_skips_non_reducible_severity(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=8, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(severity="restart", fault_type="process")

        result = minimizer.minimize(trial)

        mag_reductions = [r for r in result.reductions if r.dimension == "magnitude"]
        assert len(mag_reductions) == 0
        assert result.minimized["faults"][0]["severity"] == "restart"


class TestDurationReduction:
    def test_reduces_duration(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_duration_threshold(10)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=0, duration_steps=5, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(duration_s=60)

        result = minimizer.minimize(trial)

        dur_reductions = [r for r in result.reductions if r.dimension == "duration"]
        assert len(dur_reductions) == 1
        assert result.minimized["faults"][0]["duration_s"] < 60
        assert result.minimized["faults"][0]["duration_s"] >= 10

    def test_skips_duration_1(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=0, duration_steps=5, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(duration_s=1)

        result = minimizer.minimize(trial)

        dur_reductions = [r for r in result.reductions if r.dimension == "duration"]
        assert len(dur_reductions) == 0


class TestTimingReduction:
    def test_finds_later_start_time(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=0, duration_steps=0, timing_steps=5
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(start_s=0, duration_s=30)

        result = minimizer.minimize(trial)

        time_reductions = [r for r in result.reductions if r.dimension == "timing"]
        assert len(time_reductions) == 1
        assert result.minimized["faults"][0]["start_s"] > 0

    def test_no_timing_reduction_when_no_room(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=0, duration_steps=0, timing_steps=5
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(start_s=0, duration_s=150)

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
        trial = _make_test_trial(severity="slow-100ms", duration_s=60, start_s=0)

        result = minimizer.minimize(trial)

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
        trial = _make_test_trial(severity="slow-100ms", duration_s=60, num_faults=3)

        result = minimizer.minimize(trial)

        assert len(result.minimized["faults"]) < 3
        for f in result.minimized["faults"]:
            ms = parse_severity_ms("nw", f["severity"])
            assert ms is not None
            assert ms < 100.0


class TestMinimizationResult:
    def test_preserves_original(self):
        runner = _MockRunner(always_reproduces=True)
        oracle = _make_oracle()
        minimizer = Minimizer(runner, oracle)
        trial = _make_test_trial(severity="slow-100ms", duration_s=60)

        result = minimizer.minimize(trial)

        assert result.original["faults"][0]["severity"] == "slow-100ms"
        assert result.original["faults"][0]["duration_s"] == 60

    def test_fs_severity_reduction(self):
        runner = _MockRunner(always_reproduces=True)
        runner.set_magnitude_threshold(20000.0)
        oracle = _make_oracle()
        config = MinimizationConfig(
            max_iterations=30, magnitude_steps=8, duration_steps=0, timing_steps=0
        )
        minimizer = Minimizer(runner, oracle, config)
        trial = _make_test_trial(severity="100000", fault_type="fs")

        result = minimizer.minimize(trial)

        mag_reductions = [r for r in result.reductions if r.dimension == "magnitude"]
        assert len(mag_reductions) == 1
        final_ms = parse_severity_ms("fs", result.minimized["faults"][0]["severity"])
        assert final_ms is not None
        assert final_ms < 100000.0
        assert final_ms >= 20000.0


class TestLoadTrial:
    def test_roundtrip(self):
        trial = _make_test_trial(severity="slow-50ms", duration_s=30, num_faults=2)
        restored = load_trial(trial)

        assert restored["trial_id"] == trial["trial_id"]
        assert restored["system"]["name"] == trial["system"]["name"]
        assert len(restored["faults"]) == 2
        assert restored["faults"][0]["severity"] == "slow-50ms"
        assert restored["faults"][0]["duration_s"] == 30

    def test_minimal_dict(self):
        data = {
            "trial_id": "min-trial",
            "system": {"name": "kafka"},
            "benchmark": {"name": "perf_test", "exec_time_s": 120},
            "faults": [
                {
                    "fault_type": "nw",
                    "location": "broker1",
                    "duration_s": 10,
                    "severity": "slow-200ms",
                }
            ],
        }
        trial = load_trial(data)

        assert trial["system"]["name"] == "kafka"
        assert trial["benchmark"]["exec_time_s"] == 120
        assert len(trial["faults"]) == 1
        assert trial["faults"][0]["location"] == "broker1"
