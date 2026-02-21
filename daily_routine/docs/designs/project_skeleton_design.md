# プロジェクト骨格・共通データスキーマ設計書

## 1. 概要

- **対応する仕様書セクション:** 2章（システムアーキテクチャ）、6章（データ管理）
- **このサブタスクで実現すること:**
  - Pythonパッケージの初期構成（uv + pyproject.toml）
  - 6レイヤー間のデータフローを定義するPydanticスキーマ
  - ソースコードとランタイムデータの両方のディレクトリ構造
  - YAML形式の設定管理（グローバル設定 + プロジェクト設定）
  - CLI骨格（Typer）の最小構成

## 2. スコープ

### 対象範囲

- Pythonパッケージ構成とビルド設定（`pyproject.toml`）
- 全レイヤー間の入出力データ型定義（Pydanticモデル）
- プロジェクトランタイムデータのディレクトリ構造管理
- グローバル設定（APIキー等）とプロジェクト設定の管理機構
- CLIのエントリーポイントとサブコマンド骨格
- 基本的なロギング設定

### 対象外

- 各レイヤーのビジネスロジック実装（Phase 1）
- チェックポイント・再開機構の詳細実装（T1-1で実装）
- Web UI（T4-2で実装）
- テスト基盤（各レイヤーの設計書で個別に定義）

## 3. 技術設計

### 3.1 技術スタック

| 要素                 | 採用技術           | バージョン |
| -------------------- | ------------------ | ---------- |
| 言語                 | Python             | 3.12+      |
| パッケージ管理       | uv                 | 最新       |
| データバリデーション | Pydantic           | v2         |
| CLI                  | Typer              | 最新       |
| 設定管理             | PyYAML + Pydantic  | -          |
| ロギング             | Python標準 logging | -          |

### 3.2 ソースコードディレクトリ構造

```
daily_routine/                  # リポジトリルート
├── pyproject.toml
├── poc/                        # PoC・技術検証用（本番パッケージ外）
│   ├── video_ai/              # T0-2: 動画生成AI比較検証
│   └── image_gen/             # T0-3: 画像生成AI比較検証
├── src/
│   └── daily_routine/          # メインパッケージ
│       ├── __init__.py
│       ├── cli/                # CLI層
│       │   ├── __init__.py
│       │   └── app.py          # Typerアプリケーション定義
│       ├── schemas/            # 共通Pydanticスキーマ
│       │   ├── __init__.py
│       │   ├── project.py      # プロジェクト設定・メタデータ
│       │   ├── intelligence.py # Intelligence Engine入出力
│       │   ├── scenario.py     # Scenario Engine入出力
│       │   ├── asset.py        # Asset Generator入出力
│       │   ├── visual.py       # Visual Core入出力
│       │   ├── audio.py        # Audio Engine入出力
│       │   └── post.py         # Post-Production入出力
│       ├── config/             # 設定管理
│       │   ├── __init__.py
│       │   └── manager.py      # 設定読み込み・バリデーション
│       ├── pipeline/           # パイプラインオーケストレーション
│       │   ├── __init__.py
│       │   └── runner.py       # パイプライン実行制御（骨格のみ）
│       ├── intelligence/       # Intelligence Engine
│       │   └── __init__.py
│       ├── scenario/           # Scenario Engine
│       │   └── __init__.py
│       ├── asset/              # Asset Generator
│       │   └── __init__.py
│       ├── visual/             # Visual Core
│       │   └── __init__.py
│       ├── audio/              # Audio Engine
│       │   └── __init__.py
│       └── postproduction/     # Post-Production
│           └── __init__.py
└── tests/
    ├── __init__.py
    └── test_schemas/           # スキーマのテスト
        └── __init__.py
```

**設計判断:**

- `src/` レイアウトを採用。インストールされたパッケージとソースの混同を防ぐ。
- 各レイヤーは独立したサブパッケージとし、Phase 1で個別に実装を追加していく。
- `schemas/` はレイヤーごとにファイルを分割。全レイヤーが参照する共通パッケージとして配置。

### 3.3 ランタイムデータディレクトリ構造

仕様書6.1章をベースに、チェックポイント状態管理用のファイルを追加する。

```
{data_root}/                        # グローバル設定で指定（デフォルト: ~/.daily_routine/）
├── config.yaml                     # グローバル設定
└── projects/
    └── {project_id}/
        ├── config.yaml             # プロジェクト設定
        ├── state.yaml              # パイプライン実行状態（チェックポイント）
        ├── intelligence/
        │   └── report.json         # TrendReport
        ├── scenario/
        │   ├── scenario.json       # Scenario
        │   └── captions.json       # CaptionSet
        ├── assets/
        │   ├── character/          # キャラクターリファレンス画像
        │   ├── props/              # 小物画像
        │   └── backgrounds/        # 背景画像
        ├── clips/
        │   └── scene_{n}/          # シーンごとの動画クリップ
        ├── audio/
        │   ├── bgm/               # BGMファイル
        │   └── se/                # SEファイル
        └── output/
            └── final.mp4          # 最終出力
```

### 3.4 Pydanticスキーマ定義

レイヤー間のデータフローに基づき、以下のスキーマを定義する。

#### データフロー図

```
キーワード入力
    │
    ▼
[Intelligence Engine]
    │ TrendReport
    ▼
[Scenario Engine]
    │ Scenario (シナリオ + プロンプト + テロップ)
    ├──────────────────────┐
    ▼                      ▼
[Asset Generator]    [Audio Engine]
    │ AssetSet             │ AudioAsset
    ▼                      │
[Visual Core]              │
    │ VideoClipSet         │
    ▼                      ▼
[Post-Production] ◄────────┘
    │
    ▼
完成動画
```

#### 3.4.1 プロジェクト設定 (`schemas/project.py`)

```python
from datetime import datetime
from enum import Enum
from pathlib import Path
from pydantic import BaseModel, Field


class PipelineStep(str, Enum):
    """パイプラインのステップ"""
    INTELLIGENCE = "intelligence"
    SCENARIO = "scenario"
    ASSET = "asset"
    VISUAL = "visual"
    AUDIO = "audio"
    POST_PRODUCTION = "post_production"


class CheckpointStatus(str, Enum):
    """チェックポイントのステータス"""
    PENDING = "pending"         # 未実行
    RUNNING = "running"         # 実行中
    AWAITING_REVIEW = "awaiting_review"  # 人間の確認待ち
    APPROVED = "approved"       # 承認済み
    REJECTED = "rejected"       # 差し戻し


class StepState(BaseModel):
    """各ステップの実行状態"""
    status: CheckpointStatus = CheckpointStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class PipelineState(BaseModel):
    """パイプライン全体の実行状態"""
    project_id: str
    current_step: PipelineStep | None = None
    steps: dict[PipelineStep, StepState] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ProjectConfig(BaseModel):
    """プロジェクト設定"""
    project_id: str
    keyword: str = Field(description="検索キーワード（例：「OLの一日」）")
    output_fps: int = Field(default=30, description="出力フレームレート")
    output_duration_range: tuple[int, int] = Field(
        default=(30, 60),
        description="出力動画尺の範囲（秒）",
    )
    created_at: datetime = Field(default_factory=datetime.now)
```

#### 3.4.2 Intelligence Engine (`schemas/intelligence.py`)

```python
from pydantic import BaseModel, Field


class SceneStructure(BaseModel):
    """シーン構成の分析結果"""
    total_scenes: int
    avg_scene_duration_sec: float
    hook_techniques: list[str] = Field(description="冒頭フック手法")
    transition_patterns: list[str] = Field(description="シーン遷移パターン")


class CaptionTrend(BaseModel):
    """テロップトレンド"""
    font_styles: list[str]
    color_schemes: list[str]
    animation_types: list[str]
    positions: list[str]
    emphasis_techniques: list[str]


class VisualTrend(BaseModel):
    """映像トレンド"""
    situations: list[str] = Field(description="シチュエーション一覧")
    props: list[str] = Field(description="登場小物")
    camera_works: list[str] = Field(description="カメラワーク")
    color_tones: list[str] = Field(description="色調・フィルタ")


class AudioTrend(BaseModel):
    """音響トレンド"""
    bpm_range: tuple[int, int]
    genres: list[str]
    volume_patterns: list[str]
    se_usage_points: list[str] = Field(description="SE使用箇所")


class AssetRequirement(BaseModel):
    """素材要件"""
    characters: list[str] = Field(description="必要なキャラクター")
    props: list[str] = Field(description="必要な小物")
    backgrounds: list[str] = Field(description="必要な背景")


class TrendReport(BaseModel):
    """Intelligence Engineの出力: トレンド分析レポート"""
    keyword: str
    analyzed_video_count: int
    scene_structure: SceneStructure
    caption_trend: CaptionTrend
    visual_trend: VisualTrend
    audio_trend: AudioTrend
    asset_requirements: AssetRequirement
```

#### 3.4.3 Scenario Engine (`schemas/scenario.py`)

```python
from pydantic import BaseModel, Field


class CameraWork(BaseModel):
    """カメラワーク指定"""
    type: str = Field(description="POV, close-up, wide等")
    description: str


class SceneSpec(BaseModel):
    """シーン仕様"""
    scene_number: int
    duration_sec: float
    situation: str = Field(description="状況説明")
    camera_work: CameraWork
    caption_text: str = Field(description="テロップテキスト")
    image_prompt: str = Field(description="Asset Generator用の画像生成プロンプト")
    video_prompt: str = Field(description="Visual Core用の動画生成プロンプト")


class CharacterSpec(BaseModel):
    """キャラクター仕様"""
    name: str
    appearance: str = Field(description="外見の詳細説明")
    outfit: str = Field(description="服装の詳細説明")
    reference_prompt: str = Field(description="リファレンス画像生成用プロンプト")


class Scenario(BaseModel):
    """Scenario Engineの出力"""
    title: str
    total_duration_sec: float
    characters: list[CharacterSpec]
    scenes: list[SceneSpec]
    bgm_direction: str = Field(description="BGMの方向性指示")
```

#### 3.4.4 Asset Generator (`schemas/asset.py`)

```python
from pathlib import Path
from pydantic import BaseModel, Field


class CharacterAsset(BaseModel):
    """キャラクターアセット"""
    character_name: str
    front_view: Path = Field(description="正面画像パス")
    side_view: Path = Field(description="横向き画像パス")
    back_view: Path = Field(description="背面画像パス")
    expressions: dict[str, Path] = Field(
        default_factory=dict,
        description="表情バリエーション {表情名: 画像パス}",
    )


class PropAsset(BaseModel):
    """小物アセット"""
    name: str
    image_path: Path


class BackgroundAsset(BaseModel):
    """背景アセット"""
    scene_number: int
    description: str
    image_path: Path


class AssetSet(BaseModel):
    """Asset Generatorの出力"""
    characters: list[CharacterAsset]
    props: list[PropAsset]
    backgrounds: list[BackgroundAsset]
```

#### 3.4.5 Visual Core (`schemas/visual.py`)

```python
from pathlib import Path
from pydantic import BaseModel, Field


class VideoClip(BaseModel):
    """生成された動画クリップ"""
    scene_number: int
    clip_path: Path
    duration_sec: float
    quality_score: float | None = Field(
        default=None,
        description="品質スコア（0-1）、品質チェック後に設定",
    )


class VideoClipSet(BaseModel):
    """Visual Coreの出力"""
    clips: list[VideoClip]
```

#### 3.4.6 Audio Engine (`schemas/audio.py`)

```python
from pathlib import Path
from pydantic import BaseModel, Field


class BGM(BaseModel):
    """BGM"""
    file_path: Path
    bpm: int
    genre: str
    duration_sec: float
    source: str = Field(description="生成元（AI名 or フリー素材ライブラリ名）")


class SoundEffect(BaseModel):
    """効果音"""
    name: str
    file_path: Path
    trigger_time_ms: int = Field(description="挿入タイミング（ミリ秒）")
    scene_number: int
    trigger_description: str = Field(description="トリガーとなる動作/物体")


class AudioAsset(BaseModel):
    """Audio Engineの出力"""
    bgm: BGM
    sound_effects: list[SoundEffect]
```

#### 3.4.7 Post-Production (`schemas/post.py`)

```python
from pathlib import Path
from pydantic import BaseModel, Field


class CaptionStyle(BaseModel):
    """テロップスタイル"""
    font: str
    color: str
    background_color: str | None = None
    animation: str | None = None
    position: str = Field(description="表示位置（top, center, bottom等）")


class CaptionEntry(BaseModel):
    """テロップエントリ"""
    text: str
    start_time_ms: int
    end_time_ms: int
    style: CaptionStyle


class FinalOutput(BaseModel):
    """Post-Productionの出力"""
    video_path: Path
    duration_sec: float
    resolution: str = "1080x1920"
    fps: int
    captions: list[CaptionEntry]
```

### 3.5 設定管理

#### グローバル設定 (`~/.daily_routine/config.yaml`)

```yaml
# データ保存ルート
data_root: ~/.daily_routine

# APIキー（環境変数でもオーバーライド可能）
api_keys:
  youtube_data_api: ""
  openai: ""
  google_ai: ""
  # 他のAPIキーはADRで採用決定後に追加

# デフォルトのプロジェクト設定
defaults:
  output_fps: 30
  output_duration_range: [30, 60]

# ロギング
logging:
  level: INFO
  file: ~/.daily_routine/logs/app.log
```

#### 設定管理 (`config/manager.py`)

```python
from pathlib import Path
from pydantic import BaseModel, Field
import yaml


class ApiKeys(BaseModel):
    """APIキー設定"""
    youtube_data_api: str = ""
    openai: str = ""
    google_ai: str = ""

    class Config:
        extra = "allow"  # ADRで追加されるAPIキーに対応


class LoggingConfig(BaseModel):
    """ロギング設定"""
    level: str = "INFO"
    file: Path | None = None


class DefaultsConfig(BaseModel):
    """デフォルト設定"""
    output_fps: int = 30
    output_duration_range: tuple[int, int] = (30, 60)


class GlobalConfig(BaseModel):
    """グローバル設定"""
    data_root: Path = Path.home() / ".daily_routine"
    api_keys: ApiKeys = Field(default_factory=ApiKeys)
    defaults: DefaultsConfig = Field(default_factory=DefaultsConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


def load_global_config(path: Path | None = None) -> GlobalConfig:
    """グローバル設定を読み込む。環境変数でAPIキーをオーバーライド可能。"""
    ...


def load_project_config(project_dir: Path) -> "ProjectConfig":
    """プロジェクト設定を読み込む。"""
    ...


def get_project_dir(global_config: GlobalConfig, project_id: str) -> Path:
    """プロジェクトのデータディレクトリを取得・作成する。"""
    ...
```

**環境変数オーバーライド:** APIキーは `DAILY_ROUTINE_API_KEY_OPENAI` のように `DAILY_ROUTINE_API_KEY_{NAME}` 形式の環境変数でもオーバーライド可能とする。これにより、設定ファイルにAPIキーを直接記載する必要がなくなる。

### 3.6 CLI骨格

```python
# cli/app.py
import typer

app = typer.Typer(
    name="daily-routine",
    help="「〇〇の一日」AI動画生成パイプライン",
)


@app.command()
def run(
    keyword: str = typer.Argument(help="検索キーワード"),
    project_id: str | None = typer.Option(None, help="プロジェクトID（省略時は自動生成）"),
    step: str | None = typer.Option(None, help="特定ステップのみ実行"),
) -> None:
    """パイプラインを実行する"""
    ...


@app.command()
def status(
    project_id: str = typer.Argument(help="プロジェクトID"),
) -> None:
    """プロジェクトの実行状態を表示する"""
    ...


@app.command()
def init(
    keyword: str = typer.Argument(help="検索キーワード"),
    project_id: str | None = typer.Option(None, help="プロジェクトID"),
) -> None:
    """新規プロジェクトを初期化する"""
    ...
```

## 4. 実装計画

### ステップ1: pyproject.toml + パッケージ構成の作成

- `pyproject.toml` を作成（uv, Python 3.12+, 初期依存: pydantic, typer, pyyaml）
- `src/daily_routine/` 以下のディレクトリ・`__init__.py` を作成
- `uv sync` で仮想環境を構築
- **完了条件:** `uv run python -c "import daily_routine"` が成功する

### ステップ2: 共通Pydanticスキーマの実装

- `schemas/` 以下の全モジュールを実装（3.4節の定義に基づく）
- 各スキーマのインスタンス生成・シリアライズ・デシリアライズが正常に動作する
- **完了条件:** 各スキーマのバリデーションテストが通る

### ステップ3: 設定管理の実装

- `config/manager.py` を実装
- YAML読み込み、Pydanticバリデーション、環境変数オーバーライド
- プロジェクトディレクトリの自動作成
- **完了条件:** 設定ファイルの読み込み・バリデーション・環境変数オーバーライドが動作する

### ステップ4: CLI骨格の実装

- `cli/app.py` にTyperアプリケーションを定義
- `pyproject.toml` に `[project.scripts]` エントリーポイントを追加
- **完了条件:** `uv run daily-routine --help` でヘルプが表示される

### ステップ5: ロギング設定

- Python標準loggingの設定
- ファイル出力 + コンソール出力
- **完了条件:** 各モジュールでロガーが使用可能

## 5. テスト方針

- **スキーマテスト:** 各Pydanticモデルの生成・バリデーション・JSON変換を検証
  - 正常値でのインスタンス生成
  - 不正な型・値でのバリデーションエラー
  - JSON / dict へのシリアライズ・デシリアライズの往復テスト
- **設定管理テスト:** YAML読み込み、デフォルト値、環境変数オーバーライドを検証
- **CLIテスト:** `--help` 表示、コマンド認識を検証
- テストフレームワーク: pytest

## 6. 未決事項

| 項目                     | 詳細                                                 | 判断時期                  |
| ------------------------ | ---------------------------------------------------- | ------------------------- |
| スキーマのバージョニング | レイヤー間JSONのスキーマバージョン管理が必要になるか | Phase 2結合時に評価       |
| ~~非同期処理~~           | ~~API呼び出しの非同期化（asyncio）を初期から導入するか~~ | **解決済み: async採用を確定**。外部API呼び出しが多いため、Phase 0から `async/await` を標準とする。 |
| プロジェクトID生成ルール | UUID vs タイムスタンプ vs カスタム命名               | ステップ3実装時に決定     |
