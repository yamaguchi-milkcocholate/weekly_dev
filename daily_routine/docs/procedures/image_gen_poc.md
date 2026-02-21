# 画像生成AI比較検証（T0-3）実行手順

**対応する設計書:** `docs/designs/image_generation_ai_evaluation_design.md`

## 1. 概要

画像生成AI 3種（Stability AI / DALL-E 3 / Gemini）を同一条件で比較評価し、キャラクター一貫性・画質・API利便性の観点から Asset Generator に最適な AI を選定する。

## 2. セットアップ

### 2.1 依存パッケージのインストール

```bash
uv sync --extra poc-image
```

### 2.2 環境変数の設定

```bash
# Stability AI
export DAILY_ROUTINE_API_KEY_STABILITY="your-key"

# OpenAI (DALL-E 3 + GPT-4o Vision 評価用)
export DAILY_ROUTINE_API_KEY_OPENAI="your-key"

# Google AI (Gemini / Imagen)
export DAILY_ROUTINE_API_KEY_GOOGLE_AI="your-key"
```

## 3. 実行手順

### 方法A: LangGraph ワークフローで一括実行（推奨）

画像生成 → GPT-4o Vision 評価 → レポート生成を一括で実行する。

```bash
uv run python -m poc.image_gen.run_evaluation
```

画像が既に生成済みの場合は評価のみ実行できる。

```bash
uv run python -m poc.image_gen.run_evaluation --evaluate-only
```

### 方法B: 段階的に実行

ワークフローの各ステップを個別に理解・デバッグしたい場合。

#### ステップ1: 画像生成（3AI x 3枚 = 9枚）

```python
import asyncio
from poc.image_gen.run_evaluation import run_full_evaluation
# または個別にクライアントを使用
from poc.image_gen.clients.stability import StabilityClient
from poc.image_gen.clients.dalle import DalleClient
from poc.image_gen.clients.gemini import GeminiClient
from poc.image_gen.config import GENERATED_DIR, VIEW_PROMPTS, NEGATIVE_PROMPT, build_prompt
from poc.image_gen.clients.base import GenerationRequest

# 例: Stability AI で正面画像を生成
client = StabilityClient(output_dir=GENERATED_DIR / "stability")
request = GenerationRequest(
    prompt=build_prompt(VIEW_PROMPTS[0]),
    negative_prompt=NEGATIVE_PROMPT,
)
result = asyncio.run(client.generate(request))
print(result.image_path)
```

#### ステップ2: GPT-4o Vision 評価

```python
import asyncio
from poc.image_gen.evaluate import evaluate_all
from poc.image_gen.config import GENERATED_DIR

results = asyncio.run(evaluate_all(GENERATED_DIR))
for r in results:
    print(f"{r.ai_name}: facial={r.score.facial_consistency}, "
          f"outfit={r.score.outfit_consistency}, "
          f"style={r.score.style_consistency}, "
          f"quality={r.score.overall_quality}")
```

## 4. テストキャラクター仕様

全 AI に統一のキャラクター設定を使用する（`poc/image_gen/config.py` で定義）。

| 項目 | 仕様 |
|------|------|
| 名前 | テストキャラクター Aoi |
| 年齢外見 | 25歳前後 |
| 髪 | ダークブラウン、セミロング（毛先内巻き） |
| 目 | ブラウン、やや大きめのアーモンド型 |
| 服装 | 白ブラウス（襟付き）、ネイビータイトスカート（膝丈）、ベージュパンプス |
| アクセサリー | 小さなゴールドピアス、腕時計 |
| スタイル | セミリアリスティック（アニメ調ではない） |

### 生成画像セット（各 AI ごと 3 枚）

| # | ビュー | ファイル名 | 評価ポイント |
|---|--------|-----------|-------------|
| 1 | 正面全身 | `front.png` | 顔の詳細、服装の再現性 |
| 2 | 横向き上半身 | `side.png` | 角度変化での一貫性 |
| 3 | 斜め後ろ全身 | `back.png` | 背面方向での一貫性 |

## 5. 評価基準

### 5.1 AI 自動評価（GPT-4o Vision）

3 枚の画像セットを一括で GPT-4o Vision に入力し、以下のスコア（0〜100）を取得する。

| 評価項目 | 内容 |
|----------|------|
| `facial_consistency` | 3枚間での顔の特徴の一貫性 |
| `outfit_consistency` | 3枚間での服装の一貫性 |
| `style_consistency` | 3枚間での画風・トーンの一貫性 |
| `overall_quality` | 画像の総合品質 |

### 5.2 加重スコア

レポート生成時に以下の重みで加重スコアを算出する。

| 項目 | 重み |
|------|------|
| 顔の一貫性 | 30% |
| 服装の一貫性 | 20% |
| 画風の一貫性 | 15% |
| 総合品質 | 20% |
| 目視評価（別途実施） | 15% |

### 5.3 人間による目視評価（別途実施）

生成された 9 枚の画像を確認し、以下の項目を 1〜5 で評価する。

| 評価項目 | 評価基準 |
|---------|---------|
| 顔の一貫性 | 3枚間で同一人物として認識できるか |
| 服装の一貫性 | 服装の色・形・ディテールが一致するか |
| 画質 | 解像度、ディテール、アーティファクトの有無 |
| プロンプト追従性 | 指定した特徴が正確に反映されているか |
| スタイルの統一感 | 3枚間で画風・トーンが統一されているか |

### 5.4 API 利便性の評価

| 評価項目 | 評価内容 |
|---------|---------|
| API設計 | RESTful / SDK 提供有無 |
| レスポンス時間 | `report.json` の `total_generation_time_sec` を参照 |
| コスト | `report.json` の `total_cost_usd` を参照 |
| 出力制御 | ネガティブプロンプト・シード固定の対応状況 |

各 AI の API 情報は以下で確認できる。

```python
from poc.image_gen.clients.stability import StabilityClient
from poc.image_gen.clients.dalle import DalleClient
from poc.image_gen.clients.gemini import GeminiClient
from poc.image_gen.config import GENERATED_DIR

for Client in [StabilityClient, DalleClient, GeminiClient]:
    c = Client(output_dir=GENERATED_DIR / "tmp")
    print(c.get_api_info())
```

## 6. 出力ファイル一覧

```
poc/image_gen/
├── generated/
│   ├── stability/
│   │   ├── front.png
│   │   ├── side.png
│   │   └── back.png
│   ├── dalle/
│   │   ├── front.png
│   │   ├── side.png
│   │   └── back.png
│   └── gemini/
│       ├── front.png
│       ├── side.png
│       └── back.png
└── evaluation/
    ├── ai_evaluation.json      # GPT-4o Vision の評価結果
    └── report.json             # 総合評価レポート
```

### report.json の構造

```json
{
  "title": "画像生成AI比較検証レポート",
  "results": [
    {
      "ai_name": "...",
      "model": "...",
      "scores": {
        "facial_consistency": 85,
        "outfit_consistency": 80,
        "style_consistency": 75,
        "overall_quality": 82
      },
      "weighted_score": 81.25,
      "total_generation_time_sec": 12.3,
      "total_cost_usd": 0.195
    }
  ],
  "ranking": ["AI名1", "AI名2", "AI名3"],
  "recommendation": "AI名1"
}
```

## 7. 評価完了後

評価結果に基づき `docs/adrs/002_image_generation_ai.md` を作成する。

## 8. トラブルシューティング

### Stability AI の 401 エラー

APIキーの有効性を確認する。Stability AI のダッシュボードでクレジット残高を確認する。

### DALL-E 3 のプロンプト改変

DALL-E 3 は内部でプロンプトをリライトする（revised_prompt）。`report.json` の `metadata.revised_prompt` でリライト後のプロンプトを確認できる。

### Gemini の画像生成失敗

リージョン制限の可能性がある。`GOOGLE_CLOUD_REGION` の設定を確認する。
