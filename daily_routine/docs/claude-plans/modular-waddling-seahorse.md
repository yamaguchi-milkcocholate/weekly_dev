# T1-1 計画: CLI基盤・パイプラインオーケストレーション設計書の作成

## Context

仕様書（`/docs/specs/initial.md`）の3.1章・5.1章に基づき、T1-1「CLI基盤・パイプラインオーケストレーション」の設計書を `docs/designs/cli_pipeline_design.md` に作成する。実装は行わず、設計書の作成のみ。

## 作成する設計書の構成

`docs/designs/cli_pipeline_design.md` を新規作成する。内容は以下の通り:

### 1. 概要
- 対応する仕様書セクション: 3.1章, 5.1章
- スコープ: パイプライン順次実行、チェックポイント停止、resume/retry制御、ABC基底クラス、状態永続化
- 対象外: 各レイヤーのビジネスロジック(T1-2~T1-6)、Web UI(T4-2)、自動品質チェック(T4-1)

### 2. ユーザー操作フロー
```
run → チェックポイント停止 → 目視確認 → resume or retry → ...繰り返し → 完了
```

### 3. 状態遷移
- ステップ単位: PENDING → RUNNING → AWAITING_REVIEW → APPROVED (or ERROR → retry → RUNNING)
- パイプライン全体: 最終ステップAPPROVED時に `completed=True`

### 4. 技術設計
- **スキーマ変更** (`schemas/project.py`): ERROR追加、retry_count追加、completed追加
- **ABC基底クラス** (`pipeline/base.py`): `StepEngine(ABC, Generic[InputT, OutputT])` — execute, load_output, save_output
- **例外定義** (`pipeline/exceptions.py`): PipelineError, StepExecutionError, InvalidStateError
- **状態永続化** (`pipeline/state.py`): load_state, save_state, initialize_state
- **エンジンレジストリ** (`pipeline/registry.py`): register_engine, create_engine
- **ランナー** (`pipeline/runner.py` 書換): run_pipeline, resume_pipeline, retry_pipeline
- **CLI** (`cli/app.py` 書換): run, resume, retry, status, init

### 5. 変更対象ファイル一覧
13ファイル（修正3、新規6、テスト新規4）

### 6. 実装順序
スキーマ → 例外 → ABC → 状態管理 → レジストリ → ランナー → CLI

### 7. テスト方針
モックエンジンを使用し、AI API呼び出しなしで全フロー検証

## 対象ファイル
- 作成: `/docs/designs/cli_pipeline_design.md`

## 検証方法
設計書が以下を満たすことを確認:
- T0-1の設計書(`docs/designs/archives/project_skeleton_design.md`)と同等の粒度
- 仕様書の3.1章・5.1章の要件を網羅
- CLAUDE.mdの設計原則に準拠
