"""Tests for runtime configuration."""

from __future__ import annotations

from pathlib import Path

from faultforge.runtime import RuntimeConfig, load_runtime


class TestRuntimeConfig:
    def test_defaults(self) -> None:
        rt = RuntimeConfig()
        resolved = rt.resolve()
        assert resolved.data_dir.endswith("data")
        assert resolved.compose_root.endswith("tools")
        assert resolved.software_root.endswith("software")
        assert resolved.docker_bin == "docker"
        assert resolved.docker_compose_bin == "docker-compose"

    def test_custom_values(self) -> None:
        rt = RuntimeConfig(
            data_dir="/custom/data",
            compose_root="/custom/tools",
            software_root="/custom/software",
            docker_bin="/usr/bin/docker",
        )
        resolved = rt.resolve()
        assert resolved.data_dir == "/custom/data"
        assert resolved.compose_root == "/custom/tools"
        assert resolved.software_root == "/custom/software"
        assert resolved.docker_bin == "/usr/bin/docker"

    def test_resolve_with_base(self, tmp_path: Path) -> None:
        rt = RuntimeConfig(data_dir="mydata", compose_root="mytools")
        resolved = rt.resolve(tmp_path)
        assert resolved.data_dir == str(tmp_path / "mydata")
        assert resolved.compose_root == str(tmp_path / "mytools")


class TestLoadRuntime:
    def test_default_when_no_path(self) -> None:
        rt = load_runtime()
        assert rt.data_dir.endswith("data")

    def test_from_yaml(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "runtime.yaml"
        yaml_path.write_text(
            "data_dir: custom_data\ncompose_root: custom_tools\n",
            encoding="utf-8",
        )
        rt = load_runtime(yaml_path)
        assert rt.data_dir.endswith("custom_data")
        assert rt.compose_root.endswith("custom_tools")
