"""Tests for fault injector package."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from faultforge.injectors.network import NetworkFaultInjector
from faultforge.injectors.resource import ResourceFaultInjector
from faultforge.injectors.process import ProcessFaultInjector
from faultforge.injectors.filesystem import FilesystemFaultInjector
from faultforge.injectors.registry import InjectorRegistry


class TestNetworkFaultInjector:
    def test_inject_delay_with_tc_present(self) -> None:
        injector = NetworkFaultInjector()
        with patch.object(injector, "_exec") as mock_exec:
            mock_exec.return_value = MagicMock(returncode=0)
            injector._tc_ready.add("etcd0")
            injector.inject_delay("etcd0", 100)
            mock_exec.assert_called()
            tc_call = mock_exec.call_args[0][1]
            assert "delay" in " ".join(tc_call)
            assert "100ms" in " ".join(tc_call)

    def test_inject_loss_with_tc_present(self) -> None:
        injector = NetworkFaultInjector()
        with patch.object(injector, "_exec") as mock_exec:
            mock_exec.return_value = MagicMock(returncode=0)
            injector._tc_ready.add("etcd0")
            injector.inject_loss("etcd0", 5.0)
            tc_call = mock_exec.call_args[0][1]
            assert "loss" in " ".join(tc_call)
            assert "5.0%" in " ".join(tc_call)

    def test_clear(self) -> None:
        injector = NetworkFaultInjector()
        with patch.object(injector, "_exec") as mock_exec:
            injector.clear("etcd0")
            tc_call = mock_exec.call_args[0][1]
            assert "del" in " ".join(tc_call)

    def test_ensure_tc_raises_if_missing(self) -> None:
        injector = NetworkFaultInjector()
        with patch.object(injector, "_exec") as mock_exec:
            mock_exec.return_value = MagicMock(returncode=1)
            with pytest.raises(RuntimeError, match="tc not found"):
                injector._ensure_tc("etcd0")


class TestResourceFaultInjector:
    def test_inject_cpu(self) -> None:
        injector = ResourceFaultInjector()
        with patch.object(injector, "_run") as mock_run:
            mock_run.return_value = MagicMock(stdout="0")
            injector.inject_cpu("etcd0", "0.25")
            calls = [c[0][0] for c in mock_run.call_args_list]
            assert any("--cpus=0.25" in " ".join(c) for c in calls)

    def test_inject_mem(self) -> None:
        injector = ResourceFaultInjector()
        with patch.object(injector, "_run") as mock_run:
            mock_run.return_value = MagicMock(stdout="0")
            injector.inject_mem("etcd0", "512m")
            calls = [c[0][0] for c in mock_run.call_args_list]
            assert any("--memory=512m" in " ".join(c) for c in calls)

    def test_clear_restores_baseline(self) -> None:
        injector = ResourceFaultInjector()
        injector._baselines["etcd0"] = {"cpu": "4", "mem": "32g"}
        with patch.object(injector, "_run") as mock_run:
            injector.clear("etcd0")
            calls = [c[0][0] for c in mock_run.call_args_list]
            assert any("--cpus=4" in " ".join(c) for c in calls)
            assert any("--memory=32g" in " ".join(c) for c in calls)


class TestProcessFaultInjector:
    def test_restart(self) -> None:
        injector = ProcessFaultInjector()
        with patch.object(injector, "_run") as mock_run:
            injector.restart("etcd0")
            call = mock_run.call_args[0][0]
            assert "restart" in call
            assert "etcd0" in call

    def test_stop(self) -> None:
        injector = ProcessFaultInjector()
        with patch.object(injector, "_run") as mock_run:
            injector.stop("etcd0")
            call = mock_run.call_args[0][0]
            assert "stop" in call
            assert "etcd0" in call

    def test_kill(self) -> None:
        injector = ProcessFaultInjector()
        with patch.object(injector, "_run") as mock_run:
            injector.kill("etcd0", "SIGTERM")
            call = mock_run.call_args[0][0]
            assert "kill" in call
            assert "--signal=SIGTERM" in call


class TestFilesystemFaultInjector:
    def test_inject_raises_without_delay(self) -> None:
        injector = FilesystemFaultInjector()
        with pytest.raises(ValueError, match="delay"):
            injector.inject("etcd0")

    def test_inject_raises_without_cfs_source(self) -> None:
        injector = FilesystemFaultInjector(cfs_source="")
        with pytest.raises(FileNotFoundError):
            injector.inject("etcd0", delay="10000")

    def test_clear_raises_without_cfs_source(self) -> None:
        injector = FilesystemFaultInjector(cfs_source="")
        with pytest.raises(FileNotFoundError):
            injector.clear("etcd0")


class TestInjectorRegistry:
    def test_get_network(self) -> None:
        registry = InjectorRegistry()
        inj = registry.get("nw")
        assert isinstance(inj, NetworkFaultInjector)

    def test_get_resource(self) -> None:
        registry = InjectorRegistry()
        inj = registry.get("cpu")
        assert isinstance(inj, ResourceFaultInjector)

    def test_get_process(self) -> None:
        registry = InjectorRegistry()
        inj = registry.get("process")
        assert isinstance(inj, ProcessFaultInjector)

    def test_get_filesystem(self) -> None:
        registry = InjectorRegistry()
        inj = registry.get("fs")
        assert isinstance(inj, FilesystemFaultInjector)

    def test_get_unknown_raises(self) -> None:
        registry = InjectorRegistry()
        with pytest.raises(ValueError, match="Unknown fault domain"):
            registry.get("unknown")

    def test_caches_injector(self) -> None:
        registry = InjectorRegistry()
        inj1 = registry.get("nw")
        inj2 = registry.get("nw")
        assert inj1 is inj2
