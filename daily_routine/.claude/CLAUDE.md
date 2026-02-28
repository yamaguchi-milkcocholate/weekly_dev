# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

「〇〇の一日」AI動画生成自動化パイプライン。YouTube Shorts（9:16, 1080x1920）を自動生成する。
6層アーキテクチャ: Intelligence → Scenario → Asset → Visual → Audio → Post-Production

## コマンド

```bash
# 依存関係インストール
uv sync

# テスト実行
uv run pytest                          # 全テスト
uv run pytest tests/test_cli.py        # 単一ファイル
uv run pytest tests/test_cli.py::test_run_help  # 単一テスト

# リント・フォーマット
uv run ruff check .                    # リントチェック
uv run ruff format --check .           # フォーマットチェック
uv run ruff check --fix .              # リント自動修正
uv run ruff format .                   # フォーマット自動修正

# CLI実行
uv run daily-routine run "OLの一日"
uv run daily-routine init "検索キーワード"
uv run daily-routine status "project-id"
```

## アーキテクチャ

```
src/daily_routine/
├── cli/            # Typer CLIレイヤー（エントリーポイント）
├── schemas/        # Pydanticデータモデル（レイヤー間データ受け渡し）
├── config/         # 設定管理（YAML + 環境変数オーバーライド）
├── pipeline/       # パイプラインオーケストレーション（非同期、チェックポイント対応）
├── intelligence/   # トレンド分析エンジン
├── scenario/       # シナリオ生成エンジン
├── asset/          # アセット生成（画像）
├── visual/         # 映像生成（Image-to-Video）
├── audio/          # 音声エンジン（BGM + SE）
└── postproduction/ # ポストプロダクション（動画合成）

poc/                # PoC・技術検証用（本番パッケージに含めない）
tests/              # テストコード
docs/
├── specs/          # 仕様書（何を作るか）
├── designs/        # 設計書（どうやって作るか）
├── adrs/           # ADR（何を採用したか）
├── guidelines/                 # 開発ガイドライン
├── procedures/                 # 手順書
└── image_gen_best_practices/   # 画像生成タスク別ベストプラクティス（PoC知見の蓄積）
```

**重要な設計原則:**

- レイヤー間の依存は `schemas/` を介して行い、レイヤー同士の直接インポートは禁止
- レイヤー境界は `ABC` + `@abstractmethod` で定義
- 外部API呼び出しは `async/await` + `httpx`
- 設定は YAML + Pydantic、APIキーは環境変数（`DAILY_ROUTINE_API_KEY_{NAME}`）

## コーディング規約

- Python 3.12+、パッケージ管理は `uv`、`src/` レイアウト
- Ruff: 行長120文字、select `E/F/I/UP`
- 型ヒント必須（`list[str]`, `X | None` 等のビルトインジェネリクス使用、`typing.List` 等禁止）
- Pydantic v2 の `BaseModel` でスキーマ定義、`Field(description=...)` 付与
- ファイルパスは `pathlib.Path`（文字列パス操作禁止）
- ロギングは `logging.getLogger(__name__)`、`print()` 禁止（PoC除く）
- ログフォーマットは `%` スタイル（f-string禁止、遅延評価のため）
- コミットメッセージは日本語
- テスト命名: `test_{テスト対象}_{条件}_{期待結果}`

## 開発プロセス

仕様書 → サブタスク分解 → 設計書作成 → 実装 → フィードバック → 仕様書更新（反復）

技術選定時は ADR（`/docs/adrs/{連番}_{選定対象}.md`）を作成する。

スクリプトの実行は`uv run`を使用する。

## ガイドライン

- 画像・動画生成プロンプトを作成・レビューする際は `/docs/guidelines/visual_prompt.md` を必ず参照すること
- 画像生成の手法選定・パイプライン設計時は `/docs/image_gen_best_practices/` のタスク別ベストプラクティスを参照すること
