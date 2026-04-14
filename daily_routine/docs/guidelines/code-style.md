# コーディングルール

## 1. 言語・ランタイム

- Python 3.12+、パッケージ管理は uv
- `src/` レイアウト（`src/daily_routine/`）
- uv が管理する `.venv` を使用。グローバル環境へのインストール禁止

## 2. フォーマッタ・リンター

- Ruff をフォーマッタ・リンターの単一ツールとして使用する
- CI / pre-commit で `ruff check` と `ruff format --check` を実行する
- 行長上限: 120文字

## 3. 型ヒント

- すべての関数シグネチャに型ヒントを付与する（引数・戻り値の両方）
- Python 3.12+ のビルトインジェネリクスを使用する（`list[str]`, `dict[str, float]`, `X | None`）
- `typing.List`, `typing.Dict`, `typing.Optional` 等の旧記法は使わない

## 4. 命名規則

| 対象           | スタイル              | 例                          |
| -------------- | --------------------- | --------------------------- |
| モジュール     | snake_case            | `trend_report.py`           |
| クラス         | PascalCase            | `TrendReport`               |
| 関数・メソッド | snake_case            | `load_global_config()`      |
| 変数・引数     | snake_case            | `scene_number`              |
| 定数           | UPPER_SNAKE_CASE      | `DEFAULT_FPS = 30`          |
| Enum メンバ    | UPPER_SNAKE_CASE      | `PipelineStep.INTELLIGENCE` |
| プライベート   | 先頭アンダースコア1つ | `_validate_input()`         |

## 5. Pydantic モデル

- データスキーマは Pydantic v2 の `BaseModel` で定義する
- すべてのモデルに docstring を付ける
- フィールドの意味が名前だけで不明確な場合、`Field(description=...)` を付与する
- Enum は `str` との多重継承（`class PipelineStep(str, Enum)`）でシリアライズ時に文字列出力させる
- ファイルパスは `pathlib.Path` を使用する。文字列でのパス操作は禁止

## 6. 非同期処理

- 外部API呼び出しは `async/await` を標準とする
- HTTP クライアントには `httpx`（非同期対応）を使用する
- 同期処理が必要な場面（CLI エントリーポイント等）では `asyncio.run()` でラップする

## 7. インターフェース

- レイヤー境界やAPIクライアントのインターフェースは `ABC` + `@abstractmethod` で定義する
- レイヤー間の依存は `schemas/` を介して行い、レイヤー同士の直接インポートは禁止

## 8. インポート順序

Ruff の isort で自動整列される。順序: 標準ライブラリ → サードパーティ → ローカル（各グループ間に空行1行）。

## 9. エラーハンドリング

- 裸の `except:` / `except Exception:` で握りつぶさない
- 外部API呼び出しでは具体的な例外を捕捉し、リトライまたは意味のあるエラーメッセージをログに出す
- カスタム例外は必要に応じてモジュール内 `exceptions.py` に定義する

## 10. ロギング

- Python 標準 `logging` モジュールを使用する
- モジュールレベルで `logger = logging.getLogger(__name__)` を定義
- `print()` によるログ出力は禁止（PoC のデバッグ用途を除く）
- フォーマット文字列には f-string ではなく `%` スタイルを使用する（遅延評価のため）

## 11. 設定・シークレット管理

- 設定は YAML ファイル + Pydantic モデルで管理する
- APIキーをソースコードやYAMLファイルにハードコードしない
- APIキーは環境変数（`DAILY_ROUTINE_API_KEY_{NAME}` 形式）で注入する
- `.env` ファイルは `.gitignore` に追加する

## 12. テスト

- フレームワーク: pytest
- テストディレクトリ: `tests/`（`src/` と同階層）
- ファイル命名: `test_{module_name}.py`、関数命名: `test_{テスト対象}_{条件}_{期待結果}`
- Pydantic モデルには JSON / dict のシリアライズ・デシリアライズ往復テストを書く
- 外部APIに依存するテストはモックを使い、実API呼び出しは統合テスト（CI 対象外）として分離する

## 13. docstring

- すべての公開クラス・公開関数に docstring を付ける
- 1行で収まるものは1行 docstring、収まらないものは Google スタイル（Args / Returns / Raises）で記述する

## 14. ディレクトリ配置ルール

- `src/daily_routine/` — 本番パッケージ（プロダクションコードのみ）
- `poc/` — PoC・技術検証用（本番パッケージには含めない）
- `tests/` — テストコード
- 各パッケージには `__init__.py` を配置する

## 15. Git コミット

- コミットメッセージは日本語で記述する
- 1コミット = 1つの論理的なまとまり
- APIキー・認証情報を含むファイルをコミットしない
