# KEYFRAME / VISUAL ステップのパイプライン統合計画

## Context

ADR-003 軌道修正で KEYFRAME ステップと関連コードを実装済みだが、パイプラインレジストリ経由でのエンジン構築が未統合のため、CLIで `run` → `resume` を繰り返してもKEYFRAMEステップ以降に進めない。

**根本原因:**
- `RunwayKeyframeEngine.__init__` がオブジェクト型（`RunwayImageClient`）を要求 → レジストリの `_engine_kwargs()` はプリミティブ型のみ対応
- `DefaultVisualEngine` が `StepEngine` を実装していない（`execute`, `save_output`, `load_output` なし）
- VISUAL エンジンが `_register_engines()` に未登録

**ゴール:** `uv run daily-routine run "OLの一日"` → `resume` でVISUALステップまで実行可能にする。

## 設計方針

**既存パターン（GeminiAssetGenerator方式）に統一する。**

既存の4エンジンは全て「プリミティブ型をコンストラクタで受け取り、内部でクライアントを構築」するパターン。テスト用には `from_components()` クラスメソッドで依存注入する（`asset/generator.py:52-59` の実績パターン）。

## 実装ステップ

### Step 1: RunwayKeyframeEngine のコンストラクタ変更

**File:** `src/daily_routine/keyframe/engine.py`

- `__init__(self, image_client)` → `__init__(self, api_key="", gcs_bucket="", image_model="gen4_image_turbo")`
- api_key と gcs_bucket がある場合のみ内部で `GcsUploader` → `RunwayImageClient` を構築、なければ `None`
- `from_components(cls, image_client)` クラスメソッドを追加（テスト用DI）
- import追加: `GcsUploader`

```python
def __init__(self, api_key: str = "", gcs_bucket: str = "", image_model: str = "gen4_image_turbo") -> None:
    if api_key and gcs_bucket:
        from daily_routine.utils.uploader import GcsUploader
        uploader = GcsUploader(bucket_name=gcs_bucket)
        self._image_client = RunwayImageClient(api_key=api_key, uploader=uploader, model=image_model)
    else:
        self._image_client = None  # type: ignore[assignment]

@classmethod
def from_components(cls, image_client: RunwayImageClient) -> "RunwayKeyframeEngine":
    instance = cls.__new__(cls)
    instance._image_client = image_client
    return instance
```

### Step 2: DefaultVisualEngine に StepEngine 継承 + コンストラクタ変更

**File:** `src/daily_routine/visual/engine.py`

変更点:
1. 継承: `VisualEngine` → `StepEngine[VisualInput, VideoClipSet], VisualEngine`
2. `__init__(self, client, provider_name)` → `__init__(self, api_key="", gcs_bucket="", video_model="gen4_turbo", provider_name="runway")`
3. `from_components(cls, client, provider_name)` クラスメソッドを追加
4. `execute()` メソッド追加 — `generate_clips()` を呼ぶラッパー
5. `save_output()` メソッド追加 — `clip_set.json` として永続化
6. `load_output()` メソッド追加 — `clip_set.json` から復元
7. `create_visual_engine()` を新コンストラクタに合わせて更新
8. import追加: `StepEngine`, `VisualInput`, `VideoClipSet`（既存）, `GcsUploader`

```python
class DefaultVisualEngine(StepEngine[VisualInput, VideoClipSet], VisualEngine):

    def __init__(self, api_key: str = "", gcs_bucket: str = "", video_model: str = "gen4_turbo", provider_name: str = "runway") -> None:
        if api_key and gcs_bucket:
            uploader = GcsUploader(bucket_name=gcs_bucket)
            self._client = RunwayClient(api_key=api_key, uploader=uploader, model=video_model)
        else:
            self._client = None  # type: ignore[assignment]
        self._provider_name = provider_name

    async def execute(self, input_data: VisualInput, project_dir: Path) -> VideoClipSet:
        output_dir = project_dir / "clips"
        clip_set = await self.generate_clips(input_data.scenario, input_data.assets, output_dir)
        self.save_output(project_dir, clip_set)
        return clip_set

    def save_output(self, project_dir: Path, output: VideoClipSet) -> None:
        clips_dir = project_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        (clips_dir / "clip_set.json").write_text(output.model_dump_json(indent=2), encoding="utf-8")

    def load_output(self, project_dir: Path) -> VideoClipSet:
        path = project_dir / "clips" / "clip_set.json"
        if not path.exists():
            raise FileNotFoundError(f"VideoClipSet ファイルが見つかりません: {path}")
        return VideoClipSet.model_validate_json(path.read_text(encoding="utf-8"))
```

### Step 3: CLI でのエンジン登録 + 設定値の受け渡し

**File:** `src/daily_routine/cli/app.py`

1. `_register_engines()` に VISUAL を追加:
   ```python
   from daily_routine.visual.engine import DefaultVisualEngine
   register_engine(PipelineStep.VISUAL, DefaultVisualEngine)
   ```

2. `run`, `resume`, `retry` コマンドで `api_keys` dict に visual 設定を追加:
   ```python
   api_keys = global_config.api_keys.model_dump()
   api_keys["gcs_bucket"] = global_config.visual.runway.gcs_bucket
   api_keys["image_model"] = global_config.visual.runway.image_model
   api_keys["video_model"] = global_config.visual.runway.video_model
   ```

### Step 4: _engine_kwargs に KEYFRAME / VISUAL ケース追加

**File:** `src/daily_routine/pipeline/runner.py`

```python
if step == PipelineStep.KEYFRAME:
    return {
        "api_key": api_keys.get("runway", ""),
        "gcs_bucket": api_keys.get("gcs_bucket", ""),
        "image_model": api_keys.get("image_model", "gen4_image_turbo"),
    }

if step == PipelineStep.VISUAL:
    return {
        "api_key": api_keys.get("runway", ""),
        "gcs_bucket": api_keys.get("gcs_bucket", ""),
        "video_model": api_keys.get("video_model", "gen4_turbo"),
    }
```

### Step 5: テスト更新

**File:** `tests/test_keyframe_engine.py`
- `RunwayKeyframeEngine(image_client=mock_client)` → `RunwayKeyframeEngine.from_components(image_client=mock_client)`
- 永続化テストは引数なし `RunwayKeyframeEngine()` で OK（`load_output`/`save_output` はクライアント不要）

**File:** `tests/test_visual_engine.py`
- `DefaultVisualEngine(client=mock_client, provider_name="runway")` → `DefaultVisualEngine.from_components(client=mock_client, provider_name="runway")`
- `create_visual_engine()` テストは `RunwayConfig(video_model=...)` のまま動作可能
- `execute()`, `save_output()`, `load_output()` のテストを追加

## 検証方法

```bash
# 1. 全テスト通過
uv run pytest

# 2. リントチェック
uv run ruff check src/ tests/

# 3. パイプライン統合の手動確認（APIキー不要）
#    _build_input() で create_engine(PipelineStep.KEYFRAME).load_output() が
#    引数なしで構築できることを確認（既存テストでカバー）
```
