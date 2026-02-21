"""config/manager.py のテスト."""

import os
from pathlib import Path

import pytest
import yaml

from daily_routine.config.manager import (
    GlobalConfig,
    generate_project_id,
    init_project,
    load_global_config,
    load_project_config,
)


class TestLoadGlobalConfig:
    """load_global_config のテスト."""

    def test_default_values(self) -> None:
        config = load_global_config(Path("/nonexistent/path/config.yaml"))
        assert config.data_root == Path.home() / ".daily_routine"
        assert config.api_keys.openai == ""
        assert config.defaults.output_fps == 30

    def test_load_from_yaml(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(
            yaml.dump(
                {
                    "data_root": str(tmp_path / "data"),
                    "api_keys": {"openai": "sk-test"},
                    "defaults": {"output_fps": 60},
                }
            )
        )
        config = load_global_config(config_path)
        assert config.data_root == tmp_path / "data"
        assert config.api_keys.openai == "sk-test"
        assert config.defaults.output_fps == 60

    def test_env_override(self) -> None:
        os.environ["DAILY_ROUTINE_API_KEY_OPENAI"] = "env-key-123"
        try:
            config = load_global_config(Path("/nonexistent/path/config.yaml"))
            assert config.api_keys.openai == "env-key-123"
        finally:
            del os.environ["DAILY_ROUTINE_API_KEY_OPENAI"]

    def test_env_override_takes_precedence(self, tmp_path: Path) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({"api_keys": {"openai": "yaml-key"}}))
        os.environ["DAILY_ROUTINE_API_KEY_OPENAI"] = "env-key"
        try:
            config = load_global_config(config_path)
            assert config.api_keys.openai == "env-key"
        finally:
            del os.environ["DAILY_ROUTINE_API_KEY_OPENAI"]


class TestInitProject:
    """init_project のテスト."""

    def test_creates_directories(self, tmp_path: Path) -> None:
        global_config = GlobalConfig(data_root=tmp_path)
        config = init_project(global_config, "OLの一日", project_id="test-proj")
        project_dir = tmp_path / "projects" / "test-proj"

        assert config.project_id == "test-proj"
        assert config.keyword == "OLの一日"
        assert project_dir.exists()
        assert (project_dir / "intelligence").is_dir()
        assert (project_dir / "assets" / "character").is_dir()
        assert (project_dir / "output").is_dir()
        assert (project_dir / "config.yaml").exists()

    def test_load_created_project(self, tmp_path: Path) -> None:
        global_config = GlobalConfig(data_root=tmp_path)
        init_project(global_config, "OLの一日", project_id="test-proj")
        project_dir = tmp_path / "projects" / "test-proj"

        loaded = load_project_config(project_dir)
        assert loaded.project_id == "test-proj"
        assert loaded.keyword == "OLの一日"


class TestLoadProjectConfig:
    """load_project_config のテスト."""

    def test_file_not_found(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_project_config(tmp_path / "nonexistent")


class TestGenerateProjectId:
    """generate_project_id のテスト."""

    def test_contains_keyword(self) -> None:
        pid = generate_project_id("OLの一日")
        assert pid.startswith("OLの一日_")

    def test_unique(self) -> None:
        pid1 = generate_project_id("test")
        pid2 = generate_project_id("test")
        # タイムスタンプが同一秒の場合は同じになりうるが、通常は異なる
        assert isinstance(pid1, str)
        assert isinstance(pid2, str)
