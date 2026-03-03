"""設定読み込み・バリデーション."""

import logging
import os
from datetime import datetime
from pathlib import Path

import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from daily_routine.schemas.project import ProjectConfig

logger = logging.getLogger(__name__)

_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_DATA_ROOT = _REPO_ROOT / "outputs"
_DEFAULT_CONFIG_PATH = _REPO_ROOT / "configs" / "global.yaml"
_ENV_PREFIX = "DAILY_ROUTINE_API_KEY_"


class ApiKeys(BaseModel):
    """APIキー設定."""

    openai: str = ""
    google_ai: str = ""
    runway: str = ""

    model_config = {"extra": "allow"}


class LoggingConfig(BaseModel):
    """ロギング設定."""

    level: str = "INFO"
    file: Path | None = None


class DefaultsConfig(BaseModel):
    """デフォルト設定."""

    output_fps: int = 30
    output_duration_range: tuple[int, int] = (30, 60)


class RunwayConfig(BaseModel):
    """Runway Gen-4 固有設定."""

    video_model: str = Field(default="gen4_turbo", description="動画生成モデル名")
    image_model: str = Field(default="gen4_image_turbo", description="画像生成モデル名")
    gcs_bucket: str = Field(default="", description="GCSバケット名（画像アップロード用）")


class VisualConfig(BaseModel):
    """Visual Core 設定."""

    provider: str = Field(default="runway", description="動画生成プロバイダ: runway")
    runway: RunwayConfig = Field(default_factory=RunwayConfig)


class GlobalConfig(BaseModel):
    """グローバル設定."""

    data_root: Path = _DEFAULT_DATA_ROOT
    api_keys: ApiKeys = Field(default_factory=ApiKeys)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    visual: VisualConfig = Field(default_factory=VisualConfig)


def _apply_env_overrides(api_keys: ApiKeys) -> ApiKeys:
    """環境変数 DAILY_ROUTINE_API_KEY_{NAME} でAPIキーをオーバーライドする."""
    data = api_keys.model_dump()
    for key, value in os.environ.items():
        if key.startswith(_ENV_PREFIX) and value:
            name = key[len(_ENV_PREFIX) :].lower()
            data[name] = value
    return ApiKeys(**data)


def load_global_config(path: Path | None = None) -> GlobalConfig:
    """グローバル設定を読み込む。.envファイルと環境変数でAPIキーをオーバーライド可能."""
    load_dotenv(_REPO_ROOT / ".env")

    if path is None:
        path = _DEFAULT_CONFIG_PATH

    if path.exists():
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        logger.info("設定ファイルを読み込みました: %s", path)
    else:
        raw = {}
        logger.info("設定ファイルが見つかりません。デフォルト値を使用します: %s", path)

    config = GlobalConfig(**raw)
    config.api_keys = _apply_env_overrides(config.api_keys)
    return config


def load_project_config(project_dir: Path) -> ProjectConfig:
    """プロジェクト設定を読み込む."""
    config_path = project_dir / "config.yaml"
    if not config_path.exists():
        msg = f"プロジェクト設定ファイルが見つかりません: {config_path}"
        raise FileNotFoundError(msg)

    with open(config_path) as f:
        raw = yaml.safe_load(f) or {}

    return ProjectConfig(**raw)


def get_project_dir(global_config: GlobalConfig, project_id: str) -> Path:
    """プロジェクトのデータディレクトリを取得・作成する."""
    project_dir = global_config.data_root / "projects" / project_id
    project_dir.mkdir(parents=True, exist_ok=True)
    return project_dir


def generate_project_id(keyword: str) -> str:
    """キーワードからプロジェクトIDを生成する."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{keyword}_{timestamp}"


def init_project(global_config: GlobalConfig, keyword: str, project_id: str | None = None) -> ProjectConfig:
    """新規プロジェクトを初期化し、設定ファイルとディレクトリ構造を作成する."""
    if project_id is None:
        project_id = generate_project_id(keyword)

    project_dir = get_project_dir(global_config, project_id)

    # サブディレクトリの作成
    for subdir in [
        "intelligence",
        "scenario",
        "storyboard",
        "assets/character",
        "assets/environments",
        "assets/keyframes",
        "assets/reference/person",
        "assets/reference/clothing",
        "assets/reference/environments",
        "clips",
        "audio/bgm",
        "audio/se",
        "output",
    ]:
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)

    # プロジェクト設定の作成
    config = ProjectConfig(
        project_id=project_id,
        keyword=keyword,
        output_fps=global_config.defaults.output_fps,
        output_duration_range=global_config.defaults.output_duration_range,
    )

    # 設定ファイルの保存
    config_path = project_dir / "config.yaml"
    with open(config_path, "w") as f:
        yaml.dump(config.model_dump(mode="json"), f, allow_unicode=True, default_flow_style=False)

    logger.info("プロジェクトを初期化しました: %s", project_id)
    return config
