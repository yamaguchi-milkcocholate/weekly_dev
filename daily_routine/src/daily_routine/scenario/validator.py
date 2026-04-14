"""生成されたシナリオのバリデーション."""

from daily_routine.schemas.scenario import Scenario


class ScenarioValidationError(Exception):
    """シナリオバリデーションエラー."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"シナリオバリデーションエラー: {errors}")


class ScenarioValidator:
    """生成されたシナリオのバリデーション."""

    def validate(
        self,
        scenario: Scenario,
        duration_range: tuple[int, int],
    ) -> None:
        """シナリオの論理的整合性を検証する.

        検証項目:
        1. total_duration_sec が duration_range 内
        2. scenes が 1 件以上存在
        3. 各シーンの duration_sec > 0
        4. 各シーンの duration_sec 合計と total_duration_sec の差が ±2秒以内
        5. scene_number が 1 始まりの連番
        6. characters が 1 件以上存在

        Args:
            scenario: 検証対象のシナリオ
            duration_range: 動画尺の許容範囲（秒）[min, max]

        Raises:
            ScenarioValidationError: バリデーションエラーがある場合
        """
        errors: list[str] = []

        min_dur, max_dur = duration_range

        # 1. total_duration_sec が duration_range 内
        if not (min_dur <= scenario.total_duration_sec <= max_dur):
            errors.append(
                f"total_duration_sec が {scenario.total_duration_sec} 秒ですが、"
                f"{min_dur}〜{max_dur}秒の範囲内にしてください"
            )

        # 2. scenes が 1 件以上存在
        if len(scenario.scenes) == 0:
            errors.append("scenes が 0 件です。1 件以上のシーンが必要です")

        # 3. 各シーンの duration_sec > 0
        for scene in scenario.scenes:
            if scene.duration_sec <= 0:
                errors.append(
                    f"scene_number {scene.scene_number} の duration_sec が"
                    f" {scene.duration_sec} です。0 より大きい値にしてください"
                )

        # 4. duration_sec 合計と total_duration_sec の差が ±2秒以内
        if scenario.scenes:
            total_scenes_dur = sum(s.duration_sec for s in scenario.scenes)
            diff = abs(total_scenes_dur - scenario.total_duration_sec)
            if diff > 2.0:
                errors.append(
                    f"シーンの duration_sec 合計 ({total_scenes_dur}) と"
                    f" total_duration_sec ({scenario.total_duration_sec}) の差が"
                    f" {diff:.1f}秒です。±2秒以内にしてください"
                )

        # 5. scene_number が 1 始まりの連番
        if scenario.scenes:
            expected = list(range(1, len(scenario.scenes) + 1))
            actual = [s.scene_number for s in scenario.scenes]
            if actual != expected:
                errors.append(f"scene_number が {actual} ですが、1始まりの連番 {expected} にしてください")

        # 6. characters が 1 件以上存在
        if len(scenario.characters) == 0:
            errors.append("characters が 0 件です。1 件以上のキャラクターが必要です")

        if errors:
            raise ScenarioValidationError(errors)
