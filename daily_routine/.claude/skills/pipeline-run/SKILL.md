---
name: pipeline-run
description: 新規プロジェクトの作成からパイプラインの初回実行までを対話的にガイドする。テーマの決定、プロジェクト初期化、シード指定、パイプライン開始を順にサポートする。
argument-hint: [テーマ]
---

# パイプライン実行ガイド

新規プロジェクトを作成し、パイプラインを開始するまでを対話的にガイドする。

## 前提知識

このスキルを実行する前に、以下のファイルを読み込むこと:

- [/docs/procedures/project_setup.md](/docs/procedures/project_setup.md) — セットアップ手順書

## 入力

$ARGUMENTS

テーマ文字列（例: `OLの一日`）。指定がない場合は `AskUserQuestion` でヒアリングする。

## 実行手順

### 1. 環境の事前チェック

パイプライン実行の前提条件を確認する:

1. `daily_routine/.env` が存在し、APIキーが設定されているか確認する
2. `uv run python -c "import daily_routine; print('OK')"` で依存関係を確認する

問題がある場合は、`/project-setup` スキルの実行を案内して終了する。

### 2. テーマの決定

引数でテーマが指定されていない場合、`AskUserQuestion` で以下を確認する:

- 動画のテーマは何にするか（例: 「OLの一日」「カフェ店員の一日」など）

テーマが決まったらユーザーに確認する。

### 3. プロジェクトIDの決定

`AskUserQuestion` でプロジェクトIDの設定方法を確認する:

- **自動生成（推奨）**: システムがIDを生成する
- **手動指定**: ユーザーが任意のIDを指定する

手動指定の場合、`AskUserQuestion` でIDを入力してもらう。

### 4. シード動画情報の確認

`AskUserQuestion` でシード動画情報について確認する:

- **指定しない（推奨）**: シードなしで実行する
- **指定する**: シードファイルのパスを指定する

シードを指定する場合:

1. `AskUserQuestion` でシードファイルのパスを入力してもらう
2. 指定されたファイルが存在するか確認する
3. ファイルの内容を読み込み、妥当性を確認する

### 5. 実行コマンドの構築と確認

これまでの選択に基づいて実行コマンドを構築し、ユーザーに確認する:

```
構築されるコマンド例:
uv run daily-routine run "OLの一日"
uv run daily-routine run "OLの一日" --project-id my-project-001
uv run daily-routine run "OLの一日" --seeds seeds/my_seeds.yaml
```

`AskUserQuestion` でコマンドを確認し、実行してよいか確認する。

### 6. パイプラインの実行

1. 構築したコマンドを `daily_routine/` ディレクトリで実行する
2. 実行結果を監視し、エラーが出た場合は原因を特定して対処方法を提示する

### 7. 実行結果の報告

実行が成功した場合、以下を報告する:

1. **プロジェクトID**: 生成された（または指定した）プロジェクトID
2. **プロジェクトディレクトリ**: `outputs/projects/{project_id}/` のパス
3. **実行されたステップ**: Intelligence ステップが完了したこと
4. **現在の状態**: `AWAITING_REVIEW` で停止中であること
5. **作成されたデータ**: `intelligence/` ディレクトリ内のファイル

以下の案内を表示する:

- 「Intelligence ステップの結果を確認してください」
- 「確認後、`/checkpoint-resume` で次のステップに進めます」
- `uv run daily-routine status {project_id}` で状態を確認できること

## 注意事項

- `run` コマンドはプロジェクト初期化 + Intelligence ステップの実行を行う。`init` 単体は使わない
- 実行に時間がかかる場合があるため、ユーザーに待機を案内する
- エラーが発生した場合、`uv run daily-routine retry {project_id}` での再試行を案内する
