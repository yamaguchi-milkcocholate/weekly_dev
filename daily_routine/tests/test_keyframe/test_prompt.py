"""keyframe/prompt.py のテスト."""

from daily_routine.keyframe.prompt import build_flash_meta_prompt, build_generation_prompt


class TestBuildFlashMetaPromptNoCharacter:
    """identity_blocks が空の場合の build_flash_meta_prompt テスト."""

    def test_identity_blocks空_characterを含まない(self) -> None:
        result = build_flash_meta_prompt(
            identity_blocks=[],
            pose_instruction="",
            num_char_images=0,
            has_env_image=True,
        )
        assert "character" not in result.lower()
        assert "composes these elements" in result

    def test_identity_blocks空_pose指示を含まない(self) -> None:
        result = build_flash_meta_prompt(
            identity_blocks=[],
            pose_instruction="",
            num_char_images=0,
            has_env_image=True,
        )
        assert "character's pose" not in result

    def test_identity_blocksあり_characterを含む(self) -> None:
        result = build_flash_meta_prompt(
            identity_blocks=["Young woman, dark hair"],
            pose_instruction="standing",
            num_char_images=1,
            has_env_image=True,
        )
        assert "character" in result.lower()
        assert "Young woman, dark hair" in result


class TestBuildGenerationPromptNoCharacter:
    """num_char_images == 0 の場合の build_generation_prompt テスト."""

    def test_num_char_images_0_no_people(self) -> None:
        result = build_generation_prompt(
            flash_prompt="Coffee beans on a table",
            num_char_images=0,
            has_env_image=True,
        )
        assert "No people" in result

    def test_num_char_images_1_solo(self) -> None:
        result = build_generation_prompt(
            flash_prompt="Woman in a room",
            num_char_images=1,
            has_env_image=True,
        )
        assert "Single person only" in result

    def test_num_char_images_2_no_solo(self) -> None:
        result = build_generation_prompt(
            flash_prompt="Two people in a room",
            num_char_images=2,
            has_env_image=True,
        )
        assert "Single person" not in result
        assert "No people" not in result
        assert "Photo-realistic" in result
