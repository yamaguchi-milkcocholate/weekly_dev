# キーフレーム画像生成 PoC: キャラクター分裂問題の検証

## Context

パイプライン動作確認中、Keyframe ステップで生成された画像でキャラクターが2人に分裂する問題が発生。
Runway Gen-4 Image の reference image 機能の使い方（プロンプト構造・参照画像選択）を検証するPoCを作成する。

**根本原因の仮説:**
- `@char` タグで参照画像を渡しつつ、プロンプト内でもキャラクターの状態を記述 → モデルが2人として解釈
- 全身スーツ姿の参照画像が「ベッドで寝ている」シーンと大きく乖離

**公式ベストプラクティス（調査結果）:**
- 参照画像に含まれる要素を過度に記述しない
- `@tag [アクション] in [環境]. [照明]. [構図].` のシンプル構造が推奨
- 代名詞 (`She`) + 参照画像も有効
- 「single person only」等の明示的制約も有効

## ファイル構成

```
poc/keyframe_gen/
├── config.py              # 実験パラメータ（プロンプトパターン、シーン、戦略）
├── run_experiment.py      # メイン実行（API呼び出し + 結果保存）
└── build_report.py        # HTMLレポート生成（目視比較用）
```

生成物（git管理外）:
- `poc/keyframe_gen/generated/` — 生成画像 + experiment_log.json
- `poc/keyframe_gen/reports/` — HTMLレポート

## 実験設計

### プロンプトパターン（4種）

| ID | 名前 | テンプレート |
|----|------|-------------|
| A | 現状再現 | `@char [外見描写] [アクション] in [環境]. [照明]. [構図].` |
| B | シンプル @char | `@char [アクション]. [照明], [環境]. [構図].` |
| C | 代名詞方式 | `She [アクション]. [照明], [環境]. [構図].` (参照画像は送信) |
| D | 制約付き | `@char [アクション]. Single person only. [照明], [環境]. [構図].` |

### テストシーン（4種）

| ID | シーン | 分裂リスク | 理由 |
|----|--------|-----------|------|
| bed | ベッドで起床 | 高 | 参照画像（スーツ立ち）との乖離大 |
| cafe | カフェでコーヒー | 中 | 座りポーズ、服装は異なる |
| desk | オフィスデスク | 低 | スーツ姿・座りで参照と近い |
| walk | 街を歩く | 中 | 全身だがポーズ異なる |

### リファレンス画像

全シーンで `front.png`（正面全身画像）のみ使用。現行方式と同じ。

### 組み合わせ数

4パターン × 4シーン = **16画像** ≈ **$0.32**

## 実装ステップ

### Step 1: config.py

実験パラメータを dataclass で定義。`build_prompt()` ヘルパーを含む。

- 既存パターン参考: `poc/image_gen/config.py`

### Step 2: run_experiment.py

**再利用するコード:**
- `src/daily_routine/visual/clients/gen4_image.py` → `RunwayImageClient`, `ImageGenerationRequest`
- `src/daily_routine/utils/uploader.py` → `GcsUploader`
- `src/daily_routine/config/manager.py` → `load_global_config`

**処理フロー:**
1. 設定読み込み（global.yaml から API キー・GCS バケット取得）
2. `RunwayImageClient` インスタンス化
3. 全組み合わせを逐次実行（レート制限回避）
4. 結果画像を `generated/{pattern_id}/{scene_id}.png` に保存
5. `generated/experiment_log.json` にメタデータ保存

**CLI引数:**
```
uv run python poc/keyframe_gen/run_experiment.py [オプション]
  --patterns A,B,C,D    実行パターン指定
  --scenes bed,cafe     実行シーン指定
  --reference-dir PATH  参照画像ディレクトリ（デフォルト: test-verify プロジェクトの彩香）
  --dry-run             プロンプト生成のみ、API呼び出しなし
```

**パターンCの注意点:**
- `@char` タグを使わないが `referenceImages` は送信する
- `ImageGenerationRequest.reference_images` に `{"subject": ref_path}` で送信し、プロンプトは `She ...` とする
- Runway API が `referenceImages` の tag と `@tag` が対応しない場合の挙動を検証する目的もある

### Step 3: build_report.py

- `experiment_log.json` を読み込み
- 比較テーブル（縦軸: シーン、横軸: パターンA〜D）のHTMLを生成
- 各セル: 生成画像サムネイル + 使用プロンプト + リファレンス画像
- `reports/experiment_report.html` に出力

## 検証方法

```bash
# 1. ドライラン（プロンプト確認）
uv run python poc/keyframe_gen/run_experiment.py --dry-run

# 2. 全パターン実行
uv run python poc/keyframe_gen/run_experiment.py \
    --reference-dir outputs/projects/test-verify/assets/character/彩香

# 3. HTMLレポート生成
uv run python poc/keyframe_gen/build_report.py

# 4. ブラウザで確認
open poc/keyframe_gen/reports/experiment_report.html
```

## 期待される成果

- どのプロンプトパターンが分裂を防ぐか判明
- 結果を踏まえて `storyboard/prompt.py` の keyframe_prompt 生成ルールを改善
