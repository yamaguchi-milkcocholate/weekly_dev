# C1-F2-MA 方式キャラクター生成への移行計画

## Context

現在の Asset Generator のキャラクター生成は、参照画像を直接 Pro に渡す簡易方式で実装されている。PoC 検証（`poc/seamless/C1_result.md`）で確立された **C1-F2-MA 方式**（Flash 融合分析 → Pro マルチアングル生成）に移行し、アングル間の一貫性向上とユーザー意図の反映精度を改善する。

### 目標フロー

```
mapping.yaml で参照画像を一元管理:
  - person/clothing が指定済み → そのまま使用
  - null/空欄 → テキストから person/clothing 画像を自動生成

→ 全キャラクターが C1-F2-MA を通る:
  Flash融合分析 → Proマルチアングル生成 → Identity Block抽出
```

### スコープ

- C1-F2-MA（Flash 分析 → Pro マルチアングル生成）+ C1-ID（Identity Block 抽出）
- mapping.yaml による参照画像管理（必須）
- 参照画像の自動生成（null 時に person/clothing をテキストから生成）
- **除外**: C2-R2（環境画像生成）は別タスク

---

## 運用フロー

### 基本フロー

```
1. uv run daily-routine init "OLの一日"
2. Intelligence → Scenario ステップ実行
3. Scenario 完了 → チェックポイント（AWAITING_REVIEW）

   mapping.yaml が自動生成される（全 person/clothing は null）
   ユーザーが参照画像を指定したい場合:
     a. assets/reference/person/ に人物画像を配置
     b. assets/reference/clothing/ に服装画像を配置
     c. mapping.yaml を編集してパスを指定

4. resume → Storyboard → ASSET ステップ実行
   - mapping.yaml の指定あり → その画像で C1-F2-MA
   - null のまま → テキストから自動生成 → C1-F2-MA
```

### mapping.yaml（必須、ASSET 開始時に自動生成 or 読み込み）

```yaml
# assets/reference/mapping.yaml
characters:
  - name: "Aoi"                    # CharacterSpec.name と一致
    person: "model_a.png"          # person/ からの相対パス（null → 自動生成）
    clothing: "casual.png"         # clothing/ からの相対パス（null → 自動生成）
  - name: "Yuki"
    person: "model_a.png"          # 同じ人物画像を共有可能
    clothing: "formal.png"
  - name: "Ren"
    person: null                   # null → appearance テキストから自動生成
    clothing: null                 # null → outfit テキストから自動生成
```

### 参照画像解決フロー（ASSET ステップ開始時）

```
1. mapping.yaml を読み込む（存在しなければ Scenario から自動生成、全 null）
2. 各キャラクターについて:
   - person/clothing が指定済み → reference/{person,clothing}/ 内のファイルを使用
   - null → テキストから Pro で自動生成し reference/{person,clothing}/ に保存
3. 全キャラクターの person + clothing が揃った状態で C1-F2-MA 実行
```

---

## 実装ステップ

### Step 1: `asset/client.py` — Flash テキスト分析メソッド追加

既存の LangChain ベース実装を維持しつつ、Flash モデル用のメソッドを追加。

**変更内容**:
- `__init__` に Flash 用 `ChatGoogleGenerativeAI` インスタンスを追加（`gemini-3-flash-preview`）
- `analyze_with_flash(prompt, images, temperature=0.0) -> str` メソッドを追加
  - 画像を base64 エンコードして `HumanMessage(content=[...])` で送信
  - `response.content`（文字列）を返す
  - tenacity リトライデコレータ付与
- 既存の `generate()`, `generate_with_reference()` は変更なし

### Step 2: `asset/prompt.py` — プロンプトテンプレート追加

**追加する定数**:
- `FLASH_FUSION_ANALYSIS_PROMPT` — Flash 融合分析（`character_generation.md` から移植）
- `IDENTITY_BLOCK_EXTRACTION_PROMPT` — Identity Block 抽出
- `_MA_GENERATION_TEMPLATE` — Pro マルチアングル生成テンプレート
- `_AUTO_PERSON_TEMPLATE` — 人物ベース画像自動生成
- `_AUTO_CLOTHING_TEMPLATE` — 服装画像自動生成

**PromptBuilder に追加するメソッド**:
- `build_ma_generation_prompt(flash_description, view) -> str`
- `build_auto_person_prompt(appearance) -> str`
- `build_auto_clothing_prompt(outfit) -> str`

**既存 `_VIEW_PROMPTS` の全身条件改善**:
- `"full body"` → `"full body shot from head to feet"` + `"space below the feet"`

### Step 3: `schemas/asset.py` — ReferenceMapping スキーマ追加

```python
class CharacterReferenceSpec(BaseModel):
    """キャラクター参照画像のマッピング."""
    name: str = Field(description="キャラクター名")
    person: str | None = Field(default=None, description="人物画像ファイル名（person/ 相対パス）")
    clothing: str | None = Field(default=None, description="服装画像ファイル名（clothing/ 相対パス）")

class ReferenceMapping(BaseModel):
    """参照画像マッピング設定."""
    characters: list[CharacterReferenceSpec] = Field(default_factory=list)
```

### Step 4: `asset/base.py` — ABC シグネチャ拡張

- `generate_character()` に `person_image: Path | None = None`, `clothing_image: Path | None = None` を追加
- `generate_assets()` に `person_images: dict[str, Path] | None = None`, `clothing_images: dict[str, Path] | None = None` を追加
- 全てデフォルト `None` で後方互換維持

### Step 5: `asset/generator.py` — C1-F2-MA フロー + mapping + 自動生成

**5a. mapping.yaml の管理**:
- `_load_or_create_mapping(characters, reference_dir) -> ReferenceMapping`
  - mapping.yaml が存在すれば読み込み
  - 存在しなければ Scenario の CharacterSpec[] から生成（全 person/clothing = null）し保存

**5b. 参照画像の解決 + 自動生成**:
- `_resolve_and_prepare_references(mapping, characters, reference_dir) -> dict[str, tuple[Path, Path]]`
  - 指定あり → パスを解決して返す
  - null → `_auto_generate_references()` で自動生成後に返す

**5c. `_auto_generate_references()` — テキストから画像生成**:
```
Pro(appearance テキスト) → person/{char_name}.png
Pro(outfit テキスト)     → clothing/{char_name}.png
```

**5d. `_generate_character_c1f2ma()` — C1-F2-MA 本体**:
```
Step 1: Flash 融合分析（person + clothing → flash_description）
Step 2: Pro マルチアングル生成（front/side/back × 3回）
Step 3: Flash Identity Block 抽出（front → identity_block）
Step 4: 表情バリエーション生成（既存ロジック流用、front を参照）
```

**5e. `execute()` の全体フロー**:
```python
async def execute(self, input_data: Scenario, project_dir: Path) -> AssetSet:
    reference_dir = project_dir / "assets" / "reference"

    # 1. mapping.yaml の読み込み or 生成
    mapping = self._load_or_create_mapping(input_data.characters, reference_dir)

    # 2. 参照画像の解決（null は自動生成）
    char_refs = await self._resolve_and_prepare_references(
        mapping, input_data.characters, reference_dir
    )

    # 3. 全キャラクターで C1-F2-MA 実行
    character_tasks = [
        self._generate_character_with_semaphore(
            semaphore, char,
            output_dir / "character" / char.name,
            person_image=char_refs[char.name][0],
            clothing_image=char_refs[char.name][1],
        )
        for char in input_data.characters
    ]
    character_assets = await asyncio.gather(*character_tasks)
    ...
```

**5f. mode 文字列**:
- `"c1f2ma_manual"` — ユーザー配置画像で C1-F2-MA
- `"c1f2ma_auto"` — 自動生成画像で C1-F2-MA

### Step 6: テスト更新

**`tests/test_asset_generator.py`**:

| テストケース | 検証内容 |
|---|---|
| C1-F2-MA（手動配置） | person+clothing 指定 → Flash分析2回 + Pro生成6回 |
| C1-F2-MA（自動生成） | null → 自動生成2回 + Flash分析2回 + Pro生成6回 |
| Identity Block 抽出 | `identity_block` が空でないこと |
| mapping.yaml 自動生成 | 存在しない場合に CharacterSpec[] から生成 |
| mapping.yaml 読み込み | 既存ファイルのパスが正しく解決されること |
| 共有人物画像 | 2キャラクターが同じ person を参照できること |

**`tests/test_asset_prompt.py`**:

| テストケース | 検証内容 |
|---|---|
| `build_ma_generation_prompt()` | 各アングルの構造・全身条件の存在 |
| `build_auto_person_prompt()` | appearance テキスト埋め込み |
| `build_auto_clothing_prompt()` | outfit テキスト埋め込み |
| 既存テスト | `_VIEW_PROMPTS` 変更に伴うアサーション値修正 |

**`tests/test_schemas/test_asset.py`**:
- `ReferenceMapping` / `CharacterReferenceSpec` の作成・シリアライズ・null 処理

---

## 変更対象ファイル一覧

| ファイル | 変更種別 |
|----------|----------|
| `src/daily_routine/asset/client.py` | 修正: Flash 分析メソッド追加 |
| `src/daily_routine/asset/prompt.py` | 修正: C1-F2-MA + 自動生成テンプレート + 全身条件改善 |
| `src/daily_routine/schemas/asset.py` | 修正: `ReferenceMapping` スキーマ追加 |
| `src/daily_routine/asset/base.py` | 修正: ABC シグネチャ拡張 |
| `src/daily_routine/asset/generator.py` | 修正: C1-F2-MA フロー + mapping管理 + 自動生成 |
| `tests/test_asset_generator.py` | 修正: 全モードのテスト追加 + 既存修正 |
| `tests/test_asset_prompt.py` | 修正: 新メソッドテスト + 既存修正 |
| `tests/test_schemas/test_asset.py` | 修正: `ReferenceMapping` テスト追加 |

**変更なし**: `schemas/scenario.py`、`config/manager.py`（ディレクトリ作成済み）、`pipeline/runner.py`

## API コール数

| パス | Flash | Pro | 合計 | コスト/キャラ |
|------|-------|-----|------|--------------|
| C1-F2-MA（手動配置） | 2 | 6 | 8 | **$0.26** |
| C1-F2-MA（自動生成） | 2 | 6 + 2(auto) = 8 | 10 | **$0.34** |

## 検証方法

1. `uv run pytest tests/test_asset_prompt.py` — プロンプト構築テスト
2. `uv run pytest tests/test_asset_generator.py` — 生成フローテスト
3. `uv run pytest tests/test_schemas/test_asset.py` — スキーマテスト
4. `uv run ruff check . && uv run ruff format --check .` — リント・フォーマット
5. 手動 E2E:
   - mapping.yaml 手動指定 + 画像配置 → C1-F2-MA（手動）
   - mapping.yaml 全 null → C1-F2-MA（自動生成）
