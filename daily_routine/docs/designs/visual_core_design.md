# Visual Core 設計書

## 1. 概要

- **対応する仕様書セクション:** 3.5章（Visual Core）
- **対応するサブタスク:** T1-4（Visual Core）
- **依存するサブタスク:** T0-1（プロジェクト骨格）、T0-2（動画生成AI比較検証）
- **このサブタスクで実現すること:**
  - Runway Gen-4 Turbo（ADR-001 で採用、コスト効率重視）を使用した Image-to-Video 動画クリップ生成モジュールの実装
  - パイプラインの `PipelineStep.VISUAL` として統合可能なレイヤー実装
  - 将来の Veo 3 追加を見据えた ABC によるクライアント抽象化

## 2. スコープ

### 対象範囲

- Visual Core レイヤー（`src/daily_routine/visual/`）の本格実装
- Runway Gen-4 Turbo API クライアントの本番用実装
- GCS アップローダー実装（Runway は URL 指定入力のため、リファレンス画像を GCS にアップロードして使用）
- 動画生成クライアントの ABC 定義（プロバイダ追加に備えた抽象化）
- シーンごとの動画クリップ生成（リファレンス画像 + テキストプロンプト → 動画）
- スキーマ拡張（`schemas/visual.py`）
- 設定スキーマ追加（`config/manager.py` に `VisualConfig`）
- `ApiKeys` に `runway` フィールド明示追加
- ユニットテスト

### 対象外

- Veo 3 クライアント実装（高品質版が必要になった場合に別タスクで実施）
- 複数候補生成・品質ベースの最良選択（T4-1 品質チェックシステムと同時に実施）
- Scenario → Asset → Visual の結合検証（T2-2 で実施）
- Sound-Image Sync（T2-3 で実施）
- 自動品質チェックシステム（T4-1 で実施）
- Web UI でのチェックポイント確認画面（T4-2 で実施）
- パイプラインオーケストレーションへの統合（T1-1 で実施、本タスクではインターフェースのみ定義）

## 3. 技術設計

### 3.1 アーキテクチャ

```
src/daily_routine/visual/
├── __init__.py
├── base.py              # VisualEngine ABC（レイヤー境界）
├── engine.py            # DefaultVisualEngine 具象実装 + ファクトリ関数
└── clients/
    ├── __init__.py
    ├── base.py          # VideoGeneratorClient ABC
    └── runway.py        # Runway Gen-4 Turbo クライアント（本番用）

src/daily_routine/utils/
└── uploader.py          # ImageUploader ABC + GcsUploader（画像の GCS アップロード）
```

**設計判断:**

- `clients/` サブパッケージを設けてクライアント実装を分離する。将来 Veo 3 等のプロバイダを追加する際に `clients/veo.py` を追加するだけで済む。
- `engine.py` がクライアントの詳細を隠蔽し、上位レイヤーからは統一インターフェースでアクセスする。
- Runway は URL 指定入力のため、`utils/uploader.py` に GCS アップローダーを実装する（他レイヤーからも再利用可能）。
- T1-4 では Runway のみ実装。Veo 3 クライアントは高品質版が必要になった場合に `clients/veo.py` として追加する。

### 3.2 レイヤー境界（ABC）

`base.py` でレイヤーの抽象インターフェースを定義する。他レイヤーからの依存は `schemas/` 経由のみ。

```python
from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet
from daily_routine.schemas.scenario import Scenario
from daily_routine.schemas.visual import VideoClipSet


class VisualEngine(ABC):
    """Visual Core レイヤーの抽象インターフェース."""

    @abstractmethod
    async def generate_clips(
        self,
        scenario: Scenario,
        assets: AssetSet,
        output_dir: Path,
    ) -> VideoClipSet:
        """シナリオとアセットに基づき全シーンの動画クリップを生成する.

        Args:
            scenario: シナリオ仕様
            assets: Asset Generator の出力（リファレンス画像セット）
            output_dir: 動画クリップの出力ディレクトリ
        """
        ...

    @abstractmethod
    async def generate_scene_clip(
        self,
        scene_number: int,
        prompt: str,
        reference_image: Path,
        output_path: Path,
    ) -> Path:
        """単一シーンの動画クリップを生成する.

        Args:
            scene_number: シーン番号
            prompt: 動画生成プロンプト
            reference_image: リファレンス画像パス
            output_path: 動画ファイルの保存先パス
        """
        ...
```

### 3.3 動画生成クライアント共通インターフェース

PoC の `VideoGeneratorClient` を本番用に昇格・拡張する。

```python
from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class VideoGenerationRequest(BaseModel):
    """動画生成リクエスト."""

    reference_image_path: Path = Field(description="リファレンス画像のパス")
    prompt: str = Field(description="動画生成プロンプト")
    duration_sec: int = Field(default=8, description="動画の長さ（秒）")
    aspect_ratio: str = Field(default="9:16", description="アスペクト比")


class VideoGenerationResult(BaseModel):
    """動画生成結果."""

    video_path: Path = Field(description="生成された動画ファイルのパス")
    generation_time_sec: float = Field(description="生成にかかった時間（秒）")
    model_name: str = Field(description="使用モデル名")
    cost_usd: float | None = Field(default=None, description="推定コスト（USD）")


class VideoGeneratorClient(ABC):
    """動画生成AIクライアントの共通インターフェース."""

    @abstractmethod
    async def generate(self, request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
        """リファレンス画像から動画を生成して保存し、結果を返す.

        Args:
            request: 動画生成リクエスト
            output_path: 動画ファイルの保存先パス
        """
        ...
```

**PoC からの変更点:**

| 項目              | PoC                    | 本番                                     |
| ----------------- | ---------------------- | ---------------------------------------- |
| `metadata: dict`  | リクエスト・結果に含む | 削除（プロバイダ固有の処理はクライアント内部で解決） |
| 出力パス          | クライアント内部で決定 | 呼び出し元が `output_path` で指定        |
| Field description | なし                   | Pydantic `Field(description=...)` 付与   |

### 3.4 Runway Gen-4 Turbo クライアント

PoC（`poc/video_ai/clients/runway.py`）をベースに、本番用に昇格する。

**PoC からの変更点:**

| 項目         | PoC                              | 本番                                     |
| ------------ | -------------------------------- | ---------------------------------------- |
| モデルID     | `gen4_turbo`                     | `gen4_turbo`                             |
| 認証         | Bearer Token                     | 同左（環境変数 `DAILY_ROUTINE_API_KEY_RUNWAY`） |
| リトライ     | なし                             | 指数バックオフ付きリトライ（`tenacity`） |
| 設定         | コンストラクタ引数               | `GlobalConfig` から読み込み              |
| 出力先       | クライアント内で決定             | 呼び出し元から `output_path` で指定      |
| タイムアウト | 5分固定                          | 設定可能（デフォルト5分）                |
| 動画長       | 10秒固定                        | 5, 10秒から選択可能（デフォルト10秒）   |
| 画像入力     | URL 指定                         | GCS アップローダー経由で URL を取得      |

```python
class RunwayClient(VideoGeneratorClient):
    """Runway Gen-4 Turbo クライアント."""

    def __init__(
        self,
        api_key: str,
        uploader: "ImageUploader",
        model: str = "gen4_turbo",
    ) -> None:
        ...

    async def generate(self, request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
        """リファレンス画像をGCSにアップロードし、Runway APIで動画を生成する.

        処理フロー:
        1. リファレンス画像を GCS にアップロードして公開 URL を取得
        2. image_to_video API で動画生成タスクを作成
        3. タスクIDでポーリング（5秒間隔、最大5分）
        4. 完了後、動画 URL からダウンロードして output_path に保存
        """
        ...
```

**API仕様:**

- エンドポイント: `https://api.dev.runwayml.com/v1/image_to_video`
- 認証: Bearer Token + `X-Runway-Version: 2024-11-06`
- 入力: 画像 URL + テキストプロンプト
- 出力: 動画 URL（ダウンロード）
- 動画長: 5, 10秒（`duration` で指定、デフォルト10秒）
- アスペクト比: 9:16, 16:9
- フレームレート: 24 FPS（仕様書の最終出力は 30/60 FPS。FPS 変換は Post-Production レイヤーで実施する）
- コスト: $0.05/秒 × 10秒 = $0.50/クリップ

**リクエスト形式:**

```json
{
  "model": "gen4_turbo",
  "promptImage": "https://storage.googleapis.com/bucket/image.png",
  "promptText": "TEXT_PROMPT",
  "duration": 10,
  "ratio": "9:16"
}
```

**GCS アップローダー:**

Runway は URL 指定での画像入力が必要なため、`src/daily_routine/utils/uploader.py` に画像アップロード機能を実装する。

```python
from abc import ABC, abstractmethod
from pathlib import Path


class ImageUploader(ABC):
    """画像アップロードの抽象インターフェース."""

    @abstractmethod
    async def upload(self, image_path: Path) -> str:
        """画像をアップロードし、公開URLを返す."""
        ...


class GcsUploader(ImageUploader):
    """Google Cloud Storage へのアップローダー."""

    def __init__(self, bucket_name: str, prefix: str = "visual/") -> None:
        ...

    async def upload(self, image_path: Path) -> str:
        """画像を GCS にアップロードし、公開 URL を返す."""
        ...
```

### 3.5 VisualEngine 具象実装

クライアントの詳細を隠蔽し、シナリオに基づく動画クリップ生成を行う。

```python
class DefaultVisualEngine(VisualEngine):
    """Visual Core のデフォルト実装."""

    def __init__(self, client: VideoGeneratorClient) -> None:
        ...

    async def generate_clips(
        self,
        scenario: Scenario,
        assets: AssetSet,
        output_dir: Path,
    ) -> VideoClipSet:
        """全シーンの動画クリップを生成する.

        処理フロー:
        1. シナリオの各シーンについてリファレンス画像を特定
        2. 各シーンで generate_scene_clip を順次呼び出し
        3. VideoClipSet を構築して返す
        """
        ...

    async def generate_scene_clip(
        self,
        scene_number: int,
        prompt: str,
        reference_image: Path,
        output_path: Path,
    ) -> Path:
        """単一シーンの動画クリップを生成する.

        Args:
            scene_number: シーン番号
            prompt: SceneSpec.video_prompt
            reference_image: キャラクターの正面画像パス
            output_path: 動画ファイルの保存先パス

        Returns:
            生成された動画ファイルパス
        """
        ...
```

**リファレンス画像の選択ロジック:**

各シーンで使用するリファレンス画像は、Asset Generator の出力からキャラクターの正面画像（`front_view`）を使用する。

```
SceneSpec → (シーン内容に登場する)キャラクター名 → CharacterAsset.front_view
```

- シーンに複数キャラクターが登場する場合: メインキャラクター（`Scenario.characters[0]`）の正面画像を使用
- 仕様書 3.5章: 「リファレンス画像を全シーンで同一の参照画像として動画生成AIに入力する」に準拠

**順次処理の理由:**

- Runway API のレート制限が存在する
- 動画生成は1クリップあたり約76秒かかるため、並列化してもレート制限に抵触するリスクが高い
- 初期実装では安全な順次処理とし、Phase 2以降でレート制限の実データを踏まえて並列化を検討する

**ファクトリ関数:**

```python
def create_visual_engine(config: GlobalConfig) -> DefaultVisualEngine:
    """設定に基づいてVisualEngineを構築する.

    Args:
        config: グローバル設定

    Returns:
        プロバイダに応じたVisualEngineインスタンス

    Raises:
        ValueError: 不明なプロバイダ、または必要な設定が不足
    """
    ...
```

### 3.6 プロバイダ設定

ADR-001 の決定に従い、Runway Gen-4 Turbo をデフォルトプロバイダとして設定する。将来の Veo 3 追加に備えて `provider` 設定を用意する。

**設定項目の追加（`configs/global.yaml`）:**

```yaml
visual:
  provider: "runway" # "runway"（将来: "veo" も対応）
  runway:
    model: "gen4_turbo"
    gcs_bucket: "" # GCS バケット名（画像アップロード用）
```

**設定スキーマの追加（`config/manager.py`）:**

```python
class RunwayConfig(BaseModel):
    """Runway Gen-4 Turbo 固有設定."""

    model: str = Field(default="gen4_turbo", description="Runwayモデル名")
    gcs_bucket: str = Field(default="", description="GCSバケット名（画像アップロード用）")


class VisualConfig(BaseModel):
    """Visual Core 設定."""

    provider: str = Field(default="runway", description="動画生成プロバイダ: runway")
    runway: RunwayConfig = Field(default_factory=RunwayConfig)
```

`GlobalConfig` に `visual: VisualConfig` を追加する。

**ApiKeys への `runway` 明示追加:**

```python
class ApiKeys(BaseModel):
    """APIキー設定."""

    youtube_data_api: str = ""
    openai: str = ""
    google_ai: str = ""
    runway: str = ""  # 追加

    model_config = {"extra": "allow"}
```

### 3.7 エラーハンドリング

| エラー種別                         | 対応                                                       |
| ---------------------------------- | ---------------------------------------------------------- |
| API レート制限（429）              | 指数バックオフリトライ（`tenacity`、最大3回、初回待機5秒） |
| API タイムアウト（ポーリング超過） | `TimeoutError` を `StepExecutionError` にラップして伝播    |
| 動画未生成（API が動画を返さない） | リトライ（最大3回）後、`StepExecutionError` で停止         |
| GCP設定未設定                      | 起動時に `ValueError` で即時停止                           |
| リファレンス画像が存在しない       | `FileNotFoundError` で即時停止                             |
| 不明なプロバイダ指定               | `ValueError` で即時停止                                    |

**リトライ設定:**

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=5, min=5, max=60),
    retry=retry_if_exception_type((httpx.HTTPStatusError, TimeoutError)),
)
async def _call_api(...):
    ...
```

## 4. スキーマ設計

### 4.1 スキーマ変更（`schemas/visual.py`）

既存の `VideoClip` / `VideoClipSet` を拡張する。

```python
"""Visual Core入出力のスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class VideoClip(BaseModel):
    """生成された動画クリップ."""

    scene_number: int = Field(description="シーン番号")
    clip_path: Path = Field(description="動画ファイルパス")
    duration_sec: float = Field(description="動画の長さ（秒）")
    model_name: str = Field(description="使用モデル名")
    cost_usd: float | None = Field(default=None, description="推定コスト（USD）")
    quality_score: float | None = Field(
        default=None,
        description="品質スコア（0-1）、品質チェック後に設定",
    )
    generation_time_sec: float | None = Field(
        default=None,
        description="生成にかかった時間（秒）",
    )


class VideoClipSet(BaseModel):
    """Visual Coreの出力."""

    clips: list[VideoClip] = Field(description="シーンごとの動画クリップリスト")
    total_cost_usd: float = Field(default=0.0, description="合計推定コスト（USD）")
    provider: str = Field(default="", description="使用プロバイダ名")
```

**変更点まとめ:**

| 対象           | 変更内容                                                                                             |
| -------------- | ---------------------------------------------------------------------------------------------------- |
| `VideoClip`    | `model_name`, `cost_usd`, `generation_time_sec` を追加。全フィールドに `Field(description=...)` 付与 |
| `VideoClipSet` | `total_cost_usd`, `provider` を追加。`clips` に `Field(description=...)` 付与                        |

## 5. 入出力仕様

### 入力

| ソース          | データ                                     | スキーマ                    |
| --------------- | ------------------------------------------ | --------------------------- |
| Scenario Engine | シナリオ（シーン一覧、動画生成プロンプト） | `schemas.scenario.Scenario` |
| Asset Generator | アセットセット（キャラクター画像パス）     | `schemas.asset.AssetSet`    |
| 設定            | プロバイダ選択、GCP設定                    | `GlobalConfig.visual`       |

**入力データの関係:**

- **動画生成プロンプト:** `SceneSpec.video_prompt`（Scenario Engine が生成済み）
- **リファレンス画像:** `CharacterAsset.front_view`（Asset Generator が生成済み）
- **出力先ディレクトリ:** `projects/{project_id}/clips/`

### 出力

| データ             | スキーマ                      | 保存先                                                                |
| ------------------ | ----------------------------- | --------------------------------------------------------------------- |
| 動画クリップセット | `schemas.visual.VideoClipSet` | `projects/{id}/clips/`                                                |
| 各シーンの動画     | MP4ファイル                   | `projects/{id}/clips/scene_{nn}.mp4`                                  |
| メタデータ JSON    | -                             | `projects/{id}/clips/metadata.json`（プロバイダ、コスト、生成時間等） |

### 出力ディレクトリ構造

```
projects/{project_id}/clips/
├── metadata.json
├── scene_01.mp4
├── scene_02.mp4
└── ...
```

### 入出力例

「OLの一日」（3シーン構成）を例に、`generate_clips()` の入力と出力を示す。

#### 入力例: Scenario（Scenario Engine の出力から Visual Core が使用するフィールド）

```json
{
  "title": "忙しいOLの一日",
  "total_duration_sec": 24.0,
  "characters": [
    {
      "name": "Aoi",
      "appearance": "20代後半の日本人女性、黒髪ロング、ストレート",
      "outfit": "白ブラウス、ネイビーのタイトスカート、ベージュのパンプス",
      "reference_prompt": "A semi-realistic Japanese woman in her late 20s, long straight black hair, white blouse, navy tight skirt"
    }
  ],
  "props": [
    {
      "name": "coffee_cup",
      "description": "白いテイクアウトコーヒーカップ",
      "image_prompt": "A white takeout coffee cup, studio lighting, plain white background"
    }
  ],
  "scenes": [
    {
      "scene_number": 1,
      "duration_sec": 8.0,
      "situation": "朝、マンションの玄関を出て歩き始める",
      "camera_work": { "type": "wide", "description": "全身が映るワイドショット" },
      "caption_text": "AM 7:30 出勤",
      "image_prompt": "Modern apartment entrance, morning sunlight, urban residential area",
      "video_prompt": "A young Japanese woman in a white blouse and navy skirt walks out of a modern apartment entrance in the morning sunlight, wide shot, smooth walking motion"
    },
    {
      "scene_number": 2,
      "duration_sec": 8.0,
      "situation": "カフェでコーヒーを受け取り、一口飲む",
      "camera_work": { "type": "close-up", "description": "上半身のクローズアップ" },
      "caption_text": "毎朝のルーティン",
      "image_prompt": "Modern cafe interior, warm lighting, counter background",
      "video_prompt": "A young Japanese woman in a white blouse receives a coffee cup at a cafe counter and takes a sip, close-up shot, warm indoor lighting"
    },
    {
      "scene_number": 3,
      "duration_sec": 8.0,
      "situation": "オフィスのデスクでPCに向かって作業する",
      "camera_work": { "type": "POV", "description": "斜め後ろからのPOVショット" },
      "caption_text": "今日も頑張る",
      "image_prompt": "Modern office desk with laptop, bright office lighting",
      "video_prompt": "A young Japanese woman in a white blouse sits at a modern office desk typing on a laptop, POV shot from behind, bright office environment"
    }
  ],
  "bgm_direction": "明るくテンポの良いポップス、BPM 120前後"
}
```

#### 入力例: AssetSet（Asset Generator の出力から Visual Core が使用するフィールド）

```json
{
  "characters": [
    {
      "character_name": "Aoi",
      "front_view": "projects/OLの一日_20260223_100000/assets/character/Aoi/front.png",
      "side_view": "projects/OLの一日_20260223_100000/assets/character/Aoi/side.png",
      "back_view": "projects/OLの一日_20260223_100000/assets/character/Aoi/back.png",
      "expressions": {
        "smile": "projects/OLの一日_20260223_100000/assets/character/Aoi/expressions/smile.png"
      }
    }
  ],
  "props": [
    {
      "name": "coffee_cup",
      "image_path": "projects/OLの一日_20260223_100000/assets/props/coffee_cup.png"
    }
  ],
  "backgrounds": [
    {
      "scene_number": 1,
      "description": "マンション玄関",
      "image_path": "projects/OLの一日_20260223_100000/assets/backgrounds/scene_01.png"
    },
    {
      "scene_number": 2,
      "description": "カフェ内装",
      "image_path": "projects/OLの一日_20260223_100000/assets/backgrounds/scene_02.png"
    },
    {
      "scene_number": 3,
      "description": "オフィスデスク",
      "image_path": "projects/OLの一日_20260223_100000/assets/backgrounds/scene_03.png"
    }
  ]
}
```

**Visual Core が使用するフィールド:** `characters[0].front_view`（リファレンス画像）と各 `scenes[].video_prompt`。`props`, `backgrounds`, `side_view`, `back_view` は Visual Core では使用しない（Asset Generator / Post-Production が使用する）。

#### 処理の流れ

```
シーン1: front.png + video_prompt → RunwayClient.generate() → scene_01.mp4 (10秒, $0.50, 75.6秒)
シーン2: front.png + video_prompt → RunwayClient.generate() → scene_02.mp4 (10秒, $0.50, 78.2秒)
シーン3: front.png + video_prompt → RunwayClient.generate() → scene_03.mp4 (10秒, $0.50, 74.1秒)
```

- 全シーンで同一のリファレンス画像（`front.png`）を使用
- 各シーンの `video_prompt` が動きやカメラワークを指示
- 順次処理（シーン1完了後にシーン2を開始）

#### 出力例: VideoClipSet

```json
{
  "clips": [
    {
      "scene_number": 1,
      "clip_path": "projects/OLの一日_20260223_100000/clips/scene_01.mp4",
      "duration_sec": 10.0,
      "model_name": "gen4_turbo",
      "cost_usd": 0.5,
      "quality_score": null,
      "generation_time_sec": 75.6
    },
    {
      "scene_number": 2,
      "clip_path": "projects/OLの一日_20260223_100000/clips/scene_02.mp4",
      "duration_sec": 10.0,
      "model_name": "gen4_turbo",
      "cost_usd": 0.5,
      "quality_score": null,
      "generation_time_sec": 78.2
    },
    {
      "scene_number": 3,
      "clip_path": "projects/OLの一日_20260223_100000/clips/scene_03.mp4",
      "duration_sec": 10.0,
      "model_name": "gen4_turbo",
      "cost_usd": 0.5,
      "quality_score": null,
      "generation_time_sec": 74.1
    }
  ],
  "total_cost_usd": 1.5,
  "provider": "runway"
}
```

#### 出力例: metadata.json

```json
{
  "project_id": "OLの一日_20260223_100000",
  "provider": "runway",
  "model_name": "gen4_turbo",
  "total_scenes": 3,
  "total_cost_usd": 1.5,
  "total_generation_time_sec": 227.9,
  "generated_at": "2026-02-23T10:05:30"
}
```

#### 出力例: ディレクトリ

```
projects/OLの一日_20260223_100000/clips/
├── metadata.json
├── scene_01.mp4    # 10秒、マンション玄関から歩き出すAoi
├── scene_02.mp4    # 10秒、カフェでコーヒーを飲むAoi
└── scene_03.mp4    # 10秒、オフィスでPC作業するAoi
```

## 6. 実装計画

### ステップ1: スキーマ拡張・設定追加

- `src/daily_routine/schemas/visual.py` を拡張（`model_name`, `cost_usd`, `generation_time_sec`, `total_cost_usd`, `provider` 追加）
- `src/daily_routine/config/manager.py` に `RunwayConfig`, `VisualConfig` を追加し、`GlobalConfig.visual` を追加
- `ApiKeys` に `runway: str = ""` を明示追加
- **完了条件:** `uv run pytest` で既存テストがパス。新スキーマで `VideoClipSet` が生成できる

### ステップ2: GCS アップローダー + 動画生成クライアント共通インターフェース + Runway クライアント

- `src/daily_routine/utils/uploader.py` に `ImageUploader` ABC + `GcsUploader` を実装
- `src/daily_routine/visual/clients/base.py` に `VideoGenerationRequest`, `VideoGenerationResult`, `VideoGeneratorClient` ABC を定義
- `src/daily_routine/visual/clients/runway.py` に `RunwayClient` を実装（PoC の Runway クライアントをベースに本番化）
- Bearer Token 認証、GCS アップロード、ポーリング、tenacity リトライ
- **完了条件:** モックテストで `RunwayClient.generate()` が正しいリクエストを構築し、ポーリング後に動画を保存する

### ステップ3: VisualEngine ABC + 具象実装

- `src/daily_routine/visual/base.py` に `VisualEngine` ABC を定義
- `src/daily_routine/visual/engine.py` に `DefaultVisualEngine` を実装
- リファレンス画像の選択ロジック、ファクトリ関数（`create_visual_engine`）
- **完了条件:** モックテストで `generate_clips()` がシナリオの全シーンに対して動画を生成し、`VideoClipSet` を返す

### ステップ4: ユニットテスト

- 全コンポーネントのモックテスト
- **完了条件:** `uv run pytest tests/test_visual*.py` が全テストパス

## 7. テスト方針

### 7.1 全体方針

- **AI API呼び出しなし:** 全テストをモックで実行。外部 API（Runway）は呼び出さない
- テストフレームワーク: `pytest` + `pytest-asyncio`
- 一時ディレクトリ: `tmp_path` フィクスチャを使用

### 7.2 テストファイル構成

```
tests/
├── test_visual_client.py    # RunwayClient のモックテスト
└── test_visual_engine.py    # DefaultVisualEngine のモックテスト
```

### 7.3 テストケース一覧

#### `test_visual_client.py` — Runway クライアント

| テスト名                                                   | 検証内容                                                                  |
| ---------------------------------------------------------- | ------------------------------------------------------------------------- |
| `test_runway_generate_正常_動画ファイル生成`               | GCSアップロード → API呼び出し → ポーリング → ダウンロード → 保存の一連フロー |
| `test_runway_generate_ポーリングタイムアウト_TimeoutError` | 5分超過で `TimeoutError`                                                  |
| `test_runway_generate_動画未返却_RuntimeError`             | API がタスク失敗を返した場合                                              |
| `test_runway_generate_リクエスト構築_URLとプロンプト`      | リクエストペイロードの構造が正しいこと                                    |

#### `test_visual_engine.py` — エンジン

| テスト名                                                          | 検証内容                                             |
| ----------------------------------------------------------------- | ---------------------------------------------------- |
| `test_generate_clips_全シーン動画生成`                            | シナリオの全シーンに対してクライアントが呼び出される |
| `test_generate_clips_出力VideoClipSetの構造`                      | `clips` のサイズ、各 `VideoClip` のフィールド        |
| `test_generate_clips_コスト集計`                                  | `total_cost_usd` がクリップのコスト合計と一致        |
| `test_generate_clips_プロバイダ名設定`                            | `VideoClipSet.provider` が正しく設定される           |
| `test_generate_scene_clip_リファレンス画像不在_FileNotFoundError` | 存在しない画像パスでエラー                           |
| `test_create_visual_engine_runwayプロバイダ`                      | 設定 `provider: "runway"` で `RunwayClient` が使用される |
| `test_create_visual_engine_不明プロバイダ_ValueError`             | 不明な provider でエラー                             |

### 7.4 統合テスト（手動、CI対象外）

- 実際の Runway API を呼び出して動画を生成
- リファレンス画像からの同一性維持を目視確認
- T2-2（Scenario → Asset → Visual 結合）で本格実施

## 8. コスト見積もり

| プロバイダ         | 単価     | 動画長 | 1クリップあたり | 10シーン |
| ------------------ | -------- | ------ | --------------- | -------- |
| Runway Gen-4 Turbo | $0.05/秒 | 10秒   | $0.50           | $5.00    |

**参考（Veo 3、高品質代替時）:**

| プロバイダ         | 単価           | 動画長 | 1クリップあたり | 10シーン |
| ------------------ | -------------- | ------ | --------------- | -------- |
| Veo 3（音声なし） | $0.50/秒       | 8秒    | $4.00           | $40.00   |
| Veo 3（音声あり） | $0.75/秒       | 8秒    | $6.00           | $60.00   |

## 9. リスク・検討事項

| リスク                                    | 影響                                    | 対策                                                                     |
| ----------------------------------------- | --------------------------------------- | ------------------------------------------------------------------------ |
| Runway の品質が Veo 3 より劣る（8.5 vs 9.5） | 顔の類似度がやや低い（7.9）              | 初期フェーズでは許容。品質重視時に Veo 3 に切り替え可能                   |
| GCS アップロードの依存                        | GCS バケットの設定が前提                 | セットアップ手順をドキュメント化                                          |
| 動画生成の長い所要時間（約76秒/クリップ）     | 10シーンで約13分                         | ログに進捗を出力（n/N シーン完了）。将来の並列化で短縮可能              |
| API 仕様変更                              | クライアント実装の修正が必要            | モデル名・エンドポイントを設定値として外出し。ABC でクライアントを抽象化 |
| レート制限                                | 連続生成時にスロットリング              | `tenacity` による指数バックオフリトライ                                  |

## 10. 将来の拡張（スコープ外メモ）

本タスクのスコープ外だが、将来対応が必要な項目を記録する。

| 項目 | 対応タイミング | 概要 |
| --- | --- | --- |
| Veo 3 クライアント | 高品質版対応タスク | `visual/clients/veo.py` を追加。base64 入力のため GCS アップロード不要。品質重視の本番運用時に切り替え |
| 複数候補生成・品質選択 | T4-1（品質チェック） | `candidates` パラメータ + AI ベース品質評価（PoC `poc/video_ai/evaluate.py` を本番化） |
| 並列生成 | Phase 2以降 | `asyncio.Semaphore` によるレート制限考慮の並列化 |

## 11. 変更対象ファイル一覧

| ファイル | 操作 | 内容 |
| --- | --- | --- |
| `src/daily_routine/schemas/visual.py` | 修正 | `model_name`, `cost_usd`, `generation_time_sec`, `total_cost_usd`, `provider` 追加 |
| `src/daily_routine/config/manager.py` | 修正 | `RunwayConfig`, `VisualConfig` 追加、`GlobalConfig.visual` 追加、`ApiKeys.runway` 追加 |
| `src/daily_routine/visual/__init__.py` | 修正 | 公開インターフェースのエクスポート |
| `src/daily_routine/visual/base.py` | 新規 | `VisualEngine` ABC |
| `src/daily_routine/visual/engine.py` | 新規 | `DefaultVisualEngine` + `create_visual_engine` ファクトリ |
| `src/daily_routine/visual/clients/__init__.py` | 新規 | パッケージ初期化 |
| `src/daily_routine/visual/clients/base.py` | 新規 | `VideoGenerationRequest`, `VideoGenerationResult`, `VideoGeneratorClient` ABC |
| `src/daily_routine/visual/clients/runway.py` | 新規 | `RunwayClient` 実装（Runway Gen-4 Turbo） |
| `src/daily_routine/utils/uploader.py` | 新規 | `ImageUploader` ABC + `GcsUploader` |
| `tests/test_visual_client.py` | 新規 | `RunwayClient` モックテスト |
| `tests/test_visual_engine.py` | 新規 | `DefaultVisualEngine` モックテスト |

**合計:** 修正 3ファイル、新規 8ファイル（プロダクション 6、テスト 2）

## 12. 参考資料

- 仕様書: `/docs/specs/initial.md` 3.5章
- ADR-001: `/docs/adrs/001_video_generation_ai.md`（Runway デフォルト採用、Veo 3 高品質代替）
- Runway API ドキュメント: https://dev.runwayml.com/
- PoC 実装（Runway）: `poc/video_ai/clients/runway.py`、`poc/video_ai/clients/base.py`
- 既存スキーマ: `src/daily_routine/schemas/visual.py`、`src/daily_routine/schemas/scenario.py`、`src/daily_routine/schemas/asset.py`
- CLI基盤設計書: `/docs/designs/cli_pipeline_design.md`（`StepEngine` ABC、パイプライン統合）
- Asset Generator設計書: `/docs/designs/asset_generator_design.md`（リファレンス画像の出力仕様）
