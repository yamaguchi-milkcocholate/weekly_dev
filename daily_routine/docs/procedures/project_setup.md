# プロジェクトセットアップ・CLI利用手順

**対応する設計書:** `docs/designs/project_skeleton_design.md`

## 1. 初期セットアップ

### 1.1 環境構築

```bash
cd daily_routine/
uv sync
```

正常にセットアップされたことを確認する。

```bash
uv run python -c "import daily_routine; print('OK')"
```

### 1.2 グローバル設定

グローバル設定ファイルはリポジトリ内の `configs/global.yaml` に配置されている。

```yaml
# データ保存ルート（リポジトリルートからの相対パスで解決される）
data_root: outputs

# APIキー（環境変数でもオーバーライド可能）
api_keys:
  youtube_data_api: ""
  openai: ""
  google_ai: ""

# デフォルトのプロジェクト設定
defaults:
  output_fps: 30
  output_duration_range: [30, 60]

# ロギング
logging:
  level: INFO
```

APIキーはプロジェクトルートの `.env` ファイルで設定する。`.env.example` をコピーして使用する。

```bash
cp .env.example .env
```

```dotenv
DAILY_ROUTINE_API_KEY_STABILITY=your-stability-key
DAILY_ROUTINE_API_KEY_OPENAI=your-openai-key
DAILY_ROUTINE_API_KEY_GOOGLE_AI=your-google-ai-key
DAILY_ROUTINE_API_KEY_KLING_AK=your-kling-access-key
DAILY_ROUTINE_API_KEY_KLING_SK=your-kling-secret-key
DAILY_ROUTINE_API_KEY_LUMA=your-luma-key
DAILY_ROUTINE_API_KEY_RUNWAY=your-runway-key
```

`export` で設定した環境変数は `.env` より優先される。

## 2. CLI の利用

### 2.1 ヘルプの確認

```bash
uv run daily-routine --help
```

### 2.2 新規プロジェクトの初期化

```bash
# プロジェクトIDを自動生成
uv run daily-routine init "OLの一日"

# プロジェクトIDを指定
uv run daily-routine init "OLの一日" --project-id my-project-001
```

このコマンドで以下が作成される。

- `outputs/projects/{project_id}/config.yaml` — プロジェクト設定
- 各レイヤーのデータディレクトリ（`intelligence/`, `scenario/`, `assets/`, `clips/`, `audio/`, `output/`）

### 2.3 パイプラインの実行（Phase 1 以降）

```bash
# 全ステップを実行
uv run daily-routine run "OLの一日"

# 特定ステップのみ実行
uv run daily-routine run "OLの一日" --step intelligence
```

> 注: 現在はスタブ実装。Phase 1 で各レイヤーが実装された後に有効化される。

### 2.4 プロジェクト状態の確認（Phase 1 以降）

```bash
uv run daily-routine status my-project-001
```

> 注: 現在はスタブ実装。

## 3. テストの実行

```bash
# 全テスト
uv run pytest tests/ -v

# スキーマテストのみ
uv run pytest tests/test_schemas/ -v

# 設定管理テストのみ
uv run pytest tests/test_config.py -v

# CLIテストのみ
uv run pytest tests/test_cli.py -v
```

## 4. ランタイムデータ構造

プロジェクト初期化後のディレクトリ構造は以下の通り。

```
outputs/
└── projects/
    └── {project_id}/
        ├── config.yaml             # プロジェクト設定
        ├── intelligence/           # TrendReport
        ├── scenario/               # Scenario, CaptionSet
        ├── assets/
        │   ├── character/          # キャラクターリファレンス画像
        │   ├── props/              # 小物画像
        │   └── backgrounds/        # 背景画像
        ├── clips/                  # シーンごとの動画クリップ
        ├── audio/
        │   ├── bgm/               # BGMファイル
        │   └── se/                # SEファイル
        └── output/                 # 最終出力
```
