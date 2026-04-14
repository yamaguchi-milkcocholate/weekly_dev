# Asset Generator 設計書

## 1. 概要

- **対応する仕様書セクション:** 3.4章（Asset Generator）
- **対応するサブタスク:** T1-3（Asset Generator）
- **依存するサブタスク:** T0-1（プロジェクト骨格）、T0-3（画像生成AI比較検証）
- **このサブタスクで実現すること:**
  - Gemini（ADR-002 で採用済み）を使用したキャラクター・小物・背景のリファレンス画像生成モジュールの実装
  - キャラクター同一性を維持するためのプロンプトテンプレート管理と参照画像制御の仕組み
  - パイプラインの `PipelineStep.ASSET` として統合可能なレイヤー実装

## 2. スコープ

### 対象範囲

- Asset Generator レイヤー（`src/daily_routine/asset/`）の本格実装
- Gemini API クライアントの本番用実装（PoC から昇格）
- キャラクター（正面・横・背面 + 表情バリエーション）、小物、背景のリファレンス画像生成
- プロンプトテンプレートの設計・管理
- 2つの一貫性維持モード（プロンプトのみ / ユーザー指定参照画像）
- ユニットテスト

### 対象外

- Visual Core との連携検証（T2-2 で実施）
- Web UI でのチェックポイント確認画面（T4-2 で実施）
- 自動品質チェックシステム（T4-1 で実施）
- パイプラインオーケストレーションへの統合（T1-1 で実施、本タスクではインターフェースのみ定義）

## 3. 技術設計

### 3.1 アーキテクチャ

```
src/daily_routine/asset/
├── __init__.py
├── base.py              # AssetGenerator ABC（レイヤー境界）
├── generator.py          # GeminiAssetGenerator 実装
├── prompt.py             # プロンプトテンプレート管理
└── client.py             # Gemini API クライアント（本番用）
```

### 3.2 レイヤー境界（ABC）

`base.py` でレイヤーの抽象インターフェースを定義する。他レイヤーからの依存は `schemas/` 経由のみ。

```python
from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet, CharacterAsset, PropAsset, BackgroundAsset
from daily_routine.schemas.scenario import CharacterSpec, PropSpec, SceneSpec


class AssetGenerator(ABC):
    """Asset Generator レイヤーの抽象インターフェース."""

    @abstractmethod
    async def generate_assets(
        self,
        characters: list[CharacterSpec],
        props: list[PropSpec],
        scenes: list[SceneSpec],
        output_dir: Path,
        user_reference_images: dict[str, Path] | None = None,
    ) -> AssetSet:
        """シナリオ仕様に基づき全アセットを生成する.

        Args:
            characters: キャラクター仕様リスト
            props: 小物仕様リスト（名前・説明・画像生成プロンプトを含む）
            scenes: シーン仕様リスト
            output_dir: 出力ディレクトリ
            user_reference_images: ユーザー指定の参照画像 {キャラクター名: 画像パス}
        """
        ...

    @abstractmethod
    async def generate_character(
        self,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None = None,
    ) -> CharacterAsset:
        """1キャラクターのリファレンス画像セットを生成する.

        Args:
            character: キャラクター仕様
            output_dir: 出力ディレクトリ
            reference_image: ユーザー指定の参照画像（省略時はプロンプトのみで生成）
        """
        ...

    @abstractmethod
    async def generate_prop(
        self,
        name: str,
        description: str,
        output_dir: Path,
    ) -> PropAsset:
        """小物の画像を生成する."""
        ...

    @abstractmethod
    async def generate_background(
        self,
        scene: SceneSpec,
        output_dir: Path,
    ) -> BackgroundAsset:
        """シーンの背景画像を生成する."""
        ...
```

### 3.3 Gemini API クライアント（本番用）

PoC（`poc/image_gen/clients/gemini.py`）の実装を本番用に昇格・拡張する。

**PoC からの変更点:**

| 項目           | PoC                      | 本番                                        |
| -------------- | ------------------------ | ------------------------------------------- |
| SDK            | `langchain-google-genai` | 同左（実績ある SDK を継続利用。SDK がHTTP通信を抽象化するため `httpx` 直接使用は不要） |
| 参照画像入力   | なし                     | Gemini の参照画像機能（最大14枚）を活用     |
| リトライ       | なし                     | 指数バックオフ付きリトライ（`tenacity`）    |
| 設定           | ハードコード             | `GlobalConfig` から読み込み                 |
| 出力ファイル名 | タイムスタンプ           | `{asset_type}_{name}_{view}.png` の命名規則 |

```python
class GeminiImageClient:
    """Gemini 画像生成クライアント（本番用）."""

    def __init__(self, api_key: str, model_name: str = "gemini-3-pro-image-preview") -> None:
        ...

    async def generate(self, prompt: str, output_path: Path) -> Path:
        """プロンプトから画像を生成して保存する."""
        ...

    async def generate_with_reference(
        self,
        prompt: str,
        reference_images: list[Path],
        output_path: Path,
    ) -> Path:
        """参照画像付きで画像を生成する.

        Gemini は最大14枚の参照画像を入力可能。
        キャラクター一貫性維持のために、正面画像やユーザー指定の参照画像を
        横・背面・表情の生成時に入力する。
        """
        ...
```

### 3.4 プロンプトテンプレート管理

キャラクター一貫性を確保するための標準プロンプトテンプレートを設計する。ADR-002 の結論（「一貫性はプロンプト・入力データで補完する方針」）に基づく。

```python
class PromptBuilder:
    """プロンプトテンプレートの構築・管理."""

    def build_character_prompt(
        self,
        character: CharacterSpec,
        view: str,  # "front" | "side" | "back"
        has_reference: bool = False,
    ) -> str:
        """キャラクターのビュー別プロンプトを構築する.

        Args:
            character: キャラクター仕様
            view: 生成するビュー
            has_reference: 参照画像がある場合 True（プロンプト構造が変わる）
        """
        ...

    def build_expression_prompt(
        self,
        character: CharacterSpec,
        expression: str,
        has_reference: bool = False,
    ) -> str:
        """キャラクターの表情バリエーション用プロンプトを構築する."""
        ...

    def build_prop_prompt(self, name: str, description: str) -> str:
        """小物の画像生成プロンプトを構築する."""
        ...

    def build_background_prompt(self, scene: SceneSpec) -> str:
        """背景の画像生成プロンプトを構築する."""
        ...
```

**プロンプト設計方針:**

PoC（`poc/image_gen/config.py`）で実証済みのプロンプト構造を踏襲する。

1. **キャラクター画像:** Scenario Engine の `CharacterSpec.reference_prompt` を基盤とし、以下を付加
   - スタイル指定: `"semi-realistic style, high quality, studio lighting"`（ADR-002 で重要と判明）
   - 背景: `"plain white background"`（リファレンス画像として使うため白背景固定）
   - ビュー指定: `"front view, standing pose"` 等（PoC の `VIEW_PROMPTS` 構造を活用）
   - 参照画像ありの場合: `"Generate this same character in..."` のように同一性を強調する指示を付加
   - **表情バリエーションでも `CharacterSpec.appearance` と `outfit` をプロンプトに明示する**（T1-3 実装時に、参照画像のみに依存すると画風がイラスト調にブレる事象を確認。テキストでの外見情報補強が有効）
2. **小物画像:** 白背景、スタジオライティング、商品撮影風
3. **背景画像:** シーンの `image_prompt` を基盤とし、キャラクター不在・背景のみの指定を付加

### 3.5 キャラクター一貫性維持メカニズム

2つのモードを提供し、ユーザーの状況に応じて使い分けられるようにする。

#### モードA: プロンプトのみモード（参照画像なし）

ユーザーが参照画像を持っていない場合のデフォルトモード。Gemini が最初から全画像を生成する。

```
1. 正面画像を生成（プロンプトのみ）
   ↓
2. 正面画像を自動生成された参照画像として横向き画像を生成
   ↓
3. 正面画像を参照画像として背面画像を生成
   ↓
4. 正面画像を参照画像として各表情バリエーションを生成
```

- 正面画像がアンカーとなるため、正面画像の品質が全体を左右する
- 正面画像の生成は最大3回リトライし、品質が許容基準に達しない場合はログに警告を出力して続行（自動品質チェックは T4-1 で本格実装）

#### モードB: ユーザー参照画像モード

ユーザーが既存のキャラクター画像（イラスト、写真等）を持っている場合に使用する。ユーザー指定の画像をアンカーとして、全ビュー・表情を生成する。

```
ユーザー指定画像（任意アングル）
   ↓
1. ユーザー画像を参照画像として正面画像を生成
   ↓
2. ユーザー画像 + 正面画像を参照画像として横向き画像を生成
   ↓
3. ユーザー画像 + 正面画像を参照画像として背面画像を生成
   ↓
4. ユーザー画像 + 正面画像を参照画像として各表情バリエーションを生成
```

- ユーザー画像が全生成の基準点となるため、一貫性がモードAより高くなることが期待される
- ユーザー画像は `projects/{project_id}/assets/reference/` に配置する前提
- Gemini の参照画像上限（14枚）に余裕があるため、ユーザー画像 + 自動生成正面画像の2枚を同時参照可能

#### モード選択のインターフェース

```python
# CLI からの使用例
# モードA（デフォルト）: 参照画像なし
await generator.generate_assets(characters, props, scenes, output_dir)

# モードB: ユーザー参照画像あり
await generator.generate_assets(
    characters, props, scenes, output_dir,
    user_reference_images={"Aoi": Path("assets/reference/aoi.png")},
)
```

### 3.6 GeminiAssetGenerator 実装

```python
class GeminiAssetGenerator(AssetGenerator):
    """Gemini を使った Asset Generator 実装."""

    def __init__(self, client: GeminiImageClient, prompt_builder: PromptBuilder) -> None:
        ...

    async def generate_assets(
        self,
        characters: list[CharacterSpec],
        props: list[PropSpec],
        scenes: list[SceneSpec],
        output_dir: Path,
        user_reference_images: dict[str, Path] | None = None,
    ) -> AssetSet:
        """全アセットを生成する.

        生成順序:
        1. キャラクター画像（正面 → 横・背面・表情の順で参照画像活用）
        2. 小物画像（props の image_prompt を使用。並列生成可能）
        3. 背景画像（並列生成可能）
        """
        ...
```

**生成フロー詳細:**

1. **キャラクター画像生成**（順次処理: 参照画像の依存関係あり）
   - 各キャラクターごとに正面 → 横 → 背面 → 表情の順で生成
   - `user_reference_images` が指定されている場合はモードB、なければモードA
   - 複数キャラクターがいる場合、キャラクター間は並列生成可能
2. **小物画像生成**（並列処理可能）
   - `props: list[PropSpec]` から小物リストを取得（Scenario Engine が `PropSpec.image_prompt` を含めて統合済み）
   - 各小物の `PropSpec.image_prompt` を使って画像を生成
   - 重複する小物は1回だけ生成
3. **背景画像生成**（並列処理可能）
   - 各シーンの `SceneSpec.image_prompt` を基に背景画像を生成
   - キャラクター不在の背景として生成

### 3.7 出力ディレクトリ構造

プロジェクト初期化時（`config/manager.py` の `init_project`）に作成済みのディレクトリに出力する。

**注意:** `assets/reference/` はユーザーが参照画像を配置するためのディレクトリで、`config/manager.py` の `init_project()` のサブディレクトリリストに `"assets/reference"` を追加する必要がある。`assets/character/{character_name}/` および `assets/character/{character_name}/expressions/` は `generate_character()` 実行時に動的に作成する。

```
projects/{project_id}/assets/
├── reference/               # ユーザー指定の参照画像（モードB用、手動配置）
│   └── {character_name}.png
├── character/
│   └── {character_name}/
│       ├── front.png
│       ├── side.png
│       ├── back.png
│       └── expressions/
│           ├── smile.png
│           ├── serious.png
│           └── ...
├── props/
│   ├── {prop_name}.png
│   └── ...
└── backgrounds/
    ├── scene_01.png
    ├── scene_02.png
    └── ...
```

### 3.8 エラーハンドリング

| エラー種別                            | 対応                                           |
| ------------------------------------- | ---------------------------------------------- |
| API レート制限                        | 指数バックオフリトライ（最大3回、初回待機2秒） |
| 画像未生成（Gemini が画像を返さない） | リトライ（最大3回）後、エラーで停止            |
| API キー未設定                        | 起動時に `ValueError` で即時停止               |
| 不正なレスポンス形式                  | ログ出力 + リトライ                            |
| ユーザー参照画像が存在しない          | `FileNotFoundError` で即時停止                 |

## 4. 入出力仕様

### 入力

| ソース              | データ                   | スキーマ                                       |
| ------------------- | ------------------------ | ---------------------------------------------- |
| Scenario Engine     | キャラクター仕様         | `schemas.scenario.CharacterSpec`               |
| Scenario Engine     | シーン仕様               | `schemas.scenario.SceneSpec`                   |
| Intelligence Engine | 素材要件（小物・背景リスト） | `schemas.intelligence.AssetRequirement`        |
| ユーザー（任意）    | 参照画像                 | `dict[str, Path]`（キャラクター名 → 画像パス） |
| 設定                | API キー                 | `GlobalConfig.api_keys.google_ai`              |
| 設定                | プロジェクトディレクトリ | `GlobalConfig.data_root` 配下                  |

**入力データの関係:**

- **キャラクターリスト:** `CharacterSpec`（Scenario Engine）から取得。外見・服装・プロンプトが含まれる
- **小物リスト:** `AssetRequirement.props`（Intelligence Engine → Scenario Engine 経由）から取得。Scenario Engine がトレンド分析の素材要件をシナリオに統合済みの前提
- **背景リスト:** `SceneSpec`（Scenario Engine）の各シーン情報から導出。`AssetRequirement.backgrounds` も補助的に参照する

### 出力

| データ          | スキーマ                 | 保存先                                                                   |
| --------------- | ------------------------ | ------------------------------------------------------------------------ |
| アセットセット  | `schemas.asset.AssetSet` | `projects/{id}/assets/`                                                  |
| メタデータ JSON | -                        | `projects/{id}/assets/metadata.json`（生成時間、モデル名、使用モード等） |

### 入出力例

#### 入力例

**CharacterSpec（Scenario Engine から）:**

```python
CharacterSpec(
    name="Aoi",
    appearance="25-year-old Japanese woman, shoulder-length black hair with soft waves, "
               "slim build, 165cm tall, fair skin, gentle oval face",
    outfit="navy blue blazer over white blouse, gray pencil skirt, black low heels, "
           "small silver watch on left wrist",
    reference_prompt="A 25-year-old Japanese woman with shoulder-length black hair with soft waves, "
                     "slim build, 165cm tall, fair skin, gentle oval face. "
                     "Wearing navy blue blazer over white blouse, gray pencil skirt, black low heels, "
                     "small silver watch on left wrist. "
                     "Full body standing pose, front view, plain white background, studio lighting, "
                     "semi-realistic style, high quality",
)
```

**PropSpec（Scenario Engine から）:**

```python
PropSpec(
    name="ラテアート付きコーヒーカップ",
    description="カフェシーンで使用するラテアート付きのコーヒーカップ。白い陶器製、ハート型のラテアート",
    image_prompt="A white ceramic coffee cup with latte art in heart shape, "
                 "on plain white background, studio lighting, product photography style, high quality",
)
```

**SceneSpec（Scenario Engine から、背景生成に使用）:**

```python
SceneSpec(
    scene_number=1,
    duration_sec=3.0,
    situation="朝、主人公が目覚まし時計のアラームで目を覚ます",
    camera_work=CameraWork(type="close-up", description="顔のアップから引いていく"),
    caption_text="朝6時…今日も始まる",
    image_prompt="Modern Japanese apartment bedroom in early morning, "
                 "soft sunlight through white curtains, minimalist interior, "
                 "warm color tone, no people, photorealistic",
    video_prompt="Camera slowly pulls back, morning light gradually brightens",
)
```

**ユーザー参照画像（任意、モードB 使用時）:**

```python
user_reference_images = {
    "Aoi": Path("projects/my-project/assets/reference/aoi.png"),
}
```

#### 出力例

**AssetSet:**

```python
AssetSet(
    characters=[
        CharacterAsset(
            character_name="Aoi",
            front_view=Path("projects/my-project/assets/character/Aoi/front.png"),
            side_view=Path("projects/my-project/assets/character/Aoi/side.png"),
            back_view=Path("projects/my-project/assets/character/Aoi/back.png"),
            expressions={
                "smile": Path("projects/my-project/assets/character/Aoi/expressions/smile.png"),
                "serious": Path("projects/my-project/assets/character/Aoi/expressions/serious.png"),
                "surprised": Path("projects/my-project/assets/character/Aoi/expressions/surprised.png"),
            },
        ),
    ],
    props=[
        PropAsset(
            name="ラテアート付きコーヒーカップ",
            image_path=Path("projects/my-project/assets/props/latte_coffee_cup.png"),
        ),
        PropAsset(
            name="スマートフォン",
            image_path=Path("projects/my-project/assets/props/smartphone.png"),
        ),
    ],
    backgrounds=[
        BackgroundAsset(
            scene_number=1,
            description="朝のマンション寝室",
            image_path=Path("projects/my-project/assets/backgrounds/scene_01.png"),
        ),
        BackgroundAsset(
            scene_number=2,
            description="通勤電車内",
            image_path=Path("projects/my-project/assets/backgrounds/scene_02.png"),
        ),
        BackgroundAsset(
            scene_number=3,
            description="オフィスのデスク",
            image_path=Path("projects/my-project/assets/backgrounds/scene_03.png"),
        ),
    ],
)
```

**メタデータ JSON（`assets/metadata.json`）:**

```json
{
  "generated_at": "2026-02-24T10:30:00+09:00",
  "model_name": "gemini-3-pro-image-preview",
  "mode": "prompt_only",
  "characters_generated": 1,
  "props_generated": 2,
  "backgrounds_generated": 3,
  "total_api_calls": 9
}
```

#### 呼び出し例

**モードA（プロンプトのみ）:**

```python
generator = GeminiAssetGenerator(client=client, prompt_builder=prompt_builder)

asset_set = await generator.generate_assets(
    characters=scenario.characters,
    props=scenario.props,
    scenes=scenario.scenes,
    output_dir=Path("projects/my-project/assets"),
)
```

**モードB（ユーザー参照画像あり）:**

```python
asset_set = await generator.generate_assets(
    characters=scenario.characters,
    props=scenario.props,
    scenes=scenario.scenes,
    output_dir=Path("projects/my-project/assets"),
    user_reference_images={"Aoi": Path("projects/my-project/assets/reference/aoi.png")},
)
```

## 5. 実装計画

### ステップ1: Gemini API クライアントの本番実装

- `src/daily_routine/asset/client.py` を実装
- PoC の `GeminiClient` をベースに、参照画像入力・リトライ・設定管理を追加
- **完了条件:** API キーを設定した状態でテキストプロンプトから画像生成ができる。参照画像付き生成ができる

### ステップ2: プロンプトテンプレート管理の実装

- `src/daily_routine/asset/prompt.py` を実装
- キャラクター（ビュー別・表情別）、小物、背景のプロンプトテンプレートを定義
- 参照画像あり/なしでプロンプト構造を切り替えるロジック
- `CharacterSpec` / `SceneSpec` からプロンプトを自動構築するロジック
- **完了条件:** `CharacterSpec` を入力として、両モードの正面・横・背面のプロンプトが生成される

### ステップ3: AssetGenerator ABC と Gemini 実装

- `src/daily_routine/asset/base.py` に ABC を定義
- `src/daily_routine/asset/generator.py` に `GeminiAssetGenerator` を実装
- モードA（プロンプトのみ）とモードB（ユーザー参照画像）の両方の生成フロー
- 小物・背景の並列生成
- **完了条件:** 両モードで `generate_assets()` が `AssetSet` を返し、画像ファイルが所定ディレクトリに保存される

### ステップ4: ユニットテスト

- Gemini API クライアントのモックテスト（実 API 呼び出しなし）
- プロンプトビルダーのテスト（入力 → 期待プロンプト文字列の検証、両モード）
- `GeminiAssetGenerator` のモックテスト（モードA/B の生成フロー正しさ検証）
- **完了条件:** `uv run pytest tests/test_asset*.py` が全テストパス

## 6. テスト方針

### ユニットテスト（CI 対象）

```
tests/
├── test_asset_client.py      # GeminiImageClient のモックテスト
├── test_asset_prompt.py      # PromptBuilder のテスト
└── test_asset_generator.py   # GeminiAssetGenerator のモックテスト
```

| テスト対象             | テスト内容                                                                                                                   |
| ---------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `GeminiImageClient`    | リクエスト構築の正確性、レスポンスパース、リトライ動作、参照画像入力                                                         |
| `PromptBuilder`        | 各種プロンプトテンプレートの出力検証、モードA/B のプロンプト切り替え、`CharacterSpec` → プロンプト変換                       |
| `GeminiAssetGenerator` | モードA: 生成順序（正面 → 横 → 背面）と自動参照画像の引き渡し。モードB: ユーザー参照画像の正しい利用。出力 `AssetSet` の構造 |

### 統合テスト（手動、CI 対象外）

- 実際の Gemini API を呼び出してキャラクター画像セットを生成
- モードA/B 両方で参照画像活用時の一貫性を目視確認

## 7. リスク・検討事項

| リスク                                          | 影響                                             | 対策                                                                         |
| ----------------------------------------------- | ------------------------------------------------ | ---------------------------------------------------------------------------- |
| Gemini API がプレビュー版のため仕様変更の可能性 | クライアント実装の修正が必要                     | モデル名を設定値として外出し。クライアントを抽象化し差し替え可能に           |
| 参照画像活用でも一貫性が不十分な場合            | キャラクターの見た目がシーン間で変化             | T2-2（Scenario→Asset→Visual 結合）で実運用評価し、プロンプト調整で対応。**T1-3 実装時の知見:** 表情バリエーション生成時、参照画像のみに依存すると画風がフォトリアル→イラスト調にブレる事象を確認。`appearance`/`outfit` をテキストで明示することで緩和済み |
| ユーザー参照画像の品質が低い場合                | 生成結果の品質低下                               | ログで画像サイズ・フォーマットの情報を出力。品質チェックは T4-1 で対応       |
| 画像生成のコスト増                              | キャラクター数・シーン数に比例してAPI コスト増加 | 小物・背景は可能な限り再利用。キャラクターの表情バリエーションは必要最小限に |
| Gemini API のレート制限                         | 大量生成時にスロットリング                       | 並列数の制御（`asyncio.Semaphore`）、リトライ間隔の調整                      |

## 8. 参考資料

- 仕様書: `/docs/specs/initial.md` 3.4章
- ADR-002: `/docs/adrs/002_image_generation_ai.md`（Gemini 採用決定）
- PoC 実装: `poc/image_gen/clients/gemini.py`、`poc/image_gen/config.py`
- 既存スキーマ: `src/daily_routine/schemas/asset.py`、`src/daily_routine/schemas/scenario.py`
