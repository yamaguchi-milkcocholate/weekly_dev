"""Scenario Engine入出力のスキーマ."""

from pydantic import BaseModel, Field


class CameraWork(BaseModel):
    """カメラワーク指定."""

    type: str = Field(description="カメラワーク種別（POV, close-up, wide, follow等）")
    description: str = Field(description="カメラワークの詳細説明")


class SceneSpec(BaseModel):
    """シーン仕様."""

    scene_number: int = Field(description="1始まりの連番")
    duration_sec: float = Field(description="シーンの尺（秒）")
    situation: str = Field(description="状況説明（日本語）")
    camera_work: CameraWork
    caption_text: str = Field(description="テロップテキスト（日本語）")
    image_prompt: str = Field(
        description="Asset Generator用の背景画像生成プロンプト（英語）。キャラクター不在、背景のみ"
    )


class CharacterSpec(BaseModel):
    """キャラクター仕様."""

    name: str = Field(description="キャラクター名")
    appearance: str = Field(description="外見の詳細説明（英語）。年齢、髪型、髪色、体型等")
    outfit: str = Field(description="服装の詳細説明（英語）")
    reference_prompt: str = Field(
        description="Asset Generator用の正面リファレンス画像生成プロンプト（英語）。"
        "グリーンバック（クロマキー緑）、スタジオライティング、全身立ちポーズ"
    )


class Scenario(BaseModel):
    """Scenario Engineの出力."""

    title: str = Field(description="動画タイトル（日本語）")
    total_duration_sec: float = Field(description="動画の総尺（秒）")
    characters: list[CharacterSpec] = Field(description="キャラクター仕様リスト")
    scenes: list[SceneSpec] = Field(description="シーン仕様リスト")
    bgm_direction: str = Field(description="BGMの方向性指示（日本語）。テンポ、ジャンル、雰囲気の変化等")
