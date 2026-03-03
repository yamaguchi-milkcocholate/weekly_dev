# ReferenceComponent に purpose フィールドを追加し、参照意図を Flash に正確に伝搬する

## Context

コンポーネント化改修で `ReferenceComponent` を導入したが、動作検証で**参照画像の「用途」が Flash に伝わらない**問題が判明した。

具体例: `full_face_mask.png` を `ReferenceComponent` で指定し、ポーズ指示で「フルフェイスマスクを装着している最中」と記述したが、Flash は「マスクをベンチの横に置く」描写を生成した。

**原因**: 参照画像は `"Additional reference: フルフェイスマスク"` という曖昧なテキストでしか Flash に渡されておらず、画像番号の説明も `"Image N shows additional reference."` のみ。Flash が参照の用途（装着中 vs 背景配置 vs 雰囲気参照）を推測する余地が大きすぎる。

## 改修概要

`ReferenceComponent` に `purpose` フィールドを追加し、参照の意図をプロンプト全体に伝搬する。

```yaml
# Before
- type: reference
  image: "assets/items/full_face_mask.png"
  text: "フルフェイスマスク"

# After
- type: reference
  image: "assets/items/full_face_mask.png"
  text: "フルフェイスマスク"
  purpose: wearing    # ← 装着中であることを明示
```

## 実装ステップ

### Step 1: スキーマ変更

**`src/daily_routine/schemas/keyframe_mapping.py`**

1. `ReferencePurpose(StrEnum)` を追加:
   - `wearing` — キャラクターが装着/着用しているアイテム
   - `holding` — 手に持っているアイテム
   - `atmosphere` — 雰囲気・スタイルの参照
   - `background` — 背景に配置するオブジェクト
   - `interaction` — キャラクターが操作/使用しているもの
   - `general` — 汎用（デフォルト、後方互換フォールバック）
2. `ReferenceComponent` に `purpose: ReferencePurpose = Field(default=ReferencePurpose.GENERAL)` を追加

### Step 2: プロンプト変更

**`src/daily_routine/keyframe/prompt.py`**

1. `ReferenceInfo` データクラスを追加: `purpose: str`, `text: str`, `has_image: bool`
2. `build_flash_meta_prompt` / `build_generation_prompt` のシグネチャ: `num_reference_images: int` → `reference_infos: list[ReferenceInfo]`
3. `_build_image_description`: 参照画像の説明を purpose に応じて変更
   - `wearing` → `"Image N shows an item the character is wearing/putting on: {text}."`
   - `general` → `"Image N shows additional reference: {text}."` （現行相当）
4. `_build_reference_instructions` 関数を新設: purpose に応じた明示的な指示を生成
   - `wearing` → `"The character MUST be actively wearing/putting on '{text}' as shown in the reference image."`
   - Flash メタプロンプトの末尾に `"IMPORTANT reference instructions:\n- ..."` として追加
5. `_build_image_description` の内部で `has_image=False` の参照は Image 番号に含めない

### Step 3: エンジン変更

**`src/daily_routine/keyframe/engine.py`**

1. `ResolvedComponents`: `reference_texts: list[str]` → `reference_infos: list[ReferenceInfo]`
2. `_resolve_components`: `ReferenceComponent` → `ReferenceInfo(purpose=str(comp.purpose), text=comp.text, has_image=comp.image is not None)` に変換

### Step 4: クライアント変更

**`src/daily_routine/keyframe/client.py`**

1. `analyze_scene`: `reference_texts: list[str]` → `reference_infos: list[ReferenceInfo]`
2. 参照テキストの contents 追加を purpose 付きに変更: `"Additional reference: ..."` → `"Item reference (character wears this): ..."` 等
3. `generate_keyframe`: `reference_infos` パラメータ追加（`build_generation_prompt` に転送）

### Step 5: テスト更新

**`tests/test_schemas/test_keyframe_mapping.py`**
- `ReferencePurpose` の全値パース、未指定時のデフォルト、不正値バリデーションエラーのテスト追加
- 既存 `ReferenceComponent` テストに `purpose` 検証を追加

**`tests/test_keyframe_engine.py`** / **`tests/test_keyframe/test_engine.py`**
- `reference_texts` → `reference_infos` のアサーション変更
- `purpose` 付き参照コンポーネントのテスト追加

**`tests/test_keyframe_prompt.py`** (新規)
- `build_flash_meta_prompt` の purpose 対応テスト（wearing/general/参照なし/複数参照）
- `_build_image_description` の purpose 対応テスト

### Step 6: 検証スクリプト更新

**`poc/keyframe_gen/verify_components.py`**
- `ReferenceComponent` に `purpose` を指定（`wearing`, `atmosphere`）
- プロンプト生成検証で purpose ごとの出力差分を表示
- 実際の API コールで Flash がアイテム装着を正しく描写するか確認

## 検証方法

1. `uv run pytest tests/test_schemas/test_keyframe_mapping.py tests/test_keyframe_engine.py tests/test_keyframe/test_engine.py tests/test_keyframe_prompt.py -v`
2. `uv run ruff check src/daily_routine/schemas/keyframe_mapping.py src/daily_routine/keyframe/`
3. `uv run python poc/keyframe_gen/verify_components.py --dry-run` — オフライン検証
4. `uv run python poc/keyframe_gen/verify_components.py` — API コール検証（wearing の描写が改善されたか目視確認）
