# 設計書の実装順序方針

## Context

`docs/designs/` に6つのレイヤー設計書 + 全体フロー設計書がある。これらを実装に着手する順序を、依存関係・実装難易度・既存資産を基に決定する。

## 依存関係図

```
T1-1: CLI基盤 / パイプライン ← 全レイヤーの実行基盤
  │
  ├─ T1-2: Intelligence Engine（トレンド分析）
  │    └─ T1-5: Scenario Engine（シナリオ生成）
  │         ├─ T1-3: Asset Generator（画像生成）
  │         │    └─ T1-4: Visual Core（動画生成）
  │         └─ T1-6: Audio Engine（BGM・SE）
  │
  └─ Post-Production（全レイヤー完了後）
```

## 実装順序

| 順序 | タスクID | 設計書                          | 実装ステップ数 | 外部API                           |
| ---- | -------- | ------------------------------- | -------------- | --------------------------------- |
| 1    | T1-1     | `cli_pipeline_design.md`        | 7              | なし                              |
| 2    | T1-2     | `intelligence_engine_design.md` | 5              | YouTube Data API, Gemini, Whisper |
| 3    | T1-5     | `scenario_engine_design.md`     | 4              | OpenAI GPT-5系                    |
| 4    | T1-3     | `asset_generator_design.md`     | 4              | Gemini (画像生成)                 |
| 5    | T1-4     | `visual_core_design.md`         | 4              | Runway Gen-4 Turbo, GCS           |
| 6    | T1-6     | `audio_engine_design.md`        | 4              | Suno（オプション）, Gemini        |

## 順序の根拠

### 1. T1-1: CLI基盤・パイプライン（最優先）

- **依存される側**: 全レイヤーの `StepEngine` ABC やランナーがここで定義される
- **外部API不要**: ローカルファイルI/Oのみで完結。APIキーやコストなしで開発・テスト可能
- **既存コード活用**: `runner.py` と `cli/app.py` に骨格あり、差分実装で済む
- **実装ステップが明確**: スキーマ変更 → 例外 → ABC → 永続化 → レジストリ → ランナー → CLI

### 2. T1-2: Intelligence Engine

- パイプライン最上流。後続の Scenario / Audio が `TrendReport` を必要とする
- YouTube Data API + Gemini Vision で競合動画を分析

### 3. T1-5: Scenario Engine

- Intelligence の `TrendReport` を受けて `Scenario` を生成
- Asset / Visual / Audio / Post-Production の全てが `Scenario` に依存
- パイプラインの中核ハブ

### 4. T1-3: Asset Generator

- PoC（`poc/image_gen/`）が既にあり本番化しやすい
- Scenario → Asset の流れで自然

### 5. T1-4: Visual Core

- Asset の画像を入力として動画を生成
- PoC（`poc/video_ai/`）あり
- コスト最大（$0.50/クリップ〜）のため後半で実装

### 6. T1-6: Audio Engine

- Visual と並行実装も可能だが、Scenario + TrendReport が必要なので Scenario 以降
- Post-Production 前に完了すればよい
- Suno の商用利用ライセンス等の未決事項あり

## 並行実装の可能性

- T1-3（Asset）と T1-6（Audio）は互いに独立しており、Scenario 完了後に並行実装可能
- T1-4（Visual）は T1-3 に依存するため、T1-3 完了後に着手

## 既存実装状況

- **骨格あり**: `cli/app.py`, `pipeline/runner.py`, `config/manager.py`
- **スキーマ定義済み**: `schemas/` 配下に全レイヤーのスキーマが存在
- **テスト存在**: `tests/test_cli.py`, `tests/test_config.py`, `tests/test_schemas/`
- **PoC 存在**: `poc/image_gen/`（Asset）, `poc/video_ai/`（Visual）
- **各レイヤー**: `__init__.py` のみのスケルトン状態
