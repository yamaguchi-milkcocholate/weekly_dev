"""Visual Core入出力のスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class VideoClip(BaseModel):
    """生成された動画クリップ."""

    scene_number: int = Field(description="シーン番号")
    clip_path: Path = Field(description="動画ファイルパス")
    duration_sec: float = Field(description="動画の長さ（秒）")
    model_name: str = Field(description="使用モデル名")
    cost_usd: float | None = Field(default=None, description="推定コスト（USD）")
    quality_score: float | None = Field(
        default=None,
        description="品質スコア（0-1）、品質チェック後に設定",
    )
    generation_time_sec: float | None = Field(
        default=None,
        description="生成にかかった時間（秒）",
    )


class VideoClipSet(BaseModel):
    """Visual Coreの出力."""

    clips: list[VideoClip] = Field(description="シーンごとの動画クリップリスト")
    total_cost_usd: float = Field(default=0.0, description="合計推定コスト（USD）")
    provider: str = Field(default="", description="使用プロバイダ名")
