# APIキー設定を `.env` ファイル方式に変更

## Context

APIキーの設定方法が `~/.zshrc` 等への `export` 記述だったが、プロジェクトルートの `.env` ファイルで管理する方式に変更する。`python-dotenv` を導入し、`.env` の内容を `os.environ` に注入することで、既存の `_apply_env_overrides()` や各 PoC クライアントの `os.environ.get()` はそのまま動作する。

## 変更内容

### 1. `pyproject.toml` — 依存追加

`dependencies` に `python-dotenv>=1.0` を追加。

### 2. `.gitignore` — `.env` を除外対象に追加

```
# 環境変数（APIキー等の秘密情報）
.env
```

### 3. `.env.example`（新規作成）— テンプレート

```
DAILY_ROUTINE_API_KEY_STABILITY=
DAILY_ROUTINE_API_KEY_OPENAI=
DAILY_ROUTINE_API_KEY_GOOGLE_AI=
```

### 4. `src/daily_routine/config/manager.py` — `.env` 読み込み

- `from dotenv import load_dotenv` を追加
- `load_global_config()` の先頭で `load_dotenv(_REPO_ROOT / ".env")` を呼ぶ
- docstring を更新

### 5. `poc/image_gen/run_evaluation.py` — PoC エントリーポイント

- `main()` の先頭で `from dotenv import load_dotenv` + `load_dotenv()` を追加
- `evaluate_images()` の docstring/ログを「GPT-4o Vision」→「Gemini」に修正（前回の変更漏れ）

### 6. `tests/test_config.py` — テスト追加

- `.env` からAPIキーが読み込まれるテスト
- `export` が `.env` より優先されるテスト

### 7. ドキュメント更新

| ファイル | 変更内容 |
|---------|---------|
| `docs/procedures/api_key_setup.md` | セクション3を `.env` 方式に書き換え |
| `docs/procedures/project_setup.md` | 環境変数セクションを `.env` 方式に書き換え |
| `docs/procedures/image_gen_poc.md` | セクション2.2を `.env` 方式に書き換え |
| `docs/designs/project_skeleton_design.md` | 514行目の環境変数オーバーライド説明を更新 |

## 変更不要なファイル

| ファイル | 理由 |
|---------|------|
| `poc/image_gen/clients/stability.py` | `os.environ.get()` はそのまま動作 |
| `poc/image_gen/clients/dalle.py` | 同上 |
| `poc/image_gen/clients/gemini.py` | 同上 |
| `poc/image_gen/evaluate.py` | 同上 |
| `configs/global.yaml` | 変更なし |

## 検証方法

1. `uv sync` — 依存インストール
2. `uv run pytest tests/test_config.py -v` — テスト通過
3. `uv run ruff check .` — リントチェック
