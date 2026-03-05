---
name: pipeline-run
description: 新規プロジェクトの作成からパイプラインの初回実行までを対話的にガイドする。テーマの決定、実行モード選択、プロジェクト初期化、パイプライン開始を順にサポートする。
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

## パイプラインモード

3つの実行モードがある:

| モード | コマンド | ステップ | 用途 |
|--------|----------|----------|------|
| **Full** | `run` | Intelligence → Scenario → Storyboard → Asset → Keyframe → Visual → Audio → Post-Production | フル自動（従来通り） |
| **Planning** | `plan` | Intelligence → Scenario → Storyboard | プランニングのみ。後で手動編集 → `produce` で Production に移行 |
| **Production** | `produce` | Asset → Keyframe → Visual → Audio | コンテンツ非依存のプロダクションのみ。事前に scenario.json + storyboard.json が必要 |

## 個別順次実行方式

パイプラインは各ステップを1つずつ実行し、`AWAITING_REVIEW` で停止するチェックポイント方式で動作する。

さらに、**Asset / Keyframe / Visual** ステップはアイテム単位（キャラクター、シーン、クリップ等）で個別順次実行される。1回の `resume` で1アイテムが処理され、全アイテム完了後に次のステップへ進む。

## 実行手順

### 1. 環境の事前チェック

パイプライン実行の前提条件を確認する:

1. `.env` が存在し、APIキーが設定されているか確認する
2. `uv run python -c "import daily_routine; print('OK')"` で依存関係を確認する

問題がある場合は、`/project-setup` スキルの実行を案内して終了する。

### 2. テーマの決定

引数でテーマが指定されていない場合、`AskUserQuestion` で以下を確認する:

- 動画のテーマは何にするか（例: 「OLの一日」「カフェ店員の一日」など）

テーマが決まったらユーザーに確認する。

### 3. 実行モードの選択

`AskUserQuestion` で実行モードを確認する:

- **Full（推奨）**: フル8ステップを順次実行する
- **Planning**: プランニングのみ（Intelligence → Scenario → Storyboard）。生成結果を手動編集してから Production に移行したい場合
- **Production**: プロダクションのみ（Asset → Keyframe → Visual → Audio）。シナリオ・絵コンテが事前に確定している場合

#### Production モードを選択した場合

Production モードは既存プロジェクトに対して実行する（`produce` コマンドはプロジェクトIDのみを受け取る）。

1. `AskUserQuestion` でプロジェクトIDを入力してもらう
2. プロジェクトディレクトリの存在を確認する
3. `scenario/scenario.json` と `storyboard/storyboard.json` の存在を確認する
4. 不足している場合は、配置方法を案内して一旦終了する
5. **ステップ4b（Asset 準備）へスキップする**

#### Full / Planning モードを選択した場合

ステップ4以降へ進む。

### 4. プロジェクトIDの決定

`AskUserQuestion` でプロジェクトIDの設定方法を確認する:

- **自動生成（推奨）**: システムがIDを生成する
- **手動指定**: ユーザーが任意のIDを指定する

手動指定の場合、`AskUserQuestion` でIDを入力してもらう。

### 4b. Asset 準備（Production モードのみ）

Production モードでは、最初のステップが Asset であるため、パイプライン開始前に Asset の準備が必要。

1. **mapping.yaml の確認**: キャラクター参照画像の設定について `/checkpoint-resume` のステップ3と同じ手順でガイドする
2. **environment_seeds.yaml の確認**: 環境シードの設定について `/checkpoint-resume` のステップ4と同じ手順でガイドする

準備が完了したらステップ6へスキップする。

### 5. シード動画情報の確認（Full / Planning モードのみ）

`AskUserQuestion` でシード動画情報について確認する:

- **指定しない（推奨）**: シードなしで実行する
- **指定する**: シードファイルのパスを指定する

シードを指定する場合:

1. `AskUserQuestion` でシードファイルのパスを入力してもらう
2. 指定されたファイルが存在するか確認する
3. ファイルの内容を読み込み、妥当性を確認する

### 6. 実行コマンドの構築と確認

これまでの選択に基づいて実行コマンドを構築し、ユーザーに確認する:

```
構築されるコマンド例:

# Full モード
uv run daily-routine run "OLの一日"
uv run daily-routine run "OLの一日" --project-id my-project-001
uv run daily-routine run "OLの一日" --seeds seeds/my_seeds.yaml

# Planning モード
uv run daily-routine plan "OLの一日"
uv run daily-routine plan "OLの一日" --project-id my-project-001

# Production モード
uv run daily-routine produce my-project-001
```

`AskUserQuestion` でコマンドを確認し、実行してよいか確認する。

### 7. パイプラインの実行

1. 構築したコマンドを実行する
2. 実行結果を監視し、エラーが出た場合は原因を特定して対処方法を提示する

### 8. 実行結果の報告

実行が成功した場合、モードに応じた報告を行う:

#### 共通

1. **プロジェクトID**: 生成された（または指定した）プロジェクトID
2. **プロジェクトディレクトリ**: `outputs/projects/{project_id}/` のパス
3. **現在の状態**: `AWAITING_REVIEW` で停止中であること
4. `uv run daily-routine status {project_id}` で状態を確認できること
5. 「確認後、`/checkpoint-resume {project_id}` で次に進めます」と案内する

#### Full / Planning モード

- **実行されたステップ**: Intelligence ステップが完了したこと
- **作成されたデータ**: `intelligence/` ディレクトリ内のファイル

#### Production モード

- **実行されたステップ**: Asset ステップの**最初のアイテム**が完了したこと（Asset はアイテム単位で実行されるため、全体が完了したわけではない）
- **作成されたデータ**: `assets/` ディレクトリ内の該当アイテムのファイル
- **残りのアイテム**: 未処理のアイテム数を案内する
- 「`/checkpoint-resume {project_id}` で1アイテムずつ進めます」と案内する

## 注意事項

- `run` / `plan` コマンドはプロジェクト初期化 + 最初のステップの実行を行う。`init` 単体は使わない（Production モード除く）
- Production モードでは `init` で事前にプロジェクトを作成し、scenario.json + storyboard.json を手動配置してから `produce` を実行する
- `produce` は `scenario.json` と `storyboard.json` の存在を検証してから開始する
- 実行に時間がかかる場合があるため、ユーザーに待機を案内する
- エラーが発生した場合、`uv run daily-routine retry {project_id}` での再試行を案内する
- アイテム対応ステップ（Asset / Keyframe / Visual）でアイテム個別のエラーには `retry --item <item-id>` を使用する
