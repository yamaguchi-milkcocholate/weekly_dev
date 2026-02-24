# CLI ↔ Intelligence Engine 疎通計画

## Context

T1-2 (Intelligence Engine) の実装は完了し、44件のユニットテストが全てパスしている。
しかし、CLI から Intelligence Engine を実際に呼び出すためのインテグレーションに **4つのギャップ** がある。
これらを修正し、`uv run daily-routine run "OLの一日"` でエンドツーエンドの動作確認を行う。

## 発見したギャップ

1. **エンジン未登録**: `pipeline/__init__.py` が空で、IntelligenceEngine が registry に登録されていない
2. **APIキー未注入**: `create_engine(step)` が `_registry[step]()` を引数なしで呼ぶため、API キーが渡らない
3. **seed_videos が空**: `_build_input(INTELLIGENCE, ...)` が `IntelligenceInput(keyword=keyword)` のみ返す（seed_videos はデフォルト `[]`）→ 初回テストでは許容。拡張検索のみで動作する
4. **API キー未設定**: `.env` に YouTube Data API / Google AI のキーが必要

## 実装ステップ

### Step 1: `registry.py` に `**kwargs` サポートを追加

**ファイル**: `src/daily_routine/pipeline/registry.py`

- `create_engine(step, **kwargs)` に変更し、`_registry[step](**kwargs)` でインスタンス化する
- 各エンジンが必要なキーワード引数を受け取れるようにする

### Step 2: `pipeline/__init__.py` で IntelligenceEngine を登録

**ファイル**: `src/daily_routine/pipeline/__init__.py`

```python
from daily_routine.pipeline.registry import register_engine
from daily_routine.schemas.project import PipelineStep
from daily_routine.intelligence.engine import IntelligenceEngine

register_engine(PipelineStep.INTELLIGENCE, IntelligenceEngine)
```

### Step 3: `runner.py` で API キーを `create_engine` に渡す

**ファイル**: `src/daily_routine/pipeline/runner.py`

- `run_pipeline`, `resume_pipeline`, `retry_pipeline` に `api_keys: dict[str, str] | None = None` 引数を追加
- ヘルパー `_engine_kwargs(step, api_keys)` を新設し、ステップごとに必要なキーワード引数を構築
  - `INTELLIGENCE` → `youtube_api_key`, `google_ai_api_key`, `openai_api_key`
  - 他のステップ → 今後の実装時に追加（現時点では空 dict）
- `create_engine(step, **_engine_kwargs(step, api_keys))` で呼び出す

### Step 4: `cli/app.py` で API キーを runner に渡す

**ファイル**: `src/daily_routine/cli/app.py`

- `run` コマンド: `global_config.api_keys.model_dump()` を `run_pipeline` に渡す
- `resume` / `retry` コマンド: 同様に `api_keys` を渡す

### Step 5: `docs/procedures/api_key_setup.md` に YouTube Data API の手順を追記

**ファイル**: `docs/procedures/api_key_setup.md`

- 概要テーブルに `DAILY_ROUTINE_API_KEY_YOUTUBE_DATA_API` の行を追加（用途: Intelligence Engine — YouTube 検索・メタデータ取得）
- セクション 2 に「2.7 YouTube Data API」を追加（Google Cloud Console での API 有効化 → API キー作成の手順）
- セクション 3 の `.env` サンプルに `DAILY_ROUTINE_API_KEY_YOUTUBE_DATA_API=your-youtube-data-api-key` を追加
- 既存の `GOOGLE_AI` / `OPENAI` の用途説明に Intelligence Engine での使用を追記

> ユーザーは手順書に従って `.env` に API キーを設定する

### Step 6: 既存テストの修正

- `tests/test_pipeline/test_runner.py` — `create_engine` 呼び出しが `**kwargs` を受け取るように mock を調整
- `tests/test_pipeline/test_registry.py` — `create_engine` に `**kwargs` を渡すテストケース追加

### Step 7: エンドツーエンド動作確認

```bash
# 1. lint & test
uv run ruff check . && uv run pytest

# 2. CLI実行（seed_videos なし、拡張検索のみ）
uv run daily-routine run "OLの一日"

# 3. 期待動作:
#    - INTELLIGENCE ステップが RUNNING → AWAITING_REVIEW に遷移
#    - outputs/projects/{project_id}/intelligence/report.json が生成される
#    - report.json が TrendReport スキーマに準拠している

# 4. 状態確認
uv run daily-routine status "{project_id}"
```

## 対象外

- seed_videos を CLI から渡す機能（将来の CLIコマンド拡張で対応）
- SCENARIO 以降のステップの実装・登録
