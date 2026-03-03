"""keyframe/prompt.py のテスト."""

from daily_routine.keyframe.prompt import (
    ReferenceInfo,
    _build_image_description,
    _build_reference_instructions,
    build_flash_meta_prompt,
    build_generation_prompt,
)


class TestReferenceInfo:
    """ReferenceInfo のテスト."""

    def test_create(self) -> None:
        info = ReferenceInfo(purpose="wearing", text="マスク", has_image=True)
        assert info.purpose == "wearing"
        assert info.text == "マスク"
        assert info.has_image is True


class TestBuildImageDescription:
    """_build_image_description のテスト."""

    def test_参照なし(self) -> None:
        result = _build_image_description(1, True, [])
        assert "Image 1 shows the character reference." in result
        assert "Image 2 shows the environment reference." in result

    def test_wearing参照_画像あり(self) -> None:
        infos = [ReferenceInfo(purpose="wearing", text="フルフェイスマスク", has_image=True)]
        result = _build_image_description(1, True, infos)
        assert "Image 3 shows an item the character is wearing/putting on: フルフェイスマスク." in result

    def test_general参照_画像あり(self) -> None:
        infos = [ReferenceInfo(purpose="general", text="ラテカップ", has_image=True)]
        result = _build_image_description(1, True, infos)
        assert "Image 3 shows additional reference: ラテカップ." in result

    def test_参照_画像なし_Image番号に含めない(self) -> None:
        infos = [ReferenceInfo(purpose="atmosphere", text="暗い雰囲気", has_image=False)]
        result = _build_image_description(1, True, infos)
        assert "Image 3" not in result

    def test_複数参照_画像あり・なし混在(self) -> None:
        infos = [
            ReferenceInfo(purpose="wearing", text="マスク", has_image=True),
            ReferenceInfo(purpose="atmosphere", text="暗い雰囲気", has_image=False),
            ReferenceInfo(purpose="holding", text="カメラ", has_image=True),
        ]
        result = _build_image_description(1, True, infos)
        assert "Image 3 shows an item the character is wearing/putting on: マスク." in result
        assert "Image 4 shows an item the character is holding: カメラ." in result
        assert "Image 5" not in result

    def test_後方互換_num_reference_images_fallback(self) -> None:
        result = _build_image_description(1, True, [], num_reference_images_fallback=2)
        assert "Image 3 shows additional reference 1." in result
        assert "Image 4 shows additional reference 2." in result

    def test_purpose別テンプレート(self) -> None:
        purposes = {
            "wearing": "wearing/putting on",
            "holding": "holding",
            "atmosphere": "style/atmosphere reference",
            "background": "background object",
            "interaction": "using/interacting with",
            "general": "additional reference",
        }
        for purpose, expected_text in purposes.items():
            infos = [ReferenceInfo(purpose=purpose, text="テスト", has_image=True)]
            result = _build_image_description(1, False, infos)
            assert expected_text in result, f"purpose={purpose} の説明に '{expected_text}' が含まれません: {result}"


class TestBuildReferenceInstructions:
    """_build_reference_instructions のテスト."""

    def test_空リスト(self) -> None:
        assert _build_reference_instructions([]) == ""

    def test_generalのみ_指示なし(self) -> None:
        infos = [ReferenceInfo(purpose="general", text="何か", has_image=True)]
        assert _build_reference_instructions(infos) == ""

    def test_wearing_指示生成(self) -> None:
        infos = [ReferenceInfo(purpose="wearing", text="フルフェイスマスク", has_image=True)]
        result = _build_reference_instructions(infos)
        assert "IMPORTANT reference instructions:" in result
        assert "MUST be actively wearing/putting on 'フルフェイスマスク'" in result

    def test_複数purpose_指示生成(self) -> None:
        infos = [
            ReferenceInfo(purpose="wearing", text="マスク", has_image=True),
            ReferenceInfo(purpose="holding", text="カメラ", has_image=True),
            ReferenceInfo(purpose="general", text="参考", has_image=False),
        ]
        result = _build_reference_instructions(infos)
        assert "wearing/putting on 'マスク'" in result
        assert "holding 'カメラ'" in result
        # general は指示なし
        assert "'参考'" not in result


class TestBuildFlashMetaPrompt:
    """build_flash_meta_prompt のテスト."""

    def test_参照なし(self) -> None:
        result = build_flash_meta_prompt(
            identity_blocks=["Young adult female"],
            pose_instruction="standing",
            num_char_images=1,
            has_env_image=True,
        )
        assert "Image 1 shows the character reference." in result
        assert "Image 2 shows the environment reference." in result
        assert "IMPORTANT reference instructions:" not in result

    def test_wearing参照(self) -> None:
        infos = [ReferenceInfo(purpose="wearing", text="フルフェイスマスク", has_image=True)]
        result = build_flash_meta_prompt(
            identity_blocks=["Young adult female"],
            pose_instruction="マスクを装着中",
            num_char_images=1,
            has_env_image=True,
            reference_infos=infos,
        )
        assert "Image 3 shows an item the character is wearing/putting on: フルフェイスマスク." in result
        assert "IMPORTANT reference instructions:" in result
        assert "MUST be actively wearing/putting on 'フルフェイスマスク'" in result

    def test_general参照_指示なし(self) -> None:
        infos = [ReferenceInfo(purpose="general", text="参考画像", has_image=True)]
        result = build_flash_meta_prompt(
            identity_blocks=["Young adult female"],
            pose_instruction="standing",
            num_char_images=1,
            has_env_image=True,
            reference_infos=infos,
        )
        assert "Image 3 shows additional reference: 参考画像." in result
        assert "IMPORTANT reference instructions:" not in result

    def test_後方互換_num_reference_images(self) -> None:
        result = build_flash_meta_prompt(
            identity_blocks=["Young adult female"],
            pose_instruction="standing",
            num_char_images=1,
            has_env_image=True,
            num_reference_images=1,
        )
        assert "Image 3 shows additional reference 1." in result

    def test_複数参照(self) -> None:
        infos = [
            ReferenceInfo(purpose="wearing", text="マスク", has_image=True),
            ReferenceInfo(purpose="atmosphere", text="暗い雰囲気", has_image=False),
        ]
        result = build_flash_meta_prompt(
            identity_blocks=["Young adult female"],
            pose_instruction="マスク装着",
            num_char_images=1,
            has_env_image=True,
            reference_infos=infos,
        )
        assert "wearing/putting on: マスク" in result
        assert "IMPORTANT reference instructions:" in result
        assert "'マスク'" in result
        assert "'暗い雰囲気'" in result


class TestBuildGenerationPrompt:
    """build_generation_prompt のテスト."""

    def test_参照なし(self) -> None:
        result = build_generation_prompt(
            flash_prompt="A scene",
            num_char_images=1,
            has_env_image=True,
        )
        assert "Image 1 shows the character reference." in result
        assert "Single person only, solo" in result

    def test_wearing参照_Image説明に反映(self) -> None:
        infos = [ReferenceInfo(purpose="wearing", text="マスク", has_image=True)]
        result = build_generation_prompt(
            flash_prompt="A scene",
            num_char_images=1,
            has_env_image=True,
            reference_infos=infos,
        )
        assert "wearing/putting on: マスク" in result

    def test_後方互換_num_reference_images(self) -> None:
        result = build_generation_prompt(
            flash_prompt="A scene",
            num_char_images=1,
            has_env_image=True,
            num_reference_images=1,
        )
        assert "Image 3 shows additional reference 1." in result
