# 改修計画: 1キャラクター複数アセット（衣装バリアント）対応

## Context

現在、キャラクターアセットは「1キャラクター = 1アセット（3アングル画像 + identity_block）」の構造。
「OLの一日」のように朝（パジャマ）→通勤（スーツ）→夜（カジュアル）とシーンごとに衣装が変わるユースケースに対応できない。

**方針:** Scenario Engine は変更しない。ユーザーが `mapping.yaml` で衣装バリアントを事前定義し、`keyframe_mapping.yaml` でシーンごとの衣装を手動指定する。

## 変更ファイル一覧

| # | ファイル | 変更内容 |
|---|---------|---------|
| 1 | `src/daily_routine/schemas/asset.py` | `CharacterAsset.variant_id` 追加、`ClothingReferenceSpec` 新規、`CharacterReferenceSpec.clothing_variants` 追加 |
| 2 | `src/daily_routine/schemas/keyframe_mapping.py` | `SceneKeyframeSpec.variant_id` 追加 |
| 3 | `src/daily_routine/asset/base.py` | `generate_character()` に `variant_id` パラメータ追加 |
| 4 | `src/daily_routine/asset/generator.py` | 衣装バリアントごとに C1-F2-MA を実行するループ変更 |
| 5 | `src/daily_routine/keyframe/engine.py` | `_resolve_character()` を `character_name` + `variant_id` で解決 |
| 6 | `src/daily_routine/pipeline/runner.py` | `_auto_generate_keyframe_mapping()` で `variant_id` を含める |
| 7 | テスト各種 | 既存テスト修正 + 新規テスト追加 |

## Step 1: スキーマ変更

### 1-1. `src/daily_routine/schemas/asset.py`

**新規モデル追加:**
```python
class ClothingReferenceSpec(BaseModel):
    """衣装バリアント別の参照画像."""
    label: str = Field(description="衣装ラベル（例: 'pajama', 'suit', 'casual'）")
    clothing: str | None = Field(default=None, description="服装画像ファイル名（clothing/ 相対パス）")
```

**CharacterReferenceSpec に `clothing_variants` 追加:**
```python
class CharacterReferenceSpec(BaseModel):
    name: str
    person: str | None = None
    clothing: str | None = None              # 後方互換: 単一衣装
    clothing_variants: list[ClothingReferenceSpec] = Field(
        default_factory=list,
        description="衣装バリアント別の参照画像",
    )
```

- `clothing` のみ指定 → `variant_id="default"` の1バリアントとして扱う（後方互換）
- `clothing_variants` 指定時 → 各ラベルごとにアセット生成

**CharacterAsset に `variant_id` 追加:**
```python
class CharacterAsset(BaseModel):
    character_name: str
    variant_id: str = Field(default="default", description="衣装バリアントID")
    front_view: Path
    side_view: Path
    back_view: Path
    identity_block: str = ""
```

- デフォルト `"default"` で既存の asset_set.json は壊れない（Pydantic がデフォルト値を補完）

### 1-2. `src/daily_routine/schemas/keyframe_mapping.py`

**SceneKeyframeSpec に `variant_id` 追加:**
```python
class SceneKeyframeSpec(BaseModel):
    scene_number: int
    character: str = ""
    variant_id: str = Field(default="", description="衣装バリアントID（空=デフォルトバリアント）")
    environment: str = ""
    pose: str = ""
    reference_image: Path | None = None
    reference_text: str = ""
```

## Step 2: Asset Generator 改修

### 2-1. `src/daily_routine/asset/base.py`

`generate_character()` に `variant_id` を追加:
```python
@abstractmethod
async def generate_character(
    self,
    character: CharacterSpec,
    output_dir: Path,
    reference_image: Path | None = None,
    person_image: Path | None = None,
    clothing_image: Path | None = None,
    variant_id: str = "default",
) -> CharacterAsset:
```

### 2-2. `src/daily_routine/asset/generator.py`

**主要な変更箇所:**

**(A) `_resolve_and_prepare_references()` — 返り値の型変更**

現在: `dict[str, tuple[Path, Path]]` （キャラ名 → (person, clothing)）
変更後: `dict[str, tuple[Path, dict[str, Path]]]` （キャラ名 → (person, {label: clothing_path})）

- `clothing_variants` がある場合: 各ラベルの clothing を解決
- `clothing_variants` がなく `clothing` のみの場合: `{"default": clothing_path}` として扱う
- 両方なし: `{"default": auto_generated_path}` として自動生成

**(B) `execute()` — 衣装バリアントごとのループ**

現在（行97-109）:
```python
character_tasks = [
    self._generate_character_with_semaphore(
        semaphore, char,
        output_dir / "character" / char.name,
        person_image=char_refs[char.name][0],
        clothing_image=char_refs[char.name][1],
    )
    for char in input_data.characters
]
```

変更後:
```python
character_tasks = []
for char in input_data.characters:
    person_path, clothing_map = char_refs[char.name]
    for label, clothing_path in clothing_map.items():
        character_tasks.append(
            self._generate_character_with_semaphore(
                semaphore, char,
                output_dir / "character" / char.name / label,
                person_image=person_path,
                clothing_image=clothing_path,
                variant_id=label,
            )
        )
```

**(C) `generate_character()` + `_generate_character_c1f2ma()` — variant_id の伝播**

`generate_character()` に `variant_id` パラメータを追加し、`_generate_character_c1f2ma()` / `_generate_character_legacy()` に伝播。`CharacterAsset` 生成時に `variant_id` を設定。

**(D) `_generate_character_with_semaphore()` — variant_id パラメータ追加**

**(E) `_load_or_create_mapping()` — clothing_variants 対応**

mapping.yaml 自動生成時に `clothing_variants: [{label: "default", clothing: null}]` を生成。

**(F) `generate_assets()` — 後方互換メソッドも同様に更新**

`clothing_images` が `dict[str, Path]` → 内部で `{"default": path}` に変換して処理。

### ディスク配置

変更後:
```
assets/character/{キャラ名}/
├── default/          # clothing_variants 未使用 or label="default" の場合
│   ├── front.png
│   ├── side.png
│   └── back.png
├── pajama/           # label="pajama" の場合
│   ├── front.png
│   ├── side.png
│   └── back.png
└── suit/
    ├── front.png
    ├── side.png
    └── back.png
```

### mapping.yaml フォーマット

**既存（後方互換）:**
```yaml
characters:
  - name: Aoi
    person: model_a.png
    clothing: casual.png     # → variant_id="default" として処理
```

**新規（複数衣装）:**
```yaml
characters:
  - name: Aoi
    person: model_a.png
    clothing_variants:
      - label: pajama
        clothing: pajama.png
      - label: suit
        clothing: suit.png
      - label: casual
        clothing: casual.png
```

## Step 3: Keyframe Engine 改修

### 3-1. `src/daily_routine/keyframe/engine.py`

`_resolve_character()` を `character_name` + `variant_id` の複合キーで解決:

```python
@staticmethod
def _resolve_character(
    assets: AssetSet, spec: SceneKeyframeSpec | None
) -> CharacterAsset:
    if spec and spec.character:
        if spec.variant_id:
            # character_name + variant_id で完全一致
            for char in assets.characters:
                if char.character_name == spec.character and char.variant_id == spec.variant_id:
                    return char
            logger.warning(
                "キャラクター '%s' variant '%s' が見つかりません。名前のみで検索します",
                spec.character, spec.variant_id,
            )
        # character_name の最初のバリアント
        for char in assets.characters:
            if char.character_name == spec.character:
                return char
        logger.warning(
            "キャラクター '%s' が見つかりません。デフォルトを使用します",
            spec.character,
        )
    return assets.characters[0]
```

### keyframe_mapping.yaml フォーマット

```yaml
scenes:
  - scene_number: 1
    character: Aoi
    variant_id: pajama       # 朝のシーン
    environment: bedroom
  - scene_number: 3
    character: Aoi
    variant_id: suit         # 通勤シーン
    environment: office
  - scene_number: 7
    character: Aoi
    variant_id: casual       # 夜のシーン
    environment: cafe
```

## Step 4: Pipeline Runner 改修

### 4-1. `src/daily_routine/pipeline/runner.py`

`_auto_generate_keyframe_mapping()` (行375-428) で `variant_id` を含める:

```python
character = assets.characters[0].character_name if assets.characters else ""
variant_id = assets.characters[0].variant_id if assets.characters else ""
# ...
SceneKeyframeSpec(
    scene_number=scene.scene_number,
    character=character,
    variant_id=variant_id,
    environment=environment,
    pose=pose,
)
```

自動生成では先頭バリアントを全シーンに割当。ユーザーが手動で各シーンの衣装を編集する。

## Step 5: テスト

### 既存テスト修正（後方互換で基本通るが、一部修正が必要）

| テストファイル | 修正内容 |
|---|---|
| `tests/test_schemas/test_asset.py` | `variant_id` デフォルト値のテスト追加 |
| `tests/test_asset_generator.py` | `_resolve_and_prepare_references` の返り値型変更に追従、`execute()` テスト更新 |
| `tests/test_keyframe/test_engine.py` | `_resolve_character` の variant_id 対応テスト追加 |
| `tests/test_keyframe_engine.py` | CharacterAsset 作成箇所の確認（デフォルトで通るはず）|
| `tests/test_pipeline/test_runner.py` | `variant_id` を含む keyframe_mapping 生成テスト |

### 新規テスト

- `test_schemas/test_asset.py`: `ClothingReferenceSpec` のテスト、`clothing` → `clothing_variants` 自動変換なし（validator なし）
- `test_asset_generator.py`: 複数衣装バリアント生成テスト（2衣装 × 3アングル = 6画像 + 2 identity_block）
- `test_keyframe/test_engine.py`: `character_name` + `variant_id` 複合検索テスト、variant_id 未指定時のフォールバックテスト

## Step 6: 設計書更新

`docs/designs/t1_overall_flow.md` のセクション 3.3, 3.4, 5 を更新:
- CharacterAsset に `variant_id` が追加されたことを記載
- keyframe_mapping.yaml のフォーマット例に `variant_id` を追加
- mapping.yaml の `clothing_variants` を記載

## 検証手順

1. `uv run pytest` — 全テスト通過を確認
2. `uv run ruff check . && uv run ruff format --check .` — リント・フォーマット通過
3. 既存の asset_set.json を `AssetSet.model_validate()` で読み込めることを確認（後方互換）
4. 既存の mapping.yaml（`clothing` のみ）が正しく読み込めることを確認
5. 既存の keyframe_mapping.yaml（`variant_id` なし）が正しく読み込めることを確認

## 実装順序まとめ

```
Step 1: スキーマ変更（asset.py, keyframe_mapping.py）+ テスト
Step 2: Asset Generator 改修（base.py, generator.py）+ テスト
Step 3: Keyframe Engine 改修（engine.py）+ テスト
Step 4: Pipeline Runner 改修（runner.py）+ テスト
Step 5: 全テスト実行 + リント
Step 6: 設計書更新
```
