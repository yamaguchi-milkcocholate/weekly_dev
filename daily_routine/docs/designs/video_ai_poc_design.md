# 動画生成AI比較検証（Asset Driven Consistency PoC）設計書

## 1. 概要

- **対応する仕様書セクション:** 3.4章（Asset Generator）, 3.5章（Visual Core）, 7章（重点技術課題: Asset Driven Consistency, Video AI Selection）
- **サブタスクID:** T0-2
- **このサブタスクで実現すること:**
  - 4つの動画生成AI（Google Veo / Kling / Luma / Runway）に対し、同一のリファレンス画像を入力してImage-to-Video生成を行い、**キャラクター同一性の維持精度**を定量評価する
  - 評価結果に基づき、本パイプラインで採用する動画生成AIを選定し、ADR（`/docs/adrs/001_video_generation_ai.md`）として記録する

## 2. スコープ

### 対象範囲

- リファレンス画像（1キャラクター × 3ポーズ）の手動準備
- 4つの動画生成AIでのImage-to-Video生成（各AI 1クリップ）
- LLMベースのキャラクター同一性評価
- 評価結果の比較分析とAI選定

### 対象外

- 画像生成AIの自動化（T0-3で扱う）
- 複数キャラクターでの検証（Phase 2のT2-2で実運用評価）
- 動画生成のバッチ処理・リトライ機構（T1-4 Visual Coreで実装）
- 品質チェックの自動化フレームワーク（T4-1で実装）

## 3. 技術設計

### 3.1 全体フロー

```
[手動準備] リファレンス画像（正面・横・背面）
    ↓
[スクリプト] 各動画AI APIに画像+プロンプトを送信
    ↓
[各AI] Image-to-Video生成（4AI × 1クリップ = 4クリップ）
    ↓
[スクリプト] 生成動画からフレーム抽出
    ↓
[LLM評価] リファレンス画像 vs 抽出フレームの同一性スコアリング
    ↓
[分析] 評価結果の集約・比較レポート生成
    ↓
[成果物] ADR作成
```

### 3.2 リファレンス画像の準備

Midjourneyを使い、以下の仕様で1キャラクター分の画像を手動生成する。

| 項目 | 仕様 |
|------|------|
| キャラクター | 20代女性OL（「〇〇の一日」の典型的な主人公像） |
| ポーズ | 正面立ち姿、横向き歩行、背面立ち姿 |
| 解像度 | 1024×1024以上 |
| フォーマット | PNG |
| 背景 | 白背景（キャラクター特徴を動画AIに正確に伝えるため） |

生成した画像は `poc/video_ai/reference/` に配置する。

### 3.3 動画生成AI API仕様

#### Google Veo（Vertex AI）

| 項目 | 値 |
|------|------|
| モデル | `veo-2.0-generate-001`（コスト抑制のためVeo 2を使用） |
| エンドポイント | `POST https://us-central1-aiplatform.googleapis.com/v1/projects/{PROJECT_ID}/locations/us-central1/publishers/google/models/veo-2.0-generate-001:predictLongRunning` |
| 認証 | GCPサービスアカウント |
| 画像入力 | Base64エンコード |
| 動画長 | 8秒 |
| アスペクト比 | 9:16 |
| 推定コスト | $0.50/秒 × 8秒 = **$4.00** |

#### Kling AI

| 項目 | 値 |
|------|------|
| モデル | `kling-v2-5-turbo`（Image-to-Video対応、コスト効率良） |
| エンドポイント | `POST https://api.klingai.com/v1/videos/image2video` |
| 認証 | Bearer Token |
| 画像入力 | URL指定（事前にホスティング必要） |
| 動画長 | 5秒 |
| 推定コスト | $0.21（5秒 Standard） |

#### Luma Dream Machine

| 項目 | 値 |
|------|------|
| モデル | `ray-2` |
| エンドポイント | `POST https://api.lumalabs.ai/dream-machine/v1/generations` |
| 認証 | Bearer Token |
| 画像入力 | URL指定（`keyframes.frame0`） |
| 動画長 | 5秒 |
| 推定コスト | 約$1.60（$0.32/Mピクセル換算） |

#### Runway

| 項目 | 値 |
|------|------|
| モデル | `gen4_turbo`（コストパフォーマンス重視） |
| エンドポイント | `POST https://api.dev.runwayml.com/v1/image_to_video` |
| 認証 | Bearer Token + `X-Runway-Version: 2024-11-06` |
| 画像入力 | URL指定（`promptImage`） |
| 動画長 | 10秒 |
| 推定コスト | $0.05/秒 × 10秒 = **$0.50** |

#### 画像ホスティング

Kling・Luma・RunwayはURL指定が必要なため、リファレンス画像をGCS（Google Cloud Storage）の公開バケットにアップロードして使用する。

### 3.4 テストプロンプト

全AIに統一のプロンプトを使用し、条件を揃える。

```
A young Japanese office lady walking through a modern city street,
carrying a coffee cup, natural daylight, cinematic lighting,
vertical video 9:16 aspect ratio
```

### 3.5 評価手法（LLMベース）

#### フレーム抽出

生成された各動画から等間隔でフレームを抽出する。

| 項目 | 値 |
|------|------|
| 抽出間隔 | 1秒ごと |
| フォーマット | PNG |
| ツール | FFmpeg |

#### LLM評価プロンプト

GPT-4o Visionに以下を入力し、スコアリングさせる。

**入力:**
- リファレンス画像（正面）
- 評価対象フレーム画像

**評価プロンプト:**

```
以下の2枚の画像を比較してください。
1枚目はキャラクターのリファレンス画像（正解）です。
2枚目はAI動画生成の1フレームです。

以下の観点で1〜10のスコアをつけ、JSON形式で回答してください。

{
  "face_similarity": <顔の特徴の一致度 1-10>,
  "hair_consistency": <髪型・髪色の一致度 1-10>,
  "outfit_consistency": <服装の一致度 1-10>,
  "body_proportion": <体型・プロポーションの一致度 1-10>,
  "overall_identity": <総合的なキャラクター同一性 1-10>,
  "reasoning": "<判定理由の簡潔な説明>"
}
```

#### 集約方法

各動画の全抽出フレームのスコアを以下の方法で集約する。

| メトリクス | 計算方法 | 意味 |
|-----------|---------|------|
| 平均スコア | 全フレームの`overall_identity`平均 | 全体的な同一性維持度 |
| 最低スコア | 全フレームの`overall_identity`最小値 | 最悪ケースの品質 |
| 安定性 | `overall_identity`の標準偏差 | フレーム間のブレの少なさ |
| 各観点平均 | `face_similarity`等の各観点別平均 | 弱点の特定 |

### 3.6 追加評価項目

キャラクター同一性以外に、以下も記録する（ADRでの総合判断に使用）。

| 評価項目 | 評価方法 |
|---------|---------|
| 動きの自然さ | 目視確認（5段階） |
| プロンプト追従性 | 目視確認（5段階）— プロンプトの指示がどれだけ反映されているか |
| 生成時間 | API応答時間の計測 |
| コスト | 実際の課金額 |
| API安定性 | エラー発生有無、リトライ必要性 |

### 3.7 APIクライアントインターフェース

各動画生成AIクライアントは共通のインターフェースに従う（T0-3の画像生成AI評価と統一方針）。

```python
from abc import ABC, abstractmethod
from pathlib import Path
from pydantic import BaseModel


class VideoGenerationRequest(BaseModel):
    """動画生成リクエスト"""
    reference_image_path: Path
    prompt: str
    duration_sec: int = 5
    aspect_ratio: str = "9:16"


class VideoGenerationResult(BaseModel):
    """動画生成結果"""
    video_path: Path
    generation_time_sec: float
    model_name: str
    cost_usd: float | None = None
    metadata: dict = {}


class VideoGeneratorClient(ABC):
    """動画生成AIクライアントの共通インターフェース"""

    @abstractmethod
    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """リファレンス画像から動画を生成して保存し、結果を返す"""
        ...

    @abstractmethod
    def get_api_info(self) -> dict:
        """API情報（レート制限、コスト等）を返す"""
        ...
```

### 3.8 ディレクトリ構成

```
poc/
└── video_ai/
    ├── reference/              # リファレンス画像
    │   ├── front.png
    │   ├── side.png
    │   └── back.png
    ├── clients/                # 各AIのAPIクライアント
    │   ├── __init__.py
    │   ├── base.py            # 共通インターフェース（VideoGeneratorClient）
    │   ├── veo.py             # Google Veoクライアント
    │   ├── kling.py           # Kling AIクライアント
    │   ├── luma.py            # Luma Dream Machineクライアント
    │   └── runway.py          # Runwayクライアント
    ├── generated/              # 生成動画
    │   ├── veo/
    │   ├── kling/
    │   ├── luma/
    │   └── runway/
    ├── frames/                 # 抽出フレーム
    │   ├── veo/
    │   ├── kling/
    │   ├── luma/
    │   └── runway/
    ├── evaluation/             # 評価結果
    │   ├── veo_scores.json
    │   ├── kling_scores.json
    │   ├── luma_scores.json
    │   ├── runway_scores.json
    │   └── comparison_report.json
    ├── run_generation.py       # 全AI一括生成スクリプト
    ├── extract_frames.py       # フレーム抽出スクリプト
    ├── evaluate.py             # LLM評価スクリプト
    ├── compare.py              # 比較分析スクリプト
    └── README.md               # 実行手順
```

## 4. 実装計画

### ステップ1: リファレンス画像の準備

- Midjourneyで1キャラクター × 3ポーズの画像を手動生成
- `poc/video_ai/reference/` に配置
- GCSにアップロードし、公開URLを取得
- **完了条件:** 3枚の画像が配置され、公開URLでアクセス可能

### ステップ2: 動画生成クライアントの実装

- 共通インターフェース `VideoGeneratorClient(ABC)` を `clients/base.py` に実装
- 各AI用クライアント（`clients/veo.py`, `clients/kling.py`, `clients/luma.py`, `clients/runway.py`）を実装
- 非同期タスク方式のAPIはポーリングで完了を待機
- 一括生成スクリプト `run_generation.py` を作成
- **完了条件:** 4つのクライアントが動作し、各AIから動画が生成される

### ステップ3: フレーム抽出スクリプトの実装

- FFmpegで1秒間隔のフレーム抽出
- **完了条件:** 各動画からフレーム画像がPNGで出力される

### ステップ4: LLM評価スクリプトの実装

- GPT-4o Vision APIを使用したスコアリング
- リファレンス画像 vs 各フレームの比較を自動実行
- 結果をJSON形式で保存
- **完了条件:** 各動画のフレームごとにスコアJSONが出力される

### ステップ5: 比較分析スクリプトの実装

- 4つのAIのスコアを集約し、比較レポートを生成
- 平均スコア・最低スコア・安定性などのメトリクスを算出
- **完了条件:** `comparison_report.json` が生成され、AI間の比較が可能

### ステップ6: 実行・分析・ADR作成

- 全スクリプトを実行し、結果を収集
- 目視確認による追加評価項目も記録
- 結果に基づき `/docs/adrs/001_video_generation_ai.md` を作成
- **完了条件:** ADRが作成され、採用AIが決定される

## 5. テスト方針

| 検証対象 | 方法 |
|---------|------|
| API接続 | 各AIのAPIに最小リクエストを送信し、認証・レスポンスを確認 |
| 生成品質 | LLMスコアリングによる定量評価 + 目視確認 |
| スクリプト動作 | 各スクリプトを個別に実行し、期待する出力ファイルが生成されることを確認 |
| 評価の妥当性 | 同一フレームを複数回評価し、LLMスコアのブレ幅を確認（再現性チェック） |

## 6. 未決事項

| 項目 | 内容 | 判断タイミング |
|------|------|--------------|
| Veoのモデルバージョン | Veo 2で十分か、Veo 3.1も追加検証するか | ステップ2実行後、Veo 2の結果を見て判断 |
| LLM評価の再現性 | GPT-4o Visionのスコアリングが十分安定しているか | ステップ4実行後、同一入力での再現性テストで判断 |
| 動画長の統一 | AI間で動画長が異なる（5〜10秒）が、公平な比較が可能か | ステップ5の分析時に考慮 |
| GCS以外のホスティング | 画像URLの有効期限やアクセス制御の問題が発生した場合の代替手段 | ステップ1実行時に確認 |

## 7. コスト見積もり

| 項目 | 推定コスト |
|------|-----------|
| Veo（8秒 × 1本） | $4.00 |
| Kling（5秒 × 1本） | $0.21 |
| Luma（5秒 × 1本） | ~$1.60 |
| Runway（10秒 × 1本） | $0.50 |
| GPT-4o Vision評価（約28フレーム × 4AI） | ~$2.00 |
| GCSストレージ | ~$0.01 |
| **合計** | **~$8.32** |
