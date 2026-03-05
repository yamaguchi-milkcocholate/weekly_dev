"""keyframe/engine.py のテスト."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from daily_routine.keyframe.engine import GeminiKeyframeEngine
from daily_routine.schemas.asset import AssetSet, CharacterAsset, EnvironmentAsset
from daily_routine.schemas.keyframe_mapping import (
    KeyframeMapping,
    ReferenceComponent,
    ReferencePurpose,
    SceneKeyframeSpec,
)
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, Scenario, SceneSpec
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)


def _make_scenario() -> Scenario:
    return Scenario(
        title="テスト動画",
        total_duration_sec=6.0,
        characters=[
            CharacterSpec(
                name="花子",
                appearance="20代女性",
                outfit="白ブラウス",
                reference_prompt="A young Japanese woman",
            )
        ],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=3.0,
                situation="部屋にいる",
                camera_work=CameraWork(type="close-up", description="クローズアップ"),
                caption_text="テスト",
                image_prompt="A room",
            ),
            SceneSpec(
                scene_number=2,
                duration_sec=3.0,
                situation="カフェにいる",
                camera_work=CameraWork(type="wide", description="ワイド"),
                caption_text="テスト2",
                image_prompt="A cafe",
            ),
        ],
        bgm_direction="明るいポップス",
    )


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
                        pose_instruction="standing calmly",
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
                identity_block="Young adult female, dark hair",
            ),
        ],
    )


def _make_mock_client() -> AsyncMock:
    client = AsyncMock()
    client.analyze_scene.return_value = "A woman standing in a room"

    async def generate_keyframe_side_effect(
        char_images, env_image, flash_prompt, reference_images=None, reference_infos=None, output_path=None
    ):
        if output_path:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"generated_image")
        return output_path

    client.generate_keyframe.side_effect = generate_keyframe_side_effect
    return client


def _make_engine(client: AsyncMock) -> GeminiKeyframeEngine:
    """テスト用にエンジンインスタンスを作成する."""
    engine = GeminiKeyframeEngine(api_key="")
    engine._client = client
    return engine


class TestGenerateKeyframes:
    """generate_keyframes のテスト."""

    @pytest.mark.asyncio
    async def test_マッピングなし_2カット生成(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        result = await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        assert len(result.keyframes) == 2
        assert client.analyze_scene.call_count == 2
        assert client.generate_keyframe.call_count == 2
        assert result.keyframes[0].cut_id == "scene_01_cut_01"
        assert result.keyframes[0].generation_method == "gemini"
        assert result.keyframes[1].cut_id == "scene_02_cut_01"

    @pytest.mark.asyncio
    async def test_マッピングあり_reference_textが渡される(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=1,
                    reference_text="Warm room atmosphere",
                ),
            ]
        )

        result = await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        assert len(result.keyframes) == 2
        # scene 1: reference_infos が渡される
        call1 = client.analyze_scene.call_args_list[0]
        infos1 = call1.kwargs["reference_infos"]
        assert len(infos1) == 1
        assert infos1[0].text == "Warm room atmosphere"
        assert infos1[0].purpose == "general"
        assert infos1[0].has_image is False
        # scene 2: reference_infos は空リスト
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["reference_infos"] == []

    @pytest.mark.asyncio
    async def test_environments優先_未登録シーンはNone(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        env_image = tmp_path / "env_1.png"
        env_image.write_bytes(b"env_image")

        assets = _make_assets(tmp_path)
        assets = assets.model_copy(
            update={
                "environments": [
                    EnvironmentAsset(
                        scene_number=1,
                        image_path=env_image,
                    ),
                ],
            }
        )

        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        # scene 1: environments の画像が渡される
        call1 = client.analyze_scene.call_args_list[0]
        assert call1.kwargs["env_image"] == env_image

        # scene 2: 該当する environments がないので None
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["env_image"] is None

    @pytest.mark.asyncio
    async def test_identity_blocksが渡される(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        for call in client.analyze_scene.call_args_list:
            assert call.kwargs["identity_blocks"] == ["Young adult female, dark hair"]

    @pytest.mark.asyncio
    async def test_pose_instructionが渡される(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        # scene 1 cut 1: pose_instruction = "standing calmly"
        call1 = client.analyze_scene.call_args_list[0]
        assert call1.kwargs["pose_instruction"] == "standing calmly"

        # scene 2 cut 1: pose_instruction = "" (未設定)
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["pose_instruction"] == ""

    @pytest.mark.asyncio
    async def test_マッピングのcharacterでキャラクター切替(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        front_1 = tmp_path / "front_1.png"
        front_1.write_bytes(b"char1")
        front_2 = tmp_path / "front_2.png"
        front_2.write_bytes(b"char2")
        assets = AssetSet(
            characters=[
                CharacterAsset(
                    character_name="花子",
                    front_view=front_1,
                    identity_block="Hanako identity",
                ),
                CharacterAsset(
                    character_name="太郎",
                    front_view=front_2,
                    identity_block="Taro identity",
                ),
            ],
        )
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(scene_number=1, character="花子"),
                SceneKeyframeSpec(scene_number=2, character="太郎"),
            ]
        )

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        # scene 1: 花子のキャラ画像と identity_blocks
        call1 = client.analyze_scene.call_args_list[0]
        assert call1.kwargs["char_images"] == [front_1]
        assert call1.kwargs["identity_blocks"] == ["Hanako identity"]

        # scene 2: 太郎のキャラ画像と identity_blocks
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["char_images"] == [front_2]
        assert call2.kwargs["identity_blocks"] == ["Taro identity"]

    @pytest.mark.asyncio
    async def test_マッピングのvariant_idでキャラクターバリアント切替(self, tmp_path: Path) -> None:
        """variant_id を指定して同一キャラクターの衣装バリアントを切替."""
        output_dir = tmp_path / "keyframes"
        front_pajama = tmp_path / "front_pajama.png"
        front_pajama.write_bytes(b"pajama")
        front_suit = tmp_path / "front_suit.png"
        front_suit.write_bytes(b"suit")
        assets = AssetSet(
            characters=[
                CharacterAsset(
                    character_name="花子",
                    variant_id="pajama",
                    front_view=front_pajama,
                    identity_block="Hanako pajama",
                ),
                CharacterAsset(
                    character_name="花子",
                    variant_id="suit",
                    front_view=front_suit,
                    identity_block="Hanako suit",
                ),
            ],
        )
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(scene_number=1, character="花子", variant_id="pajama"),
                SceneKeyframeSpec(scene_number=2, character="花子", variant_id="suit"),
            ]
        )

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        # scene 1: pajama バリアント
        call1 = client.analyze_scene.call_args_list[0]
        assert call1.kwargs["char_images"] == [front_pajama]
        assert call1.kwargs["identity_blocks"] == ["Hanako pajama"]

        # scene 2: suit バリアント
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["char_images"] == [front_suit]
        assert call2.kwargs["identity_blocks"] == ["Hanako suit"]

    @pytest.mark.asyncio
    async def test_variant_id未指定_名前のみで最初のバリアント(self, tmp_path: Path) -> None:
        """variant_id 未指定時は character_name で最初に見つかったバリアントを使用."""
        output_dir = tmp_path / "keyframes"
        front_pajama = tmp_path / "front_pajama.png"
        front_pajama.write_bytes(b"pajama")
        front_suit = tmp_path / "front_suit.png"
        front_suit.write_bytes(b"suit")
        assets = AssetSet(
            characters=[
                CharacterAsset(
                    character_name="花子",
                    variant_id="pajama",
                    front_view=front_pajama,
                    identity_block="Hanako pajama",
                ),
                CharacterAsset(
                    character_name="花子",
                    variant_id="suit",
                    front_view=front_suit,
                    identity_block="Hanako suit",
                ),
            ],
        )
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        # variant_id を指定しない
        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(scene_number=1, character="花子"),
            ]
        )

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        # scene 1: 最初のバリアント（pajama）が使われる
        call1 = client.analyze_scene.call_args_list[0]
        assert call1.kwargs["char_images"] == [front_pajama]

    @pytest.mark.asyncio
    async def test_マッピングのenvironmentで環境切替(self, tmp_path: Path) -> None:
        output_dir = tmp_path / "keyframes"
        env_a = tmp_path / "env_a.png"
        env_a.write_bytes(b"env_a")
        env_b = tmp_path / "env_b.png"
        env_b.write_bytes(b"env_b")

        assets = _make_assets(tmp_path)
        assets = assets.model_copy(
            update={
                "environments": [
                    EnvironmentAsset(
                        scene_number=1,
                        description="オフィス",
                        image_path=env_a,
                    ),
                    EnvironmentAsset(
                        scene_number=2,
                        description="カフェ",
                        image_path=env_b,
                    ),
                ],
            }
        )

        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        # scene 2 にオフィス環境を上書き指定
        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(scene_number=2, environment="オフィス"),
            ]
        )

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        # scene 1: マッピングなし → scene_number=1 の環境（env_a）
        call1 = client.analyze_scene.call_args_list[0]
        assert call1.kwargs["env_image"] == env_a

        # scene 2: マッピングで "オフィス" を指定 → env_a（description一致）
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["env_image"] == env_a

    @pytest.mark.asyncio
    async def test_has_character_false_char_images空(self, tmp_path: Path) -> None:
        """has_character=False のカットでは char_images=[], identity_blocks=[] が渡される."""
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)
        scenario = _make_scenario()
        # scene 2 のカットを has_character=False に
        storyboard = Storyboard(
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
                            has_character=True,
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
                            action_description="コーヒー豆のクローズアップ",
                            motion_prompt="Steam rises slowly",
                            keyframe_prompt="Coffee beans on wooden table",
                            transition=Transition.CUT,
                            has_character=False,
                        ),
                    ],
                ),
            ],
        )
        client = _make_mock_client()
        engine = _make_engine(client)

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        # scene 1: has_character=True → キャラクター画像あり
        call1 = client.analyze_scene.call_args_list[0]
        assert len(call1.kwargs["char_images"]) == 1
        assert len(call1.kwargs["identity_blocks"]) == 1

        # scene 2: has_character=False → キャラクター画像なし
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["char_images"] == []
        assert call2.kwargs["identity_blocks"] == []

    @pytest.mark.asyncio
    async def test_全カットhas_character_false_キャラクターなし_エラーなし(self, tmp_path: Path) -> None:
        """全カットが has_character=False + assets.characters=[] でもエラーにならない."""
        output_dir = tmp_path / "keyframes"
        assets = AssetSet(characters=[])
        scenario = _make_scenario()
        storyboard = Storyboard(
            title="テスト動画",
            total_duration_sec=3.0,
            total_cuts=1,
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
                            motion_intensity=MotionIntensity.STATIC,
                            camera_work="static",
                            action_description="コーヒー豆のクローズアップ",
                            motion_prompt="Steam rises slowly",
                            keyframe_prompt="Coffee beans on wooden table",
                            transition=Transition.CUT,
                            has_character=False,
                        ),
                    ],
                ),
            ],
        )
        client = _make_mock_client()
        engine = _make_engine(client)

        result = await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        assert len(result.keyframes) == 1
        call1 = client.analyze_scene.call_args_list[0]
        assert call1.kwargs["char_images"] == []
        assert call1.kwargs["identity_blocks"] == []

    @pytest.mark.asyncio
    async def test_purpose付き参照がreference_infosに伝搬(self, tmp_path: Path) -> None:
        """purpose を指定した ReferenceComponent が reference_infos に正しく変換される."""
        output_dir = tmp_path / "keyframes"
        ref_img = tmp_path / "mask.png"
        ref_img.write_bytes(b"mask_image")
        assets = _make_assets(tmp_path)
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=1,
                    components=[
                        ReferenceComponent(image=ref_img, text="フルフェイスマスク", purpose=ReferencePurpose.WEARING),
                        ReferenceComponent(text="暗い雰囲気", purpose=ReferencePurpose.ATMOSPHERE),
                    ],
                ),
            ]
        )

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        call1 = client.analyze_scene.call_args_list[0]
        infos = call1.kwargs["reference_infos"]
        assert len(infos) == 2
        assert infos[0].purpose == "wearing"
        assert infos[0].text == "フルフェイスマスク"
        assert infos[0].has_image is True
        assert infos[1].purpose == "atmosphere"
        assert infos[1].text == "暗い雰囲気"
        assert infos[1].has_image is False

    @pytest.mark.asyncio
    async def test_has_character_false_マッピングにCharacterComponent指定でもスキップ(self, tmp_path: Path) -> None:
        """keyframe_mapping に CharacterComponent が含まれていても has_character=False なら char_images が空."""
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)
        scenario = _make_scenario()
        # scene 2 を has_character=False に
        storyboard = Storyboard(
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
                            has_character=True,
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
                            motion_intensity=MotionIntensity.STATIC,
                            camera_work="static",
                            action_description="コーヒー豆のクローズアップ",
                            motion_prompt="Steam rises slowly",
                            keyframe_prompt="Coffee beans on wooden table",
                            transition=Transition.CUT,
                            has_character=False,
                        ),
                    ],
                ),
            ],
        )
        client = _make_mock_client()
        engine = _make_engine(client)

        from daily_routine.schemas.keyframe_mapping import CharacterComponent

        # マッピングに CharacterComponent を明示的に含める
        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=2,
                    components=[
                        CharacterComponent(character="花子"),
                    ],
                ),
            ]
        )

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        # scene 1: has_character=True → キャラクター画像あり
        call1 = client.analyze_scene.call_args_list[0]
        assert len(call1.kwargs["char_images"]) == 1

        # scene 2: has_character=False → マッピングに CharacterComponent があってもスキップ
        call2 = client.analyze_scene.call_args_list[1]
        assert call2.kwargs["char_images"] == []
        assert call2.kwargs["identity_blocks"] == []


class TestItemSupport:
    """アイテム単位実行のテスト."""

    def test_supports_items_True(self) -> None:
        engine = GeminiKeyframeEngine(api_key="")
        assert engine.supports_items is True

    def test_list_items_全カットID(self, tmp_path: Path) -> None:
        from daily_routine.schemas.pipeline_io import KeyframeInput

        storyboard = _make_storyboard()
        scenario = _make_scenario()
        assets = _make_assets(tmp_path)
        engine = GeminiKeyframeEngine(api_key="")

        input_data = KeyframeInput(scenario=scenario, storyboard=storyboard, assets=assets)
        items = engine.list_items(input_data, tmp_path)

        assert items == ["scene_01_cut_01", "scene_02_cut_01"]

    @pytest.mark.asyncio
    async def test_execute_item_1カット生成(self, tmp_path: Path) -> None:
        from daily_routine.schemas.pipeline_io import KeyframeInput

        storyboard = _make_storyboard()
        scenario = _make_scenario()
        assets = _make_assets(tmp_path)
        client = _make_mock_client()
        engine = _make_engine(client)

        input_data = KeyframeInput(scenario=scenario, storyboard=storyboard, assets=assets)
        await engine.execute_item("scene_01_cut_01", input_data, tmp_path)

        result = engine.load_output(tmp_path)
        assert len(result.keyframes) == 1
        assert result.keyframes[0].cut_id == "scene_01_cut_01"

    @pytest.mark.asyncio
    async def test_execute_item_差分追記(self, tmp_path: Path) -> None:
        """2回目のexecute_itemで追記されること."""
        from daily_routine.schemas.pipeline_io import KeyframeInput

        storyboard = _make_storyboard()
        scenario = _make_scenario()
        assets = _make_assets(tmp_path)
        client = _make_mock_client()
        engine = _make_engine(client)

        input_data = KeyframeInput(scenario=scenario, storyboard=storyboard, assets=assets)
        await engine.execute_item("scene_01_cut_01", input_data, tmp_path)
        await engine.execute_item("scene_02_cut_01", input_data, tmp_path)

        result = engine.load_output(tmp_path)
        assert len(result.keyframes) == 2
        assert result.keyframes[0].cut_id == "scene_01_cut_01"
        assert result.keyframes[1].cut_id == "scene_02_cut_01"


def _make_style_continuity_storyboard() -> Storyboard:
    """スタイル連続性テスト用: 4カット / 3シーン / 2環境."""
    return Storyboard(
        title="スタイル連続性テスト",
        total_duration_sec=12.0,
        total_cuts=4,
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
                        action_description="朝の部屋",
                        motion_prompt="@char wakes up",
                        keyframe_prompt="@char in bedroom",
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
                        action_description="カフェに到着",
                        motion_prompt="@char walks in",
                        keyframe_prompt="@char at cafe",
                        transition=Transition.CUT,
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=3,
                scene_duration_sec=6.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_03_cut_01",
                        scene_number=3,
                        cut_number=1,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="close-up",
                        action_description="部屋に戻る",
                        motion_prompt="@char sits down",
                        keyframe_prompt="@char in bedroom evening",
                        transition=Transition.CUT,
                    ),
                    CutSpec(
                        cut_id="scene_03_cut_02",
                        scene_number=3,
                        cut_number=2,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="slow zoom-out",
                        action_description="部屋でリラックス",
                        motion_prompt="@char relaxes",
                        keyframe_prompt="@char relaxing in bedroom",
                        transition=Transition.CUT,
                    ),
                ],
            ),
        ],
    )


def _make_style_continuity_assets(tmp_path: Path) -> tuple[AssetSet, Path, Path]:
    """スタイル連続性テスト用アセット（2環境: env_a, env_b）を返す."""
    front_view = tmp_path / "front.png"
    front_view.write_bytes(b"fake_image")
    env_a = tmp_path / "env_a.png"
    env_a.write_bytes(b"env_a")
    env_b = tmp_path / "env_b.png"
    env_b.write_bytes(b"env_b")

    assets = AssetSet(
        characters=[
            CharacterAsset(
                character_name="花子",
                front_view=front_view,
                identity_block="Young adult female",
            ),
        ],
        environments=[
            EnvironmentAsset(scene_number=1, image_path=env_a, description="部屋"),
            EnvironmentAsset(scene_number=2, image_path=env_b, description="カフェ"),
            EnvironmentAsset(scene_number=3, image_path=env_a, description="部屋"),
        ],
    )
    return assets, env_a, env_b


class TestStyleContinuity:
    """スタイル連続性のテスト."""

    @pytest.mark.asyncio
    async def test_同一環境の連続カットに前カット参照が注入される(self, tmp_path: Path) -> None:
        """cut 1,2 は参照なし、cut 3,4 に atmosphere ref が注入される."""
        output_dir = tmp_path / "keyframes"
        assets, env_a, env_b = _make_style_continuity_assets(tmp_path)
        storyboard = _make_style_continuity_storyboard()
        scenario = _make_scenario()
        client = _make_mock_client()
        engine = _make_engine(client)

        # scene 3 の environment は "部屋" → env_a にマッピング
        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(scene_number=3, environment="部屋"),
            ]
        )

        result = await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
            keyframe_mapping=keyframe_mapping,
        )

        assert len(result.keyframes) == 4

        # cut 1 (scene 1, env_a): アンカー → 参照なし
        call1 = client.analyze_scene.call_args_list[0]
        assert all(info.purpose != "atmosphere" or info.text != _atmosphere_text()
                   for info in call1.kwargs["reference_infos"])

        # cut 2 (scene 2, env_b): 別環境アンカー → 参照なし
        call2 = client.analyze_scene.call_args_list[1]
        assert all(info.purpose != "atmosphere" or info.text != _atmosphere_text()
                   for info in call2.kwargs["reference_infos"])

        # cut 3 (scene 3, env_a): scene 1 の env_a を参照
        call3 = client.analyze_scene.call_args_list[2]
        atmo_refs3 = [info for info in call3.kwargs["reference_infos"] if info.text == _atmosphere_text()]
        assert len(atmo_refs3) == 1
        assert atmo_refs3[0].purpose == "atmosphere"
        assert atmo_refs3[0].has_image is True

        # cut 4 (scene 3 cut 2, env_a): scene 3 cut 1 を参照
        call4 = client.analyze_scene.call_args_list[3]
        atmo_refs4 = [info for info in call4.kwargs["reference_infos"] if info.text == _atmosphere_text()]
        assert len(atmo_refs4) == 1

    @pytest.mark.asyncio
    async def test_異なる環境のカットには前カット参照が注入されない(self, tmp_path: Path) -> None:
        """env_a と env_b 間でクロス参照が発生しない."""
        output_dir = tmp_path / "keyframes"
        assets, env_a, env_b = _make_style_continuity_assets(tmp_path)
        # 2カットのみ: scene 1 (env_a), scene 2 (env_b)
        storyboard = Storyboard(
            title="テスト",
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
                            camera_work="zoom-in",
                            action_description="部屋",
                            motion_prompt="@char moves",
                            keyframe_prompt="@char in room",
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
                            camera_work="pan",
                            action_description="カフェ",
                            motion_prompt="@char walks",
                            keyframe_prompt="@char at cafe",
                            transition=Transition.CUT,
                        ),
                    ],
                ),
            ],
        )
        scenario = _make_scenario()
        client = _make_mock_client()
        engine = _make_engine(client)

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        # どちらのカットにも atmosphere スタイル連続性参照がない
        for call in client.analyze_scene.call_args_list:
            assert all(info.text != _atmosphere_text() for info in call.kwargs["reference_infos"])

    @pytest.mark.asyncio
    async def test_環境なしカットにはスタイル連続性スキップ(self, tmp_path: Path) -> None:
        """env_image=None のカットはグルーピング対象外."""
        output_dir = tmp_path / "keyframes"
        assets = _make_assets(tmp_path)  # environments 未設定
        scenario = _make_scenario()
        storyboard = _make_storyboard()
        client = _make_mock_client()
        engine = _make_engine(client)

        await engine.generate_keyframes(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            output_dir=output_dir,
        )

        # 環境なし → スタイル連続性参照は注入されない
        for call in client.analyze_scene.call_args_list:
            assert all(info.text != _atmosphere_text() for info in call.kwargs["reference_infos"])

    @pytest.mark.asyncio
    async def test_execute_item_前カット参照が注入される(self, tmp_path: Path) -> None:
        """既存キーフレームがある状態で execute_item が前カット参照を注入する."""
        from daily_routine.schemas.asset import KeyframeAsset
        from daily_routine.schemas.pipeline_io import KeyframeInput

        assets, env_a, env_b = _make_style_continuity_assets(tmp_path)
        storyboard = _make_style_continuity_storyboard()
        scenario = _make_scenario()
        client = _make_mock_client()
        engine = _make_engine(client)

        keyframe_mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(scene_number=3, environment="部屋"),
            ]
        )

        # scene_01_cut_01 の既存キーフレームを作成
        kf_dir = tmp_path / "assets" / "keyframes"
        kf_dir.mkdir(parents=True, exist_ok=True)
        existing_kf = kf_dir / "scene_01_cut_01.png"
        existing_kf.write_bytes(b"existing_keyframe")

        assets_with_kf = assets.model_copy(
            update={
                "keyframes": [
                    KeyframeAsset(
                        scene_number=1,
                        image_path=existing_kf,
                        prompt="existing prompt",
                        cut_id="scene_01_cut_01",
                        generation_method="gemini",
                    ),
                ],
            }
        )

        # AssetSet を保存（execute_item が load_output で読み込む）
        engine.save_output(tmp_path, assets_with_kf)

        input_data = KeyframeInput(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            keyframe_mapping=keyframe_mapping,
        )

        # scene_03_cut_01 を生成: scene 1 (env_a) のキーフレームが参照される
        await engine.execute_item("scene_03_cut_01", input_data, tmp_path)

        # analyze_scene に atmosphere 参照が渡されている
        call = client.analyze_scene.call_args_list[0]
        atmo_refs = [info for info in call.kwargs["reference_infos"] if info.text == _atmosphere_text()]
        assert len(atmo_refs) == 1
        assert existing_kf in call.kwargs["reference_images"]


def _atmosphere_text() -> str:
    """スタイル連続性参照のテキストを返す（テストのアサーション用）."""
    from daily_routine.keyframe.engine import _STYLE_CONTINUITY_REF

    return _STYLE_CONTINUITY_REF.text
