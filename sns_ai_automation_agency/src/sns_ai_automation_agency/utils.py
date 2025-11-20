import os
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel


class CachePathManager:
    _instance = None

    def __new__(cls, app_name: str = "my_app"):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, app_name: str = "my_app"):
        if self._initialized:
            return
        self._initialized = True

        self.root = Path(os.getenv("CACHE_HOME", Path.home() / ".cache")) / app_name
        self.root.mkdir(parents=True, exist_ok=True)

    def subdir(self, name: str) -> Path:
        """サブディレクトリ作成＋返却"""
        p = self.root / name
        p.mkdir(parents=True, exist_ok=True)
        return p

    def file(self, *parts: str) -> Path:
        """root 以下のファイルパスを返す（必要なら親ディレクトリ生成）"""
        p = self.root.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        return p


def to_serializable(obj: Any) -> Any:
    """LangGraph / Pydantic 混在オブジェクトを JSON 可能な dict へ安全変換"""

    # Pydantic BaseModel
    if isinstance(obj, BaseModel):
        # Pydantic v2 でも v1 でも動作
        return {k: to_serializable(v) for k, v in obj.dict().items()}

    # Enum
    if isinstance(obj, Enum):
        return obj.value

    # pathlib.Path
    if isinstance(obj, Path):
        return str(obj)

    # list / tuple
    if isinstance(obj, (list, tuple)):
        return [to_serializable(v) for v in obj]

    # dict
    if isinstance(obj, dict):
        return {k: to_serializable(v) for k, v in obj.items()}

    # その他（int, float, str, None など）はそのまま
    return obj
