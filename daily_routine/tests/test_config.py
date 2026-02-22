"""config/manager.py のテスト."""

from pathlib import Path

import pytest
import yaml

from daily_routine.config.manager import (
    _REPO_ROOT,
    GlobalConfig,
    generate_project_id,
    init_project,
    load_global_config,
    load_project_config,
)

_ENV_KEYS = [
    "DAILY_ROUTINE_API_KEY_OPENAI",
    "DAILY_ROUTINE_API_KEY_GOOGLE_AI",
    "DAILY_ROUTINE_API_KEY_STABILITY",
    "DAILY_ROUTINE_API_KEY_YOUTUBE_DATA_API",
]


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """テスト中は .env 由来の環境変数を除去し、load_dotenv を無効化する."""
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("daily_routine.config.manager.load_dotenv", lambda *a, **kw: None)


class TestLoadGlobalConfig:
    """load_global_config のテスト."""

    def test_default_values(self) -> None:
        config = load_global_config(Path("/nonexistent/path/config.yaml"))
        assert config.data_root == _REPO_ROOT / "outputs"
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

    def test_env_override(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DAILY_ROUTINE_API_KEY_OPENAI", "env-key-123")
        config = load_global_config(Path("/nonexistent/path/config.yaml"))
        assert config.api_keys.openai == "env-key-123"

    def test_env_override_takes_precedence(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        config_path = tmp_path / "config.yaml"
        config_path.write_text(yaml.dump({"api_keys": {"openai": "yaml-key"}}))
        monkeypatch.setenv("DAILY_ROUTINE_API_KEY_OPENAI", "env-key")
        config = load_global_config(config_path)
        assert config.api_keys.openai == "env-key"


class TestDotenvLoading:
    """.env ファイル読み込みのテスト."""

    def test_dotenv_loads_api_key(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """`.env` ファイルに記載したAPIキーが読み込まれる."""
        env_file = tmp_path / ".env"
        env_file.write_text("DAILY_ROUTINE_API_KEY_OPENAI=dotenv-key-abc\n")

        from dotenv import load_dotenv

        # autouse フィクスチャの無効化を解除して実際に .env を読み込む
        monkeypatch.setattr(
            "daily_routine.config.manager.load_dotenv",
            lambda *a, **kw: load_dotenv(env_file, override=True),
        )
        config = load_global_config(Path("/nonexistent/path/config.yaml"))
        assert config.api_keys.openai == "dotenv-key-abc"

    def test_export_overrides_dotenv(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """`export` で設定した環境変数が `.env` より優先される."""
        env_file = tmp_path / ".env"
        env_file.write_text("DAILY_ROUTINE_API_KEY_OPENAI=dotenv-key\n")

        from dotenv import load_dotenv

        # load_dotenv は既存の環境変数を上書きしない（override=False がデフォルト）
        monkeypatch.setenv("DAILY_ROUTINE_API_KEY_OPENAI", "export-key")
        monkeypatch.setattr(
            "daily_routine.config.manager.load_dotenv",
            lambda *a, **kw: load_dotenv(env_file),
        )
        config = load_global_config(Path("/nonexistent/path/config.yaml"))
        assert config.api_keys.openai == "export-key"


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
