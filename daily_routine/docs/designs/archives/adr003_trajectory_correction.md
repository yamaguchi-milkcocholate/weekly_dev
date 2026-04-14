# ADR-003 軌道修正設計書

## 1. 概要

- **対応するADR:** [ADR-003: 動画生成ワークフローの設計](/docs/adrs/003_video_generation_workflow.md)
- **目的:** 2段階パイプライン（Gen-4 Image → Gen-4 Video）への移行に伴い、既存の設計書・実装・仕様書を整合的に更新する
- **影響範囲:** パイプラインステップ追加（KEYFRAME）、Scenario Engine、Asset Generator（スキーマのみ）、Visual Core、全体フロー設計書、仕様書

## 2. 背景

T1-4（Visual Core）の統合検証で、正面立ちポーズ画像をそのまま I2V の入力に使う方式ではシーン内容が反映されない問題が判明した。ADR-003 で Runway エコシステム内の2段階パイプラインを採用し、以下のワークフローに移行する:

```
キャラクター基本画像 (front_view)
        ↓ referenceImages として @char 参照
keyframe_prompt → Gen-4 Image Turbo → キーフレーム画像
        ↓ promptImage として入力
motion_prompt → Gen-4 Turbo I2V → 動画クリップ
```

## 3. スコープ

### 対象範囲

1. **スキーマ変更:** `SceneSpec` のプロンプトフィールド分離、`AssetSet` のキーフレーム画像対応
2. **パイプラインステップ追加:** `PipelineStep.KEYFRAME` の新設（ASSET と VISUAL の間にチェックポイント付きで挿入）
3. **Keyframe Engine 新規実装:** Gen-4 Image クライアント + キーフレーム生成エンジン
4. **Visual Core 修正:** キーフレーム画像を入力として使用するよう変更
5. **Scenario Engine 設計書の更新:** プロンプト生成ルールの変更
6. **全体フロー設計書の更新:** データフロー図・コスト見積もりの更新
7. **仕様書の更新:** パイプライン説明の更新
8. **既存テストの修正:** スキーマ変更に伴うテスト更新

### 対象外

- Scenario Engine の実装修正（T1-5 実装時に本設計書の内容を反映する）
- Asset Generator の実装修正（T1-3 実装時に本設計書の内容を反映する）
- Post-Production への影響（変更なし）
- Audio Engine への影響（変更なし）

## 4. 変更設計

### 4.1 スキーマ変更

#### 4.1.1 `schemas/scenario.py` — SceneSpec

`video_prompt` を `keyframe_prompt` + `motion_prompt` に分離する。

**変更前:**

```python
class SceneSpec(BaseModel):
    scene_number: int
    duration_sec: float
    situation: str
    camera_work: CameraWork
    caption_text: str
    image_prompt: str   # Asset Generator 用（背景画像）
    video_prompt: str   # Visual Core 用（動画生成）
```

**変更後:**

```python
class SceneSpec(BaseModel):
    scene_number: int
    duration_sec: float
    situation: str
    camera_work: CameraWork
    caption_text: str
    image_prompt: str = Field(
        description="Asset Generator用の背景画像生成プロンプト（英語）。キャラクター不在、背景のみ"
    )
    keyframe_prompt: str = Field(
        description="Gen-4 Image用のキーフレーム画像生成プロンプト（英語）。"
        "シーンの場所・状況にキャラクターを配置した構図を記述。"
        "@charタグでキャラクターを参照"
    )
    motion_prompt: str = Field(
        description="Visual Core用の動画生成プロンプト（英語）。"
        "Subject Motion + Scene Motion + Camera Motionの3要素で構成。"
        "入力画像に既にある情報（外見・服装・場所）は記述しない"
    )
```

**`image_prompt` を残す理由:**

`image_prompt` は Asset Generator が背景画像を生成するためのプロンプトであり、キーフレーム画像とは別の役割を持つ。背景画像はキャラクター不在の純粋な背景であり、Post-Production でのコンポジションや、チェックポイントでのシーン確認に使用される可能性がある。

#### 4.1.2 `schemas/asset.py` — KeyframeAsset + AssetSet 拡張

**追加:**

```python
class KeyframeAsset(BaseModel):
    """キーフレーム画像アセット."""

    scene_number: int = Field(description="シーン番号")
    image_path: Path = Field(description="キーフレーム画像ファイルパス")
    prompt: str = Field(description="生成に使用したプロンプト")
```

**AssetSet の変更:**

```python
class AssetSet(BaseModel):
    characters: list[CharacterAsset]
    props: list[PropAsset]
    backgrounds: list[BackgroundAsset]
    keyframes: list[KeyframeAsset] = Field(
        default_factory=list,
        description="各シーンのキーフレーム画像（Gen-4 Imageで生成）"
    )
```

`keyframes` は `default_factory=list` でオプショナルにする。Asset Generator の `generate_assets()` 実行時点では空リストのままとし、後続の KEYFRAME ステップで生成・格納される。

#### 4.1.3 プロジェクトディレクトリ構造の追加

```
projects/{project_id}/
├── assets/
│   ├── character/
│   ├── props/
│   ├── backgrounds/
│   └── keyframes/          # 新規: キーフレーム画像
│       ├── scene_01.png
│       ├── scene_02.png
│       └── ...
└── clips/
```

### 4.2 パイプラインステップ分離（KEYFRAME ステップ新設）

キーフレーム画像生成（$0.02/枚）と動画生成（$0.50/本）はコスト差が25倍あるため、KEYFRAME ステップを独立させてチェックポイントを設ける。ユーザーがキーフレーム画像を確認・承認してから動画生成に進む。

#### 4.2.1 パイプラインフロー

**変更前:**

```
Intelligence → Scenario → Asset → [チェックポイント] → Visual → Audio → Post-Production
```

**変更後:**

```
Intelligence → Scenario → Asset → [チェックポイント]
  → Keyframe → [チェックポイント: ユーザーがキーフレーム画像を確認]
  → Visual → Audio → Post-Production
```

**ユーザー体験:**

1. Asset ステップ完了後、キャラクター・背景画像を確認して承認
2. Keyframe ステップがキーフレーム画像を生成（$0.16/8シーン）
3. ユーザーが `assets/keyframes/` 内のキーフレーム画像を確認
   - 構図・キャラクター配置・シーンの雰囲気が意図通りか判断
   - 問題があれば `retry` でキーフレームのみ再生成（$0.16）
4. 承認後、Visual ステップが動画を生成（$4.00/8シーン）

#### 4.2.2 `PipelineStep` enum の変更

```python
class PipelineStep(StrEnum):
    INTELLIGENCE = "intelligence"
    SCENARIO = "scenario"
    ASSET = "asset"
    KEYFRAME = "keyframe"          # 新規追加
    VISUAL = "visual"
    AUDIO = "audio"
    POST_PRODUCTION = "post_production"
```

#### 4.2.3 `STEP_ORDER` の変更

```python
STEP_ORDER: list[PipelineStep] = [
    PipelineStep.INTELLIGENCE,
    PipelineStep.SCENARIO,
    PipelineStep.ASSET,
    PipelineStep.KEYFRAME,         # ASSET と VISUAL の間に挿入
    PipelineStep.VISUAL,
    PipelineStep.AUDIO,
    PipelineStep.POST_PRODUCTION,
]
```

#### 4.2.4 パイプライン入力型の追加

`schemas/pipeline_io.py` に `KeyframeInput` を追加する:

```python
class KeyframeInput(BaseModel):
    """Keyframe Engine のパイプライン入力（複合）."""

    scenario: Scenario
    assets: AssetSet
```

`_build_input()` に KEYFRAME ケースを追加:

```python
elif step == PipelineStep.KEYFRAME:
    scenario = scenario_engine.load_output(project_dir)
    assets = asset_engine.load_output(project_dir)
    return KeyframeInput(scenario=scenario, assets=assets)
```

### 4.3 Keyframe Engine（新規）

#### 4.3.1 アーキテクチャ

```
src/daily_routine/keyframe/
├── __init__.py
├── base.py              # KeyframeEngineBase ABC
└── engine.py            # RunwayKeyframeEngine 実装
```

クライアント実装は `visual/clients/` に配置する（Runway API クライアントを1箇所に集約）:

```
src/daily_routine/visual/clients/
├── base.py              # VideoGeneratorClient ABC（既存）
├── runway.py            # RunwayClient（動画生成、既存）
└── gen4_image.py        # RunwayImageClient（画像生成、新規）
```

#### 4.3.2 Gen-4 Image クライアント

`visual/clients/gen4_image.py` を新規作成する。

```python
class ImageGenerationRequest(BaseModel):
    """画像生成リクエスト."""

    prompt: str = Field(description="画像生成プロンプト（@tagを含む）")
    reference_images: dict[str, Path] = Field(
        description="参照画像 {tag: 画像パス}"
    )
    aspect_ratio: str = Field(default="9:16", description="アスペクト比")


class ImageGenerationResult(BaseModel):
    """画像生成結果."""

    image_path: Path = Field(description="生成された画像ファイルのパス")
    model_name: str = Field(description="使用モデル名")
    cost_usd: float | None = Field(default=None, description="推定コスト（USD）")


class RunwayImageClient:
    """Runway Gen-4 Image クライアント."""

    def __init__(
        self,
        api_key: str,
        uploader: ImageUploader,
        model: str = "gen4_image_turbo",
    ) -> None:
        ...

    async def generate(
        self,
        request: ImageGenerationRequest,
        output_path: Path,
    ) -> ImageGenerationResult:
        """キーフレーム画像を生成する.

        処理フロー:
        1. 参照画像を GCS にアップロード
        2. Gen-4 Image API でリクエスト（referenceImages + @tag）
        3. タスクIDでポーリング
        4. 完了後、画像URLからダウンロードして保存
        """
        ...
```

**API リクエスト形式:**

```json
{
  "model": "gen4_image_turbo",
  "promptText": "@char sits at a modern office desk, typing on laptop, soft daylight",
  "referenceImages": [
    { "uri": "https://storage.googleapis.com/.../front.png", "tag": "char" }
  ]
}
```

**コスト:** Gen-4 Image Turbo = 2 credits/枚 = $0.02/枚

#### 4.3.3 KeyframeEngineBase ABC

```python
class KeyframeEngineBase(ABC):
    """Keyframe Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def generate_keyframes(
        self,
        scenario: Scenario,
        assets: AssetSet,
        output_dir: Path,
    ) -> AssetSet:
        """全シーンのキーフレーム画像を生成する.

        Args:
            scenario: シナリオ（keyframe_prompt を含む）
            assets: アセットセット（characters[0].front_view を参照画像として使用）
            output_dir: キーフレーム画像の出力ディレクトリ

        Returns:
            keyframes が追加された AssetSet
        """
        ...
```

**入出力の型:**

- **入力:** `KeyframeInput`（Scenario + AssetSet）
- **出力:** `AssetSet`（keyframes が追加された状態）

出力型を `AssetSet` にする理由: Visual ステップの入力は `VisualInput(scenario, assets)` であり、keyframes が入った AssetSet をそのまま渡せる。新しい出力型を定義する必要がない。

#### 4.3.4 RunwayKeyframeEngine 実装

```python
class RunwayKeyframeEngine(StepEngine[KeyframeInput, AssetSet], KeyframeEngineBase):
    """Runway Gen-4 Image を使ったキーフレーム生成エンジン."""

    def __init__(self, image_client: RunwayImageClient) -> None:
        self._image_client = image_client

    async def execute(self, input_data: KeyframeInput, project_dir: Path) -> AssetSet:
        """キーフレーム画像を生成する."""
        output_dir = project_dir / "assets" / "keyframes"
        assets = await self.generate_keyframes(
            scenario=input_data.scenario,
            assets=input_data.assets,
            output_dir=output_dir,
        )
        self.save_output(project_dir, assets)
        return assets

    async def generate_keyframes(
        self,
        scenario: Scenario,
        assets: AssetSet,
        output_dir: Path,
    ) -> AssetSet:
        output_dir.mkdir(parents=True, exist_ok=True)
        reference_image = assets.characters[0].front_view

        keyframes = []
        for scene in scenario.scenes:
            keyframe_path = output_dir / f"scene_{scene.scene_number:02d}.png"
            request = ImageGenerationRequest(
                prompt=scene.keyframe_prompt,
                reference_images={"char": reference_image},
            )
            result = await self._image_client.generate(request, keyframe_path)
            keyframes.append(KeyframeAsset(
                scene_number=scene.scene_number,
                image_path=keyframe_path,
                prompt=scene.keyframe_prompt,
            ))

        # AssetSet のコピーに keyframes を追加して返す
        return assets.model_copy(update={"keyframes": keyframes})

    def save_output(self, project_dir: Path, output: AssetSet) -> None:
        """AssetSet（keyframes 含む）を保存する."""
        metadata_path = project_dir / "assets" / "asset_set.json"
        metadata_path.write_text(output.model_dump_json(indent=2))

    def load_output(self, project_dir: Path) -> AssetSet:
        """保存済みの AssetSet を読み込む."""
        metadata_path = project_dir / "assets" / "asset_set.json"
        return AssetSet.model_validate_json(metadata_path.read_text())
```

**エンジン登録（`cli/app.py`）:**

```python
register_engine(PipelineStep.KEYFRAME, RunwayKeyframeEngine)
```

### 4.4 Visual Core の変更

キーフレーム生成が KEYFRAME ステップに分離されたため、Visual Core はシンプルになる。

#### 4.4.1 DefaultVisualEngine の変更

**変更前:** `front_view` + `video_prompt` → 動画

**変更後:** `keyframes[].image_path` + `motion_prompt` → 動画

```python
class DefaultVisualEngine(VisualEngine):

    def __init__(self, client: RunwayClient, provider_name: str = "runway") -> None:
        self._client = client
        self._provider_name = provider_name

    async def generate_clips(
        self,
        scenario: Scenario,
        assets: AssetSet,
        output_dir: Path,
    ) -> VideoClipSet:
        """全シーンの動画クリップを生成する."""
        output_dir.mkdir(parents=True, exist_ok=True)
        clips = []

        for scene in scenario.scenes:
            # キーフレーム画像を取得（KEYFRAME ステップで生成済み）
            keyframe = self._find_keyframe(assets, scene.scene_number)
            output_path = output_dir / f"scene_{scene.scene_number:02d}.mp4"

            request = VideoGenerationRequest(
                reference_image_path=keyframe.image_path,
                prompt=scene.motion_prompt,
                duration_sec=10,
                aspect_ratio="9:16",
            )
            result = await self._client.generate(request, output_path)
            clips.append(VideoClip(
                scene_number=scene.scene_number,
                clip_path=result.video_path,
                duration_sec=scene.duration_sec,
                model_name=result.model_name,
                cost_usd=result.cost_usd,
                generation_time_sec=result.generation_time_sec,
            ))

        return VideoClipSet(clips=clips, ...)

    def _find_keyframe(self, assets: AssetSet, scene_number: int) -> KeyframeAsset:
        for kf in assets.keyframes:
            if kf.scene_number == scene_number:
                return kf
        msg = f"キーフレーム画像が見つかりません: scene_{scene_number}"
        raise FileNotFoundError(msg)
```

**変更点のまとめ:**

- コンストラクタから `image_client` を削除（キーフレーム生成は KEYFRAME ステップの責務）
- `reference_image` が `front_view` → `keyframe.image_path` に変更
- `prompt` が `video_prompt` → `motion_prompt` に変更
- `_find_keyframe()` ヘルパーを追加

#### 4.4.2 `create_visual_engine()` ファクトリ

変更なし（既存のまま）。`RunwayClient` のみを使用する。

#### 4.4.3 VisualInput の変更

`_build_input()` の VISUAL ケースは変更なし。ただし、`assets` は KEYFRAME ステップの出力（keyframes 含む）を `load_output()` で取得する:

```python
elif step == PipelineStep.VISUAL:
    scenario = scenario_engine.load_output(project_dir)
    # KEYFRAME ステップの出力（keyframes 含む AssetSet）を取得
    assets = keyframe_engine.load_output(project_dir)
    return VisualInput(scenario=scenario, assets=assets)
```

### 4.5 設定の拡張

**`config/manager.py` の RunwayConfig 変更:**

```python
class RunwayConfig(BaseModel):
    video_model: str = Field(default="gen4_turbo", description="動画生成モデル名")
    image_model: str = Field(default="gen4_image_turbo", description="画像生成モデル名")
    gcs_bucket: str = Field(default="", description="GCSバケット名")
```

**`configs/global.yaml` の変更:**

```yaml
visual:
  provider: "runway"
  runway:
    video_model: "gen4_turbo"
    image_model: "gen4_image_turbo"
    gcs_bucket: "daily-routine-weekly-dev"
```

### 4.6 Scenario Engine 設計書への修正指示

Scenario Engine の設計書（`scenario_engine_design.md`）に以下の変更を反映する。

#### 4.6.1 SceneSpec 生成ルールの変更

設計書「3.6.1 シナリオ生成ルール」の「4. シーン仕様」を以下に更新する:

**変更前:**

> - `video_prompt`: Visual Core 向け動画生成プロンプト（英語）。キャラクターの**動作・カメラワーク・背景・雰囲気のみ**を記述し、キャラクターの外見描写は含めない

**変更後:**

> - `keyframe_prompt`: Gen-4 Image 向けキーフレーム画像生成プロンプト（英語）。シーンの場所・状況にキャラクターを配置した構図を記述する。`@char` タグでキャラクターを参照し、照明・雰囲気を含める。背景画像（`image_prompt`）とは異なり、キャラクターを含む完成構図を記述する
> - `motion_prompt`: Visual Core 向け動画生成プロンプト（英語）。`/docs/guidelines/visual_prompt.md` に準拠する。Subject Motion + Scene Motion + Camera Motion の3要素で構成し、入力画像に既にある情報（外見・服装・場所）は記述しない。能動態の精密な動詞を使用する

#### 4.6.2 プロンプト言語ルールの更新

> - `image_prompt`, `keyframe_prompt`, `motion_prompt`, `reference_prompt`, `appearance`, `outfit`: 英語

#### 4.6.3 出力例の更新

設計書の入出力例を更新する。代表的な1シーンの例:

```json
{
  "scene_number": 1,
  "duration_sec": 4.0,
  "situation": "朝7時、スマホのアラームが鳴り響く。布団の中から手だけ出してアラームを止めようとするが、スマホを落としてしまい慌てて起き上がる",
  "camera_work": {
    "type": "close-up",
    "description": "スマートフォン画面のクローズアップから、慌てて起き上がる主人公へパンアップ"
  },
  "caption_text": "朝7時…まだ眠い…💤",
  "image_prompt": "A cozy Japanese bedroom at morning, warm sunlight streaming through white curtains, messy bed with pastel pink bedding, nightstand with alarm clock, warm filter, soft pastel tones, no people, background only, high quality",
  "keyframe_prompt": "@char lies in a cozy bed with pastel pink bedding, reaching one hand toward a smartphone on the nightstand, warm morning sunlight streaming through white curtains, close-up shot from above, sleepy atmosphere",
  "motion_prompt": "She reaches out from under the blanket to grab the smartphone, accidentally knocks it off the nightstand, then quickly sits up in a panic. The curtains sway gently in the morning breeze. Camera pans up from the smartphone to her startled face."
}
```

#### 4.6.4 後続レイヤーへの提供データの更新

| 後続レイヤー | 提供データ | 用途 |
| --- | --- | --- |
| Asset Generator | `SceneSpec.image_prompt` | 背景画像の生成プロンプト |
| Keyframe Engine | `SceneSpec.keyframe_prompt` | キーフレーム画像の生成プロンプト |
| Visual Core | `SceneSpec.motion_prompt` | 動画クリップの生成プロンプト |

### 4.7 Visual Core 設計書への修正指示

`visual_core_design.md` に以下の変更を反映する。

#### 4.7.1 アーキテクチャの更新

```
src/daily_routine/visual/
├── __init__.py
├── base.py              # VisualEngine ABC
├── engine.py            # DefaultVisualEngine + ファクトリ（キーフレーム生成は削除）
└── clients/
    ├── __init__.py
    ├── base.py          # VideoGeneratorClient ABC + ImageGeneratorClient ABC
    ├── runway.py        # RunwayClient（動画生成、既存）
    └── gen4_image.py    # RunwayImageClient（画像生成、新規。Keyframe Engine が使用）
```

#### 4.7.2 入力データの変更

| データ | 変更前 | 変更後 |
| --- | --- | --- |
| リファレンス画像 | `CharacterAsset.front_view`（全シーン共通） | `front_view` → キーフレーム画像（シーンごと） |
| プロンプト | `SceneSpec.video_prompt` | `SceneSpec.motion_prompt` |

#### 4.7.3 コスト見積もりの更新

| 項目 | 単価 | 8シーン |
| --- | --- | --- |
| Gen-4 Image Turbo（キーフレーム） | $0.02/枚 | $0.16 |
| Gen-4 Turbo（動画 10秒） | $0.50/本 | $4.00 |
| **合計** | | **$4.16** |

### 4.8 全体フロー設計書への修正指示

`t1_overall_flow.md` に以下の変更を反映する。

#### 4.8.1 データフロー図の更新

「3.3 Asset Generator → Visual Core」を以下に更新:

| データ | 使用レイヤー | 用途 |
| --- | --- | --- |
| `CharacterAsset.front_view` | Keyframe Engine | キーフレーム画像生成の参照画像（`@char` タグで参照） |
| `SceneSpec.keyframe_prompt` | Keyframe Engine | キーフレーム画像の生成プロンプト |
| `KeyframeAsset.image_path` | Visual Core | 動画生成の入力画像 |
| `SceneSpec.motion_prompt` | Visual Core | 動画クリップの生成プロンプト |

**重要:** 処理は2つの独立したパイプラインステップで実行される。まず KEYFRAME ステップで `front_view` + `keyframe_prompt` からキーフレーム画像を生成し、チェックポイントでユーザー承認を得た後、VISUAL ステップでキーフレーム画像 + `motion_prompt` から動画を生成する。

#### 4.8.2 技術スタック横断ビューの更新

| 用途 | 採用技術 | 使用レイヤー | ADR |
| --- | --- | --- | --- |
| キーフレーム画像生成 | Runway Gen-4 Image Turbo | Keyframe Engine | ADR-003 |
| 動画生成 | Runway Gen-4 Turbo | Visual Core | ADR-001, ADR-003 |
| 動画生成（高品質代替） | Runway Gen-4.5 | Visual Core | ADR-003 |

#### 4.8.3 パイプラインステップの更新

パイプラインフロー図に KEYFRAME ステップを追加:

```
Intelligence → Scenario → Asset → [チェックポイント]
  → Keyframe → [チェックポイント] → Visual → Audio → Post-Production
```

#### 4.8.4 コスト見積もりの更新

| レイヤー | 主要コスト | 見積もり |
| --- | --- | --- |
| Keyframe Engine | Gen-4 Image Turbo $0.02/枚 | 8シーンで **$0.16** |
| Visual Core（動画） | Gen-4 Turbo $0.50/10秒 | 8シーンで **$4.00** |
| 合計 | | **$4.16** |

### 4.9 仕様書（`specs/initial.md`）への修正指示

パイプライン説明を更新する:

> **Keyframe Engine（新規レイヤー）:**
> キャラクター正面画像を参照画像として、Gen-4 Image Turbo でシーン構図のキーフレーム画像を生成する。Asset と Visual の間に位置し、チェックポイントでユーザー承認を得てから次のステップに進む。
>
> **Visual Core（変更）:**
> Keyframe Engine が生成したキーフレーム画像を入力として、Gen-4 Turbo I2V で動画クリップを生成する。

パイプラインフロー図を7ステップに更新する:

> Intelligence → Scenario → Asset → **Keyframe** → Visual → Audio → Post-Production

## 5. 実装計画

### ステップ1: スキーマ変更

1. `schemas/scenario.py` の `SceneSpec` を変更（`video_prompt` → `keyframe_prompt` + `motion_prompt`）
2. `schemas/asset.py` に `KeyframeAsset` を追加、`AssetSet.keyframes` を追加
3. `schemas/pipeline_io.py` に `KeyframeInput` を追加
4. `schemas/project.py` の `PipelineStep` に `KEYFRAME` を追加
5. `config/manager.py` の `RunwayConfig.model` を `video_model` + `image_model` に分離
6. `configs/global.yaml` を更新
7. 既存テストの修正（`video_prompt` → `motion_prompt` への参照更新）

**完了条件:** `uv run pytest` で全テストパス

### ステップ2: Gen-4 Image クライアント実装

1. `visual/clients/gen4_image.py` に `RunwayImageClient` を実装
2. `referenceImages` + `@tag` 構文のリクエスト構築
3. ポーリング（既存 RunwayClient のパターンを踏襲）
4. 画像ダウンロード・保存
5. `tests/test_visual_gen4_image.py` にモックテストを作成

**完了条件:** モックテストでリクエスト構築・ポーリング・保存の一連のフローが動作する

### ステップ3: Keyframe Engine 実装

1. `keyframe/__init__.py`, `keyframe/base.py`, `keyframe/engine.py` を新規作成
2. `KeyframeEngineBase` ABC を定義（`generate_keyframes()` メソッド）
3. `RunwayKeyframeEngine` を実装（`StepEngine[KeyframeInput, AssetSet]` + `KeyframeEngineBase`）
4. `tests/test_keyframe_engine.py` にモックテストを作成

**完了条件:** モックテストでキーフレーム生成フロー（参照画像 + keyframe_prompt → キーフレーム画像 → AssetSet 更新）が動作する

### ステップ4: パイプライン統合

1. `pipeline/runner.py` の `STEP_ORDER` に `PipelineStep.KEYFRAME` を追加
2. `pipeline/runner.py` の `_build_input()` に KEYFRAME ケースを追加
3. `pipeline/runner.py` の `_build_input()` の VISUAL ケースを修正（KEYFRAME ステップの出力を使用）
4. `cli/app.py` でエンジン登録（`register_engine(PipelineStep.KEYFRAME, RunwayKeyframeEngine)`）
5. 既存パイプラインテストの修正

**完了条件:** `uv run pytest` で全テストパス。KEYFRAME ステップがパイプラインの正しい位置で実行される

### ステップ5: Visual Core の変更

1. `visual/engine.py` の `DefaultVisualEngine` からキーフレーム生成関連コードを削除
2. `generate_clips()` を変更: `front_view` + `video_prompt` → `keyframe.image_path` + `motion_prompt`
3. `_find_keyframe()` ヘルパーメソッドを追加
4. 既存テストの修正

**完了条件:** モックテストで `keyframe.image_path` + `motion_prompt` による動画生成が動作する。`uv run pytest` で全テストパス

### ステップ6: 設計書・仕様書の更新

1. `scenario_engine_design.md` のプロンプト生成ルールと入出力例を更新
2. `visual_core_design.md` のアーキテクチャ・入力データ・コスト見積もりを更新
3. `t1_overall_flow.md` のデータフロー・技術スタック・コスト見積もり・パイプラインフローを更新
4. `specs/initial.md` の Visual Core 説明を更新、Keyframe Engine の説明を追加

**完了条件:** ドキュメント間の整合性チェックがパスする

### ステップ7: 統合検証（PoC）

1. `poc/keyframe_pipeline_verify.py` を作成
2. 実際の Runway API でキーフレーム画像生成 → チェックポイント → 動画生成のフローを検証
3. シーン1のみで検証（キーフレーム $0.02 + 動画 $0.50 = $0.52）

**完了条件:** キーフレーム画像にキャラクターがシーン内に配置され、チェックポイントで一時停止し、承認後に動画でシーン内容が反映されることを確認

## 6. テスト方針

### 新規テスト

| ファイル | テスト内容 |
| --- | --- |
| `tests/test_visual_gen4_image.py` | `RunwayImageClient` のモックテスト（リクエスト構築、@tag参照、ポーリング） |
| `tests/test_keyframe_engine.py` | `RunwayKeyframeEngine` のモックテスト（全シーンのキーフレーム生成、AssetSet更新、save/load） |
| `tests/test_pipeline_keyframe.py` | KEYFRAME ステップのパイプライン統合テスト（STEP_ORDER、_build_input()、チェックポイント） |

### 既存テスト修正

| ファイル | 修正内容 |
| --- | --- |
| `tests/test_schemas/test_scenario.py` | `video_prompt` → `keyframe_prompt` + `motion_prompt` |
| `tests/test_schemas/test_asset.py` | `KeyframeAsset`、`AssetSet.keyframes` の追加 |
| `tests/test_visual_engine.py` | `front_view` → `keyframe.image_path`、`video_prompt` → `motion_prompt`、`image_client` 削除 |
| `tests/test_visual_client.py` | 変更なし（既存の RunwayClient テストはそのまま） |
| `tests/test_pipeline_runner.py` | `STEP_ORDER` に KEYFRAME が含まれることの確認、_build_input() の更新 |

## 7. コスト影響

| 項目 | 変更前 | 変更後 | 差分 |
| --- | --- | --- | --- |
| キーフレーム画像（8シーン） | $0（なし） | $0.16 | +$0.16 |
| 動画生成（8シーン × 10秒） | $4.00 | $4.00 | ±$0 |
| **合計** | **$4.00** | **$4.16** | **+$0.16** |

キーフレーム画像の追加コストは $0.02/枚と極めて低い。動画品質の大幅な向上に対して十分に見合うコスト増。

## 8. リスク

| リスク | 影響 | 対策 |
| --- | --- | --- |
| `video_prompt` 廃止による破壊的変更 | 既存テスト・Scenario Engine 実装の修正が必要 | ステップ1でスキーマ変更と全テスト修正を一括実施 |
| Gen-4 Image API の `@tag` 構文が期待通り動作しない | キャラクター再現性の低下 | ステップ7の PoC で事前検証。問題があれば Gemini フォールバックを検討 |
| キーフレーム画像の品質がシーン意図と乖離 | 動画品質に直結 | `keyframe_prompt` の書き方をガイドラインに準拠して検証・改善。KEYFRAME チェックポイントでユーザーが確認可能 |
| パイプラインステップ追加による既存テスト破壊 | `STEP_ORDER`、`_build_input()` の変更が多くのテストに影響 | ステップ4で集中的にパイプライン統合テストを修正 |
| KEYFRAME ステップの出力を VISUAL ステップが正しく取得できない | 動画生成が失敗する | `_build_input()` で `keyframe_engine.load_output()` を使用し、AssetSet 経由でキーフレームを受け渡す設計により疎結合を維持 |

## 9. 変更対象ファイル一覧

### 実装ファイル

| ファイル | 操作 | 内容 |
| --- | --- | --- |
| `src/daily_routine/schemas/scenario.py` | 修正 | `video_prompt` → `keyframe_prompt` + `motion_prompt` |
| `src/daily_routine/schemas/asset.py` | 修正 | `KeyframeAsset` 追加、`AssetSet.keyframes` 追加 |
| `src/daily_routine/schemas/pipeline_io.py` | 修正 | `KeyframeInput` 追加 |
| `src/daily_routine/schemas/project.py` | 修正 | `PipelineStep.KEYFRAME` 追加 |
| `src/daily_routine/config/manager.py` | 修正 | `RunwayConfig.model` → `video_model` + `image_model` |
| `configs/global.yaml` | 修正 | `model` → `video_model` + `image_model` |
| `src/daily_routine/keyframe/__init__.py` | 新規 | Keyframe Engine パッケージ |
| `src/daily_routine/keyframe/base.py` | 新規 | `KeyframeEngineBase` ABC |
| `src/daily_routine/keyframe/engine.py` | 新規 | `RunwayKeyframeEngine` 実装 |
| `src/daily_routine/visual/clients/gen4_image.py` | 新規 | `RunwayImageClient` 実装 |
| `src/daily_routine/visual/engine.py` | 修正 | `front_view` → `keyframe.image_path`、`video_prompt` → `motion_prompt`、`image_client` 削除 |
| `src/daily_routine/pipeline/runner.py` | 修正 | `STEP_ORDER` に KEYFRAME 追加、`_build_input()` 更新 |
| `src/daily_routine/cli/app.py` | 修正 | `RunwayKeyframeEngine` のエンジン登録追加 |

### テストファイル

| ファイル | 操作 | 内容 |
| --- | --- | --- |
| `tests/test_visual_gen4_image.py` | 新規 | `RunwayImageClient` モックテスト |
| `tests/test_keyframe_engine.py` | 新規 | `RunwayKeyframeEngine` モックテスト |
| `tests/test_pipeline_keyframe.py` | 新規 | KEYFRAME パイプライン統合テスト |
| `tests/test_schemas/test_scenario.py` | 修正 | `video_prompt` → `keyframe_prompt` + `motion_prompt` |
| `tests/test_schemas/test_asset.py` | 修正 | `KeyframeAsset` テスト追加 |
| `tests/test_visual_engine.py` | 修正 | keyframe 入力対応、`image_client` 削除 |
| `tests/test_pipeline_runner.py` | 修正 | `STEP_ORDER`、`_build_input()` の更新対応 |

### ドキュメントファイル

| ファイル | 操作 | 内容 |
| --- | --- | --- |
| `docs/designs/scenario_engine_design.md` | 修正 | プロンプト生成ルール・入出力例の更新 |
| `docs/designs/visual_core_design.md` | 修正 | アーキテクチャ・入力・コスト更新、キーフレーム生成責務の削除 |
| `docs/designs/t1_overall_flow.md` | 修正 | データフロー・技術スタック・コスト・パイプラインフローの更新 |
| `docs/specs/initial.md` | 修正 | パイプライン説明の更新、Keyframe Engine 追加 |

### PoC ファイル

| ファイル | 操作 | 内容 |
| --- | --- | --- |
| `poc/keyframe_pipeline_verify.py` | 新規 | 2段階パイプライン検証（キーフレーム → チェックポイント → 動画） |

**合計:** 修正 15ファイル、新規 7ファイル
