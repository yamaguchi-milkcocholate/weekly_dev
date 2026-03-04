---
name: checkpoint-resume
description: チェックポイントからパイプラインを再開する。現在のステップに応じた準備作業（Asset設定、環境シード作成など）を対話的にガイドし、次のステップへ進める。
argument-hint: <プロジェクトID>
---

# チェックポイント再開ガイド

`AWAITING_REVIEW` 状態のパイプラインを、ステップに応じた準備作業をガイドしながら再開する対話型スキル。

## 前提知識

このスキルを実行する前に、以下のファイルを読み込むこと:

- [/docs/procedures/project_setup.md](/docs/procedures/project_setup.md) — セットアップ手順書（特にセクション2.4〜2.6）

## 入力

$ARGUMENTS

プロジェクトID（例: `my-project-001`）。指定がない場合は `AskUserQuestion` でヒアリングする。

## パイプラインモード

パイプラインは3つのモードで動作する。モードによってステップ構成が異なる:

| モード | ステップ構成 | 開始コマンド |
|--------|-------------|-------------|
| **Full** | Intelligence → Scenario → Storyboard → Asset → Keyframe → Visual → Audio → Post-Production | `run` |
| **Planning** | Intelligence → Scenario → Storyboard | `plan` |
| **Production** | Asset → Keyframe → Visual → Audio | `produce` |

現在のモードは `state.yaml` の `steps` キーに含まれるステップから判別する。`resume` コマンドは全モード共通で動作する。

## 実行手順

### 1. プロジェクト状態の確認

1. 引数でプロジェクトIDが指定されていない場合、`AskUserQuestion` で入力を求める
2. `uv run daily-routine status {project_id}` を実行し、現在の状態を取得する
3. `state.yaml` を読み込み、現在のステップと状態を特定する
4. **パイプラインモードを判別する**:
   - `steps` に `intelligence` が含まれ、`asset` も含まれる → Full モード
   - `steps` に `intelligence` が含まれ、`asset` が含まれない → Planning モード
   - `steps` に `intelligence` が含まれず、`asset` が含まれる → Production モード

状態に応じて分岐する:

- **AWAITING_REVIEW**: ステップ別のレビューガイドへ進む（ステップ2）
- **ERROR**: エラー対応を案内する（ステップ7）
- **COMPLETED**: パイプライン完了を案内する（ステップ6b）
- **RUNNING**: 実行中であることを案内して終了

### 2. 完了ステップのレビューガイド

現在 `AWAITING_REVIEW` のステップに応じて、適切なレビュー方法をガイドする。

#### Intelligence ステップ完了後

1. `intelligence/` ディレクトリ内のデータを読み込む
2. トレンド分析の結果をユーザーに要約して提示する
3. `AskUserQuestion` で確認: 「この分析結果で次のステップ（Scenario）に進みますか？」

#### Scenario ステップ完了後

1. `scenario/` ディレクトリ内のデータを読み込む
2. シナリオの概要をユーザーに提示する:
   - シーン構成
   - キャラクター一覧（名前、外見、衣装）
   - 各シーンの概要
3. `AskUserQuestion` で確認: 「このシナリオで次のステップ（Storyboard）に進みますか？」

#### Storyboard ステップ完了後

1. `storyboard/` ディレクトリ内のデータを読み込む
2. ストーリーボードの概要を提示する
3. **モードに応じた分岐:**
   - **Full モード**: 次の Asset ステップに進む前に準備が必要であることを説明し、ステップ3（Asset 準備）へ案内する
   - **Planning モード**: これがプランニングの最終ステップであることを説明し、ステップ6b（完了案内）へ進む

#### Asset ステップ完了後

1. `assets/` ディレクトリ内の生成結果を確認する
2. 生成されたキャラクター画像・環境画像の一覧を提示する
3. `AskUserQuestion` で確認: 「生成結果を確認して、次のステップ（Keyframe）に進みますか？」

#### Keyframe ステップ完了後

1. `assets/keyframes/` 内のキーフレーム画像を確認する
2. 生成されたキーフレームの一覧を提示する
3. `AskUserQuestion` で確認: 「キーフレームを確認して、次のステップ（Visual）に進みますか？」

#### Visual ステップ完了後

1. `clips/` ディレクトリ内の動画クリップを確認する
2. 生成されたクリップの一覧を提示する
3. `AskUserQuestion` で確認: 「映像クリップを確認して、次のステップ（Audio）に進みますか？」

#### Audio ステップ完了後

1. `audio/` ディレクトリ内のファイルを確認する
2. BGM・SE の一覧を提示する
3. **モードに応じた分岐:**
   - **Full モード**: `AskUserQuestion` で確認: 「音声素材を確認して、最終ステップ（Post-Production）に進みますか？」
   - **Production モード**: これがプロダクションの最終ステップであることを説明し、ステップ6b（完了案内）へ進む

### 3. Asset ステップの準備: キャラクター参照画像（mapping.yaml）

Storyboard ステップ完了後（Full モード）、または Production モード開始前に実施する。

`AskUserQuestion` でキャラクター参照画像の設定方法を確認する:

- **自動生成（推奨）**: mapping.yaml を作成せず、テキストから自動生成する
- **参照画像を手動指定する**: 人物・服装の参照画像を用意して指定する

#### 自動生成の場合

1. 「mapping.yaml を作成しない場合、全キャラクターの person/clothing が自動生成されます」と説明する
2. ステップ4（環境シード設定）へ進む

#### 手動指定の場合

Scenario のキャラクター情報を読み込み、キャラクター一覧を提示する。

各キャラクターについて `AskUserQuestion` で確認する:

1. **人物画像**: `assets/reference/person/` に配置する画像ファイル名（null で自動生成）
2. **服装画像**: `assets/reference/clothing/` に配置する画像ファイル名（null で自動生成）

ユーザーの回答に基づいて `assets/reference/mapping.yaml` を生成する:

```yaml
# assets/reference/mapping.yaml
characters:
  - name: "{キャラクター名}"
    person: "{画像ファイル名 or null}"
    clothing: "{画像ファイル名 or null}"
```

画像ファイルの配置を案内する:

1. 人物画像 → `assets/reference/person/` に配置
2. 服装画像 → `assets/reference/clothing/` に配置
3. ファイルが正しく配置されたか確認する

### 4. Asset ステップの準備: 環境シード（environment_seeds.yaml）

**このファイルは必須。** 存在しない場合、Asset ステップはエラーになる。

#### 4.1 シーン情報の提示

Storyboard のデータからシーン一覧を読み込み、各シーンの情報を提示する:

- シーン番号
- シーンの場所・状況
- image_prompt の内容

#### 4.2 各シーンの環境ソース設定

各シーンについて `AskUserQuestion` で確認する:

- **generate（推奨）**: テキストから自動生成する（参照写真不要）
- **reference**: 参照写真から環境を再現する

#### reference を選択した場合

1. `AskUserQuestion` で参照画像のファイル名を入力してもらう
2. `assets/reference/environments/` に画像を配置するよう案内する
3. `AskUserQuestion` で修正指示（modification）があるか確認する:
   - なし: そのまま再現
   - あり: 修正内容を入力してもらう（例: 「Change the atmosphere to SUNSET.」）。ただし日本語の場合はClaude Codeが英語に翻訳してからファイルに書き込む

#### 4.3 environment_seeds.yaml の生成

ユーザーの回答に基づいて `assets/reference/environment_seeds.yaml` を生成する:

```yaml
environments:
  - scene_number: 1
    source: reference
    reference_image: "photo.png"
    description: "シーンの説明"
    modification: ""

  - scene_number: 2
    source: generate
    description: "シーンの説明"
```

生成したファイルの内容をユーザーに確認する。

#### 4.4 参照画像の配置確認

`source: reference` のシーンがある場合:

1. `assets/reference/environments/` ディレクトリの中身を確認する
2. 指定されたファイルが存在するか検証する
3. 不足している場合、どのファイルを配置する必要があるかを案内する
4. `AskUserQuestion` で「画像を配置しましたか？」と確認する

### 5. パイプラインの再開

すべての準備が完了したら:

1. 実行するコマンドを提示する: `uv run daily-routine resume {project_id}`
2. `AskUserQuestion` で実行確認を取る
3. コマンドを `daily_routine/` ディレクトリで実行する
4. 実行結果を監視し、エラーがあれば対処する

### 6. 実行結果の報告

実行が成功した場合:

1. 完了したステップを報告する
2. 次のステップが何かを案内する
3. 次のチェックポイントでの準備事項を事前に案内する:
   - 次が Asset ステップの場合: 「mapping.yaml と environment_seeds.yaml の準備が必要です」
4. 「確認後、再度 `/checkpoint-resume {project_id}` で次のステップに進めます」と案内する

### 6b. パイプライン完了時の案内

最終ステップの approve でパイプラインが完了した場合、モードに応じた案内を行う:

#### Full モード

- 「パイプラインが完了しました」と報告する
- 最終出力の確認方法を案内する

#### Planning モード

- 「プランニングが完了しました」と報告する
- 以下の次のアクションを案内する:
  - `scenario/scenario.json` と `storyboard/storyboard.json` を手動編集できること
  - 編集後、`uv run daily-routine produce {project_id}` でプロダクションパイプラインを開始できること
  - `/pipeline-run` で Production モードを選択することもできること

#### Production モード

- 「プロダクションパイプラインが完了しました」と報告する
- 生成された映像・音声素材の確認方法を案内する

### 7. エラー対応

`ERROR` 状態の場合:

1. エラー内容を `state.yaml` から読み取り、ユーザーに提示する
2. 可能であれば原因と対処方法を提案する
3. `AskUserQuestion` で再試行するか確認する
4. 再試行する場合: `uv run daily-routine retry {project_id}` を実行する

## 注意事項

- `environment_seeds.yaml` は Asset ステップの**必須ファイル**。作成しないと Asset ステップがエラーになる
- `mapping.yaml` は任意。作成しない場合は全キャラクターが自動生成される
- 参照画像は人物が写り込んでいてもOK（C2-R2 が自動で除去する）
- 同じ参照画像を複数のシーン/キャラクターで共有できる
- modification フィールドは英語で記述する（アングル変更、雰囲気変更、オブジェクト追加等）
- Production モードでは Intelligence 未実行のため、Audio ステップで AudioTrend にデフォルト値が使用される
