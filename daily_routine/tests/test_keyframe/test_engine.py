"""keyframe/engine.py のテスト."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from daily_routine.keyframe.engine import RunwayKeyframeEngine, _resolve_style_reference
from daily_routine.schemas.asset import AssetSet, BackgroundAsset, CharacterAsset, PropAsset
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)
from daily_routine.schemas.style_mapping import SceneStyleReference, StyleMapping
from daily_routine.visual.clients.gen4_image import ImageGenerationRequest, ImageGenerationResult


def _make_storyboard() -> Storyboard:
    return Storyboard(
        title="テスト動画",
        total_duration_sec=6.0,
        total_cuts=2,
        scenes=[
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=3.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_01_cut_01",
                        scene_number=1,
                        cut_number=1,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="slow zoom-in",
                        action_description="テスト動作1",
                        motion_prompt="@char moves slowly",
                        keyframe_prompt="@char in a room",
                        transition=Transition.CUT,
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=2,
                scene_duration_sec=3.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_02_cut_01",
                        scene_number=2,
                        cut_number=1,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="pan left",
                        action_description="テスト動作2",
                        motion_prompt="@char walks",
                        keyframe_prompt="@char at a cafe",
                        transition=Transition.CUT,
                    ),
                ],
            ),
        ],
    )


def _make_assets(tmp_path: Path) -> AssetSet:
    front_view = tmp_path / "front.png"
    front_view.write_bytes(b"fake_image")
    return AssetSet(
        characters=[
            CharacterAsset(
                character_name="花子",
                front_view=front_view,
                side_view=tmp_path / "side.png",
                back_view=tmp_path / "back.png",
            ),
        ],
        props=[
            PropAsset(name="スマホ", image_path=tmp_path / "smartphone.png"),
        ],
        backgrounds=[
            BackgroundAsset(
                scene_number=1,
                description="テスト背景",
                image_path=tmp_path / "bg.png",
            ),
        ],
    )


def _make_mock_client() -> AsyncMock:
    client = AsyncMock()

    async def generate_side_effect(request: ImageGenerationRequest, output_path: Path) -> ImageGenerationResult:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"generated_image")
        return ImageGenerationResult(
            image_path=output_path,
            model_name="gen4_image_turbo",
            cost_usd=0.02,
        )

    client.generate = AsyncMock(side_effect=generate_side_effect)
    return client


def _make_engine(client: AsyncMock) -> RunwayKeyframeEngine:
    """テスト用にエンジンインスタンスを作成する."""
    engine = RunwayKeyframeEngine(api_key="", gcs_bucket="")
    engine._image_client = client
    return engine


class TestGenerateKeyframes:
    """generate_keyframes のテスト."""

    @pytest.mark.asyncio
    async def test_スタイルマッピングなし_charのみで生成(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        result = await engine.generate_keyframes(
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        assert len(result.keyframes) == 2
        # 2回呼ばれたことを確認
        assert client.generate.call_count == 2
        # 各呼び出しで reference_images が char のみ
        for call in client.generate.call_args_list:
            request = call.args[0]
            assert "char" in request.reference_images
            assert "location" not in request.reference_images

    @pytest.mark.asyncio
    async def test_スタイルマッピングあり_locationが追加(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        assets = _make_assets(tmp_path)
        storyboard = _make_storyboard()

        # スタイル参照画像を作成
        ref_image = project_dir / "assets" / "reference" / "cafe.png"
        ref_image.parent.mkdir(parents=True)
        ref_image.write_bytes(b"style_reference")

        style_mapping = StyleMapping(
            mappings=[
                SceneStyleReference(scene_number=1, reference=Path("assets/reference/cafe.png")),
            ]
        )

        client = _make_mock_client()
        engine = _make_engine(client)

        result = await engine.generate_keyframes(
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            style_mapping=style_mapping,
            project_dir=project_dir,
        )

        assert len(result.keyframes) == 2
        assert client.generate.call_count == 2

        # scene 1: char + location
        req_scene1 = client.generate.call_args_list[0].args[0]
        assert "char" in req_scene1.reference_images
        assert "location" in req_scene1.reference_images

        # scene 2: char のみ（マッピングなし）
        req_scene2 = client.generate.call_args_list[1].args[0]
        assert "char" in req_scene2.reference_images
        assert "location" not in req_scene2.reference_images

    @pytest.mark.asyncio
    async def test_スタイル参照画像が存在しない_警告のみで生成継続(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        project_dir = tmp_path / "project"
        project_dir.mkdir()
        assets = _make_assets(tmp_path)
        storyboard = _make_storyboard()

        # 参照画像ファイルは作成しない
        style_mapping = StyleMapping(
            mappings=[
                SceneStyleReference(scene_number=1, reference=Path("assets/reference/missing.png")),
            ]
        )

        client = _make_mock_client()
        engine = _make_engine(client)

        result = await engine.generate_keyframes(
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            style_mapping=style_mapping,
            project_dir=project_dir,
        )

        assert len(result.keyframes) == 2
        # ファイルが存在しないので location は追加されない
        req_scene1 = client.generate.call_args_list[0].args[0]
        assert "location" not in req_scene1.reference_images


class TestResolveStyleReference:
    """_resolve_style_reference のテスト."""

    def test_絶対パス_そのまま返す(self, tmp_path: Path) -> None:
        abs_path = tmp_path / "absolute" / "image.png"
        result = _resolve_style_reference(abs_path, tmp_path / "project")
        assert result == abs_path

    def test_seedsパス_リポジトリルートから解決(self, tmp_path: Path) -> None:
        # project_dir = repo_root/outputs/projects/test-id
        project_dir = tmp_path / "outputs" / "projects" / "test-id"
        project_dir.mkdir(parents=True)
        path = Path("seeds/captures/abc/7.png")
        result = _resolve_style_reference(path, project_dir)
        assert result == tmp_path / "seeds" / "captures" / "abc" / "7.png"

    def test_相対パス_プロジェクトディレクトリから解決(self, tmp_path: Path) -> None:
        project_dir = tmp_path / "outputs" / "projects" / "test-id"
        project_dir.mkdir(parents=True)
        path = Path("assets/reference/cafe.png")
        result = _resolve_style_reference(path, project_dir)
        assert result == project_dir / "assets" / "reference" / "cafe.png"
