# expressions生成処理の削除

## Context

Asset Generatorのキャラクター生成で、表情バリエーション（smile, serious, surprised）を3枚生成しているが、下流のKeyframe Engine・Visual Core等では一切使用されていない。不要なAPI呼び出し（3回/キャラ、約$0.12/キャラ）とストレージを消費しているため、生成処理を削除する。

## 変更対象ファイル

### 1. `src/daily_routine/schemas/asset.py`
- `CharacterAsset.expressions` フィールドを削除（L29-32）

### 2. `src/daily_routine/asset/prompt.py`
- `_EXPRESSION_PROMPTS` 辞書を削除（L22-28）
- `build_expression_prompt()` メソッドを削除（L149-179）

### 3. `src/daily_routine/asset/generator.py`
- `_DEFAULT_EXPRESSIONS` 定数を削除（L38）
- **C1-F2-MA メソッド内:**
  - expressions ディレクトリ作成を削除（L380-381）
  - 表情生成ループを削除（L410-417）
  - `CharacterAsset` コンストラクタから `expressions=expressions` を削除（L425）
- **Legacy メソッド内:**
  - expressions ディレクトリ作成を削除（L437-438）
  - 表情生成ループを削除（L467-479）
  - `CharacterAsset` コンストラクタから `expressions=expressions` を削除（L487）

### 4. `tests/test_asset_generator.py`
- 表情生成テストを削除（`test_generate_character_モードA_表情3種生成`、`test_C1F2MA_表情3種生成` 等）
- APIコール数のアサーションを更新（表情生成分の3回を減算）

### 5. `tests/test_asset_prompt.py`
- `TestBuildExpressionPrompt` テストクラスを削除（L89-114）

### 6. `tests/test_schemas/test_asset.py`
- expressions関連のテストがあれば削除

### 7. `docs/designs/t1_overall_flow.md`
- プロジェクトディレクトリ構造から `expressions/` エントリを削除（L461）

## 影響範囲

- 下流（Keyframe Engine, Visual Core, Storyboard等）での expressions 参照は **ゼロ** → 影響なし
- `CharacterAsset.expressions` のデフォルト値は `dict()` のため、既存のシリアライズ済みデータに expressions フィールドがあっても Pydantic が無視するだけ → 後方互換性の問題なし

## 検証方法

```bash
uv run pytest tests/test_asset_generator.py tests/test_asset_prompt.py tests/test_schemas/test_asset.py -v
uv run ruff check src/daily_routine/asset/ src/daily_routine/schemas/asset.py
uv run ruff format --check src/daily_routine/asset/ src/daily_routine/schemas/asset.py
```
