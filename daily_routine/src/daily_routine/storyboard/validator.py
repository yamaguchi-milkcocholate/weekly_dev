"""生成された Storyboard のバリデーション."""

import re

from daily_routine.schemas.storyboard import Storyboard


class StoryboardValidationError(Exception):
    """Storyboard バリデーションエラー."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Storyboard バリデーションエラー: {errors}")


_CUT_ID_PATTERN = re.compile(r"^scene_\d{2}_cut_\d{2}$")


class StoryboardValidator:
    """生成された Storyboard のバリデーション."""

    def validate(self, storyboard: Storyboard) -> None:
        """Storyboard の論理的整合性を検証する.

        検証項目:
        1. 全体カット数が 10〜40
        2. 各カットの尺が 2〜5 秒（整数）
        3. シーン内カット合計 = シーンの scene_duration_sec
        4. 全カット合計 = total_duration_sec
        5. keyframe_prompt が空でないこと
        6. cut_id が scene_{NN}_cut_{NN} 形式
        7. motion_prompt が英語であること（簡易チェック）
        8. keyframe_prompt に @char タグが含まれること
        9. transition が有効な値であること（Pydantic で保証）
        10. action_description に @char タグが含まれないこと
        11. シーン間の最初のカットに cross_fade が設定されていること

        Args:
            storyboard: 検証対象の Storyboard

        Raises:
            StoryboardValidationError: バリデーションエラーがある場合
        """
        errors: list[str] = []

        all_cuts = [cut for scene in storyboard.scenes for cut in scene.cuts]

        # 1. 全体カット数が 10〜40
        total_cuts = len(all_cuts)
        if not (10 <= total_cuts <= 40):
            errors.append(f"全体カット数が {total_cuts} です。10〜40 の範囲内にしてください")

        # 2. 各カットの尺が 2〜5 秒（整数）
        for cut in all_cuts:
            if cut.duration_sec != int(cut.duration_sec):
                errors.append(f"{cut.cut_id} の duration_sec が {cut.duration_sec} です。整数にしてください")
            if not (2 <= cut.duration_sec <= 5):
                errors.append(f"{cut.cut_id} の duration_sec が {cut.duration_sec} です。2〜5 秒にしてください")

        # 3. シーン内カット合計 = シーンの scene_duration_sec
        for scene in storyboard.scenes:
            cuts_total = sum(c.duration_sec for c in scene.cuts)
            if abs(cuts_total - scene.scene_duration_sec) > 0.01:
                errors.append(
                    f"シーン {scene.scene_number} のカット合計 ({cuts_total}) と"
                    f" scene_duration_sec ({scene.scene_duration_sec}) が一致しません"
                )

        # 4. 全カット合計 = total_duration_sec
        all_cuts_total = sum(c.duration_sec for c in all_cuts)
        if abs(all_cuts_total - storyboard.total_duration_sec) > 0.01:
            errors.append(
                f"全カット合計 ({all_cuts_total}) と"
                f" total_duration_sec ({storyboard.total_duration_sec}) が一致しません"
            )

        # 5. keyframe_prompt が空でないこと
        for cut in all_cuts:
            if not cut.keyframe_prompt.strip():
                errors.append(f"{cut.cut_id} の keyframe_prompt が空です")

        # 6. cut_id が scene_{NN}_cut_{NN} 形式
        for cut in all_cuts:
            if not _CUT_ID_PATTERN.match(cut.cut_id):
                errors.append(f"{cut.cut_id} が scene_NN_cut_NN 形式ではありません")

        # 7. motion_prompt が英語であること（日本語文字を含まないか簡易チェック）
        for cut in all_cuts:
            if re.search(r"[\u3040-\u30ff\u4e00-\u9fff]", cut.motion_prompt):
                errors.append(f"{cut.cut_id} の motion_prompt に日本語が含まれています。英語で記述してください")

        # 8. keyframe_prompt の @char タグチェック（has_character に応じた条件付き）
        for cut in all_cuts:
            if cut.has_character and "@char" not in cut.keyframe_prompt:
                errors.append(f"{cut.cut_id} の keyframe_prompt に @char タグが含まれていません（has_character=true）")
            if not cut.has_character and "@char" in cut.keyframe_prompt:
                errors.append(f"{cut.cut_id} の keyframe_prompt に @char タグが含まれています（has_character=false）")

        # 10. action_description に @char タグが含まれないこと
        for cut in all_cuts:
            if "@char" in cut.action_description:
                errors.append(
                    f"{cut.cut_id} の action_description に @char タグが含まれています。"
                    "キャラクター名（日本語名）を使用してください"
                )

        # 11. シーン間の最初のカットに cross_fade が設定されていること
        for scene in storyboard.scenes:
            if scene.scene_number == 1:
                continue
            first_cut = scene.cuts[0] if scene.cuts else None
            if first_cut and first_cut.transition != "cross_fade":
                errors.append(
                    f"{first_cut.cut_id} はシーン {scene.scene_number} の最初のカットです。"
                    f"トランジションを cross_fade にしてください（現在: {first_cut.transition}）"
                )

        if errors:
            raise StoryboardValidationError(errors)
