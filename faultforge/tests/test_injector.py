"""Tests for network fault injector."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from faultforge.injector import NetworkFaultInjector, parse_severity


class TestNetworkFaultInjector:
    def test_inject_delay_installs_tc(self) -> None:
        injector = NetworkFaultInjector()
        with (
            patch("faultforge.injector.subprocess.run") as mock_run,
        ):
            # First call: which tc -> not found
            # Second call: apt-get install -> success
            # Third call: tc qdisc add
            mock_run.side_effect = [
                MagicMock(returncode=1),  # which tc fails
                MagicMock(returncode=0),  # apt-get install succeeds
                MagicMock(returncode=0),  # tc qdisc add succeeds
            ]
            injector.inject_delay("etcd0", 100)
            assert mock_run.call_count == 3
            # Third call is the tc command
            tc_args = mock_run.call_args_list[2][0][0]
            assert "docker" in tc_args
            assert "exec" in tc_args
            assert "etcd0" in tc_args
            assert "tc" in tc_args
            assert "delay" in tc_args
            assert "100ms" in tc_args

    def test_inject_delay_skips_install_if_tc_exists(self) -> None:
        injector = NetworkFaultInjector()
        with patch("faultforge.injector.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)  # which tc succeeds
            injector.inject_delay("etcd0", 100)
            assert mock_run.call_count == 2  # which tc + tc qdisc add

    def test_inject_loss(self) -> None:
        injector = NetworkFaultInjector()
        with (
            patch("faultforge.injector.subprocess.run") as mock_run,
        ):
            mock_run.side_effect = [
                MagicMock(returncode=0),  # which tc succeeds
                MagicMock(returncode=0),  # tc qdisc add
            ]
            injector.inject_loss("etcd0", 5.0)
            tc_args = mock_run.call_args_list[1][0][0]
            assert "loss" in tc_args
            assert "5.0%" in tc_args

    def test_clear(self) -> None:
        injector = NetworkFaultInjector()
        with patch("faultforge.injector.subprocess.run") as mock_run:
            # clear() does not call _ensure_tc, only _run_tc
            mock_run.return_value = MagicMock(returncode=0)
            injector.clear("etcd0")
            assert mock_run.call_count == 1
            tc_args = mock_run.call_args[0][0]
            assert "del" in tc_args
            assert "root" in tc_args

    def test_caches_tc_installed(self) -> None:
        injector = NetworkFaultInjector()
        with patch("faultforge.injector.subprocess.run") as mock_run:
            mock_run.side_effect = [
                MagicMock(returncode=1),  # which tc fails
                MagicMock(returncode=0),  # apt-get install
                MagicMock(returncode=0),  # tc qdisc add
                MagicMock(returncode=0),  # which tc (cached, not called)
                MagicMock(returncode=0),  # tc qdisc add
            ]
            injector.inject_delay("etcd0", 100)
            injector.inject_delay("etcd0", 50)
            # First call: 3 subprocess runs (which tc, apt-get, tc add)
            # Second call: 1 subprocess run (tc add, skips install)
            assert mock_run.call_count == 4


class TestParseSeverity:
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
