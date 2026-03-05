"""パイプラインステップの基底クラス."""

from abc import ABC, abstractmethod
from pathlib import Path


class StepEngine[InputT, OutputT](ABC):
    """パイプラインステップの基底クラス.

    各レイヤーエンジン（Intelligence, Scenario, ...）はこのクラスを継承し、
    execute / load_output / save_output を実装する。
    """

    @abstractmethod
    async def execute(self, input_data: InputT, project_dir: Path) -> OutputT:
        """ステップのメイン処理を実行する.

        Args:
            input_data: このステップに必要な全入力データ
            project_dir: プロジェクトデータディレクトリ

        Returns:
            このステップの出力データ
        """

    @abstractmethod
    def load_output(self, project_dir: Path) -> OutputT:
        """永続化済みの出力データを読み込む.

        resume時に前ステップの出力を取得するために使用。

        Args:
            project_dir: プロジェクトデータディレクトリ

        Returns:
            保存済みの出力データ
        """

    @abstractmethod
    def save_output(self, project_dir: Path, output: OutputT) -> None:
        """出力データを永続化する.

        Args:
            project_dir: プロジェクトデータディレクトリ
            output: 保存する出力データ
        """

    @property
    def supports_items(self) -> bool:
        """アイテム単位実行に対応するかどうか."""
        return False

    def list_items(self, input_data: InputT, project_dir: Path) -> list[str]:
        """生成するアイテムIDの順序付きリストを返す.

        Args:
            input_data: このステップに必要な全入力データ
            project_dir: プロジェクトデータディレクトリ

        Returns:
            アイテムIDのリスト
        """
        raise NotImplementedError

    async def execute_item(self, item_id: str, input_data: InputT, project_dir: Path) -> None:
        """1アイテムを生成し、出力を差分保存する.

        Args:
            item_id: 生成対象のアイテムID
            input_data: このステップに必要な全入力データ
            project_dir: プロジェクトデータディレクトリ
        """
        raise NotImplementedError
