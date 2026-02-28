# Seamless Keyframe PoC 実装計画

## Context

現在のキーフレーム生成は各カットを独立して生成しており、キャラクター不一致・シーン間の断絶・Seeds との乖離が発生している。`poc/seamless/plan.md` に定義された 3 つの実験を FLUX Kontext（fal.ai 経由）で実行するため、`config.py` と `run_experiment.py` を実装する。

## 作成ファイル

### 1. `poc/seamless/config.py` — 実験パラメータ定義

**データモデル:**

```python
class Endpoint(str, Enum):
    PRO = "fal-ai/flux-pro/kontext"           # $0.04/画像
    MAX_MULTI = "fal-ai/flux-pro/kontext/max/multi"  # $0.08/画像

@dataclass
class GenerationStep:
    step_id: str              # "scene_6", "pass_1", "step_1" etc.
    endpoint: Endpoint
    prompt: str
    guidance_scale: float = 3.5
    seed: int | None = 42
    num_images: int = 1
    use_seed_capture: bool = True
    use_character_ref: bool = False     # Max Multi 用
    use_previous_output: bool = False   # 連鎖用
    output_filename: str = ""

@dataclass
class ExperimentPattern:
    id: str                    # "D-A", "I-B", "anchor" etc.
    name: str
    experiment_group: str      # "exp1_max_multi", "exp2_iterative", "exp3_anchor_chain"
    steps: list[GenerationStep]
    description: str = ""
```

**定数:**
- `CHARACTER_DNA`: キャラクター仕様（美咲）を全プロンプト共通で使用
- `IDENTITY_LOCK`: "Maintain exact character identity..." + "Single person only, solo"
- `SEED_CAPTURE_DIR`: `seeds/captures/tamachan_life_/`
- `CHARACTER_REF`: `poc/video_ai/reference/front.png`
- `DEFAULT_SCENE_IMAGE`: `6.png`（代表シーン）

**実験定義（5 パターン、計 8 画像）:**

| パターン | 実験 | ステップ数 | Endpoint | コスト |
|----------|------|-----------|----------|--------|
| D-A | exp1 | 1 | MAX_MULTI | $0.08 |
| D-B | exp1 | 1 | PRO | $0.04 |
| I-A | exp2 | 1 | PRO | $0.04 |
| I-B | exp2 | 3（連鎖） | PRO | $0.12 |
| anchor | exp3 | 2（連鎖） | PRO | $0.08 |
| **合計** | | **8** | | **$0.36** |

**プロンプト設計方針:**
- Kontext は in-context editor → "Replace the person in this image" 形式で指示
- 全プロンプトに `IDENTITY_LOCK` を付与
- I-B の 3 パス: Pass1=人物差し替え → Pass2=照明調整 → Pass3=顔ディテール
- Exp3 Step2: "Same woman, adjust pose..." で前出力を参照

**ヘルパー関数:**
- `get_patterns_by_experiment(experiment_id)` — exp1/exp2/exp3 でフィルタ
- `get_patterns_by_ids(ids)` — パターン ID でフィルタ
- `estimate_cost(patterns)` / `count_images(patterns)`

### 2. `poc/seamless/run_experiment.py` — 実験実行スクリプト

**argparse:**
- `--experiment`: exp1 / exp2 / exp3（指定なしで全実験）
- `--patterns`: カンマ区切りパターン ID（例: D-A,I-B）
- `--dry-run`: プロンプト確認・コスト見積もりのみ
- `--seed-image`: Seed キャプチャのパス指定
- `--character-ref`: キャラクター参照画像のパス指定

**コア処理フロー:**

```
1. 参照画像を fal CDN にアップロード（fal_client.upload_file）
2. パターンごとにループ:
   a. ステップごとに順次実行:
      - 入力画像 URL を決定（seed / 前ステップ出力）
      - fal_client.subscribe() で API 呼び出し
      - 出力画像をダウンロード保存
      - 出力 URL を次ステップに渡す（連鎖）
   b. ステップ失敗時は後続の連鎖ステップをスキップ
3. experiment_log.json に全結果を保存
4. サマリ表示（成功/失敗/コスト）
```

**重要な設計判断:**
- `fal_client.subscribe()` は同期（ポーリング内蔵）→ 連鎖ステップは必然的に逐次実行
- 中間出力の URL は fal CDN 上にあるため再アップロード不要
- ローカル保存は記録用のみ

### 3. `pyproject.toml` — 依存追加

```toml
[project.optional-dependencies]
poc-seamless = ["fal-client>=0.5"]
```

## 出力ディレクトリ構成

```
poc/seamless/generated/
├── exp1_max_multi/
│   ├── D-A/scene_6.png
│   └── D-B/scene_6.png
├── exp2_iterative/
│   ├── I-A/scene_6.png
│   └── I-B/
│       ├── pass_1.png
│       ├── pass_2.png
│       └── pass_3.png
├── exp3_anchor_chain/
│   └── anchor/
│       ├── step_1.png
│       └── step_2.png
└── experiment_log.json
```

## 参照する既存ファイル

- `poc/keyframe_gen/config.py` — dataclass 構造、ヘルパー関数パターン
- `poc/keyframe_gen/run_experiment.py` — argparse、ログ、JSON 出力パターン
- `poc/seamless/plan.md` — 実験設計・プロンプト方針・評価基準
- `seeds/captures/tamachan_life_/6.png` — 代表 Seed キャプチャ
- `poc/video_ai/reference/front.png` — キャラクター参照画像

## 実装順序

1. `pyproject.toml` に `poc-seamless` 依存追加 → `uv sync --extra poc-seamless`
2. `poc/seamless/config.py` 作成
3. `poc/seamless/run_experiment.py` 作成
4. `--dry-run` で各実験のプロンプト・コスト確認
5. 実験実行: exp1 → exp2 → exp3

## 検証方法

```bash
# ドライラン（全実験）
uv run python poc/seamless/run_experiment.py --dry-run

# 実験ごとのドライラン
uv run python poc/seamless/run_experiment.py --experiment exp1 --dry-run

# 特定パターンのみ実行
uv run python poc/seamless/run_experiment.py --patterns D-A

# 全実験実行
uv run python poc/seamless/run_experiment.py
```

ドライランで以下を確認:
- 全 5 パターン・8 画像分のプロンプトが正しく出力される
- 推定コストが $0.36 と表示される
- 参照画像パスが正しく解決される
