# スタイル参照画像によるキーフレーム品質改善 設計書

## 1. 概要

Keyframe Engine が生成するキーフレーム画像に、ユーザー提供の**スタイル参照画像**（ロケーション・色味・雰囲気）を注入する機能を追加する。

現状のキーフレーム生成はテキストプロンプト + キャラクター参照画像（`@char`）のみで構図を決定しており、SNS でバズっている動画の「空気感」（照明の質・色温度・空間の奥行き感）を再現できない。テキストだけでは伝えられない視覚情報を、参照画像1枚で伝える。

## 2. 対象範囲

### 対象

- スタイル参照画像のマッピングスキーマ定義
- Keyframe Engine への参照画像注入（`@char` + `@location`）
- パイプラインのデータフロー変更（マッピング情報を Keyframe Engine に届ける）
- seeds YAML からの既存キャプチャ活用

### 対象外

- Intelligence Engine の変更（既存の `scene_captures` の扱いは変更しない）
- Storyboard Engine の変更（プロンプト生成ルールの変更は本設計に含まない）
- 参照画像の自動選定（LLM によるシーン↔キャプチャのマッチング）
- 参照画像の前処理（人物除去のインペイント等）

## 3. 背景と動機

### 3.1 現在の品質問題

パイプライン検証で生成されたキーフレーム画像に以下の問題が確認された:

1. **AI生成感が強い** — SNS で実写ベースの人気動画と比較すると、照明・色味・質感が「いかにもAI」に見える
2. **空気感の再現が困難** — 「warm amber highlights」等のテキスト指示だけでは、具体的な照明の質を制御しきれない
3. **シーン間の視覚的統一感が弱い** — 各カットが独立して生成されるため、色調やトーンにばらつきが出る

### 3.2 参照画像の効果

Runway Gen-4 Image は `referenceImages` で複数の参照画像を受け取れる。現状は `@char`（キャラクター同一性）のみ使用しているが、ロケーション参照を追加することで:

- 照明の質・色温度がテキストより正確に伝わる
- 空間の奥行き感・インテリアの質感が反映される
- SNS で実際にバズっている動画のトーンに寄せられる

### 3.3 参照画像の種類と安全性

| カテゴリ               | 参照画像として使うか    | 人物混入リスク           | 対処法                                       |
| ---------------------- | ----------------------- | ------------------------ | -------------------------------------------- |
| Location（環境・空間） | はい                    | 人物が映っている場合あり | 人物なしの画像を選定、または事前に除去       |
| Color Grading（色味）  | はい（Location と兼用） | 風景・物撮りから取得可能 | 人物なし素材を選べば安全                     |
| Outfit（服装）         | 将来検討                | 顔なしクロップで対処可能 | 本設計のスコープ外                           |
| Composition（構図）    | いいえ                  | —                        | プロンプトで制御（Storyboard Engine の責務） |

**重要:** 参照画像に実在人物が映っている場合、生成画像にその人物の特徴が混入するリスクがある。Location 参照は**人物が映っていない画像**を使用することを前提とする。

## 4. ユーザーワークフロー

### 4.1 3フェーズ方式

ユーザーは動画構成のプロではないため、最初から完璧な参照画像を揃えることは期待しない。パイプラインの進行に合わせて段階的に解像度を上げる。

```
Phase 1: ラフ投入（パイプライン実行前）
  ユーザーが seeds YAML に参考画像をラフに入れる
  → この時点では動画構成が未確定。タグ付け不要
      ↓
  Intelligence → Scenario → Storyboard（チェックポイントで停止）
      ↓
Phase 2: マッピング（Storyboard レビュー時）
  ユーザーが自動生成されたシーン構成を確認し:
  ・既存の参考画像をシーンに割り当てる
  ・足りない参考画像を追加する
  → style_mapping.yaml を作成
      ↓
  ユーザーが Storyboard を approve
      ↓
Phase 3: キーフレーム生成
  Keyframe Engine がマッピングに基づき参照画像を注入して生成
```

### 4.2 Phase 1: seeds YAML（変更なし）

既存の seeds YAML の `scene_captures` をそのまま活用する。新しいフィールドの追加は不要。

```yaml
# seeds/ol.yaml（変更なし）
seed_videos:
  - url: "https://youtube.com/shorts/..."
    note: "営業職の忙しさを、細かなカット割りで..."
    scene_captures:
      - image_path: "seeds/captures/TUI5ILZIcqU/7.png"
        description: "帰宅後のリラックスタイム。暖色の間接照明。"
        timestamp_sec: 39
      - image_path: "seeds/captures/TUI5ILZIcqU/3.png"
        description: "PC作業のPOVショット。ミニマルな構図。"
        timestamp_sec: 11
```

### 4.3 Phase 2: style_mapping.yaml（新規）

Storyboard レビュー時にユーザーが作成する。場所はプロジェクトディレクトリの `storyboard/` 配下。

```yaml
# outputs/projects/{id}/storyboard/style_mapping.yaml

mappings:
  - scene_number: 1
    reference: "seeds/captures/TUI5ILZIcqU/7.png"
  - scene_number: 3
    reference: "assets/reference/cafe.png" # 追加画像
  - scene_number: 5
    reference: "seeds/captures/TUI5ILZIcqU/3.png"
  # scene 2,4,6,7 は指定なし → キャラ参照のみで生成（現状と同じ）
```

**パス解決ルール:**

- 相対パスはプロジェクトルート（`outputs/projects/{id}/`）からの相対パスとして解決する
- `seeds/` で始まるパスはリポジトリルートからの相対パスとして解決する（seeds YAML の `image_path` と同じ規則）

**追加画像の配置先:**

```
outputs/projects/{id}/
├── assets/
│   ├── reference/          # ユーザーが追加画像を配置する
│   │   ├── cafe.png
│   │   └── bedroom.png
```

`assets/reference/` はプロジェクトディレクトリ構成（`t1_overall_flow.md` セクション6）で既に定義済み。

### 4.4 style_mapping.yaml が存在しない場合

**フォールバック:** マッピングファイルが存在しない場合、全カットをキャラクター参照のみで生成する（現状と同じ動作）。これにより後方互換性を維持する。

## 5. スキーマ設計

### 5.1 新規スキーマ: StyleMapping

```python
# src/daily_routine/schemas/style_mapping.py

"""スタイル参照画像のマッピングスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class SceneStyleReference(BaseModel):
    """1シーンのスタイル参照画像."""

    scene_number: int = Field(description="シーン番号")
    reference: Path = Field(description="参照画像のパス")


class StyleMapping(BaseModel):
    """スタイル参照画像のマッピング."""

    mappings: list[SceneStyleReference] = Field(
        default_factory=list,
        description="シーン番号と参照画像のマッピング",
    )

    def get_reference(self, scene_number: int) -> Path | None:
        """指定シーンの参照画像パスを返す。未指定なら None."""
        for m in self.mappings:
            if m.scene_number == scene_number:
                return m.reference
        return None
```

### 5.2 KeyframeInput の変更

```python
# schemas/pipeline_io.py

class KeyframeInput(BaseModel):
    """Keyframe Engine のパイプライン入力（複合）."""

    scenario: Scenario
    storyboard: Storyboard
    assets: "AssetSet"
    style_mapping: StyleMapping | None = None  # 追加
```

### 5.3 既存スキーマの変更

なし。`SeedVideo`, `SceneCapture`, `TrendReport`, `Storyboard`, `AssetSet` は変更しない。

## 6. Keyframe Engine の変更

### 6.1 現状の生成フロー

```python
# keyframe/engine.py（現状）
reference_image = assets.characters[0].front_view

request = ImageGenerationRequest(
    prompt=cut.keyframe_prompt,           # "@char stretches beside the bed..."
    reference_images={"char": reference_image},  # front.png のみ
)
```

### 6.2 変更後の生成フロー

```python
# keyframe/engine.py（変更後）
reference_image = assets.characters[0].front_view

# スタイル参照画像の解決
reference_images: dict[str, Path] = {"char": reference_image}
if style_mapping:
    style_ref = style_mapping.get_reference(cut.scene_number)
    if style_ref and style_ref.exists():
        reference_images["location"] = style_ref

request = ImageGenerationRequest(
    prompt=cut.keyframe_prompt,
    reference_images=reference_images,  # {"char": front.png, "location": cafe.png}
)
```

### 6.3 Runway API への影響

`referenceImages` に `{"tag": "location"}` が追加される。プロンプト内に `@location` タグが含まれていなくても、Runway API は参照画像の雰囲気（色味・照明・空間）を出力に反映する。

**`@location` タグをプロンプトに含めるかどうか:**

- 含めない場合: 参照画像の雰囲気が「ヒント」として使われる（弱い影響）
- 含める場合: 参照画像の内容が「配置指示」として使われる（強い影響）

本設計では**プロンプトに `@location` タグは含めない**方針とする。`keyframe_prompt` は引き続き `@char` のみを使用し、Location 参照は雰囲気の「寄せ」として機能させる。これにより:

- 既存の keyframe_prompt（Storyboard Engine 出力）を変更する必要がない
- 参照画像が未指定のシーンと指定済みのシーンで、プロンプト構造が変わらない
- 参照画像の影響度が過度にならない

> **注意:** この方針は PoC での検証結果に基づいて再検討する可能性がある。`@location` タグを明示した方が効果的な場合は、Storyboard Engine のプロンプト生成ルールの改修が別途必要になる。

### 6.4 execute() の変更

```python
async def execute(self, input_data: KeyframeInput, project_dir: Path) -> AssetSet:
    output_dir = project_dir / "assets" / "keyframes"
    return await self.generate_keyframes(
        storyboard=input_data.storyboard,
        assets=input_data.assets,
        output_dir=output_dir,
        style_mapping=input_data.style_mapping,  # 追加
    )
```

### 6.5 generate_keyframes() の変更

```python
async def generate_keyframes(
    self,
    storyboard: Storyboard,
    assets: AssetSet,
    output_dir: Path,
    style_mapping: StyleMapping | None = None,  # 追加
) -> AssetSet:
    reference_image = assets.characters[0].front_view
    all_cuts = [cut for scene in storyboard.scenes for cut in scene.cuts]

    keyframes: list[KeyframeAsset] = []
    for i, cut in enumerate(all_cuts, start=1):
        # 参照画像の構築
        reference_images: dict[str, Path] = {"char": reference_image}
        if style_mapping:
            style_ref = style_mapping.get_reference(cut.scene_number)
            if style_ref:
                resolved = self._resolve_path(style_ref, project_dir)
                if resolved.exists():
                    reference_images["location"] = resolved
                    logger.info(
                        "スタイル参照画像を適用: scene=%d, path=%s",
                        cut.scene_number, resolved,
                    )
                else:
                    logger.warning(
                        "スタイル参照画像が見つかりません: scene=%d, path=%s",
                        cut.scene_number, style_ref,
                    )

        request = ImageGenerationRequest(
            prompt=cut.keyframe_prompt,
            reference_images=reference_images,
        )
        result = await self._image_client.generate(request, keyframe_path)
        # ... 以下は現状と同じ
```

## 7. パイプライン統合

### 7.1 \_build_input の変更

`runner.py` の `_build_input` で、KEYFRAME ステップ時に `style_mapping.yaml` を読み込む。

```python
if step == PipelineStep.KEYFRAME:
    scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
    storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
    assets = create_engine(PipelineStep.ASSET).load_output(project_dir)
    style_mapping = _load_style_mapping(project_dir)  # 追加
    return KeyframeInput(
        scenario=scenario,
        storyboard=storyboard,
        assets=assets,
        style_mapping=style_mapping,
    )
```

### 7.2 \_load_style_mapping ヘルパー

```python
_STYLE_MAPPING_FILENAME = "style_mapping.yaml"

def _load_style_mapping(project_dir: Path) -> StyleMapping | None:
    """style_mapping.yaml を読み込む。ファイルが存在しなければ None を返す."""
    mapping_path = project_dir / "storyboard" / _STYLE_MAPPING_FILENAME
    if not mapping_path.exists():
        logger.info("style_mapping.yaml が見つかりません。スタイル参照なしで生成します")
        return None

    import yaml
    data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    return StyleMapping.model_validate(data)
```

### 7.3 パス解決ルール

`style_mapping.yaml` 内のパスは以下の順序で解決する:

1. 絶対パスならそのまま使用
2. `seeds/` で始まるパス → リポジトリルートからの相対パスとして解決
3. それ以外 → プロジェクトディレクトリ（`outputs/projects/{id}/`）からの相対パスとして解決

```python
def _resolve_path(self, path: Path, project_dir: Path) -> Path:
    """style_mapping 内のパスを実ファイルパスに解決する."""
    if path.is_absolute():
        return path
    # seeds/ で始まるパスはリポジトリルートから
    if str(path).startswith("seeds/"):
        return project_dir.parent.parent.parent / path  # outputs/projects/{id} → repo root
    # それ以外はプロジェクトディレクトリから
    return project_dir / path
```

> **注意:** リポジトリルートの解決方法は実装時に `global.yaml` の `data_root` 等から算出する方が堅牢。上記は簡易的な実装例。

## 8. データフロー全体図

```
seeds/ol.yaml
  └─ scene_captures[].image_path ─────────────────────┐
                                                       │
Intelligence → Scenario → Storyboard (checkpoint)     │
                               │                       │
                               ▼                       ▼
                    ユーザーがシーン構成を確認    既存キャプチャ
                    + 追加画像を配置              + 追加画像
                               │                       │
                               ▼                       │
                    style_mapping.yaml を作成 ◄─────────┘
                    (scene_number → image_path)
                               │
                               ▼
                    ユーザーが approve
                               │
                    Asset Generator
                               │
                               ▼
                    Keyframe Engine
                    ├─ @char: front.png（全カット共通）
                    └─ @location: style_ref.png（マッピングありのシーンのみ）
                               │
                               ▼
                    キーフレーム画像生成
```

## 9. ファイル配置

### 9.1 プロジェクトディレクトリ

```
outputs/projects/{id}/
├── storyboard/
│   ├── storyboard.json           # Storyboard（自動生成）
│   └── style_mapping.yaml        # スタイルマッピング（ユーザー手動作成）
├── assets/
│   ├── reference/                # ユーザー追加の参照画像
│   │   ├── cafe.png
│   │   └── bedroom.png
│   ├── character/                # キャラクターアセット（自動生成）
│   ├── keyframes/                # キーフレーム画像（自動生成）
│   └── asset_set.json
```

### 9.2 新規ソースファイル

```
src/daily_routine/
├── schemas/
│   └── style_mapping.py          # StyleMapping スキーマ（新規）
```

### 9.3 変更ソースファイル

```
src/daily_routine/
├── schemas/
│   └── pipeline_io.py            # KeyframeInput に style_mapping を追加
├── keyframe/
│   └── engine.py                 # 参照画像の構築ロジック変更
├── pipeline/
│   └── runner.py                 # _build_input で style_mapping を読み込み
```

## 10. コスト影響

スタイル参照画像を追加しても、Runway Gen-4 Image API の料金は変わらない（$0.02/枚）。参照画像の GCS アップロードコストも無視できる程度。

## 11. 実装計画

### ステップ1: StyleMapping スキーマ定義

- `src/daily_routine/schemas/style_mapping.py` を新規作成
- `SceneStyleReference`, `StyleMapping` を定義
- ユニットテスト: `get_reference()` の動作確認

**完了条件:** `uv run pytest tests/test_schemas/` が通る

### ステップ2: KeyframeInput の拡張

- `schemas/pipeline_io.py` の `KeyframeInput` に `style_mapping: StyleMapping | None = None` を追加
- 既存テストが壊れないことを確認（デフォルト None で後方互換）

**完了条件:** `uv run pytest` 全テスト通過

### ステップ3: Keyframe Engine の変更

- `keyframe/engine.py` の `generate_keyframes()` に `style_mapping` 引数を追加
- `execute()` から `style_mapping` を渡す
- 参照画像の構築ロジック（`@char` + `@location`）を実装
- パス解決ロジックを実装
- ユニットテスト: マッピングあり/なし/ファイル不存在の各ケース

**完了条件:** `uv run pytest tests/test_keyframe/` が通る

### ステップ4: パイプライン統合

- `runner.py` の `_build_input` で `_load_style_mapping()` を追加
- YAML 読み込み + `StyleMapping` へのバリデーション
- ファイル不存在時は None（フォールバック）

**完了条件:** `uv run pytest tests/test_pipeline/` が通る

### ステップ5: 動作検証

- `test-verify` プロジェクトで以下を検証:
  1. `style_mapping.yaml` なし → 現状と同じ動作（回帰なし）
  2. `style_mapping.yaml` あり → 参照画像付きでキーフレーム生成
  3. 参照画像ありのシーンとなしのシーンが混在 → 各シーンで正しく動作
- 生成画像の品質を目視確認

**完了条件:** キーフレーム画像に参照画像の雰囲気が反映されている

## 12. 将来の拡張

本設計のスコープ外だが、将来検討する可能性のある拡張:

| 項目                       | 概要                                                                                     |
| -------------------------- | ---------------------------------------------------------------------------------------- |
| `@location` タグの明示利用 | プロンプトに `@location` タグを含め、参照画像の影響度を上げる。PoC 結果に基づいて判断    |
| Outfit 参照画像            | シーンごとの衣装変更。`@outfit` タグで服装だけ変える。顔なしクロップが前提               |
| LLM 自動マッピング         | Storyboard の situation と scene_captures の description を LLM がマッチングして自動提案 |
| 参照画像の前処理           | 人物が映っている参照画像から自動で人物を除去（インペイント）                             |
