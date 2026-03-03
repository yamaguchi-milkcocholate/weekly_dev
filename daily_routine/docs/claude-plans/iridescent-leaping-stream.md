# t1_overall_flow.md 設計書との乖離修正計画

## Context

設計書 `docs/designs/t1_overall_flow.md` に C1-C3 PoC 知見を反映した Keyframe Engine（Gemini C3-I1 方式）、スキーマ拡張、パイプライン統合の設計が記載されているが、実装は旧方式（Runway Gen-4 Image + StyleMapping）のまま。本計画でこれらの乖離を全て解消する。

---

## Phase 1: スキーマ追加（後方互換、デフォルト値あり）

### 1.1 `src/daily_routine/schemas/asset.py`

- `CharacterAsset` に `identity_block: str = Field(default="", description="Identity Block テキスト（C1-ID 出力）")` 追加
- `EnvironmentAsset` モデル新規追加:
  ```python
  class EnvironmentAsset(BaseModel):
      scene_number: int
      description: str
      image_path: Path
      source_type: str = Field(default="generated")  # reference/generated/text_fallback
  ```
- `AssetSet` に `environments: list[EnvironmentAsset] = Field(default_factory=list)` 追加
- `KeyframeAsset` に `cut_id: str = Field(default="")`, `generation_method: str = Field(default="gemini")` 追加

### 1.2 `src/daily_routine/schemas/storyboard.py`

- `CutSpec` に `pose_instruction: str = Field(default="", description="ポーズ指示（C3-I1 Flash分析入力）")` 追加

### 1.3 `src/daily_routine/schemas/keyframe_mapping.py`【新規】

```python
class SceneKeyframeSpec(BaseModel):
    scene_number: int
    character: str = ""
    environment: str = ""
    pose: str = ""
    reference_image: Path | None = None
    reference_text: str = ""

class KeyframeMapping(BaseModel):
    scenes: list[SceneKeyframeSpec] = Field(default_factory=list)
    def get_spec(self, scene_number: int) -> SceneKeyframeSpec | None: ...
```

### 1.4 `src/daily_routine/schemas/pipeline_io.py`

- `KeyframeInput.style_mapping: StyleMapping | None` → `keyframe_mapping: KeyframeMapping | None = None`
- `PostProductionInput` に `storyboard: Storyboard` フィールド追加
- import を `StyleMapping` → `KeyframeMapping` に変更

---

## Phase 2: Keyframe Engine 書き換え（Runway → Gemini C3-I1）

### 2.1 `src/daily_routine/keyframe/client.py`【新規】

PoC (`poc/seamless/run_phase_c3.py`) の `google.genai` SDK パターンを本番化。既存の `asset/client.py` は `langchain_google_genai` を使用しているが、C3-I1 では Flash テキスト生成（`response_modalities=["TEXT"]`）が必要なため、`google-genai` SDK を直接使用する専用クライアントを新規作成。

```python
class GeminiKeyframeClient:
    """Gemini C3-I1 キーフレーム生成クライアント（Flash+Pro 2パス）."""

    async def analyze_scene(self, char_image, env_image, identity_block, pose_instruction,
                            reference_image=None, reference_text="") -> str:
        """Step 1: Flash 最小指示分析 → シーンプロンプト."""

    async def generate_keyframe(self, char_image, env_image, flash_prompt,
                                 reference_image=None, output_path=...) -> Path:
        """Step 2: Pro シーン画像生成 → キーフレーム画像(9:16)."""
```

- Flash: `gemini-3-flash-preview`, `response_modalities=["TEXT"]`, `temperature=0.0`
- Pro: `gemini-3-pro-image-preview`, `response_modalities=["TEXT", "IMAGE"]`, `aspect_ratio="9:16"`
- リトライ: 3回、指数バックオフ（PoC と同じパターン）

### 2.2 `src/daily_routine/keyframe/prompt.py`【新規】

PoC `config_c3.py` の C3-I1 プロンプトテンプレートを移植:

- `C3I1_FLASH_META_PROMPT` — Flash 分析用メタプロンプト
- `C3I1_GENERATION_TEMPLATE` — Pro 生成用テンプレート

### 2.3 `src/daily_routine/keyframe/base.py`

ABC シグネチャを設計書に合わせて更新:

```python
@abstractmethod
async def generate_keyframes(
    self,
    scenario: Scenario,
    storyboard: Storyboard,
    assets: AssetSet,
    output_dir: Path,
    keyframe_mapping: KeyframeMapping | None = None,
    project_dir: Path | None = None,
) -> AssetSet: ...
```

### 2.4 `src/daily_routine/keyframe/engine.py`【全面書き換え】

`RunwayKeyframeEngine` → `GeminiKeyframeEngine` に変更。

処理フロー（各カットに対して）:
1. キャラクター解決: `assets.characters[0].front_view` + `identity_block`
2. 環境解決: `assets.environments` からシーン番号で検索、なければ `assets.backgrounds` フォールバック
3. ポーズ取得: `cut.pose_instruction`
4. KeyframeMapping 参照: `reference_image`, `reference_text`（任意）
5. **Step 1**: `client.analyze_scene(...)` → `flash_prompt`
6. **Step 2**: `client.generate_keyframe(...)` → キーフレーム画像
7. `KeyframeAsset(cut_id=cut.cut_id, generation_method="gemini", ...)` 生成

`_resolve_style_reference` 関数を削除。`save_output`/`load_output` は維持。

### 2.5 `src/daily_routine/keyframe/__init__.py`

エクスポートを `RunwayKeyframeEngine` → `GeminiKeyframeEngine` に変更。

---

## Phase 3: パイプラインランナー修正

### 3.1 `src/daily_routine/pipeline/runner.py`

**a) `_load_style_mapping` → `_load_keyframe_mapping` にリネーム**
- ファイル名: `style_mapping.yaml` → `keyframe_mapping.yaml`
- 型: `StyleMapping` → `KeyframeMapping`

**b) KEYFRAME ステップの `_build_input` 修正**
```python
keyframe_mapping = _load_keyframe_mapping(project_dir)
return KeyframeInput(scenario=..., storyboard=..., assets=..., keyframe_mapping=keyframe_mapping)
```

**c) POST_PRODUCTION ステップの `_build_input` 修正**
```python
storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
return PostProductionInput(scenario=..., storyboard=storyboard, video_clips=..., audio_asset=...)
```

**d) `_engine_kwargs` の KEYFRAME ステップ修正**
```python
if step == PipelineStep.KEYFRAME:
    return {"api_key": api_keys.get("google_ai", "")}
```
（Runway 関連の `gcs_bucket`, `image_model` を削除）

**e) `create_engine` の KEYFRAME ステップ修正**
- `RunwayKeyframeEngine` → `GeminiKeyframeEngine` に変更

**f) `StyleMapping` の import 削除**

---

## Phase 4: keyframe_mapping.yaml 自動生成

### 4.1 `src/daily_routine/pipeline/runner.py` に追加

`resume_pipeline` で ASSET → KEYFRAME 遷移時に `_auto_generate_keyframe_mapping(project_dir)` を呼び出す。

```python
def _auto_generate_keyframe_mapping(project_dir: Path) -> None:
    """Storyboard + AssetSet から keyframe_mapping.yaml を自動生成する.

    既存ファイルがあれば上書きしない（ユーザー編集を保護）。
    """
    mapping_path = project_dir / "storyboard" / "keyframe_mapping.yaml"
    if mapping_path.exists():
        return
    # Storyboard の各カットから character × environment × pose を導出
    # YAML として保存
```

---

## Phase 5: Visual Core 修正

### 5.1 `src/daily_routine/visual/engine.py`

`_find_keyframe` を `cut_id` 優先検索に変更（`scene_number` フォールバック付き）:

```python
@staticmethod
def _find_keyframe(assets: AssetSet, cut_id: str, scene_number: int) -> KeyframeAsset:
    for kf in assets.keyframes:
        if kf.cut_id and kf.cut_id == cut_id:
            return kf
    for kf in assets.keyframes:
        if kf.scene_number == scene_number:
            return kf
    raise FileNotFoundError(...)
```

呼び出し元（L89）も更新: `self._find_keyframe(assets, cut.cut_id, cut.scene_number)`

---

## Phase 6: 旧スキーマ非推奨化

### 6.1 `src/daily_routine/schemas/style_mapping.py`

ファイル冒頭に非推奨コメントを追加。プロダクションコードからの全 import を削除済みのため、ファイル自体は残す（テスト互換）。

---

## Phase 7: テスト更新

| テストファイル | 変更内容 |
|---|---|
| `tests/test_schemas/test_asset.py` | `identity_block`, `EnvironmentAsset`, `environments`, `cut_id`, `generation_method` テスト追加 |
| `tests/test_schemas/test_keyframe_mapping.py`【新規】| `SceneKeyframeSpec`, `KeyframeMapping.get_spec()` テスト |
| `tests/test_keyframe_engine.py` | `GeminiKeyframeEngine` + `GeminiKeyframeClient` mock に全面書き換え |
| `tests/test_pipeline/test_runner.py` | `_load_keyframe_mapping`, KEYFRAME/POST_PRODUCTION の `_build_input`, `_engine_kwargs` 更新 |
| `tests/test_visual_engine.py` | `KeyframeAsset` に `cut_id` 追加、`_find_keyframe` の引数変更 |

---

## 変更ファイル一覧

### 新規作成
| ファイル | 内容 |
|---|---|
| `src/daily_routine/schemas/keyframe_mapping.py` | KeyframeMapping, SceneKeyframeSpec |
| `src/daily_routine/keyframe/client.py` | GeminiKeyframeClient (Flash+Pro) |
| `src/daily_routine/keyframe/prompt.py` | C3-I1 プロンプトテンプレート |
| `tests/test_schemas/test_keyframe_mapping.py` | KeyframeMapping テスト |

### 修正
| ファイル | 変更概要 |
|---|---|
| `src/daily_routine/schemas/asset.py` | フィールド追加 + EnvironmentAsset |
| `src/daily_routine/schemas/storyboard.py` | pose_instruction 追加 |
| `src/daily_routine/schemas/pipeline_io.py` | KeyframeMapping 導入 + PostProductionInput に Storyboard |
| `src/daily_routine/keyframe/base.py` | ABC シグネチャ更新 |
| `src/daily_routine/keyframe/engine.py` | 全面書き換え（Gemini C3-I1） |
| `src/daily_routine/keyframe/__init__.py` | エクスポート変更 |
| `src/daily_routine/pipeline/runner.py` | keyframe_mapping 対応 + PostProduction 修正 + engine_kwargs |
| `src/daily_routine/visual/engine.py` | _find_keyframe を cut_id 対応 |
| `src/daily_routine/schemas/style_mapping.py` | 非推奨コメント追加 |
| `tests/test_keyframe_engine.py` | GeminiKeyframeEngine テストに書き換え |
| `tests/test_pipeline/test_runner.py` | keyframe_mapping + PostProduction テスト |
| `tests/test_visual_engine.py` | cut_id 対応 |
| `tests/test_schemas/test_asset.py` | 新フィールドテスト追加 |

---

## 検証手順

```bash
# 1. Phase 1 完了後 — スキーマテスト
uv run pytest tests/test_schemas/ -v

# 2. Phase 2-4 完了後 — Keyframe + Pipeline テスト
uv run pytest tests/test_keyframe_engine.py tests/test_pipeline/ -v

# 3. Phase 5 完了後 — Visual テスト
uv run pytest tests/test_visual_engine.py -v

# 4. 全体確認
uv run pytest tests/ -v

# 5. E2E — diving シードでパイプライン実行（KEYFRAME ステップまで）
uv run daily-routine run "ダイビングOLの一日" --seeds seeds/diving.yaml
# → resume を繰り返し、KEYFRAME ステップで Gemini C3-I1 が動作することを確認
```
