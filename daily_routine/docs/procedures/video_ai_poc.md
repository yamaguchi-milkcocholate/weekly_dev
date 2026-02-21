# 動画生成AI比較検証（T0-2）実行手順

**対応する設計書:** `docs/designs/video_ai_poc_design.md`

## 1. 概要

4つの動画生成AI（Google Veo / Kling / Luma / Runway）に同一のリファレンス画像を入力し、キャラクター同一性の維持精度を定量評価する。

## 2. セットアップ

### 2.1 依存パッケージのインストール

```bash
uv sync --extra poc-video
```

### 2.2 環境変数の設定

```bash
# Kling AI
export DAILY_ROUTINE_API_KEY_KLING="your-key"

# Luma Dream Machine
export DAILY_ROUTINE_API_KEY_LUMA="your-key"

# Runway
export DAILY_ROUTINE_API_KEY_RUNWAY="your-key"

# GPT-4o Vision（評価用）
export DAILY_ROUTINE_API_KEY_OPENAI="your-key"
# または
export OPENAI_API_KEY="your-key"
```

Veo は GCP サービスアカウント認証を使用する。

```bash
gcloud auth login
gcloud config set project YOUR_GCP_PROJECT_ID
```

### 2.3 FFmpeg の確認

フレーム抽出に FFmpeg が必要。

```bash
ffmpeg -version
```

未インストールの場合:

```bash
brew install ffmpeg
```

## 3. 実行手順

### ステップ1: リファレンス画像の準備

Midjourney で以下の仕様でキャラクター画像を生成する。

| 項目 | 仕様 |
|------|------|
| キャラクター | 20代女性OL |
| ポーズ | 正面立ち姿、横向き歩行、背面立ち姿 |
| 解像度 | 1024x1024以上 |
| フォーマット | PNG |
| 背景 | 白背景 |

生成した画像を配置する。

```bash
poc/video_ai/reference/
├── front.png   # 正面
├── side.png    # 横向き
└── back.png    # 背面
```

### ステップ2: 画像のGCSアップロード（Kling/Luma/Runway用）

Kling、Luma、Runway は URL 指定で画像を入力するため、GCS にアップロードする。

```bash
# reference/ 内の全画像を一括アップロード
uv run python poc/video_ai/gcs.py --bucket YOUR_BUCKET
```

アップロード結果として各画像の公開 URL が表示される。

### ステップ3: 動画生成

```bash
# 全AI一括生成（GCSバケット指定で自動アップロード）
uv run python poc/video_ai/run_generation.py \
    --gcs-bucket YOUR_BUCKET \
    --veo-project-id YOUR_GCP_PROJECT

# 特定のAIのみ実行
uv run python poc/video_ai/run_generation.py \
    --gcs-bucket YOUR_BUCKET \
    --ais kling,runway

# 既にアップロード済みの画像URLを直接指定
uv run python poc/video_ai/run_generation.py \
    --image-url https://storage.googleapis.com/YOUR_BUCKET/poc/video_ai/reference/front.png
```

生成結果は `poc/video_ai/generated/{ai_name}/output.mp4` に保存される。
サマリーは `poc/video_ai/generated/generation_summary.json` に出力される。

### ステップ4: フレーム抽出

生成された動画から 1 秒間隔でフレームを PNG として抽出する。

```bash
uv run python poc/video_ai/extract_frames.py

# 特定のAIのみ
uv run python poc/video_ai/extract_frames.py --ais veo,kling
```

抽出されたフレームは `poc/video_ai/frames/{ai_name}/frame_001.png` 〜 に保存される。

### ステップ5: LLM評価（GPT-4o Vision）

リファレンス画像（正面）と各フレームを GPT-4o Vision で比較し、同一性スコアを算出する。

```bash
uv run python poc/video_ai/evaluate.py

# 特定のAIのみ
uv run python poc/video_ai/evaluate.py --ais veo,kling
```

各AIの評価結果は `poc/video_ai/evaluation/{ai_name}_scores.json` に保存される。

**評価項目（各フレームに対して 1〜10 のスコア）:**

| 項目 | 内容 |
|------|------|
| `face_similarity` | 顔の特徴の一致度 |
| `hair_consistency` | 髪型・髪色の一致度 |
| `outfit_consistency` | 服装の一致度 |
| `body_proportion` | 体型・プロポーションの一致度 |
| `overall_identity` | 総合的なキャラクター同一性 |

### ステップ6: 比較分析

```bash
uv run python poc/video_ai/compare.py
```

`poc/video_ai/evaluation/comparison_report.json` に比較レポートが生成される。
コンソールにキャラクター同一性ランキングが表示される。

**集約メトリクス:**

| メトリクス | 内容 |
|-----------|------|
| 平均スコア | 全フレームの `overall_identity` 平均 |
| 最低スコア | 最悪ケースの品質 |
| 安定性（標準偏差） | フレーム間のブレの少なさ |

### ステップ7: 追加評価（目視確認）

自動評価に加え、以下を手動で記録する。

| 評価項目 | 評価方法 |
|---------|---------|
| 動きの自然さ | 目視確認（5段階） |
| プロンプト追従性 | 目視確認（5段階） |
| 生成時間 | `generation_summary.json` の値を参照 |
| 実コスト | 各APIの課金履歴を確認 |
| API安定性 | エラー発生有無、リトライ必要性 |

### ステップ8: ADR 作成

評価結果に基づき `docs/adrs/001_video_generation_ai.md` を作成する。

## 4. 出力ファイル一覧

```
poc/video_ai/
├── generated/
│   ├── {ai_name}/output.mp4           # 生成動画
│   └── generation_summary.json         # 生成結果サマリー
├── frames/
│   └── {ai_name}/frame_*.png           # 抽出フレーム
└── evaluation/
    ├── {ai_name}_scores.json           # AI別の評価スコア
    └── comparison_report.json          # 比較レポート
```

## 5. コスト見積もり

| 項目 | 推定コスト |
|------|-----------|
| Veo（8秒 x 1本） | $4.00 |
| Kling（5秒 x 1本） | $0.21 |
| Luma（5秒 x 1本） | ~$1.60 |
| Runway（10秒 x 1本） | $0.50 |
| GPT-4o Vision評価 | ~$2.00 |
| **合計** | **~$8.32** |

## 6. トラブルシューティング

### Veo の認証エラー

```bash
gcloud auth print-access-token  # トークンが取得できるか確認
```

### 動画が生成されない

`generation_summary.json` でエラー内容を確認する。APIキーの有効性やレート制限を確認する。

### フレーム抽出に失敗する

FFmpeg がインストールされているか、動画ファイルが正常かを確認する。

```bash
ffprobe poc/video_ai/generated/{ai_name}/output.mp4
```
