# Storyboard Engine 設計書

## 1. 概要

Scenario（脚本）と Keyframe/Visual（撮影）の間に **Storyboard（絵コンテ）** レイヤーを新設する。

現在のパイプラインでは、Scenario が「何が起きるか」と「どう撮るか」を兼ねており、1シーン = 1カット = 10秒動画という粗い粒度で映像を生成している。YouTube Shorts ではテンポの速いカット割りが重要であり、また Image-to-Video（I2V）モデルは短尺・単一アクションで最も品質が出る。

Storyboard Engine は Scenario の各シーンを **複数のカット** に分解し、カットごとに尺・カメラワーク・動きの指示・トランジションを決定する。全カットを I2V（Image-to-Video）で生成し、短いカットの繋ぎ合わせでテンポを実現する。

## 2. 対象範囲

### 対象

- Storyboard スキーマの定義
- LLM ベースの Storyboard 生成エンジン
- パイプラインへの統合（新ステップ追加）
- 下流ステップ（Keyframe, Visual）のインターフェース変更設計

### 対象外

- Keyframe Engine / Visual Engine の実装変更（別設計書で対応）
- Scenario Engine のプロンプト変更（Storyboard 分離に伴い keyframe_prompt / motion_prompt を削除する変更は本設計の実装計画に含む）

## 3. 背景と動機

### 3.1 現在の品質問題

実際のパイプライン実行で以下の問題が確認された:

1. **motion_prompt が I2V の特性に合っていない** — 1つのプロンプトに複数アクション・カメラ変更を詰め込んでいる
2. **10秒は長すぎる** — I2V モデルは2-3秒の短尺で最も品質が安定する
3. **テンポが遅い** — YouTube Shorts の人気動画は2-5秒/カットが主流（シード動画分析: 41秒間に8キャプチャ = 平均5秒）
4. **カット間のつなぎが考慮されていない** — シーン単位の生成のため、テンポやトランジションの制御ができない

### 3.2 映像制作の分業モデル

実際の映像制作では「脚本」と「絵コンテ」は別工程:

| 工程 | 役割 | 対応するパイプラインステップ |
|------|------|------------------------------|
| 脚本（Script） | 何が起きるか（ストーリー） | Scenario |
| 絵コンテ（Storyboard） | どう撮るか（カット割り・技術指示） | **Storyboard（新設）** |

### 3.3 I2V 統一方式の設計判断

**決定:** 全カットを I2V（キーフレーム1枚 → 動画）で生成する。

**背景:** Runway Gen-4 Turbo は `first_frame` のみ対応で、`last_frame`（始点+終点の補間）は非対応。補間対応モデル（`gen3a_turbo`, `veo3.1`）は品質・尺制限の面で Gen-4 Turbo と併用が難しい。

**方針:** 複雑なアクションは「動作前」「動作後」の複数カットに分割し、カット切り替えで不自然さを吸収する。YouTube Shorts ではカットのテンポが速いため、カット間の繋がりの不自然さは問題にならない。

| カット種別 | 例 | 生成方式 | 推奨尺 |
|---|---|---|---|
| カメラワークのみ | ズームイン、パン、スローパン | I2V（キーフレーム1枚） | 2-5秒 |
| 微細な動き | 髪なびき、湯気、瞬き | I2V（キーフレーム1枚） | 2-3秒 |
| アクション（単一） | コーヒーを飲む、手帳に書く | I2V（キーフレーム1枚） | 2-3秒 |
| アクション（複雑） | 鞄を持って立ち上がる | 2カットに分割（立ち上がる → 鞄を持つ） | 各2秒 |

## 4. スキーマ設計

### 4.1 新規スキーマ: `schemas/storyboard.py`

```python
"""絵コンテ（Storyboard）スキーマ."""

from enum import StrEnum

from pydantic import BaseModel, Field


class MotionIntensity(StrEnum):
    """動きの強度."""

    STATIC = "static"      # カメラワークのみ（被写体は静止）
    SUBTLE = "subtle"      # 微細な動き（髪揺れ、湯気、瞬き）
    MODERATE = "moderate"  # 中程度の動き（コーヒーを飲む、ページをめくる）
    DYNAMIC = "dynamic"    # 大きな動き（歩く、立ち上がる）


class Transition(StrEnum):
    """カット間トランジション."""

    CUT = "cut"              # ハードカット（直接繋ぎ）
    FADE_IN = "fade_in"      # フェードイン（黒→映像）
    FADE_OUT = "fade_out"    # フェードアウト（映像→黒）
    CROSS_FADE = "cross_fade"  # クロスフェード（前カット→次カット）


class CutSpec(BaseModel):
    """1カットの絵コンテ."""

    cut_id: str = Field(description="カットID（例: 'scene_02_cut_01'）")
    scene_number: int = Field(description="所属シーン番号")
    cut_number: int = Field(description="シーン内のカット番号（1始まり）")
    duration_sec: float = Field(description="カットの尺（2〜5秒、整数）")
    motion_intensity: MotionIntensity = Field(description="動きの強度")
    camera_work: str = Field(
        description="カメラワーク指示（英語、例: 'slow zoom-in from medium to close-up'）"
    )
    action_description: str = Field(
        description="動作の説明（日本語、ユーザー確認用）"
    )
    motion_prompt: str = Field(
        description="動画生成プロンプト（英語、Subject Motion + Scene Motion + Camera Motion）"
    )
    keyframe_prompt: str = Field(
        description="キーフレーム画像プロンプト（英語、@char タグでキャラクター参照）"
    )
    transition: Transition = Field(
        default=Transition.CUT,
        description="次のカットへのトランジション種別"
    )


class SceneStoryboard(BaseModel):
    """1シーンの絵コンテ."""

    scene_number: int = Field(description="シーン番号")
    scene_duration_sec: float = Field(description="シーン全体の尺（カットの合計）")
    cuts: list[CutSpec] = Field(description="カットリスト")


class Storyboard(BaseModel):
    """全体の絵コンテ."""

    title: str = Field(description="動画タイトル")
    total_duration_sec: float = Field(description="全体尺（全カットの合計）")
    total_cuts: int = Field(description="総カット数")
    scenes: list[SceneStoryboard] = Field(description="シーンごとの絵コンテ")
```

**設計判断:**
- `CutType` は廃止。全カットを I2V で生成するため、生成戦略の分岐は不要
- `keyframe_prompts: list[str]` → `keyframe_prompt: str`（単数形）に変更。常に1枚のみ
- `duration_sec` は整数（2〜5秒）。Runway Gen-4 Turbo API が整数指定（2-10秒）のため
- `Transition` を追加。カット間の繋ぎ方を LLM が文脈に応じて指定する

### 4.2 Scenario スキーマの変更

Storyboard 分離に伴い、SceneSpec から以下のフィールドを **削除** する:

| フィールド | 移動先 | 理由 |
|---|---|---|
| `keyframe_prompt` | `CutSpec.keyframe_prompt` | カット単位で生成する |
| `motion_prompt` | `CutSpec.motion_prompt` | カット単位で指示する |

SceneSpec に **残す** フィールド:

| フィールド | 理由 |
|---|---|
| `scene_number` | シーン識別 |
| `duration_sec` | シーン全体の尺（Storyboard の制約条件） |
| `situation` | シーンの状況説明（ストーリー） |
| `camera_work` | 大まかなカメラワーク方針（Storyboard が詳細化） |
| `caption_text` | テロップ文言（ストーリー要素） |
| `image_prompt` | 背景画像生成プロンプト（シーン単位で共通） |

### 4.3 パイプライン入力型の追加

`schemas/pipeline_io.py` に追加:

```python
class StoryboardInput(BaseModel):
    """Storyboard Engine のパイプライン入力."""

    scenario: Scenario


class KeyframeInput(BaseModel):
    """Keyframe Engine のパイプライン入力（変更）."""

    scenario: Scenario
    storyboard: Storyboard  # 追加
    assets: AssetSet


class VisualInput(BaseModel):
    """Visual Core のパイプライン入力（変更）."""

    scenario: Scenario
    storyboard: Storyboard  # 追加
    assets: AssetSet
```

## 5. Storyboard 生成ロジック

### 5.1 エンジン構成

```
StoryboardEngine(StepEngine[StoryboardInput, Storyboard])
    └─ LLM (OpenAI GPT-5 系)
```

Scenario Engine と同じ LLM を使用する。Structured Output で `Storyboard` を直接生成する。

### 5.2 システムプロンプト設計

LLM に以下の知識を埋め込む:

**I2V モデルの特性と制約:**
- 1枚の静止画から連続フレームを予測する技術（Runway Gen-4 Turbo）
- 得意: 小さな動き（1-2アクション）、カメラワーク、微細な変化
- 苦手: 大きな構図変更、場面転換、複数アクションの連続
- 最適な尺: 2-3秒（最大5秒）
- 生成可能な尺: 2〜10秒（整数指定）
- 1カット = 1枚のキーフレーム画像から動画を生成

**複雑なアクションの分割ルール:**
- 1カットに含めるアクションは1つまで
- 複雑な動作は「動作前の構え」「動作中」「動作後の状態」に分割する
- カット切り替えで不自然さを吸収する（ショート動画のテンポに合致）
- 例: 「鞄を持って立ち上がる」→ カット1「立ち上がる動作」+ カット2「鞄を手に取る」

**YouTube Shorts のテンポ:**
- 冒頭1-2秒でフック（高速ダイジェスト or インパクトカット）
- 平均カット尺: 2-5秒
- 1分動画で15-25カットが目安
- 単調なカットが3つ以上続かないようにする

**カメラワーク語彙:**
- Static, Slow zoom-in, Slow zoom-out, Pan left/right, Tilt up/down
- Dolly in/out, Track left/right, Crane up/down, Orbit
- Handheld (subtle shake)

**プロンプト品質ルール:**
- `/docs/guidelines/visual_prompt.md` のルールに従う
- motion_prompt: Subject Motion + Scene Motion + Camera Motion の3要素構成
- keyframe_prompt: `@char` タグでキャラクター参照、背景・ライティング含む
- 画像に既に含まれる情報（外見、服装、場所）を motion_prompt で繰り返さない
- 精確な動詞を使う（walks, sips, glances, tilts, leans）

### 5.3 入力（ユーザープロンプト）

```
以下のシナリオをカット分解してください。

タイトル: {scenario.title}
全体尺: {scenario.total_duration_sec}秒

キャラクター:
- {character.name}: {character.appearance}, {character.outfit}

シーン一覧:
Scene {n}: {situation} ({duration_sec}秒, {camera_work.type})
  テロップ: {caption_text}
  背景: {image_prompt}
...
```

### 5.4 生成ルール（システムプロンプト内に記載）

1. **各シーンを1〜5カットに分解する**
2. **カットの合計尺がシーンの `duration_sec` と一致すること**
3. **全カットの合計尺が `total_duration_sec` と一致すること**
4. **1カットの尺は 2〜5秒（整数）**
5. **1カットのアクションは1つまで。** 複雑な動作は複数カットに分割する
6. **keyframe_prompt には `@char` タグを使用してキャラクターを参照する**
7. **motion_prompt は英語、action_description は日本語**
8. **motion_prompt に被写体の外見・服装・場所の説明を含めない**（キーフレーム画像に反映済み）
9. **冒頭シーンのカットは短め（2秒）にしてテンポを出す**
10. **トランジションの使い分け:**
    - 同一シーン内のカット間: `cut`（ハードカット）を基本とする
    - シーン間の切り替え: `cross_fade` または `fade_out` → `fade_in`
    - 冒頭: 最初のカットに `fade_in` を設定可能
    - エンディング: 最後のカットに `fade_out` を設定可能

### 5.5 バリデーション

生成後に以下を検証する:

| チェック項目 | 条件 |
|---|---|
| カット数 | 全体で 10〜40 カット |
| カット尺 | 各カット 2〜5 秒（整数） |
| シーン尺整合 | シーン内カット合計 = シーンの duration_sec |
| 全体尺整合 | 全カット合計 = total_duration_sec |
| keyframe_prompt | 空でないこと |
| cut_id 形式 | `scene_{NN}_cut_{NN}` 形式 |
| motion_prompt 言語 | 英語であること |
| `@char` タグ | keyframe_prompt に含まれること |
| transition | 有効な `Transition` enum 値であること |

バリデーション失敗時は Scenario Engine と同様にリトライ（最大3回）。

## 6. パイプライン統合

### 6.1 ステップ順序の変更

```
変更前: Intelligence → Scenario → Asset    → Keyframe → Visual → Audio → Post
変更後: Intelligence → Scenario → Storyboard → Asset    → Keyframe → Visual → Audio → Post
```

Storyboard は Scenario の直後、Asset の前に配置する。Asset Generator は Scenario のみを入力とし Storyboard には依存しないが、将来的にカット数に応じたアセット最適化を行う可能性があるため、この順序とする。

### 6.2 PipelineStep Enum の変更

```python
class PipelineStep(StrEnum):
    INTELLIGENCE = "intelligence"
    SCENARIO = "scenario"
    STORYBOARD = "storyboard"  # 新規追加
    ASSET = "asset"
    KEYFRAME = "keyframe"
    VISUAL = "visual"
    AUDIO = "audio"
    POST_PRODUCTION = "post_production"
```

### 6.3 _build_input の変更

```python
if step == PipelineStep.STORYBOARD:
    scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
    return StoryboardInput(scenario=scenario)

if step == PipelineStep.KEYFRAME:
    scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
    storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
    assets = create_engine(PipelineStep.ASSET).load_output(project_dir)
    return KeyframeInput(scenario=scenario, storyboard=storyboard, assets=assets)

if step == PipelineStep.VISUAL:
    scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
    storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
    assets = create_engine(PipelineStep.KEYFRAME).load_output(project_dir)
    return VisualInput(scenario=scenario, storyboard=storyboard, assets=assets)
```

### 6.4 永続化

```
projects/{project_id}/
├── storyboard/
│   └── storyboard.json    # Storyboard（JSON）
```

### 6.5 _engine_kwargs

```python
if step == PipelineStep.STORYBOARD:
    return {"api_key": api_keys.get("openai", "")}
```

## 7. 下流ステップへの影響

### 7.1 Keyframe Engine

**変更前:** シーン単位で1枚のキーフレーム生成
**変更後:** カット単位で1枚ずつキーフレーム生成

| 項目 | 変更前 | 変更後 |
|---|---|---|
| 入力 | `SceneSpec.keyframe_prompt` | `CutSpec.keyframe_prompt` |
| 生成単位 | 1シーン = 1枚 | 1カット = 1枚 |
| 出力 | `KeyframeAsset(scene_number, image_path)` | `KeyframeAsset(cut_id, image_path)` ※要スキーマ変更 |
| 総数目安 | 9枚（9シーン） | 20〜30枚（カット数と同数） |

### 7.2 Visual Engine

**変更前:** シーン単位で10秒動画生成
**変更後:** カット単位で2-5秒動画生成（全て I2V）

| 項目 | 変更前 | 変更後 |
|---|---|---|
| 入力 | `SceneSpec.motion_prompt` + キーフレーム1枚 | `CutSpec.motion_prompt` + キーフレーム1枚 |
| 生成単位 | 1シーン = 1動画 | 1カット = 1動画 |
| 動画尺 | 10秒固定 | 2-5秒（CutSpec.duration_sec、整数） |
| 生成戦略 | I2V のみ | I2V のみ（変更なし） |
| 出力 | `VideoClip(scene_number, ...)` | `VideoClip(cut_id, ...)` ※要スキーマ変更 |

### 7.3 Post-Production

カット単位のクリップを結合する。`Storyboard` のカット順序に従い、`CutSpec.transition` で指定されたトランジションを適用して連結する。

| トランジション | 処理 |
|---|---|
| `cut` | 直接連結（トランジションなし） |
| `fade_in` | 黒画面から徐々に映像を表示 |
| `fade_out` | 映像から徐々に黒画面に遷移 |
| `cross_fade` | 前カットと次カットのクロスディゾルブ |

### 7.4 コスト影響

| 項目 | 変更前 | 変更後（推定） |
|---|---|---|
| キーフレーム枚数 | 9枚 | 20〜30枚（カット数と同数） |
| キーフレームコスト | $0.18 | $0.40〜0.60 |
| 動画クリップ数 | 9本 × 10秒 | 20〜30本 × 3秒平均 |
| 動画コスト | $4.50 | $3.00〜4.50（60〜90秒 × $0.05/秒） |
| **合計** | **$4.68** | **$3.40〜5.10** |

カット数は増えるが1カットの尺が短くなるため、動画コストはほぼ同等。キーフレームコストは増加するが、トータルでは大きな変動なし。

## 8. 実装計画

### ステップ1: Storyboard スキーマ定義

- `src/daily_routine/schemas/storyboard.py` を新規作成
- `MotionIntensity`, `Transition`, `CutSpec`, `SceneStoryboard`, `Storyboard` を定義

**完了条件:** `uv run pytest` でインポートエラーなし

### ステップ2: Scenario スキーマから keyframe_prompt / motion_prompt を削除

- `SceneSpec` から `keyframe_prompt`, `motion_prompt` を削除
- Scenario Engine のプロンプトテンプレートを更新
- 関連テストを更新

**完了条件:** `uv run pytest tests/test_scenario/` が通る

### ステップ3: StoryboardEngine の実装

- `src/daily_routine/storyboard/` パッケージを新規作成
  - `base.py` — `StoryboardEngineBase` ABC
  - `engine.py` — `OpenAIStoryboardEngine(StepEngine[StoryboardInput, Storyboard])`
  - `prompt.py` — システムプロンプト構築
  - `validator.py` — バリデーションロジック
- OpenAI Structured Output で `Storyboard` を直接生成
- バリデーション失敗時のリトライ（最大3回）

**完了条件:** モックテストで Storyboard が生成・バリデーションされる

### ステップ4: パイプライン統合

- `PipelineStep` に `STORYBOARD` を追加
- `STEP_ORDER` を更新
- `_build_input` に STORYBOARD / 更新された KEYFRAME, VISUAL ケースを追加
- `_engine_kwargs` に STORYBOARD ケースを追加
- CLI の `_register_engines` に登録
- `StoryboardInput` を `pipeline_io.py` に追加
- `KeyframeInput`, `VisualInput` に `storyboard` フィールドを追加

**完了条件:** `uv run pytest tests/test_pipeline/` が通る

### ステップ5: テスト

- `tests/test_storyboard/test_engine.py` — Storyboard 生成のモックテスト
- `tests/test_storyboard/test_validator.py` — バリデーションのユニットテスト
- `tests/test_storyboard/test_prompt.py` — プロンプト構築のテスト
- 既存テストの更新（Scenario スキーマ変更の影響）

**完了条件:** `uv run pytest` 全テスト通過

## 9. テスト方針

### 9.1 ユニットテスト

| テスト対象 | テスト内容 |
|---|---|
| `StoryboardValidator` | カット尺範囲（2-5秒整数）、シーン尺整合、全体尺整合、keyframe_prompt 非空、cut_id 形式、transition 有効値 |
| `StoryboardPromptBuilder` | システムプロンプトに I2V 制約が含まれること、Scenario 情報が埋め込まれること |
| `OpenAIStoryboardEngine` | モック LLM で Storyboard が生成されること、バリデーション失敗時にリトライすること |
| `StepEngine` 統合 | `execute`, `save_output`, `load_output` のラウンドトリップ |

### 9.2 統合テスト

- パイプラインランナー経由で STORYBOARD ステップが実行できること
- `_build_input` で KEYFRAME, VISUAL に `storyboard` が渡されること

## 10. 解決済みの未決事項

| 項目 | 調査結果 | 決定 |
|---|---|---|
| **Runway 補間 API** | Gen-4 Turbo は `first_frame` のみ対応、`last_frame` 非対応。補間対応は `gen3a_turbo`（旧世代、5/10秒のみ）と `veo3.1` のみ | **I2V のみに統一。** 複雑なアクションは複数カットに分割し、カット切り替えで吸収する |
| **動画尺の指定粒度** | Gen-4 Turbo は 2025年10月のアップデートで **2〜10秒の任意の整数** をサポート | **2〜5秒の整数指定。** トリミング方式は不要 |
| **Storyboard の LLM 選択** | — | **OpenAI GPT-5 系に決定。** Scenario Engine と同じ LLM を使用し、Structured Output の実績を活かす |
| **カット間トランジション** | — | **Storyboard で指定。** `CutSpec.transition` フィールドで LLM がカット文脈に応じて最適なトランジションを選択する |
