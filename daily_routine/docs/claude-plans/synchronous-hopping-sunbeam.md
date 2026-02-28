# Seeds リファクタリング: YouTube前提の排除

## Context

現状の Intelligence Engine はシード動画の入力に YouTube URL を前提としている（`SeedVideo.url` → YouTube Data API → メタデータ・字幕取得 → 拡張検索）。これを排除し、ユーザー提供のテキスト（`note`）+ キャプチャ画像（`scene_captures`）のみで分析するシンプルな構造に変更する。

**変更方針:**
- `SeedVideo.url` を削除（`video_path` も入れない）
- Phase B（YouTube 拡張検索）を廃止
- 分析は `note` + `scene_captures` ベースのまま
- YouTube 関連ファイル・依存を削除

## スキーマ変更

```python
# Before
class SeedVideo(BaseModel):
    url: str                              # 削除
    note: str = ""
    scene_captures: list[SceneCapture] = []

# After
class SeedVideo(BaseModel):
    note: str = ""                        # テキスト説明のみ
    scene_captures: list[SceneCapture] = []
```

```yaml
# seeds YAML: Before
seed_videos:
  - url: "https://youtube.com/shorts/TUI5ILZIcqU"
    note: "営業職の忙しさを..."
    scene_captures: [...]

# After
seed_videos:
  - note: "営業職の忙しさを..."
    scene_captures: [...]
```

## 実装ステップ

### Step 1: SeedVideo スキーマ変更
**`src/daily_routine/intelligence/base.py`**
- `SeedVideo.url` フィールドを削除
- `IntelligenceEngineBase.analyze()` から `max_expand_videos` 引数を削除

### Step 2: TrendAggregator 書き換え
**`src/daily_routine/intelligence/trend_aggregator.py`**
- `SeedVideoData`: `video_id`, `metadata: VideoMetadata`, `transcript` を全削除 → `scene_captures` + `user_note` のみ
- `ExpandedVideoData`: クラスごと削除
- `aggregate()`: `expanded_videos` 引数を削除
- `_build_contents()`: YouTube メタデータ・字幕描画を削除。`user_note` + キャプチャ画像 + description で構築
- `_SYSTEM_PROMPT`: YouTube 固有文言を汎用化
- `VideoMetadata`, `TranscriptResult` インポート削除

### Step 3: IntelligenceEngine 簡素化
**`src/daily_routine/intelligence/engine.py`**
- コンストラクタ: `youtube_api_key`, `openai_api_key` 削除 → `google_ai_api_key` のみ
- `analyze()`: Phase A・B 全削除。SeedVideo → SeedVideoData 直接変換 + TrendAggregator のみ
- YouTube/Transcript/Downloader インポート全削除

### Step 4: YouTube 専用ファイル削除
- `src/daily_routine/intelligence/youtube.py`
- `src/daily_routine/intelligence/transcript.py`
- `src/daily_routine/intelligence/downloader.py`

### Step 5: パイプライン統合の更新
- **`src/daily_routine/schemas/pipeline_io.py`**: `IntelligenceInput.max_expand_videos` 削除
- **`src/daily_routine/pipeline/runner.py`**: `_engine_kwargs` INTELLIGENCE → `google_ai_api_key` のみに

### Step 6: CLI の更新
**`src/daily_routine/cli/app.py`**
- `_load_seeds()`: `entry["url"]` 参照を削除。`SeedVideo(note=..., scene_captures=...)` で構築

### Step 7: 設定の更新
- **`src/daily_routine/config/manager.py`**: `ApiKeys.youtube_data_api` 削除
- **`configs/global.yaml`**: `youtube_data_api` 行を削除

### Step 8: 依存パッケージの整理
**`pyproject.toml`**: `youtube-transcript-api`, `yt-dlp` を削除 → `uv sync`

### Step 9: seeds YAML の更新
**`seeds/ol.yaml`**: `url:` 行を削除

### Step 10: テスト更新
**削除:** `test_youtube.py`, `test_transcript.py`, `test_downloader.py`
**書き換え:** `test_engine.py`, `test_trend_aggregator.py`, `test_cli.py`, `test_runner.py`

## 検証
1. `uv sync`
2. `uv run ruff check . && uv run ruff format --check .`
3. `uv run pytest` 全テスト通過
