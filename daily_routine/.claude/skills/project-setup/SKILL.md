---
name: project-setup
description: 初回セットアップを対話的にガイドする。環境構築・グローバル設定・APIキー設定を順に確認し、正常に動作するまでサポートする。
---

# プロジェクトセットアップガイド

初めてこのプロジェクトを使う人が、環境構築からAPIキー設定までを順を追って完了できるようガイドする対話型スキル。

## 前提知識

このスキルを実行する前に、以下のファイルを読み込むこと:

- [/docs/procedures/project_setup.md](/docs/procedures/project_setup.md) — セットアップ手順書

## 実行手順

### 1. 現在の環境を診断する

まず、ユーザーの環境状態を自動的にチェックする。以下のコマンドを順に実行し、結果を把握する:

1. `uv --version` で `uv` がインストールされているか確認する
2. `daily_routine/` ディレクトリの存在を確認する
3. `daily_routine/.env` ファイルの存在を確認する
4. `daily_routine/configs/global.yaml` の存在を確認する

診断結果をユーザーに報告し、どのステップから開始するかを提示する。すべて完了済みの場合はその旨伝えて終了する。

### 2. 依存関係のインストール

`uv` が未インストールの場合:

1. ユーザーに `uv` のインストール方法を案内する（`curl -LsSf https://astral.sh/uv/install.sh | sh`）
2. インストール後、`uv --version` で確認する

`uv` がインストール済みの場合:

1. `cd daily_routine/ && uv sync` を実行する
2. 正常にインストールされたか確認する: `uv run python -c "import daily_routine; print('OK')"`
3. エラーが出た場合は原因を特定し、対処方法をユーザーに提示する

結果を報告し、次のステップに進むか `AskUserQuestion` で確認する。

### 3. グローバル設定の確認

`daily_routine/configs/global.yaml` を読み込み、内容をユーザーに説明する:

- `data_root`: データ出力先（デフォルト: `outputs`）
- `defaults.output_fps`: 出力FPS
- `defaults.output_duration_range`: 出力動画の長さ範囲
- `logging.level`: ログレベル

`AskUserQuestion` で以下を確認する:

- デフォルト設定のまま進めるか、変更が必要か
- 変更が必要な場合、どの項目を変更するかヒアリングし、`configs/global.yaml` を編集する

### 4. APIキーの設定

`.env` ファイルの状態を確認する。

#### 4.1 `.env` ファイルが存在しない場合

1. ユーザーに説明: 「APIキーは `.env` ファイルで管理します。テンプレートからコピーします。」
2. `cp daily_routine/.env.example daily_routine/.env` を実行する
3. 作成された `.env` を読み込んで内容をユーザーに提示する

#### 4.2 設定すべきAPIキーの確認

`AskUserQuestion` で、どのAPIサービスを利用するかを確認する（複数選択可）:

- **Stability AI** (`DAILY_ROUTINE_API_KEY_STABILITY`) — 画像生成
- **OpenAI** (`DAILY_ROUTINE_API_KEY_OPENAI`) — テキスト生成
- **Google AI** (`DAILY_ROUTINE_API_KEY_GOOGLE_AI`) — テキスト生成
- **Kling** (`DAILY_ROUTINE_API_KEY_KLING_AK`, `DAILY_ROUTINE_API_KEY_KLING_SK`) — 動画生成
- **Luma** (`DAILY_ROUTINE_API_KEY_LUMA`) — 動画生成
- **Runway** (`DAILY_ROUTINE_API_KEY_RUNWAY`) — 動画生成

#### 4.3 APIキーの入力

選択されたサービスごとに:

1. ユーザーにAPIキーの入力を促す（`AskUserQuestion` で1つずつ）
2. 入力されたキーで `.env` ファイルを更新する
3. `export` で環境変数を設定した場合はそちらが優先されることを説明する

### 5. セットアップ完了の確認

最終チェックを実施する:

1. `cd daily_routine/ && uv run python -c "import daily_routine; print('OK')"` で動作確認
2. `.env` にAPIキーが設定されていることを確認（値は表示しない、設定済みかどうかのみ）

すべて正常であれば、以下を案内する:

- 「セットアップが完了しました。`/pipeline-run` でパイプラインを実行できます。」
- CLIのヘルプ: `uv run daily-routine --help`

## 注意事項

- APIキーの値をログやチャットに出力しない（`***` でマスクする）
- エラーが出た場合は対処方法を具体的に提示し、解決するまで次のステップに進まない
- ユーザーが「スキップしたい」と言った場合は、スキップの影響を説明した上で次へ進む
