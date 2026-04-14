# 小物（Props）画像生成機能の削除

## Context

Asset Generator で小物（Props）の画像を生成しているが、生成された画像は下流ステップ（Keyframe Engine, Visual Core）でほとんど使用されておらず、APIコールのコストだけがかかっている。Intelligence → Scenario → Asset Generator → AssetSet の全レイヤーから props 関連のコードとスキーマを削除する。

## 削除方針

- `PropSpec`（Scenario スキーマ）: **削除** — `image_prompt` フィールドが Asset Generator の画像生成専用
- `PropAsset`（Asset スキーマ）: **削除** — 生成物そのもの
- `VisualTrend.props` / `AssetRequirement.props`（Intelligence スキーマ）: **削除** — 下流で PropSpec を生成するためのデータだったため不要に
- 既存のシリアライズ済みデータ（`scenario.json`, `asset_set.json` 等）は非互換になるが、開発段階のため許容

## 変更対象ファイル

### Phase 1: スキーマ変更

**`src/daily_routine/schemas/asset.py`**
- `PropAsset` クラスを削除（L22-26）
- `AssetSet.props` フィールドを削除（L60）

**`src/daily_routine/schemas/scenario.py`**
- `PropSpec` クラスを削除（L38-45）
- `Scenario.props` フィールドを削除（L54）

**`src/daily_routine/schemas/intelligence.py`**
- `VisualTrend.props` を削除（L29）
- `AssetRequirement.props` を削除（L47）

### Phase 2: Asset Generator 層

**`src/daily_routine/asset/base.py`**
- `generate_assets()` から `props` パラメータを削除
- `generate_prop()` 抽象メソッドを削除
- import から `PropAsset`, `PropSpec` を除去

**`src/daily_routine/asset/generator.py`**
- `execute()` から `props=input_data.props` を削除（L85）
- `generate_assets()` から `props` パラメータと小物生成ブロック（L151-168）を削除
- `AssetSet` 構築から `props=list(prop_assets)` を削除（L183）
- ログメッセージから小物カウントを削除（L191-195）
- `generate_prop()` メソッドを削除（L275-291）
- `_generate_prop_with_semaphore()` メソッドを削除（L323-331）
- import から `PropAsset`, `PropSpec` を除去

**`src/daily_routine/asset/prompt.py`**
- `build_prop_prompt()` メソッドを削除（L104-116）

### Phase 3: Scenario Engine 層

**`src/daily_routine/scenario/prompt.py`**
- `build_system_prompt()` から:
  - `- 登場小物: {", ".join(vt.props)}`（L53）を削除
  - `- 小物: {", ".join(ar.props)}`（L65）を削除
  - `### 3. 小物仕様（props）` セクション全体（L83-87）を削除
  - 言語ルールから `PropSpec.name, PropSpec.description` を削除（L103）

### Phase 4: テスト更新

| ファイル | 変更内容 |
|----------|----------|
| `tests/test_schemas/test_asset.py` | `PropAsset` import・使用箇所を除去 |
| `tests/test_schemas/test_scenario.py` | `PropSpec` import・使用箇所を除去 |
| `tests/test_schemas/test_intelligence.py` | `props=` 引数を除去 |
| `tests/test_asset_generator.py` | `prop` fixture, `TestGenerateProp` クラス, 重複小物テスト, 各テストの `props=` 引数を除去 |
| `tests/test_asset_prompt.py` | `TestBuildPropPrompt` クラスを除去 |
| `tests/test_storyboard/test_prompt.py` | `PropSpec` import・使用箇所を除去 |
| `tests/test_visual_engine.py` | `PropAsset`/`PropSpec` import・使用箇所を除去 |
| `tests/test_keyframe/test_engine.py` | `PropAsset` import・使用箇所を除去 |
| `tests/test_scenario/test_engine.py` | `PropSpec`・`props=` 使用箇所を除去 |
| `tests/test_scenario/test_validator.py` | `PropSpec`・`_make_prop()`・`props=` を除去 |
| `tests/test_scenario/test_prompt.py` | `props=` 引数を除去 |
| `tests/test_intelligence/test_engine.py` | `"props"` キーを除去 |
| `tests/test_intelligence/test_trend_aggregator.py` | `"props"` キーを除去 |

### Phase 5: ドキュメント更新

**`docs/designs/t1_overall_flow.md`**
- AssetSet の説明から「小物」を削除
- Asset Generator の入力テーブルから props 行を削除
- 処理ロジックから【小物】セクションを削除
- 出力テーブルから PropAsset 行を削除
- スキーマ一覧テーブルから PropSpec/PropAsset を削除
- ディレクトリ構造から `props/` を削除
- コスト見積もりから小物行を削除

**`docs/procedures/project_setup.md`**
- ディレクトリ構造から `props/` を削除

## 検証

```bash
# テスト実行
uv run pytest tests/ -v

# リント
uv run ruff check .
uv run ruff format --check .
```
