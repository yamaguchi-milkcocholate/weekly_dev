# SNS AI Automation Agency

エリア紹介ショート動画自動生成システム（PoC 版）

## 概要

駅名・注目ポイント・動画秒数・Canva テンプレートを入力すると、事実ベースのテロップ付き縦動画を自動生成するシステムです。

### 主な機能

- **Perplexity API**: 事実ベースの情報検索
- **テロップ自動生成**: 12-16 字の短文テロップ作成
- **Canva 連携**: Bulk Create による映像生成
- **TTS 音声合成**: ElevenLabs/Murf API によるナレーション生成
- **FFmpeg 合成**: 映像+音声の自動合成

## 技術スタック

- **Python 3.11+**
- **FastAPI** (本格実装時)
- **JupyterLab** (実験・開発)
- **FFmpeg** (動画合成)
- **Cloud Run** (デプロイ先)

## 開発環境構築

### 1. 前提条件

- **uv**: Python パッケージマネージャ
- **Python 3.11 以上**

uv のインストール:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
# または
brew install uv
```

### 2. プロジェクトセットアップ

```bash
# リポジトリクローン
git clone <repository-url>
cd sns_ai_automation_agency

# 仮想環境作成・依存関係インストール
uv sync

# 環境変数設定
cp .env.example .env
# .envファイルを編集してAPIキーを設定
```

### 3. 環境変数設定

`.env`ファイルに以下の API キーを設定してください：

```env
# 必須: Perplexity API (事実情報検索用)
PERPLEXITY_API_KEY=your_perplexity_api_key_here

# オプション: 将来の機能拡張用
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
OPENAI_API_KEY=your_openai_api_key_here
```

#### API キーの取得方法

- **Perplexity API**: [Perplexity AI](https://www.perplexity.ai/) でアカウント作成後、API 設定から取得
- **ElevenLabs**: [ElevenLabs](https://elevenlabs.io/) でアカウント作成、API 設定から取得

### 4. 実行確認

#### JupyterLab 起動

```bash
uv run jupyter lab
```

#### Python 環境確認

```bash
uv run python --version
uv run which python
```

#### パッケージ確認

```bash
uv pip list
```

## 使用方法

### 1. 実験用 Notebook

Perplexity API の動作確認：

```bash
uv run jupyter lab perplexity_experiment.ipynb
```

この Notebook で以下をテストできます：

- Perplexity API による事実情報取得
- テロップ自動生成（12-16 字）
- スライド構成 JSON 生成
- Canva Bulk Create 用 CSV 出力

### 2. サンプル実行

吉祥寺の例：

- **エリア**: 吉祥寺
- **キーワード**: 公園、商店街、カフェ
- **動画尺**: 18 秒

## プロジェクト構造

```
sns_ai_automation_agency/
├── src/sns_ai_automation_agency/     # メインパッケージ
│   └── __init__.py
├── docs/                             # 設計書・要件定義
│   ├── DEFINISION_DOC.md
│   └── DESING_DOC.md
├── perplexity_experiment.ipynb       # 実験用Notebook
├── pyproject.toml                    # プロジェクト設定
├── .env.example                      # 環境変数テンプレート
└── README.md
```

## 開発フロー

### Phase 1: 実験・検証 (現在)

1. Perplexity API による素材抽出ロジック検証
2. テロップ生成アルゴリズム調整
3. スライド構成の最適化

### Phase 2: 本格実装

1. FastAPI Orchestrator 開発
2. TTS 統合（ElevenLabs/Murf）
3. FFmpeg 自動合成

### Phase 3: 統合・デプロイ

1. Zapier 連携
2. Cloud Run デプロイ
3. Canva Bulk Create 統合

## トラブルシューティング

### uv コマンドが見つからない

```bash
# uvを再インストール
curl -LsSf https://astral.sh/uv/install.sh | sh
source ~/.bashrc  # または ~/.zshrc
```

### API キーエラー

- `.env`ファイルの存在確認
- API キーの形式確認（前後のスペース等）
- Perplexity API の利用制限確認

### JupyterLab が起動しない

```bash
# 依存関係を再インストール
uv sync --reinstall
uv run jupyter lab --version
```

## ライセンス

MIT License

## 開発者

yamaguchi-milkcocholate
