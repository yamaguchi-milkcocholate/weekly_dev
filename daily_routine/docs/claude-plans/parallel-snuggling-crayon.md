# C2 環境画像生成の実装計画

## Context

Asset Generator は現在キャラクター生成（C1）のみ実装されており、環境生成（C2）が未実装。
`EnvironmentAsset` スキーマと下流の消費側（keyframe/engine, pipeline/runner）は既に整備済み。
PoC（`poc/seamless/C2_result.md`）で **C2-R2（参照画像→Pro 1パスで人物除去・環境再現）** が $0.04/環境で採用決定済み。

**ゴール**: 環境画像を生成し `AssetSet.environments` に格納する。2つのソースモードに対応:
1. **reference**: ユーザーの参照写真（人物入り可）から C2-R2 で人物除去・環境再現
2. **generate**: `SceneSpec.image_prompt` からテキストベースで環境画像を自動生成

## 方針

- **YAML シードファイル必須**: `assets/reference/environment_seeds.yaml` で全シーンの環境を定義。ファイルがなければエラー
- **source フィールドで分岐**: `reference`（参照写真から再現）/ `generate`（テキストから生成）
- **C2-R2-MOD 対応**: source=reference の場合に modification（修正指示）を指定可能
- **C2-ED は実装しない**: `EnvironmentAsset.description` は YAML のユーザー指定値を使用
- **既存 GeminiImageClient を使用**: LangChain ベースの既存クライアント（`asset/client.py`）を活用。新規クライアント作成不要
  - `generate_with_reference()` → source=reference（C2-R2）
  - `generate()` → source=generate（テキストベース）

---

## 運用計画（データ準備）

### ユーザーが準備するもの

**1. 環境参照写真**（source=reference のシーンのみ）を `assets/reference/environments/` に配置:
```
assets/reference/environments/
├── diving_boat.png      # 人物入りOK。C2-R2 が人物を除去する
├── kart_circuit.png
└── sunset_beach.jpg
```

**2. シード定義ファイル**を `assets/reference/environment_seeds.yaml` に作成:
```yaml
environments:
  - scene_number: 1
    source: reference                          # 参照写真から環境再現
    reference_image: "diving_boat.png"         # environments/ からの相対パス
    description: "ダイビングボートと海"         # keyframe_mapping 照合用（任意）
    modification: ""                           # C2-R2 のまま

  - scene_number: 2
    source: generate                           # テキストベースで自動生成
    description: "カフェの内装"                 # SceneSpec.image_prompt を使用

  - scene_number: 3
    source: reference
    reference_image: "diving_boat.png"         # 同じ参照画像を再利用可能
    description: "サンセットのボート"
    modification: "Change the atmosphere to SUNSET. Warm orange and pink sky, golden hour lighting."
```

---

## 実装ステップ

### Step 1: スキーマ追加 — `src/daily_routine/schemas/asset.py`

`EnvironmentSeedSpec` / `EnvironmentSeeds` モデルを追加。

```python
class EnvironmentSeedSpec(BaseModel):
    """環境シード仕様."""
    scene_number: int
    source: str = Field(description="生成ソース: 'reference' or 'generate'")
    reference_image: str = Field(default="", description="参照画像ファイル名（source=referenceの時必須）")
    modification: str = Field(default="", description="C2-R2-MOD 修正指示（source=referenceの時のみ有効）")
    description: str = Field(default="", description="環境の説明（keyframe_mapping照合用）")

class EnvironmentSeeds(BaseModel):
    """環境シード定義."""
    environments: list[EnvironmentSeedSpec] = Field(default_factory=list)
```

**テスト**: `tests/test_schemas/test_asset.py` に追加

### Step 2: プロンプト追加 — `src/daily_routine/asset/prompt.py`

PoC 検証済みプロンプトをそのまま移植（`poc/seamless/config_c2.py` の `C2R2_PROMPT`）。

定数:
```python
_C2R2_BASE_PROMPT = (
    "Image 1 shows a photo with people in a specific environment.\n"
    "Recreate ONLY the environment/location from this image, "
    "removing all people completely.\n"
    "Keep: the exact same location type, structures, weather, lighting, "
    "color palette, atmosphere, time of day.\n"
    "Remove: all people, all persons.\n"
    "The scene must have NO people, no persons, completely empty.\n"
    "Composition: eye level camera, suitable for placing "
    "a full-body standing person in the center of the frame.\n"
    "Photo-realistic, natural lighting."
)

_C2_TEXT_GENERATION_SUFFIX = (
    "\nThe scene must have NO people, no persons, completely empty.\n"
    "Composition: eye level camera, suitable for placing "
    "a full-body standing person in the center of the frame.\n"
    "Photo-realistic, natural lighting."
)
```

`PromptBuilder` に追加:
- `build_environment_prompt(modification: str = "") -> str` — C2-R2 / C2-R2-MOD
- `build_environment_text_prompt(image_prompt: str) -> str` — image_prompt + 構図指示サフィックス

**テスト**: `tests/test_asset_prompt.py` に追加

### Step 3: ジェネレータ統合 — `src/daily_routine/asset/generator.py`

`GeminiAssetGenerator` に環境生成を追加。新規クライアントは作らず、既存の `self._client`（GeminiImageClient）を使用。

**`execute()` 変更** (L61-88):
- `assets/reference/environment_seeds.yaml` を読み込み
- `generate_assets()` に `env_seeds`, `env_reference_dir`, `scenes` を渡す

**`generate_assets()` 変更** (L111-160):
- キャラクター生成後に環境生成を追加
- 環境生成は順次実行（通常 2-5 件）

**追加するプライベートメソッド**:
```python
def _load_environment_seeds(self, seeds_path: Path) -> EnvironmentSeeds:
    """YAML シードファイルを読み込む。ファイルがなければ FileNotFoundError."""

async def _generate_environments(
    self,
    env_seeds: EnvironmentSeeds,
    scenes: list[SceneSpec],
    env_reference_dir: Path,
    output_dir: Path,
) -> list[EnvironmentAsset]:
    """全環境画像を順次生成する."""

async def _generate_single_environment(
    self,
    seed: EnvironmentSeedSpec,
    scenes: list[SceneSpec],
    env_reference_dir: Path,
    output_dir: Path,
) -> EnvironmentAsset:
    """1環境画像を生成し EnvironmentAsset を返す."""
```

**生成フロー**:
```
source=reference:
    prompt = PromptBuilder.build_environment_prompt(modification)
    self._client.generate_with_reference(prompt, [ref_image_path], output_path)
    → EnvironmentAsset(source_type="reference")

source=generate:
    image_prompt = SceneSpec(scene_number).image_prompt
    prompt = PromptBuilder.build_environment_text_prompt(image_prompt)
    self._client.generate(prompt, output_path)
    → EnvironmentAsset(source_type="generated")
```

**テスト**: `tests/test_asset_generator.py` に追加

---

## 変更ファイル一覧

| ファイル | 操作 | 内容 |
|---------|------|------|
| `src/daily_routine/schemas/asset.py` | MODIFY | `EnvironmentSeedSpec`, `EnvironmentSeeds` 追加 |
| `src/daily_routine/asset/prompt.py` | MODIFY | C2-R2 + テキスト生成プロンプト + メソッド2つ追加 |
| `src/daily_routine/asset/generator.py` | MODIFY | 環境生成ロジック統合（source分岐、既存クライアント使用） |
| `tests/test_schemas/test_asset.py` | MODIFY | シードスキーマテスト |
| `tests/test_asset_prompt.py` | MODIFY | 環境プロンプトテスト |
| `tests/test_asset_generator.py` | MODIFY | 環境生成テスト |

**変更不要**:
- `asset/client.py` — 既存の `generate()` と `generate_with_reference()` をそのまま使用
- `keyframe/engine.py` — `_resolve_environment()` は既に `assets.environments` を検索済み
- `pipeline/runner.py` — `_auto_generate_keyframe_mapping()` は既に `assets.environments` をイテレート済み
- `config/manager.py` — `assets/environments/` と `assets/reference/environments/` は既に作成される

---

## テスト計画

### スキーマ (`tests/test_schemas/test_asset.py`)
- `test_EnvironmentSeedSpec_reference_作成`
- `test_EnvironmentSeedSpec_generate_作成`
- `test_EnvironmentSeeds_YAML辞書からパース`

### プロンプト (`tests/test_asset_prompt.py`)
- `test_build_environment_prompt_基本_C2R2プロンプト`
- `test_build_environment_prompt_MOD_修正指示が末尾に追加`
- `test_build_environment_text_prompt_image_promptにサフィックス追加`

### ジェネレータ (`tests/test_asset_generator.py`)
- `test_generate_assets_環境reference_EnvironmentAsset生成`
- `test_generate_assets_環境generate_SceneSpecのimage_prompt使用`
- `test_generate_assets_環境MOD付き_修正プロンプト使用`
- `test_load_environment_seeds_YAML読み込み`
- `test_load_environment_seeds_YAML未存在_FileNotFoundError`
- `test_generate_assets_参照画像未存在_FileNotFoundError`

### 検証コマンド
```bash
uv run pytest tests/test_schemas/test_asset.py tests/test_asset_prompt.py tests/test_asset_generator.py -v
uv run pytest -v  # 全テスト通過確認
uv run ruff check . && uv run ruff format --check .  # リント確認
```
