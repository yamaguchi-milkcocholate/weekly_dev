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

## 個別順次実行方式

パイプラインは **ステップ単位** と **アイテム単位** の2段階で個別順次実行する。

### ステップレベル

各ステップは1つずつ実行され、完了後に `AWAITING_REVIEW` で停止する。`resume` で承認すると次のステップへ進む。

### アイテムレベル（Asset / Keyframe / Visual）

**Asset、Keyframe、Visual** ステップはアイテム対応エンジンで動作する。アイテム（キャラクター、シーン、クリップ等）を**1つずつ実行・停止**する。

- ステップ開始時: アイテムリストを初期化し、**最初のアイテムのみ実行** → `AWAITING_REVIEW` で停止
- `resume` 実行時: 現在のアイテムを承認し、**次の未処理アイテムを実行** → `AWAITING_REVIEW` で停止
- 全アイテム完了時: ステップを承認し、**次のステップの最初のアイテム（またはステップ全体）を実行**

つまり、アイテム対応ステップでは **アイテム数分だけ `resume` が必要** になる。

### 状態遷移の例（Asset ステップがキャラクター3体の場合）

```
resume 1回目: Asset アイテム「Aoi」を承認 → アイテム「Yuki」を実行 → AWAITING_REVIEW
resume 2回目: Asset アイテム「Yuki」を承認 → アイテム「Ren」を実行 → AWAITING_REVIEW
resume 3回目: Asset アイテム「Ren」を承認 → 全アイテム完了 → Keyframe ステップ開始
              → Keyframe アイテム「Scene 1」を実行 → AWAITING_REVIEW
```

### retry --item による個別アイテム再試行

アイテム対応ステップでエラーが発生した場合、個別アイテムのみ再試行できる:

```bash
uv run daily-routine retry <project-id> --item <item-id>
```

`--item` なしの `retry` はステップ全体を再実行する（ERROR 状態のステップのみ）。
`--item` 指定時は AWAITING_REVIEW / APPROVED / ERROR 状態のアイテムを再生成できる。

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

**アイテム対応ステップの場合**は、`status` 出力のアイテム一覧も確認する。current アイテムがどれか、承認済み/未処理/エラーのアイテムがそれぞれいくつあるかを把握する。

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

#### Asset ステップ — アイテム完了後

Asset はアイテム単位で実行される。`resume` ごとに1アイテムが処理される。

1. `status` のアイテム一覧を確認する（どのアイテムが完了/未処理/エラーか）
2. 完了したアイテムの生成結果を確認する（`assets/character/` や `assets/environments/` 内のファイル）
3. **未処理アイテムがある場合**: 生成結果の確認を促し、`AskUserQuestion` で確認: 「次のアイテムを実行しますか？」
4. **全アイテム完了の場合**: 全体の生成結果を提示し、`AskUserQuestion` で確認: 「次のステップ（Keyframe）に進みますか？」

> 注: Asset → Keyframe 遷移時に `storyboard/keyframe_mapping.yaml` が自動生成される（既存ファイルがあれば上書きしない）。

#### Keyframe ステップ — アイテム完了後

Keyframe もアイテム単位で実行される。

1. `status` のアイテム一覧を確認する
2. 完了したアイテムのキーフレーム画像を確認する（`assets/keyframes/` 内のファイル）
3. **未処理アイテムがある場合**: 生成結果の確認を促し、`AskUserQuestion` で確認: 「次のアイテムを実行しますか？」
4. **全アイテム完了の場合**: 全体の生成結果を提示し、`AskUserQuestion` で確認: 「次のステップ（Visual）に進みますか？」

> 注: アイテムの生成結果に問題がある場合、`retry --item <item-id>` で個別に再生成できる。

#### Visual ステップ — アイテム完了後

Visual もアイテム単位で実行される。

1. `status` のアイテム一覧を確認する
2. 完了したアイテムの動画クリップを確認する（`clips/` 内のファイル）
3. **未処理アイテムがある場合**: 生成結果の確認を促し、`AskUserQuestion` で確認: 「次のアイテムを実行しますか？」
4. **全アイテム完了の場合**: 全体の生成結果を提示し、`AskUserQuestion` で確認: 「次のステップ（Audio）に進みますか？」

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
3. **衣装バリアント**: シーンごとに衣装が変わる場合は `clothing_variants` を使用するか確認する

ユーザーの回答に基づいて `assets/reference/mapping.yaml` を生成する:

**単一衣装:**

```yaml
# assets/reference/mapping.yaml
characters:
  - name: "{キャラクター名}"
    person: "{画像ファイル名 or null}"
    clothing: "{画像ファイル名 or null}"
```

**複数衣装（衣装バリアント）:**

```yaml
characters:
  - name: "{キャラクター名}"
    person: "{画像ファイル名 or null}"
    clothing_variants:
      - label: "pajama"
        clothing: "{画像ファイル名 or null}"
      - label: "suit"
        clothing: "{画像ファイル名 or null}"
```

画像ファイルの配置を案内する:

1. 人物画像 → `assets/reference/person/` に配置
2. 服装画像 → `assets/reference/clothing/` に配置
3. ファイルが正しく配置されたか確認する

### 4. Asset ステップの準備: 環境シード（environment_seeds.yaml）

**このファイルは必須。** 存在しない場合、Asset ステップはエラーになる。

**重要**: 環境シードの作成・編集を開始する前に、必ず以下のベストプラクティスを読み込むこと:

- [/docs/image_gen_best_practices/environment_generation.md](/docs/image_gen_best_practices/environment_generation.md)
  - 特に「modification プロンプトの書き方ガイド」セクションを必ず参照する

読み込み後、ユーザーに以下のメッセージを出力すること:

> 環境画像の modification プロンプトのベストプラクティスを読み込みました。modification の記入時はガイドラインに沿って英語プロンプトを生成します。

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
   - あり: 修正内容を日本語で入力してもらい、ベストプラクティス（`environment_generation.md` の「modification プロンプトの書き方ガイド」）に従って英語プロンプトに変換する。変換後のプロンプトをユーザーに提示して確認を取ってから書き込む

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
3. コマンドを実行する
4. 実行結果を監視し、エラーがあれば対処する

### 6. 実行結果の報告

実行が成功した場合:

1. 完了した内容を報告する（ステップ完了 or アイテム完了）
2. **アイテム対応ステップの場合**: 残りのアイテム数と次のアイテムを案内する
3. **ステップが完了した場合**: 次のステップが何かを案内する
4. 次のチェックポイントでの準備事項を事前に案内する:
   - 次が Asset ステップの場合: 「mapping.yaml と environment_seeds.yaml の準備が必要です」
   - Asset → Keyframe 遷移時: 「keyframe_mapping.yaml が自動生成されます。必要に応じて編集できます」
5. 「確認後、再度 `/checkpoint-resume {project_id}` で次に進めます」と案内する

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
2. **アイテム対応ステップの場合**: どのアイテムがエラーかを特定し、提示する
3. 可能であれば原因と対処方法を提案する
4. `AskUserQuestion` で再試行方法を確認する:
   - **ステップ全体を再試行**: `uv run daily-routine retry {project_id}`
   - **個別アイテムのみ再試行**（アイテム対応ステップの場合）: `uv run daily-routine retry {project_id} --item {item_id}`

## 注意事項

- `environment_seeds.yaml` は Asset ステップの**必須ファイル**。作成しないと Asset ステップがエラーになる
- `mapping.yaml` は任意。作成しない場合は全キャラクターが自動生成される
- 参照画像は人物が写り込んでいてもOK（C2-R2 が自動で除去する）
- 同じ参照画像を複数のシーン/キャラクターで共有できる
- modification フィールドは英語で記述する（アングル変更、雰囲気変更、オブジェクト追加等）
- Production モードでは Intelligence 未実行のため、Audio ステップで AudioTrend にデフォルト値が使用される
- Asset → Keyframe 遷移時に `storyboard/keyframe_mapping.yaml` が自動生成される（既存ファイルは上書きしない）
- アイテム対応ステップ（Asset / Keyframe / Visual）では、`resume` 1回で1アイテムが処理される
- `retry --item` は AWAITING_REVIEW / APPROVED / ERROR 状態のアイテムに対して実行可能
