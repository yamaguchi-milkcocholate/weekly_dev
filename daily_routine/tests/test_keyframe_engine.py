"""GeminiKeyframeEngine のモックテスト."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from daily_routine.keyframe.engine import GeminiKeyframeEngine
from daily_routine.schemas.asset import AssetSet, CharacterAsset, KeyframeAsset
from daily_routine.keyframe.prompt import ReferenceInfo
from daily_routine.schemas.keyframe_mapping import (
    CharacterComponent,
    KeyframeMapping,
    ReferenceComponent,
    ReferencePurpose,
    SceneKeyframeSpec,
)
from daily_routine.schemas.pipeline_io import KeyframeInput
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, Scenario, SceneSpec
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)


@pytest.fixture
def sample_scenario() -> Scenario:
    """テスト用Scenario."""
    return Scenario(
        title="テスト動画",
        total_duration_sec=16.0,
        characters=[
            CharacterSpec(
                name="Aoi",
                appearance="20代女性",
                outfit="白ブラウス",
                reference_prompt="A young Japanese woman",
            )
        ],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=8.0,
                situation="朝、玄関を出る",
                camera_work=CameraWork(type="wide", description="全身ショット"),
                caption_text="AM 7:30 出勤",
                image_prompt="Modern apartment entrance",
            ),
            SceneSpec(
                scene_number=2,
                duration_sec=8.0,
                situation="カフェでコーヒーを飲む",
                camera_work=CameraWork(type="close-up", description="クローズアップ"),
                caption_text="毎朝のルーティン",
                image_prompt="Cafe interior",
            ),
        ],
        bgm_direction="明るいポップス",
    )


@pytest.fixture
def sample_storyboard() -> Storyboard:
    """テスト用Storyboard."""
    return Storyboard(
        title="テスト動画",
        total_duration_sec=16.0,
        total_cuts=4,
        scenes=[
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=8.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_01_cut_01",
                        scene_number=1,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="wide shot, static",
                        action_description="玄関のドアを開ける",
                        motion_prompt="She opens the door and steps out",
                        keyframe_prompt="@char walks out of a modern apartment entrance, morning light",
                        transition=Transition.FADE_IN,
                        pose_instruction="standing at doorway",
                    ),
                    CutSpec(
                        cut_id="scene_01_cut_02",
                        scene_number=1,
                        cut_number=2,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.DYNAMIC,
                        camera_work="medium shot, slow zoom-in",
                        action_description="歩き出す",
                        motion_prompt="She walks forward confidently",
                        keyframe_prompt="@char walks on a residential street, morning sunlight",
                        pose_instruction="walking forward",
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=2,
                scene_duration_sec=8.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_02_cut_01",
                        scene_number=2,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="close-up, static",
                        action_description="コーヒーカップに手を伸ばす",
                        motion_prompt="She reaches for a coffee cup",
                        keyframe_prompt="@char sits at a cafe counter with a coffee cup",
                        transition=Transition.CROSS_FADE,
                    ),
                    CutSpec(
                        cut_id="scene_02_cut_02",
                        scene_number=2,
                        cut_number=2,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="close-up, slow dolly in",
                        action_description="コーヒーを飲む",
                        motion_prompt="She picks up the cup and takes a sip",
                        keyframe_prompt="@char sips coffee at a cafe counter",
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_assets(tmp_path: Path) -> AssetSet:
    """テスト用AssetSet."""
    char_dir = tmp_path / "assets" / "character" / "Aoi"
    char_dir.mkdir(parents=True)
    front = char_dir / "front.png"
    front.write_bytes(b"fake-png")

    return AssetSet(
        characters=[
            CharacterAsset(
                character_name="Aoi",
                front_view=front,
                identity_block="Young adult female, dark brown hair",
            )
        ],
    )


@pytest.fixture
def multi_char_assets(tmp_path: Path) -> AssetSet:
    """テスト用AssetSet（複数キャラクター）."""
    aoi_dir = tmp_path / "assets" / "character" / "Aoi"
    aoi_dir.mkdir(parents=True)
    aoi_front = aoi_dir / "front.png"
    aoi_front.write_bytes(b"fake-aoi")

    saki_dir = tmp_path / "assets" / "character" / "Saki"
    saki_dir.mkdir(parents=True)
    saki_front = saki_dir / "front.png"
    saki_front.write_bytes(b"fake-saki")

    return AssetSet(
        characters=[
            CharacterAsset(
                character_name="Aoi",
                front_view=aoi_front,
                identity_block="Young adult female, dark brown hair",
            ),
            CharacterAsset(
                character_name="Saki",
                front_view=saki_front,
                identity_block="Young adult female, blonde hair",
            ),
        ],
    )


def _make_mock_client() -> AsyncMock:
    """モックの GeminiKeyframeClient を作成する."""
    mock_client = AsyncMock()
    mock_client.analyze_scene.return_value = "A young woman standing at the entrance"

    async def mock_generate_keyframe(
        char_images, env_image, flash_prompt, reference_images=None, reference_infos=None, output_path=None
    ):
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-keyframe")
        return output_path

    mock_client.generate_keyframe.side_effect = mock_generate_keyframe
    return mock_client


class TestGenerateKeyframes:
    """GeminiKeyframeEngine.generate_keyframes のテスト."""

    @pytest.mark.asyncio
    async def test_generate_keyframes_全カット生成(
        self, sample_scenario: Scenario, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """全カットのキーフレーム画像が生成される."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)
        output_dir = tmp_path / "assets" / "keyframes"
        result = await engine.generate_keyframes(sample_scenario, sample_storyboard, sample_assets, output_dir)

        assert mock_client.analyze_scene.await_count == 4
        assert mock_client.generate_keyframe.await_count == 4
        assert len(result.keyframes) == 4

    @pytest.mark.asyncio
    async def test_generate_keyframes_AssetSet構造(
        self, sample_scenario: Scenario, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """出力のAssetSetにkeyframesが正しく追加される."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)
        output_dir = tmp_path / "assets" / "keyframes"
        result = await engine.generate_keyframes(sample_scenario, sample_storyboard, sample_assets, output_dir)

        # 元のアセットは保持される
        assert len(result.characters) == 1
        assert result.characters[0].character_name == "Aoi"

        # キーフレームが追加されている
        assert len(result.keyframes) == 4
        assert result.keyframes[0].scene_number == 1
        assert result.keyframes[0].cut_id == "scene_01_cut_01"
        assert result.keyframes[0].generation_method == "gemini"
        assert result.keyframes[2].scene_number == 2

    @pytest.mark.asyncio
    async def test_generate_keyframes_identity_blocksリストが渡される(
        self, sample_scenario: Scenario, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """analyze_scene に identity_blocks リストが渡される."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)
        output_dir = tmp_path / "assets" / "keyframes"
        await engine.generate_keyframes(sample_scenario, sample_storyboard, sample_assets, output_dir)

        for call in mock_client.analyze_scene.call_args_list:
            assert call.kwargs["identity_blocks"] == ["Young adult female, dark brown hair"]
            assert call.kwargs["char_images"] == [sample_assets.characters[0].front_view]

    @pytest.mark.asyncio
    async def test_generate_keyframes_キャラクター不在_ValueError(
        self, sample_scenario: Scenario, sample_storyboard: Storyboard, tmp_path: Path
    ) -> None:
        """キャラクターがない場合エラー."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)
        empty_assets = AssetSet(characters=[])

        with pytest.raises(ValueError, match="キャラクターアセット"):
            await engine.generate_keyframes(sample_scenario, sample_storyboard, empty_assets, tmp_path / "keyframes")

    @pytest.mark.asyncio
    async def test_generate_keyframes_複数キャラクター(
        self,
        sample_scenario: Scenario,
        sample_storyboard: Storyboard,
        multi_char_assets: AssetSet,
        tmp_path: Path,
    ) -> None:
        """複数キャラクターのコンポーネントが正しく解決される."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)

        mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=1,
                    components=[
                        CharacterComponent(character="Aoi"),
                        CharacterComponent(character="Saki"),
                    ],
                ),
            ]
        )

        output_dir = tmp_path / "assets" / "keyframes"
        await engine.generate_keyframes(
            sample_scenario, sample_storyboard, multi_char_assets, output_dir, keyframe_mapping=mapping
        )

        # scene_number=1 のカットでは2キャラクターが渡される
        scene1_calls = [
            c for c in mock_client.analyze_scene.call_args_list if len(c.kwargs["char_images"]) == 2
        ]
        assert len(scene1_calls) == 2  # scene 1 has 2 cuts
        for call in scene1_calls:
            assert len(call.kwargs["identity_blocks"]) == 2
            assert call.kwargs["identity_blocks"][0] == "Young adult female, dark brown hair"
            assert call.kwargs["identity_blocks"][1] == "Young adult female, blonde hair"

    @pytest.mark.asyncio
    async def test_generate_keyframes_キャラクターと参照コンポーネント混在(
        self,
        sample_scenario: Scenario,
        sample_storyboard: Storyboard,
        sample_assets: AssetSet,
        tmp_path: Path,
    ) -> None:
        """キャラクター + 参照コンポーネントが混在するマッピング."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)

        ref_img = tmp_path / "ref" / "latte.png"
        ref_img.parent.mkdir(parents=True)
        ref_img.write_bytes(b"fake-ref")

        mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=2,
                    components=[
                        CharacterComponent(character="Aoi"),
                        ReferenceComponent(image=ref_img, text="ラテカップ"),
                    ],
                ),
            ]
        )

        output_dir = tmp_path / "assets" / "keyframes"
        await engine.generate_keyframes(
            sample_scenario, sample_storyboard, sample_assets, output_dir, keyframe_mapping=mapping
        )

        # scene_number=2 のカットで参照が渡される
        scene2_calls = [
            c for c in mock_client.analyze_scene.call_args_list
            if c.kwargs.get("reference_images") and len(c.kwargs["reference_images"]) > 0
        ]
        assert len(scene2_calls) == 2  # scene 2 has 2 cuts
        for call in scene2_calls:
            assert call.kwargs["reference_images"] == [ref_img]
            infos = call.kwargs["reference_infos"]
            assert len(infos) == 1
            assert infos[0].text == "ラテカップ"
            assert infos[0].purpose == "general"
            assert infos[0].has_image is True


    @pytest.mark.asyncio
    async def test_generate_keyframes_purpose付き参照コンポーネント(
        self,
        sample_scenario: Scenario,
        sample_storyboard: Storyboard,
        sample_assets: AssetSet,
        tmp_path: Path,
    ) -> None:
        """purpose を指定した参照コンポーネントが reference_infos に正しく伝搬される."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)

        ref_img = tmp_path / "ref" / "mask.png"
        ref_img.parent.mkdir(parents=True)
        ref_img.write_bytes(b"fake-mask")

        mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=2,
                    components=[
                        CharacterComponent(character="Aoi"),
                        ReferenceComponent(
                            image=ref_img, text="フルフェイスマスク", purpose=ReferencePurpose.WEARING
                        ),
                    ],
                ),
            ]
        )

        output_dir = tmp_path / "assets" / "keyframes"
        await engine.generate_keyframes(
            sample_scenario, sample_storyboard, sample_assets, output_dir, keyframe_mapping=mapping
        )

        # scene_number=2 のカットで purpose=wearing が渡される
        scene2_calls = [
            c for c in mock_client.analyze_scene.call_args_list
            if c.kwargs.get("reference_infos") and len(c.kwargs["reference_infos"]) > 0
        ]
        assert len(scene2_calls) == 2
        for call in scene2_calls:
            infos = call.kwargs["reference_infos"]
            assert len(infos) == 1
            assert infos[0].purpose == "wearing"
            assert infos[0].text == "フルフェイスマスク"
            assert infos[0].has_image is True


class TestKeyframeEngineExecute:
    """GeminiKeyframeEngine.execute のテスト."""

    @pytest.mark.asyncio
    async def test_execute_KeyframeInput経由(
        self, sample_scenario: Scenario, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """execute が generate_keyframes を呼び、save_output で保存する."""
        mock_client = _make_mock_client()
        engine = GeminiKeyframeEngine.from_components(client=mock_client)
        input_data = KeyframeInput(scenario=sample_scenario, storyboard=sample_storyboard, assets=sample_assets)
        result = await engine.execute(input_data, tmp_path)

        assert isinstance(result, AssetSet)
        assert len(result.keyframes) == 4


class TestKeyframeEnginePersistence:
    """GeminiKeyframeEngine の永続化テスト."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        """save_output → load_output のラウンドトリップ."""
        engine = GeminiKeyframeEngine()

        assets = AssetSet(
            characters=[
                CharacterAsset(
                    character_name="Aoi",
                    front_view=Path("assets/character/front.png"),
                    identity_block="Young adult female",
                )
            ],
            keyframes=[
                KeyframeAsset(
                    scene_number=1,
                    image_path=Path("assets/keyframes/scene_01_cut_01.png"),
                    prompt="flash generated prompt",
                    cut_id="scene_01_cut_01",
                    generation_method="gemini",
                ),
                KeyframeAsset(
                    scene_number=2,
                    image_path=Path("assets/keyframes/scene_02_cut_01.png"),
                    prompt="flash generated prompt 2",
                    cut_id="scene_02_cut_01",
                    generation_method="gemini",
                ),
            ],
        )

        engine.save_output(tmp_path, assets)
        loaded = engine.load_output(tmp_path)

        assert len(loaded.keyframes) == 2
        assert loaded.keyframes[0].scene_number == 1
        assert loaded.keyframes[0].cut_id == "scene_01_cut_01"
        assert loaded.keyframes[0].generation_method == "gemini"
        assert loaded.keyframes[0].image_path == Path("assets/keyframes/scene_01_cut_01.png")
        assert loaded.characters[0].character_name == "Aoi"
        assert loaded.characters[0].identity_block == "Young adult female"

    def test_load_output_ファイル未存在_FileNotFoundError(self, tmp_path: Path) -> None:
        """保存ファイルがない場合エラー."""
        engine = GeminiKeyframeEngine()

        with pytest.raises(FileNotFoundError, match="AssetSet"):
            engine.load_output(tmp_path)
