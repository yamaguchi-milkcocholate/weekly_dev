# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

「リアル制約 × AI創造」の掛け算で価値を生むAIパイプライン基盤。リアル空間の制約を忠実にデジタル化し、AIがその制約の中で創造・予測する。パイプラインの入口（データ取得方法）を差し替えることで、空間デザイン・フィジカルAI等の領域に横展開する設計。

### 実行モデル: Claude Code as Processing Engine

Claude Codeを処理エンジンとして使用する。ユーザーがClaude Codeに自然言語で指示し、Claude Codeがスクリプト実行・外部API呼び出し・ファイル操作を判断・実行する。

- **スキル**: `.claude/skills/` に定義。Claude Codeが必要に応じて呼び出す
- **スクリプト**: `scripts/` に定義。`uv run` で実行する

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
```

## アーキテクチャ

```
poc/                # PoC・技術検証用
scripts/            # ユーティリティスクリプト
docs/
├── specs/          # 仕様書（何を作るか）
├── designs/        # 設計書（どうやって作るか）
├── adrs/           # ADR（何を採用したか）
├── guidelines/     # 開発ガイドライン
├── procedures/     # 手順書
├── image_gen_best_practices/  # 画像生成タスク別ベストプラクティス
└── memo/           # メモ・検討資料
```

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
- Blender Python（bpy）をCLIから実行する際は `blender-python` スキルを参照すること。`blender` コマンドの直接呼び出しは禁止（bundled Pythonの解決に失敗する）。必ず `scripts/run_blender.sh` ラッパー経由で実行する
