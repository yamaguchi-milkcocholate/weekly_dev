# PoC 8: Geminiマルチアングル一貫性の改善

作成日: 2026-04-01

## 目的

Geminiで複数アングルの画像を生成する際、AIが追加する小物・装飾の位置をアングル間で一貫させる手法を検証する。

## 背景

- PoC 6でGeminiのスタイル転写は高品質と確認済み（構造維持97.8、スタイル反映95.8）
- ただしPoC 6では「AIに追加させない（re-skinningのみ）」方針で一貫性を確保していた
- SNSレベルの動画には生活感（小物・装飾・植物等）が必要
- Blenderでの小物3D配置は高コストで非現実的
- → **Geminiに小物を追加させつつ、アングル間で一貫させたい**

### PoC 6で判明している制約

- 各画像は独立に生成されるため、AIが追加する要素がアングルごとに異なる
- スタイルテキストにオブジェクト名（"plant", "rug"等）を書くと追加されるが、位置は毎回ランダム
- 2画像入力はスタイル画像の空間的性質を取り込んでしまい構造が崩壊する（PoC 6で確認済み）

## 検証アイデア

### 方法1: 俯瞰reference方式

```
Step 1: 俯瞰（カメラ6）+ スタイルテキスト + 小物追加指示
        → Geminiでリッチなレイアウトの俯瞰画像を生成
Step 2: 各アングル生成時に、Step 1の俯瞰画像をreferenceとして渡す
        → 「この俯瞰に見えるオブジェクト配置を守って、このアングルから描け」
```

- **入力**: レンダリング画像（構造）+ 俯瞰reference画像（小物配置の正解）+ テキストプロンプト
- **期待**: 俯瞰で見える小物の位置・種類を各アングルでも維持
- **リスク**: PoC 6で「2画像入力は構造を崩す」と確認済み。ただし今回は同一空間の俯瞰なので、スタイル画像とは性質が異なる

### 方法2: テキスト配置指示方式

```
Step 1: 俯瞰画像を生成（方法1と同じ）
Step 2: 俯瞰画像の小物配置をテキストで記述（座標・位置関係）
Step 3: 各アングル生成時に、テキスト配置指示のみで生成（2画像入力を回避）
```

- **入力**: レンダリング画像（1枚のみ）+ スタイルテキスト + 配置テキスト
- **期待**: 2画像入力の構造崩壊リスクを回避しつつ、テキストで配置を拘束
- **リスク**: テキストの空間記述でGeminiが正確に配置できるかは不明

### 方法3: 段階的生成方式

```
Step 1: 全カメラでre-skinningのみ実行（PoC 6と同じ、小物追加なし）
Step 2: re-skinning済み画像に対して、小物を追加する指示を出す
        → 俯瞰で追加した小物リストを各アングルにも適用
```

- **入力**: re-skinning済み画像 + 小物追加指示テキスト
- **期待**: 構造維持はre-skinningで確保済み、小物追加のみに集中
- **リスク**: 2段階の画像変換で品質が劣化する可能性

## 検証計画

### Phase 1: 俯瞰reference方式の検証（方法1）

最もシンプルで効果が高い可能性がある方法1から検証する。

#### 1-1: 俯瞰画像の生成

- **入力**: `poc/3dcg_poc7/input/カメラ6.png`（高解像度素レンダリング俯瞰）
- **プロンプト**: PoC 6のre-skinningプロンプト + 小物追加許可の指示
  - 小物リスト例: 観葉植物、クッション、本・雑誌、ラグ、テーブル上の小物
  - スタイル: 北欧ナチュラル（PoC 6で検証済み）
- **出力**: リッチなレイアウトの俯瞰画像

#### 1-2: 各アングル画像の生成（俯瞰reference付き）

- **入力**:
  - Image 1: `poc/3dcg_poc7/input/カメラN.png`（各アングルの素レンダリング）
  - Image 2: Step 1-1で生成した俯瞰画像（reference）
- **プロンプト**:
  - Image 1の構造を維持（SPATIAL LOCK）
  - Image 2に見える小物の配置を参照（位置・種類を一致させる）
  - Image 2のスタイル・テクスチャも維持
- **対象カメラ**: カメラ1, 2, 3, 4（4アングル、俯瞰から見える範囲）
- **コスト**: $0.134 × 5枚 = $0.67

#### 1-3: 一貫性評価

- 俯瞰画像と各アングル画像を比較
- 評価基準:
  - **小物位置の一貫性**: 俯瞰で見える位置に小物があるか
  - **小物種類の一貫性**: 同じ小物が同じ見た目か
  - **構造維持**: 壁・家具配置が崩れていないか（PoC 6基準: 97.8以上が目標）
  - **スタイル一貫性**: 全アングルで同じ雰囲気か

### Phase 2: 方法1が不十分な場合の代替検証

方法1で構造崩壊が発生した場合:
- **方法2（テキスト配置指示）** を検証
- **方法3（段階的生成）** を検証

## 成功基準

- 3アングル以上で小物の位置・種類が概ね一致していること
- 構造維持スコアが95以上（PoC 6のre-skinning基準に近い水準）
- Blenderでの手動配置なしで生活感のあるレイアウトが実現できること

## 技術スタック

- **モデル**: Gemini 3.0 Pro Image（`gemini-3-pro-image-preview`）
- **API**: PoC 6の `clients/gemini.py` を流用（2画像入力に拡張）
- **評価**: PoC 6の `evaluate.py` を参考に一貫性評価を追加
- **環境変数**: `DAILY_ROUTINE_API_KEY_GOOGLE_AI`
- **実行**: `uv run python poc/3dcg_poc8/run_experiment.py`

## 実装方針

PoC 6のコードを参考に、以下を新規作成:
- `poc/3dcg_poc8/config.py` — カメラ定義・プロンプトテンプレート
- `poc/3dcg_poc8/run_experiment.py` — 実験実行スクリプト
- PoC 6の `clients/` を再利用（シンボリックリンクまたはコピー）

## 検証ログ

### 実験1: 俯瞰画像の生成方式検証（2026-04-01）

1段階（スタイル+小物同時）と2段階（re-skinning→小物追加）を比較し、2段階方式を採用。

- **入力**: `poc/3dcg_poc8/input/カメラ6.png`（Blender素レンダリング俯瞰）
- **スタイル参照**: `poc/3dcg_poc8/input/style_ref.png`（ヴィンテージカフェ風）
- **モデル**: Gemini 3.0 Pro Image
- **実行スクリプト**: `poc/3dcg_poc8/run_overhead.py`

#### 採用方式: 2段階（re-skinning → 小物自由追加）

**Pass 1 — re-skinning**: PoC 6と同じ方式。構造を確定させる。

**Pass 2 — 小物追加**: 構造を維持したまま、小物を自由に追加させる。

#### 確定プロンプト設計原則

1. **スタイルテキストはstyle_ref画像の明るさ・トーンを正確に記述する** — 暗い表現（"dark wood tones"等）は結果を大きく暗くする
2. **小物は自由配置にする** — 配置先を細かく指定すると家具自体が変形する
3. **小物のサイズをALLOWED/NOT ALLOWEDで制限する** — 自由すぎるとキッチン等の大型家具が追加される
4. **壁保護ルールを明示する** — 「WALLS ARE SACRED」
5. **構造維持は「PIXEL-LEVEL POSITION LOCK」で強調する**

#### 確定プロンプト（Pass 2: 小物追加）

```text
This is a photorealistic interior photograph. Add small lifestyle items to make it feel lived-in and cozy.

STRICT RULES:
1. WALLS ARE SACRED: All walls, partitions, and room boundaries must remain exactly as they are.
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

#### 実行フロー: インタラクティブ・イテレーション

各Passの生成は自動一括ではなく、Claude Codeとユーザーが対話しながら反復的に実行する。

```text
Pass 1（re-skinning）:
  生成 → Claudeが構造維持・スタイル類似性を評価 → ユーザー確認
  → NGなら原因を特定しプロンプト修正 → 再生成
  → OKなら Pass 2 へ

Pass 2（小物追加）:
  生成 → Claudeが構造維持・小物の適切さを評価 → ユーザー確認
  → NGなら原因を特定しプロンプト修正 → 再生成
  → OKなら確定
```

Claudeの評価観点:

- **style_refとの類似性**: 明るさ・色調・素材感がstyle_ref画像と合っているか
- **構造維持**: 壁・家具の位置が元のレンダリングから変わっていないか
- **小物の適切さ**（Pass 2）: 大型家具の追加がないか、通路を塞いでいないか

#### 出力ファイル

- `output/2pass_step1_カメラ6.png` — re-skinningのみ（構造確定）
- `output/2pass_step2_カメラ6.png` — 小物追加済み（俯瞰reference用）

### 実験2: スキル化＋新入力での検証（2026-04-01）

実験1の知見をスキル `3dcg-style-apply-living` に反映し、新しい入力画像で検証した。

- **入力**: `poc/3dcg_poc8/input/overhead.png`（新しい俯瞰レンダリング）
- **スタイル参照**: `poc/3dcg_poc8/input/style_ref.png`（インダストリアル×ヴィンテージ）
- **実行スクリプト**: `.claude/skills/3dcg-style-apply-living/scripts/run_generate.py`

#### スタイルテキスト

```text
Warm industrial-vintage aesthetic. Rich herringbone hardwood flooring in warm medium-brown oak tones. Walls are bright white plaster, smooth and clean finish throughout. Furniture surfaces use a mix of natural light oak wood and matte black metal frames. Soft warm lighting with color temperature around 3000K, creating a cozy golden ambient glow. Fabric textures are natural linen and cotton in muted earth tones — beige, cream, and soft brown. Ceiling is white with exposed dark metal conduit details. Overall bright and airy atmosphere with warm undertones, not dark or moody.
```

#### イテレーション履歴

| # | Pass | 結果 | 修正内容 |
|---|------|------|----------|
| 1 | Pass 1 | NG | レンガアクセント壁が生成された → スタイルテキストからレンガ要素を完全除去 |
| 2 | Pass 1 | OK | 壁は白プラスター、ヘリンボーンフローリング、構造維持良好 |
| 3 | Pass 2 | NG | 左下通路が小物で塞がれた → `--extra-instructions` で通路確保を明示 |
| 4 | Pass 2 | OK | 通路確保、小物は自然な配置 |

#### 出力ファイル

- `output/step1_overhead.png` — re-skinning済み（Pass 1確定）
- `output/step2_overhead.png` — 小物追加済み（Pass 2確定）

#### コスト

- 生成4回 × $0.134 = **$0.536**

#### 知見

1. **スタイルテキストに含まれる素材名はそのまま適用される** — style_refにレンガがあっても、テキストで「white plaster」と書けばレンガは出ない。テキスト化の段階でフィルタリングできる
2. **`--extra-instructions` 引数の追加** — プロンプト修正時にコードを書き換える手間を解消。任意の追加指示をコマンドライン引数で渡せるようにした
3. **通路塞ぎはPass 2の頻出問題** — 小物追加時に通路を塞ぐ傾向がある。`--extra-instructions` での明示的な回避指示が有効

## 次のアクション

1. Phase 1-2: 確定した俯瞰画像を俯瞰referenceとして各アングル（カメラ1〜5）を生成
2. Phase 1-3: アングル間の一貫性評価
