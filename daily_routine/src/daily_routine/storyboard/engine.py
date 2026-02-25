"""OpenAI Storyboard Engine（ABCの具象実装）."""

import logging
from pathlib import Path

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.pipeline_io import StoryboardInput
from daily_routine.schemas.scenario import Scenario
from daily_routine.schemas.storyboard import Storyboard
from daily_routine.storyboard.base import StoryboardEngineBase
from daily_routine.storyboard.prompt import StoryboardPromptBuilder
from daily_routine.storyboard.validator import StoryboardValidationError, StoryboardValidator

logger = logging.getLogger(__name__)

_STORYBOARD_FILENAME = "storyboard.json"
_DEFAULT_MODEL = "gpt-5"


class OpenAIStoryboardEngine(StepEngine[StoryboardInput, Storyboard], StoryboardEngineBase):
    """OpenAI GPT-5 系を使った Storyboard Engine 実装.

    LangChain ChatOpenAI + with_structured_output で Storyboard を生成する。
    StepEngine[StoryboardInput, Storyboard] を実装しパイプラインに統合しつつ、
    StoryboardEngineBase の generate() も実装する。
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = _DEFAULT_MODEL,
        max_retries: int = 3,
    ) -> None:
        self._api_key = api_key
        self._model_name = model_name
        self._max_retries = max_retries
        self._prompt_builder = StoryboardPromptBuilder()
        self._validator = StoryboardValidator()

    async def execute(self, input_data: StoryboardInput, project_dir: Path) -> Storyboard:
        """パイプラインステップとして実行する."""
        return await self.generate(
            scenario=input_data.scenario,
            output_dir=project_dir,
        )

    async def generate(
        self,
        scenario: Scenario,
        output_dir: Path,
    ) -> Storyboard:
        """シナリオからカット分解された絵コンテを生成する.

        1. プロンプト構築（Phase A）
        2. LangChain ChatOpenAI + Structured Output で生成（Phase B）
        3. バリデーション（Phase C）
        4. バリデーション失敗時は最大 max_retries 回リトライ
        """
        if not self._api_key:
            msg = "OpenAI API キーが設定されていません"
            raise ValueError(msg)

        llm = ChatOpenAI(
            model=self._model_name,
            api_key=self._api_key,
        )
        structured_llm = llm.with_structured_output(Storyboard)

        # Phase A: プロンプト構築
        system_prompt = self._prompt_builder.build_system_prompt()
        user_prompt = self._prompt_builder.build_user_prompt(scenario)

        messages: list[BaseMessage] = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_prompt),
        ]

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 2):  # 初回 + リトライ回数
            logger.info("Storyboard 生成: 試行 %d/%d", attempt, self._max_retries + 1)

            try:
                # Phase B: LLM 生成
                storyboard = await self._call_llm(structured_llm, messages)

                # Phase C: バリデーション
                self._validator.validate(storyboard)

                logger.info(
                    "Storyboard 生成に成功しました: %d カット",
                    storyboard.total_cuts,
                )
                return storyboard

            except StoryboardValidationError as e:
                last_error = e
                logger.warning(
                    "Storyboard バリデーションエラー（試行 %d）: %s",
                    attempt,
                    e.errors,
                )

                if attempt <= self._max_retries:
                    # リトライ: エラーフィードバックをプロンプトに追加
                    retry_prompt = self._prompt_builder.build_retry_prompt(e.errors)
                    messages.append(AIMessage(content="（前回の生成結果）"))
                    messages.append(HumanMessage(content=retry_prompt))

        # 最大リトライ超過
        msg = f"Storyboard 生成が {self._max_retries + 1} 回失敗しました"
        raise RuntimeError(msg) from last_error

    async def _call_llm(
        self,
        structured_llm: object,
        messages: list[BaseMessage],
    ) -> Storyboard:
        """LangChain Structured Output で Storyboard を取得する."""
        result = await structured_llm.ainvoke(messages)

        if not isinstance(result, Storyboard):
            msg = "LLM が Storyboard を返しませんでした"
            raise RuntimeError(msg)

        return result

    def load_output(self, project_dir: Path) -> Storyboard:
        """永続化済みの Storyboard を読み込む."""
        storyboard_path = project_dir / "storyboard" / _STORYBOARD_FILENAME
        if not storyboard_path.exists():
            msg = f"Storyboard ファイルが見つかりません: {storyboard_path}"
            raise FileNotFoundError(msg)
        return Storyboard.model_validate_json(storyboard_path.read_text(encoding="utf-8"))

    def save_output(self, project_dir: Path, output: Storyboard) -> None:
        """Storyboard を永続化する."""
        storyboard_dir = project_dir / "storyboard"
        storyboard_dir.mkdir(parents=True, exist_ok=True)

        storyboard_path = storyboard_dir / _STORYBOARD_FILENAME
        storyboard_path.write_text(
            output.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("Storyboard を保存しました: %s", storyboard_path)
