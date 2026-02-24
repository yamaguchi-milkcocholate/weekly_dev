"""OpenAI Scenario Engine（ABCの具象実装）."""

import json
import logging
from pathlib import Path

from openai import AsyncOpenAI

from daily_routine.pipeline.base import StepEngine
from daily_routine.scenario.base import ScenarioEngineBase
from daily_routine.scenario.prompt import ScenarioPromptBuilder
from daily_routine.scenario.validator import ScenarioValidationError, ScenarioValidator
from daily_routine.schemas.intelligence import TrendReport
from daily_routine.schemas.scenario import Scenario

logger = logging.getLogger(__name__)

_SCENARIO_FILENAME = "scenario.json"


class OpenAIScenarioEngine(StepEngine[TrendReport, Scenario], ScenarioEngineBase):
    """OpenAI GPT-5 系を使った Scenario Engine 実装.

    StepEngine[TrendReport, Scenario] を実装しパイプラインに統合しつつ、
    ScenarioEngineBase の generate() も実装する。
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gpt-4.1",
        max_retries: int = 2,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._max_retries = max_retries
        self._prompt_builder = ScenarioPromptBuilder()
        self._validator = ScenarioValidator()

    async def execute(self, input_data: TrendReport, project_dir: Path) -> Scenario:
        """パイプラインステップとして実行する."""
        return await self.generate(
            trend_report=input_data,
            output_dir=project_dir,
        )

    async def generate(
        self,
        trend_report: TrendReport,
        output_dir: Path,
        duration_range: tuple[int, int] = (30, 60),
        user_direction: str | None = None,
    ) -> Scenario:
        """TrendReport からシナリオを生成する.

        1. プロンプト構築（Phase A）
        2. OpenAI API に Structured Output で生成リクエスト（Phase B）
        3. バリデーション（Phase C）
        4. バリデーション失敗時は最大 max_retries 回リトライ
        5. output_dir/scenario/scenario.json に保存
        """
        if not self._api_key:
            msg = "OpenAI API キーが設定されていません"
            raise ValueError(msg)

        client = AsyncOpenAI(api_key=self._api_key)

        # Phase A: プロンプト構築
        system_prompt = self._prompt_builder.build_system_prompt(trend_report)
        user_prompt = self._prompt_builder.build_user_prompt(
            keyword=trend_report.keyword,
            duration_range=duration_range,
            user_direction=user_direction,
        )

        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 2):  # 初回 + リトライ回数
            logger.info("シナリオ生成: 試行 %d/%d", attempt, self._max_retries + 1)

            try:
                # Phase B: LLM 生成
                scenario = await self._call_openai(client, messages)

                # Phase C: バリデーション
                self._validator.validate(scenario, duration_range)

                logger.info("シナリオ生成に成功しました: %s", scenario.title)
                return scenario

            except ScenarioValidationError as e:
                last_error = e
                logger.warning(
                    "シナリオバリデーションエラー（試行 %d）: %s",
                    attempt,
                    e.errors,
                )

                if attempt <= self._max_retries:
                    # リトライ: エラーフィードバックをプロンプトに追加
                    retry_prompt = self._prompt_builder.build_retry_prompt(e.errors)
                    messages.append({"role": "assistant", "content": "（前回の生成結果）"})
                    messages.append({"role": "user", "content": retry_prompt})

        # 最大リトライ超過
        msg = f"シナリオ生成が {self._max_retries + 1} 回失敗しました"
        raise RuntimeError(msg) from last_error

    async def _call_openai(
        self,
        client: AsyncOpenAI,
        messages: list[dict[str, str]],
    ) -> Scenario:
        """OpenAI API を呼び出し、Structured Output でシナリオを取得する."""
        response = await client.beta.chat.completions.parse(
            model=self._model_name,
            messages=messages,
            response_format=Scenario,
        )

        parsed = response.choices[0].message.parsed
        if parsed is None:
            refusal = response.choices[0].message.refusal
            msg = f"OpenAI がリクエストを拒否しました: {refusal}"
            raise RuntimeError(msg)

        return parsed

    def load_output(self, project_dir: Path) -> Scenario:
        """永続化済みの Scenario を読み込む."""
        scenario_path = project_dir / "scenario" / _SCENARIO_FILENAME
        if not scenario_path.exists():
            msg = f"Scenarioファイルが見つかりません: {scenario_path}"
            raise FileNotFoundError(msg)
        data = json.loads(scenario_path.read_text(encoding="utf-8"))
        return Scenario.model_validate(data)

    def save_output(self, project_dir: Path, output: Scenario) -> None:
        """Scenario を永続化する."""
        scenario_dir = project_dir / "scenario"
        scenario_dir.mkdir(parents=True, exist_ok=True)

        scenario_path = scenario_dir / _SCENARIO_FILENAME
        scenario_path.write_text(
            output.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Scenario を保存しました: %s", scenario_path)
