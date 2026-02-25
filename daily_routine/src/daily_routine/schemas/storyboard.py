"""絵コンテ（Storyboard）スキーマ."""

from enum import StrEnum

from pydantic import BaseModel, Field


class MotionIntensity(StrEnum):
    """動きの強度."""

    STATIC = "static"  # カメラワークのみ（被写体は静止）
    SUBTLE = "subtle"  # 微細な動き（髪揺れ、湯気、瞬き）
    MODERATE = "moderate"  # 中程度の動き（コーヒーを飲む、ページをめくる）
    DYNAMIC = "dynamic"  # 大きな動き（歩く、立ち上がる）


class Transition(StrEnum):
    """カット間トランジション."""

    CUT = "cut"  # ハードカット（直接繋ぎ）
    FADE_IN = "fade_in"  # フェードイン（黒→映像）
    FADE_OUT = "fade_out"  # フェードアウト（映像→黒）
    CROSS_FADE = "cross_fade"  # クロスフェード（前カット→次カット）


class CutSpec(BaseModel):
    """1カットの絵コンテ."""

    cut_id: str = Field(description="カットID（例: 'scene_02_cut_01'）")
    scene_number: int = Field(description="所属シーン番号")
    cut_number: int = Field(description="シーン内のカット番号（1始まり）")
    duration_sec: float = Field(description="カットの尺（2〜5秒、整数）")
    motion_intensity: MotionIntensity = Field(description="動きの強度")
    camera_work: str = Field(description="カメラワーク指示（英語、例: 'slow zoom-in from medium to close-up'）")
    action_description: str = Field(description="動作の説明（日本語、ユーザー確認用）")
    motion_prompt: str = Field(description="動画生成プロンプト（英語、Subject Motion + Scene Motion + Camera Motion）")
    keyframe_prompt: str = Field(description="キーフレーム画像プロンプト（英語、@char タグでキャラクター参照）")
    transition: Transition = Field(default=Transition.CUT, description="次のカットへのトランジション種別")


class SceneStoryboard(BaseModel):
    """1シーンの絵コンテ."""

    scene_number: int = Field(description="シーン番号")
    scene_duration_sec: float = Field(description="シーン全体の尺（カットの合計）")
    cuts: list[CutSpec] = Field(description="カットリスト")


class Storyboard(BaseModel):
    """全体の絵コンテ."""

    title: str = Field(description="動画タイトル")
    total_duration_sec: float = Field(description="全体尺（全カットの合計）")
    total_cuts: int = Field(description="総カット数")
    scenes: list[SceneStoryboard] = Field(description="シーンごとの絵コンテ")
