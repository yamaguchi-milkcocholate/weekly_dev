---
name: 3dcg-style-apply-living
description: 3dcg-style-applyの出力（re-skinning済み画像）に生活感のある小物を追加し、フォトリアリスティックなインテリア画像を生成する。俯瞰画像をreferenceとして各カメラアングルでも小物配置の一貫性を担保する。Gemini 3.0 Pro Imageを使用し、インタラクティブにClaudeが評価しユーザーが確認しながら反復的に品質を高める。インテリア画像に生活感を追加したい、小物・装飾を追加したい、俯瞰referenceでマルチアングルの小物一貫性を担保したいタスクで必ずこのスキルを参照すること。
argument-hint: <workdir>
---

# 3dcg-style-apply-living

`3dcg-style-apply` の出力（re-skinning済み画像）を入力とし、生活感のある小物を追加してフォトリアリスティックなインテリア画像を生成する。

俯瞰画像への小物追加を先に行い、その結果をreferenceとして各カメラアングルでも小物配置を一貫させる。

## 入力

```text
<workdir>/
├── input/
│   ├── overhead.png              # 俯瞰画像（3dcg-style-apply出力）
│   └── camera/
│       ├── カメラ1.png           # 各カメラ画像（3dcg-style-apply出力）
│       └── ...カメラN.png
```

## 出力

```text
<workdir>/
└── output/
    ├── step2_overhead.png        # 俯瞰: 小物追加済み（最終出力）
    ├── カメラ1.png               # 各カメラ: 小物追加済み（最終出力）
    └── ...カメラN.png
```

## 前提条件

- `3dcg-style-apply` スキルを先に実行済みであること。入力画像はすべてそのスキルの出力（re-skinning済み・フォトリアリスティック・テクスチャあり）
- 環境変数 `DAILY_ROUTINE_API_KEY_GOOGLE_AI` が設定済み

## 処理フロー

### Phase 1: 俯瞰画像への小物追加（インタラクティブ・イテレーション）

`<workdir>/input/overhead.png`（re-skinning済み）に対して小物を追加する。

**実行コマンド**:

```bash
uv run python .claude/skills/3dcg-style-apply-living/scripts/run_generate.py \
    --input <workdir>/input/overhead.png \
    --prompt-type add-items \
    --output <workdir>/output/step2_overhead.png
```

**プロンプト**:

```text
This is a photorealistic interior photograph. Add small lifestyle items to make it feel lived-in and cozy.

STRICT RULES:
1. WALLS ARE SACRED: All walls, partitions, and room boundaries must remain exactly as they are. Do NOT remove, merge, open up, or alter any wall. The room shape and all wall positions must be pixel-identical to the input.
2. DO NOT change, move, resize, or reshape any existing furniture. Every existing object must remain pixel-identical.
3. DO NOT change the camera angle, lighting style, or color grading.
4. DO NOT place items in walkways or open floor passages between furniture.
5. Keep the same photorealistic quality and style as the input image.

Freely add small decorative and lifestyle items wherever they look natural and realistic.

ALLOWED (small, hand-held or tabletop size only):
- Potted plants (small), books, magazines, coffee cups, dishes, cushions, throw blankets, candles, photo frames, pen holders, small clocks

NOT ALLOWED (do NOT add these):
- Kitchen appliances, sinks, stoves, refrigerators, shelving units, cabinets, large furniture, lamps, rugs, curtains, or any item larger than a shoebox
```

**Claudeの評価観点**:

- 構造維持: 壁・家具の位置が変わっていないか。壁が消えていないか
- 小物の適切さ: 大型家具が追加されていないか。通路を塞いでいないか
- 家具の変形: 既存家具が別のものに変わっていないか

生成結果をユーザーに提示し確認を得る。NGなら原因を特定しプロンプトを修正して再生成（`--extra-instructions` で追加指示可能）。OKならPhase 2へ。

### Phase 2: 各カメラへの小物追加（インタラクティブ・イテレーション）

各カメラ画像（re-skinning済み）に対して、Phase 1の俯瞰出力をreferenceとして小物を追加する。カメラごとに順次実行し、各結果をユーザーに確認してもらう。

**実行コマンド**（カメラごとに実行）:

```bash
uv run python .claude/skills/3dcg-style-apply-living/scripts/run_generate.py \
    --input <workdir>/input/camera/カメラN.png \
    --reference <workdir>/output/step2_overhead.png \
    --prompt-type add-items-ref \
    --output <workdir>/output/カメラN.png
```

**プロンプト**:

```text
Image 1 is a photorealistic interior photograph from a specific camera angle. Image 2 is a photorealistic overhead view of the SAME room, showing small lifestyle items that have been added.

Your task: Add small lifestyle items to Image 1 so that it is CONSISTENT with Image 2.

STRICT RULES — violations will ruin the result:
1. PIXEL-LEVEL STRUCTURE LOCK: All walls, partitions, room boundaries, furniture, camera angle, lighting, and color grading in Image 1 must remain pixel-identical. Do NOT change ANYTHING about the existing scene.
2. ITEM CONSISTENCY: Look at Image 2 (overhead) to see what small items exist and where they are placed. Add the same types of items in the corresponding positions as seen from this camera angle.
3. ONLY ADD small items that are visible in Image 2. Do NOT invent new items.
4. DO NOT place items in walkways or open floor passages.
5. Keep the same photorealistic quality and style as Image 1.

ALLOWED items (only if visible in Image 2):
- Potted plants (small), books, magazines, coffee cups, dishes, cushions, throw blankets, candles, photo frames, pen holders, small clocks

NOT ALLOWED (do NOT add these even if they seem to appear in Image 2):
- Kitchen appliances, sinks, stoves, refrigerators, shelving units, cabinets, large furniture, lamps, rugs, curtains, or any item larger than a shoebox
```

**Claudeの評価観点**:

- 構造維持: 壁・家具の位置が変わっていないか
- 俯瞰との一貫性: 俯瞰画像に写っている小物が、カメラアングルから見た正しい位置に配置されているか
- 小物の適切さ: 俯瞰にない小物が追加されていないか。大型家具が追加されていないか
- カメラアングル維持: 視点・パースが元画像と変わっていないか

生成結果をユーザーに提示し確認を得る。NGなら原因を特定しプロンプトを修正して再生成（`--extra-instructions` で追加指示可能）。OKなら次のカメラへ。

### Phase 3: 結果確認

全出力画像（俯瞰 + 全カメラ）をユーザーに提示する。カメラ間の小物一貫性を最終確認。

## コスト

- Gemini 3.0 Pro Image: $0.134/枚
- 俯瞰1回 + カメラN回 = $0.134 × (1 + N)（再生成が発生すると増加）

## スクリプト

`.claude/skills/3dcg-style-apply-living/scripts/run_generate.py` を使用する。
