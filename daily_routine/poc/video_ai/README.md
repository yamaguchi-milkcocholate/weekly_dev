# 動画生成AI比較検証（PoC）

4つの動画生成AI（Google Veo / Kling / Luma / Runway）でImage-to-Video生成を行い、キャラクター同一性の維持精度を定量評価する。

## セットアップ

```bash
uv sync --extra poc-video
```

### 環境変数

```bash
# Kling AI
export DAILY_ROUTINE_API_KEY_KLING="your-key"

# Luma Dream Machine
export DAILY_ROUTINE_API_KEY_LUMA="your-key"

# Runway
export DAILY_ROUTINE_API_KEY_RUNWAY="your-key"

# GPT-4o Vision（評価用）
export DAILY_ROUTINE_API_KEY_OPENAI="your-key"
# または export OPENAI_API_KEY="your-key"
```

Veoは `gcloud auth login` で認証する。

## 実行手順

### 1. リファレンス画像の準備

1. Midjourneyで1キャラクター × 3ポーズ（正面・横・背面）の画像を生成
2. `poc/video_ai/reference/` に `front.png`, `side.png`, `back.png` として配置

GCSへのアップロードは動画生成スクリプトが自動で行う（`--gcs-bucket` 指定時）。
手動でアップロードする場合:

```bash
uv run python poc/video_ai/gcs.py --bucket YOUR_BUCKET
```

### 2. 動画生成

```bash
# GCSバケット指定（ローカル画像を自動アップロード）
uv run python poc/video_ai/run_generation.py \
    --gcs-bucket YOUR_BUCKET \
    --veo-project-id YOUR_GCP_PROJECT
```

特定のAIのみ実行する場合:

```bash
uv run python poc/video_ai/run_generation.py \
    --gcs-bucket YOUR_BUCKET \
    --ais kling,runway
```

既にアップロード済みのURLを直接指定する場合:

```bash
uv run python poc/video_ai/run_generation.py \
    --image-url https://storage.googleapis.com/YOUR_BUCKET/front.png
```

### 3. フレーム抽出

```bash
uv run python poc/video_ai/extract_frames.py
```

### 4. LLM評価

```bash
uv run python poc/video_ai/evaluate.py
```

### 5. 比較分析

```bash
uv run python poc/video_ai/compare.py
```

`poc/video_ai/evaluation/comparison_report.json` に比較レポートが生成される。

## ディレクトリ構成

```
poc/video_ai/
├── reference/          # リファレンス画像（手動配置）
├── clients/            # 各AIのAPIクライアント
│   ├── base.py         # 共通インターフェース
│   ├── veo.py          # Google Veo
│   ├── kling.py        # Kling AI
│   ├── luma.py         # Luma Dream Machine
│   └── runway.py       # Runway
├── generated/          # 生成動画
├── frames/             # 抽出フレーム
├── evaluation/         # 評価結果JSON
├── gcs.py              # GCSアップロードユーティリティ
├── run_generation.py   # 一括生成スクリプト
├── extract_frames.py   # フレーム抽出
├── evaluate.py         # LLM評価
└── compare.py          # 比較分析
```
