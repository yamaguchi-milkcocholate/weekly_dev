# プロジェクトセットアップ・CLI利用手順

**対応する設計書:** `docs/designs/t1_overall_flow.md`, `docs/designs/project_skeleton_design.md`

## 1. 初期セットアップ

### 1.1 環境構築

```bash
cd daily_routine/
uv sync
```

正常にセットアップされたことを確認する。

```bash
uv run python -c "import daily_routine; print('OK')"
```

### 1.2 グローバル設定

グローバル設定ファイルはリポジトリ内の `configs/global.yaml` に配置されている。

```yaml
# データ保存ルート（リポジトリルートからの相対パスで解決される）
data_root: outputs

# APIキー（環境変数でもオーバーライド可能）
api_keys:
  youtube_data_api: ""
  openai: ""
  google_ai: ""

# デフォルトのプロジェクト設定
defaults:
  output_fps: 30
  output_duration_range: [30, 60]

# ロギング
logging:
  level: INFO
```

APIキーはプロジェクトルートの `.env` ファイルで設定する。`.env.example` をコピーして使用する。

```bash
cp .env.example .env
```

```dotenv
DAILY_ROUTINE_API_KEY_STABILITY=your-stability-key
DAILY_ROUTINE_API_KEY_OPENAI=your-openai-key
DAILY_ROUTINE_API_KEY_GOOGLE_AI=your-google-ai-key
DAILY_ROUTINE_API_KEY_KLING_AK=your-kling-access-key
DAILY_ROUTINE_API_KEY_KLING_SK=your-kling-secret-key
DAILY_ROUTINE_API_KEY_LUMA=your-luma-key
DAILY_ROUTINE_API_KEY_RUNWAY=your-runway-key
```

`export` で設定した環境変数は `.env` より優先される。

## 2. CLI の利用

### 2.1 ヘルプの確認

```bash
uv run daily-routine --help
```

### 2.2 新規プロジェクトの初期化

```bash
# プロジェクトIDを自動生成
uv run daily-routine init "OLの一日"

# プロジェクトIDを指定
uv run daily-routine init "OLの一日" --project-id my-project-001
```

このコマンドで以下が作成される。

- `outputs/projects/{project_id}/config.yaml` — プロジェクト設定
- 各レイヤーのデータディレクトリ（`intelligence/`, `scenario/`, `storyboard/`, `assets/`, `clips/`, `audio/`, `output/`）

### 2.3 パイプラインの実行

パイプラインはチェックポイント方式で動作する。各ステップ完了後に `AWAITING_REVIEW` で停止し、ユーザーが確認・承認した後に次のステップへ進む。

```bash
# パイプラインを新規実行（プロジェクト初期化 + Intelligence ステップを実行）
uv run daily-routine run "OLの一日"

# プロジェクトIDを指定して実行
uv run daily-routine run "OLの一日" --project-id my-project-001

# シード動画情報を指定して実行
uv run daily-routine run "OLの一日" --seeds seeds/my_seeds.yaml
```

`run` はプロジェクトを初期化し、最初のステップ（Intelligence）を実行して停止する。

### 2.4 チェックポイントからの再開

```bash
# AWAITING_REVIEW のステップを承認し、次のステップを実行
uv run daily-routine resume my-project-001
```

`resume` を繰り返すことで、パイプラインを1ステップずつ進める。ステップの実行順序は以下の通り。

1. Intelligence → 2. Scenario → 3. Storyboard → 4. Asset → 5. Keyframe → 6. Visual → 7. Audio → 8. Post-Production

#### Asset ステップの参照画像管理（mapping.yaml）

Asset ステップはキャラクター生成に **C1-F2-MA 方式**（Flash 融合分析 → Pro マルチアングル生成）を使用する。参照画像は `assets/reference/mapping.yaml` で一元管理される。

**Asset ステップ開始時の動作:**
1. `mapping.yaml` が存在すれば読み込む
2. 存在しなければ Scenario の CharacterSpec から自動生成（全 person/clothing = null）
3. person/clothing が指定済み → その画像で C1-F2-MA を実行
4. null のまま → テキスト（appearance/outfit）から自動生成 → C1-F2-MA を実行

**参照画像を手動指定したい場合:**

Storyboard ステップ完了後のチェックポイント（`AWAITING_REVIEW`）で以下を行う。

1. `assets/reference/person/` に人物画像を配置
2. `assets/reference/clothing/` に服装画像を配置
3. `assets/reference/mapping.yaml` を作成（または編集）してパスを指定

**単一衣装（従来方式）:**

```yaml
# assets/reference/mapping.yaml
characters:
  - name: "Aoi"                    # CharacterSpec.name と一致
    person: "model_a.png"          # person/ からの相対パス（null → 自動生成）
    clothing: "casual.png"         # clothing/ からの相対パス（null → 自動生成）
  - name: "Yuki"
    person: "model_a.png"          # 同じ人物画像を共有可能
    clothing: "formal.png"
  - name: "Ren"
    person: null                   # null → appearance テキストから自動生成
    clothing: null                 # null → outfit テキストから自動生成
```

**複数衣装（衣装バリアント）:**

シーンごとに衣装が変わる場合（例: 朝はパジャマ、通勤はスーツ、夜はカジュアル）、`clothing_variants` で衣装バリアントを定義する。

```yaml
# assets/reference/mapping.yaml
characters:
  - name: "Aoi"
    person: "model_a.png"
    clothing_variants:             # clothing の代わりに clothing_variants を使用
      - label: "pajama"            # バリアントID（keyframe_mapping.yaml で参照）
        clothing: "pajama.png"     # clothing/ からの相対パス（null → 自動生成）
      - label: "suit"
        clothing: "suit.png"
      - label: "casual"
        clothing: "casual.png"
```

- `clothing` のみ指定 → `variant_id="default"` の1バリアントとして扱う（後方互換）
- `clothing_variants` 指定時 → 各ラベルごとにアセット生成（3アングル画像 + Identity Block）
- 生成された画像は `assets/character/{キャラ名}/{variant_id}/` に配置される

> 注: mapping.yaml を作成せずに resume すると、全キャラクターの person/clothing が自動生成される。

#### Asset ステップの環境シード管理（environment_seeds.yaml）

Asset ステップは環境画像生成に `assets/reference/environment_seeds.yaml` を使用する。**このファイルは必須**（存在しない場合エラーになる）。

Storyboard ステップ完了後のチェックポイント（`AWAITING_REVIEW`）で以下を行う。

**1. 環境シードファイルを作成する:**

```yaml
# assets/reference/environment_seeds.yaml
environments:
  - scene_number: 1
    source: reference                          # 参照写真から環境再現（C2-R2）
    reference_image: "diving_boat.png"         # environments/ からの相対パス
    description: "ダイビングボートと海"         # 環境の説明（任意）
    modification: ""                           # 修正なし

  - scene_number: 2
    source: generate                           # テキストベースで自動生成
    description: "カフェの内装"                 # SceneSpec.image_prompt を使用

  - scene_number: 3
    source: reference
    reference_image: "diving_boat.png"         # 同じ参照画像を再利用可能
    description: "サンセットのボート"
    modification: "Change the atmosphere to SUNSET. Warm orange and pink sky, golden hour lighting."
```

| フィールド | 必須 | 説明 |
|-----------|------|------|
| `scene_number` | Yes | シーン番号（SceneSpec.scene_number と対応） |
| `source` | Yes | `reference`（参照写真から再現）or `generate`（テキストから生成） |
| `reference_image` | source=reference の時 | `assets/reference/environments/` からの相対ファイル名 |
| `description` | No | 環境の説明（keyframe_mapping 照合用） |
| `modification` | No | C2-R2-MOD 修正指示（source=reference の時のみ）。アングル変更・雰囲気変更・オブジェクト追加等を英語で記述 |

**2. 環境参照写真を配置する（source=reference のシーンのみ）:**

```
assets/reference/environments/
├── diving_boat.png      # 人物入りOK。C2-R2 が自動で人物を除去する
├── kart_circuit.png
└── sunset_beach.jpg
```

**source の使い分け:**

| source | 用途 | 入力 |
|--------|------|------|
| `reference` | 実在の場所の雰囲気を忠実に再現したい | 参照写真（人物入り可） |
| `generate` | 参照写真がない / 架空の場所 | SceneSpec.image_prompt（自動） |

#### Keyframe ステップの衣装バリアント指定（keyframe_mapping.yaml）

Asset ステップ完了後のチェックポイントで `storyboard/keyframe_mapping.yaml` が自動生成される。衣装バリアントを使用している場合、各シーンに `variant_id` を指定して衣装を切り替える。

```yaml
# storyboard/keyframe_mapping.yaml（自動生成 → ユーザー編集）
scenes:
  - scene_number: 1
    character: "Aoi"
    variant_id: "pajama"         # 朝のシーン → パジャマ
    environment: "bedroom"
    pose: "stretching"

  - scene_number: 3
    character: "Aoi"
    variant_id: "suit"           # 通勤シーン → スーツ
    environment: "office"
    pose: "walking"

  - scene_number: 7
    character: "Aoi"
    variant_id: "casual"         # 夜のシーン → カジュアル
    environment: "cafe"
    pose: "sitting"
```

- `variant_id` を指定すると、対応する衣装バリアントの `CharacterAsset`（3アングル画像 + Identity Block）が使用される
- `variant_id` を省略（空文字）すると、そのキャラクター名で最初に見つかったバリアントが使用される
- 自動生成時は先頭バリアントが全シーンに割り当てられるため、ユーザーが各シーンの衣装を手動で編集する

### 2.5 エラー時の再試行

```bash
# ERROR 状態のステップを再実行
uv run daily-routine retry my-project-001
```

### 2.6 プロジェクト状態の確認

```bash
uv run daily-routine status my-project-001
```

> 注: `status` は `run` 実行後に利用可能。`init` のみではパイプライン状態ファイル（`state.yaml`）が作成されないため、`run` で最初のステップを実行してから使用する。

## 3. テストの実行

```bash
# 全テスト
uv run pytest tests/ -v

# スキーマテストのみ
uv run pytest tests/test_schemas/ -v

# 設定管理テストのみ
uv run pytest tests/test_config.py -v

# CLIテストのみ
uv run pytest tests/test_cli.py -v
```

## 4. ランタイムデータ構造

プロジェクト初期化後のディレクトリ構造は以下の通り。

```
outputs/
└── projects/
    └── {project_id}/
        ├── config.yaml             # プロジェクト設定
        ├── state.yaml              # パイプライン状態（run 実行後に生成）
        ├── intelligence/           # TrendReport
        ├── scenario/               # Scenario
        ├── storyboard/             # Storyboard, keyframe_mapping.yaml
        ├── assets/
        │   ├── reference/          # ユーザー提供の参照素材
        │   │   ├── mapping.yaml    # キャラクター参照画像マッピング（自動生成 → ユーザー編集）
        │   │   ├── environment_seeds.yaml  # 環境シード定義（必須、ユーザー作成）
        │   │   ├── person/         # 人物参照画像（C1-F2-MA 入力）
        │   │   ├── clothing/       # 服装参照画像（C1-F2-MA 入力）
        │   │   └── environments/   # 環境参照写真（C2-R2 入力）
        │   ├── character/          # キャラクターリファレンス画像（{name}/{variant_id}/）
        │   ├── environments/       # 環境画像（C2-R2 出力）
        │   ├── backgrounds/        # 背景画像
        │   └── keyframes/          # キーフレーム画像
        ├── clips/                  # カット単位の動画クリップ
        ├── audio/
        │   ├── bgm/               # BGMファイル
        │   └── se/                # SEファイル
        └── output/                 # 最終出力
```
