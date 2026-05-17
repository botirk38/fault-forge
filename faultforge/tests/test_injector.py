"""Tests for network fault injector."""

from __future__ import annotations

from unittest.mock import patch

from faultforge.injector import NetworkFaultInjector, parse_severity


class TestNetworkFaultInjector:
    def test_inject_delay(self) -> None:
        injector = NetworkFaultInjector()
        with patch("faultforge.injector.subprocess.run") as mock_run:
            injector.inject_delay("etcd0", 100)
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert "docker" in args
            assert "exec" in args
            assert "etcd0" in args
            assert "delay" in args
            assert "100ms" in args

    def test_inject_loss(self) -> None:
        injector = NetworkFaultInjector()
        with patch("faultforge.injector.subprocess.run") as mock_run:
            injector.inject_loss("etcd0", 5.0)
            args = mock_run.call_args[0][0]
            assert "loss" in args
            assert "5.0%" in args

    def test_clear(self) -> None:
        injector = NetworkFaultInjector()
        with patch("faultforge.injector.subprocess.run") as mock_run:
            injector.clear("etcd0")
            args = mock_run.call_args[0][0]
            assert "del" in args
            assert "root" in args

    def test_custom_docker_bin(self) -> None:
        injector = NetworkFaultInjector(docker_bin="/usr/bin/docker")
        with patch("faultforge.injector.subprocess.run") as mock_run:
            injector.inject_delay("etcd0", 50)
            args = mock_run.call_args[0][0]
            assert args[0] == "/usr/bin/docker"


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
