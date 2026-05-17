"""Tests for network fault injector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from faultforge.injector import NetworkFaultInjector, parse_severity


class TestNetworkFaultInjector:
    def test_inject_delay(self) -> None:
        injector = NetworkFaultInjector()
        with (
            patch.object(injector, "_get_pid", return_value="12345"),
            patch("faultforge.injector.subprocess.run") as mock_run,
        ):
            injector.inject_delay("etcd0", 100)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "nsenter" in args
            assert "-t" in args
            assert "12345" in args
            assert "-n" in args
            assert "tc" in args
            assert "delay" in args
            assert "100ms" in args

    def test_inject_loss(self) -> None:
        injector = NetworkFaultInjector()
        with (
            patch.object(injector, "_get_pid", return_value="12345"),
            patch("faultforge.injector.subprocess.run") as mock_run,
        ):
            injector.inject_loss("etcd0", 5.0)
            args = mock_run.call_args[0][0]
            assert "loss" in args
            assert "5.0%" in args

    def test_clear(self) -> None:
        injector = NetworkFaultInjector()
        with (
            patch.object(injector, "_get_pid", return_value="12345"),
            patch("faultforge.injector.subprocess.run") as mock_run,
        ):
            injector.clear("etcd0")
            args = mock_run.call_args[0][0]
            assert "del" in args
            assert "root" in args

    def test_get_pid(self) -> None:
        injector = NetworkFaultInjector()
        with patch("faultforge.injector.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(stdout="54321\n")
            pid = injector._get_pid("etcd0")
            assert pid == "54321"
            mock_run.assert_called_once_with(
                ["docker", "inspect", "-f", "{{.State.Pid}}", "etcd0"],
                capture_output=True,
                text=True,
                check=True,
            )


class TestParseSeverity:
    def test_slow_delay(self) -> None:
        kind, value = parse_severity("slow-100ms")
        assert kind == "delay"
        assert value == 100

    def test_slow_100ms(self) -> None:
        kind, value = parse_severity("slow-100ms")
        assert kind == "delay"
        assert value == 100

    def test_loss(self) -> None:
        kind, value = parse_severity("loss-5pct")
        assert kind == "loss"
        assert value == 5.0

    def test_unknown_raises(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="Unknown severity"):
            parse_severity("partition-all")
