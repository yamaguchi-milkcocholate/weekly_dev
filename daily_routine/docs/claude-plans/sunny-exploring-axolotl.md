# キャラクターアセットのグリーンバック化

## Context

キャラクターアセット生成時の背景を白/ニュートラルからグリーンバック（クロマキー緑）に変更する。これにより、Keyframe Engine でキャラクターを環境画像に合成する際のキャラクター抽出精度が向上する。

## 変更対象ファイル

### 1. `src/daily_routine/asset/prompt.py` — 主要変更

**定数リネーム + 値変更:**
- `_WHITE_BG` → `_CHARACTER_BG` にリネーム
- 値を `"plain white background"` → `"solid bright green chroma key background (#00FF00)"` に変更

**テンプレート更新:**
- `_MA_GENERATION_TEMPLATE` (L60): `"neutral background"` → `"solid bright green chroma key background (#00FF00)"`
- `_AUTO_PERSON_TEMPLATE` (L76): `"plain white background"` → `"solid bright green chroma key background (#00FF00)"`

**メソッド更新:**
- `build_character_prompt()` (L128, L137): `_WHITE_BG` → `_CHARACTER_BG`

**変更しない:**
- `_AUTO_CLOTHING_TEMPLATE` (L83): 服装フラットレイ写真は白背景のまま維持
- `_C2R2_BASE_PROMPT` / `_C2_TEXT_GENERATION_SUFFIX`: 環境生成は無関係

### 2. `src/daily_routine/schemas/scenario.py` (L32-35)

`reference_prompt` の Field description を更新:
- `"白背景"` → `"グリーンバック（クロマキー緑）"`

### 3. `src/daily_routine/scenario/prompt.py` (L77-79)

LLM へのシステムプロンプト内の `reference_prompt` 生成指示を更新:
- `"白背景"` → `"グリーンバック（solid bright green chroma key background）"`

### 4. `tests/test_asset_prompt.py`

- L11: import `_WHITE_BG` → `_CHARACTER_BG`
- L33: fixture の `reference_prompt` 内 `"plain white background"` → `"solid bright green chroma key background (#00FF00)"`
- L65: assertion `_WHITE_BG` → `_CHARACTER_BG`
- L126: assertion `"plain white background"` → `"solid bright green chroma key background"`
- L141: **変更しない**（服装テンプレートは白背景維持）

### 5. テストフィクスチャ更新（5ファイル）

`reference_prompt` の文字列内 `"white background"` → `"green chroma key background"` に更新:
- `tests/test_asset_generator.py`
- `tests/test_scenario/test_validator.py`
- `tests/test_scenario/test_engine.py`
- `tests/test_storyboard/test_engine.py`
- `tests/test_storyboard/test_prompt.py`

### 6. `docs/image_gen_best_practices/character_generation.md`

プロンプトテンプレート例の `"neutral background"` → `"solid bright green chroma key background (#00FF00)"` に更新（L63, L98, L110 付近）

## 変更しないもの

| 対象 | 理由 |
|------|------|
| `_AUTO_CLOTHING_TEMPLATE` | 服装のフラットレイ写真。キャラクターの背景ではない |
| 環境生成プロンプト全般 | 環境画像の生成であり、キャラクター背景とは無関係 |
| `keyframe/` レイヤー | キャラ画像を identity 参照として使用するだけで、背景色は漏れない |
| `visual/` / `postproduction/` | キーフレーム画像を消費するため、キャラアセット背景に依存しない |

## 検証

```bash
uv run pytest                     # 全テスト通過を確認
uv run ruff check .               # リントチェック
uv run ruff format --check .      # フォーマットチェック
```
