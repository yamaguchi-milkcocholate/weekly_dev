---
name: 3dcg-style-apply
description: 3Dレンダリング画像（テクスチャなし）にスタイル参照画像の雰囲気を適用し、フォトリアリスティックなインテリア画像を生成する。Gemini 3.0 Pro Imageのテキストスタイル方式を使用し、3Dの空間構造（壁・家具配置・カメラアングル）を忠実に維持しながらスタイルを適用する。3Dレンダリングのリアル化、インテリアスタイル適用、テクスチャなしレンダリングの写真化、スタイル参照画像の適用、部屋の雰囲気変更に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <workdir>
---

# 3dcg-style-apply

3Dレンダリング画像にスタイル参照画像の雰囲気を適用してフォトリアリスティックなインテリア画像を生成する。

## 入力

```text
<workdir>/
├── input/
│   ├── カメラ1.png 〜 カメラN.png   # 3Dレンダリング画像（テクスチャなし）
│   └── style_ref.png                # スタイル参照画像
```

## 出力

```text
<workdir>/
└── output/
    ├── カメラ1.png 〜 カメラN.png   # スタイル適用済み画像
    └── evaluation/                   # 評価結果JSON
```

## 前提条件

- 環境変数 `DAILY_ROUTINE_API_KEY_GOOGLE_AI` が設定済み

## 処理フロー

### Phase 1: スタイル参照画像のテキスト化

`<workdir>/input/style_ref.png` を読み取り、以下の観点で英語のテキスト記述を作成する。

**分析観点**: 全体の雰囲気、色調・カラーパレット、壁の素材、床の素材、照明の種類・色温度、家具の素材感、ファブリックの質感、装飾要素（植物・小物）

**禁止**: 空間構造に関する記述（"open floor plan", "large windows", "stairs", "high ceiling" 等）は含めない。含めるとGeminiが構造を変更してしまう。

**記述形式**: 英語、短い文章の連続、具体的な素材名・色名を使う。

例:

```text
Industrial loft aesthetic with exposed concrete walls and ceiling. Raw concrete (grey) texture on walls and ceiling. Cool, muted color palette with grey, dark green, and natural wood accents. Large tropical indoor plants (monstera, palm) as key accents. Warm ambient lighting mixed with cool natural light. Concrete or dark stone flooring. Minimal, functional furniture with metal and wood materials. Slightly moody, atmospheric feel with soft shadows.
```

### Phase 2: 画像生成

```bash
# 全カメラ実行
uv run python <workdir>/run_experiment.py \
    --style-text "<Phase 1で作成したテキスト>"

# 特定カメラのみ
uv run python <workdir>/run_experiment.py \
    --style-text "<テキスト>" \
    --cameras カメラ4

# コスト確認
uv run python <workdir>/run_experiment.py \
    --style-text "<テキスト>" \
    --dry-run
```

コスト: Gemini 3.0 Pro Image $0.134/枚、6カメラで約$0.80。

### Phase 3: 結果確認

`<workdir>/output/` 内の生成画像を読み取り、ユーザーに提示する。

確認ポイント:

1. 壁の位置・家具配置がレンダリング画像と一致しているか
2. スタイルが反映されているか
3. 複数カメラ間でスタイルが統一されているか

問題がある場合はPhase 1のテキスト記述を調整して再実行する。
