# Seamless Keyframe PoC 計画

## 1. 背景・課題

### 現状の問題

現在のキーフレーム生成（`keyframe/engine.py`）は、各カットを**独立して**生成している。

```
cut_1 → Runway API → keyframe_1.png
cut_2 → Runway API → keyframe_2.png  ← cut_1 とは無関係に生成
cut_3 → Runway API → keyframe_3.png  ← cut_1, cut_2 とは無関係に生成
```

結果として以下の問題が発生:

1. **キャラクターの不一致**: 同一キャラクターでも顔・体型・服装がカットごとに異なる
2. **シーン間の乖離**: シーン間で色味・空間の連続性がない
3. **Seeds との乖離**: 参照動画のキャプチャ画像（seeds）の雰囲気がほとんど反映されない

### 根本原因

- `@char` 参照のみでは、AI生成キャラクター画像（白背景スタジオ写真）から「同一人物」を再現する精度に限界がある
- `@location` 参照は「雰囲気のヒント」に留まり、seeds キャプチャの構図・空間を活かしきれない
- カット間の参照関係がないため、前後のシーンが視覚的に無関係になる

## 2. 提案するアプローチ

### コンセプト: Progressive Transformation（段階的変換）

Seeds のキャプチャ画像を**出発点**として、少しずつ変換を重ねることで、元の雰囲気を保ちながら AI キャラクターの世界に変換する。

```
[Seed キャプチャ] → Step 1: 人物差し替え → Step 2: 環境調整 → [最終キーフレーム]
```

### コンセプト: Sequential Referencing（逐次参照）

シーン N+1 を生成する際に、シーン N の出力を参照画像として渡すことで、視覚的連続性を確保する。

```
scene_1 → Runway API → output_1
scene_2 → Runway API (参照: output_1) → output_2
scene_3 → Runway API (参照: output_2) → output_3
```

## 3. 技術的制約

### Runway Gen-4 Image API

- **エンドポイント**: `POST /v1/text_to_image` のみ（image_to_image は未提供）
- **参照画像**: `referenceImages` で最大複数枚指定可能
  - `@char` タグ: キャラクター同一性を保つ（プロンプトに @char 記述必須）
  - `@location` タグ: 環境・空間の雰囲気をヒントとして使う
  - タグなし（`subject` 等）: 汎用参照
- **コスト**: $0.02 / 画像
- **制約**: 参照画像は URL 経由（GCS アップロード必須）

### 制約から導かれる方式

image_to_image API がないため、「元画像を直接編集する」ことはできない。代わりに:

- **参照画像の組み合わせ**で「元画像に近い出力」を誘導する
- Seeds キャプチャを `@location` として渡し、**環境の色味・構図・雰囲気**を継承
- AI キャラクターを `@char` として渡し、**人物の差し替え**を実現
- プロンプトで**構図・アクション・カメラワーク**を明示的に指定

## 4. 実験設計

すべての実験で FLUX Kontext（fal.ai 経由）を使用する。代表シーンは **scene 6**（6.png — 人物大きめ・動きあり、差し替え難易度が最も高い）に統一。

### 実験 1: Max Multi-Image による人物直接差し替え

Kontext Max の multi-image エンドポイント（`fal-ai/flux-pro/kontext/max/multi`）を使い、seed キャプチャとキャラクター参照画像の 2 枚を入力して、構図を保ったまま人物を差し替える。

Runway の `@char` + `@location` による間接的な誘導ではなく、**「この構図でこの人物に差し替えて」と明示的に指示**できる点が本質的な違い。

| パターン | 方式 | 入力 | 検証ポイント |
|----------|------|------|-------------|
| D-A | Max Multi（2枚入力） | image_1: seed キャプチャ, image_2: front.png | 構図保持度 + キャラクター反映度 |
| D-B | Pro I2I（1枚入力） | image: seed キャプチャ + プロンプトで人物記述 | Multi なしとの比較 |

**生成数**: 2 パターン × 1 シーン = 2 画像

**コスト**: D-A: $0.08 / D-B: $0.04 → 合計 $0.12

### 実験 2: Iterative In-Context Editing vs 1パス

1回のプロンプトで全変更を指示する場合 vs 段階的にプロンプト編集を重ねる場合の品質差を検証。

| パターン | パス数 | 各パスの内容 | 検証ポイント |
|----------|--------|-------------|-------------|
| I-A | 1パス | 人物差し替え＋環境調整＋照明を1プロンプトで同時指示 | ベースライン |
| I-B | 3パス | Pass1: 人物差し替え → Pass2: 照明を warm golden hour に → Pass3: 顔ディテール精緻化 | 段階的編集の品質向上度 |

**生成数**: I-A: 1画像 / I-B: 1シーン × 3パス = 3画像 → 合計 4 画像（最終出力は I-A: 1, I-B: 1 の比較）

**コスト**: I-A: $0.04 / I-B: $0.04 × 3 = $0.12 → 合計 $0.16

### 実験 3: Character Anchor Chain（キャラクター固定連鎖生成）

前シーンの出力を次シーンの入力として連鎖生成し、シーン間のキャラクター一貫性と視覚的連続性を検証する。

Kontext では前シーン出力を**直接入力画像**として「この人物をそのまま次のシーンに」と指示できる。

**連鎖フロー**（最小構成: 2ステップで連鎖効果を検証）:
```
seed_6.png → Kontext (人物差し替え) → output_6a
output_6a  → Kontext ("Same woman, adjust to [微修正指示],
              maintaining exact facial features and outfit") → output_6b
```

**生成数**: 2 画像

**コスト**: $0.04 × 2 = $0.08

## 5. 評価基準

各実験で生成された画像を以下の観点で評価する:

1. **キャラクター一致度**: キャラクター参照画像とどの程度同一人物に見えるか（5段階）
2. **環境再現度**: seed キャプチャの雰囲気（色味・空間・照明）がどの程度再現されているか（5段階）
3. **構図保持度**: seed キャプチャの構図・カメラアングルがどの程度保持されているか（5段階）
4. **人物混入**: seed キャプチャの実在人物の特徴が出力に漏れていないか（二値）
5. **連鎖安定性**（実験 3 のみ）: 連鎖ステップ後もキャラクターのアイデンティティが崩れていないか（5段階）

## 6. 実装構成

```
poc/seamless/
├── plan.md               # 本ドキュメント
├── config.py             # 実験パラメータ定義
├── run_experiment.py     # 実験実行スクリプト
├── references/           # seed キャプチャ → seeds/captures/ からコピーまたはシンボリックリンク
├── generated/            # 生成画像出力先
│   ├── exp1_max_multi/
│   │   ├── D-A/
│   │   └── D-B/
│   ├── exp2_iterative/
│   │   ├── I-A/
│   │   └── I-B/
│   ├── exp3_anchor_chain/
│   └── experiment_log.json
└── reports/              # 評価レポート出力先
```

### 既存 PoC（`poc/keyframe_gen/`）との関係

- `run_experiment.py` の基本構造（argparse, async, ログ）を流用
- `config.py` のパターン定義構造（PromptPattern, Scene）を参考にするが、新規定義
- FLUX Kontext は fal.ai 経由で呼び出し（`fal-ai/flux-pro/kontext/max/multi`, `fal-ai/flux-pro/kontext`）

## 7. 実行手順

```bash
# 1. ドライラン（プロンプト確認・コスト見積もり）
uv run python poc/seamless/run_experiment.py --experiment exp1 --dry-run

# 2. 実験 1: Max Multi 人物差し替え
uv run python poc/seamless/run_experiment.py --experiment exp1

# 3. 実験 2: Iterative Editing vs 1パス
uv run python poc/seamless/run_experiment.py --experiment exp2

# 4. 実験 3: Character Anchor Chain
uv run python poc/seamless/run_experiment.py --experiment exp3

# 5. 特定パターンのみ実行
uv run python poc/seamless/run_experiment.py --experiment exp1 --patterns D-A
```

## 8. コスト見積もり

| 実験 | 画像数 | コスト | API |
|------|--------|--------|-----|
| 実験 1: Max Multi 人物差し替え | 2 | $0.12 | FLUX Kontext Max |
| 実験 2: Iterative Editing vs 1パス | 4 | $0.16 | FLUX Kontext Pro |
| 実験 3: Character Anchor Chain | 2 | $0.08 | FLUX Kontext Pro |
| **合計** | **8** | **$0.36** | |

## 9. 成功基準

以下を満たす組み合わせが 1 つ以上見つかれば PoC 成功とする:

1. キャラクター一致度 ≥ 3/5（同一人物と認識可能）
2. 環境再現度 ≥ 3/5（seed の雰囲気が感じられる）
3. 構図保持度 ≥ 3/5（seed の構図・カメラアングルが維持されている）
4. 人物混入なし（seed の実在人物の特徴が出ていない）

## 10. 方法論調査: 実写画像から高品質なAI画像を生成するベストプラクティス

### 10.1 段階的変換（Progressive Transformation）

**核心原則: 一度に大きく変えず、複数パスで段階的に変換する。**

絵画制作のプロセス（ラフスケッチ → 精密画 → ディテール仕上げ）と同じ考え方。研究によると、変換をステージに分割すると満足度94% vs 単一の複雑なプロンプトの67%。

#### マルチパス・ワークフロー

| パス | Denoising Strength | 目的 |
|------|-------------------|------|
| Pass 1（構造変換） | 0.7 - 0.8 | 大きな構造変更。キャラクター置換、ポーズ変更 |
| Pass 2（ディテール洗練） | 0.4 - 0.5 | 顔の特徴、服の質感など細部の調整 |
| Pass 3（仕上げ） | 0.2 - 0.3 | 肌質、照明の自然さなど微細な品質向上 |

各パスで**前回の出力を次回の入力**として使用する。

#### 低ノイズ段階的アプローチ（保守的）

より慎重に変換する場合:
- Pass 1: denoise 0.25（初期微調整）
- Pass 2: denoise 0.30（Pass 1の結果を基に構築）
- Pass 3: denoise 0.35（最終仕上げ）

#### Denoising Strength の基本原則

| 範囲 | 効果 | 用途 |
|------|------|------|
| 0.0 - 0.2 | 元画像をほぼ保持 | 微細な色調補正、ノイズ除去 |
| 0.2 - 0.4 | 軽微な変更 | **構図を保ちたい場合はこの範囲** |
| 0.4 - 0.6 | バランスの取れた変更 | **一般的な用途で最も安定** |
| 0.6 - 0.7 | 中程度の変更 | キャラクター置換 |
| 0.7 - 1.0 | 大幅な変更 | ほぼ新規生成に近い |

#### Hires Fix + img2img の2段階ディテール強化

1. **低解像度で初期生成** → 構図とキャラクターを確定
2. **アップスケーラーで2倍に拡大**
3. **img2img でディテール追加**（denoising 0.1 - 0.3）

→ メモリ制限を克服しつつ、アーティファクトなしで画質向上。

### 10.2 参照画像の選び方・使い方

#### 参照画像の品質要件

| 要素 | 推奨 | 理由 |
|------|------|------|
| 解像度 | 1024x1024px 以上 | モデルが特徴を正確に読み取れる |
| 被写体の占有率 | フレームの 60-80% | 特徴が十分なサイズで捉えられる |
| 背景 | シンプル・単色 | モデルがキャラクター特徴に集中できる |
| 品質 | 高解像度・鮮明 | ぼけ・ノイズがない状態 |

#### キャラクター参照画像のバリエーション構成

| 種類 | 割合 | 用途 |
|------|------|------|
| 正面ショット | 40% | 顔の特徴が最も明確 |
| 3/4アングル | 30% | 斜めからの顔 |
| 横顔 | 20% | プロフィールビュー |
| 表情バリエーション | 10% | 笑顔、真面目な顔など |

**注意:** 髪や手で顔が隠れている画像は品質低下の原因。顔が明確に見える画像を選ぶ。

#### マルチリファレンスの使い分け

異なる側面に対して**別々の参照画像**を使い分ける:
1. **キャラクター外見** 用の参照画像（@char）
2. **環境・空間** 用の参照画像（@location）
3. **スタイル** 用の参照画像（@style）

→ 各要素を独立に制御できる。

#### 参照画像に実在の人物が映っている場合の対処

Seeds キャプチャを @location 参照として使う場合、人物の特徴が出力に漏れるリスクがある。

**対策:**
1. **事前に人物を Inpainting で除去** → 背景のみの画像を参照として渡す
2. **段階的な除去**: まず四肢 → 次に胴体 → 最後に背景ディテール修正
3. **マスクのコツ**: 人物の輪郭ぎりぎりではなく少し余白を持たせる
4. **参照強度を低く設定**: スタイル参照の場合、影響度を低くすることで特徴漏れを最小化

### 10.3 プロンプト構造化テクニック

#### 推奨プロンプト構造

```
[被写体] + [アクション/ポーズ] + [環境] + [スタイル + ライティング + カメラ]
```

| 要素 | 記述例 | 優先度 |
|------|--------|--------|
| 被写体 | "a young woman with short black hair" | 最高（最初に書く） |
| アクション | "sitting at a cafe, reading" | 高 |
| 環境 | "in a cozy Tokyo cafe" | 高 |
| ライティング | "soft natural window light" | 中 |
| カメラ | "close-up portrait, 85mm lens" | 中 |
| ムード | "peaceful, warm" | 低 |

#### プロンプトの長さと品質

- **最適な長さ: 15-50語**。密度重視で全ての語が意味のある方向性を提供すること
- 簡潔で構造化された20語のプロンプトは、冗長な100語の記述を上回る
- 自然言語が推奨: "A curious red fox exploring a misty autumn forest" > "Fox, forest, autumn, misty"

#### 照明・カメラの記述

**照明:**
- `"golden hour natural light from the left"`
- `"soft studio lighting with subtle shadows"`
- `"dramatic backlit silhouette"`

**カメラ:**
- `"85mm portrait lens, shallow depth of field"`
- `"wide-angle, low-angle perspective"`
- `"over-the-shoulder shot, cinematic"`

#### ネガティブプロンプトのベストプラクティス

- **50-150語の焦点を絞ったもの**が最適。500語以上は逆効果
- 「no」「don't」は使わない。除外したいものをそのまま記述する
- 実際に発生した問題に対処する（最小限から始めて反復）

**人物の二重化・分裂を防ぐ:**
```
duplicate, multiple people, cloned face, duplicated features
```
**ポジティブプロンプトにも追加:**
```
alone, solo, single person
```

**矛盾回避が重要:** 矛盾する指示が失敗の23%の原因。参照画像の内容とプロンプトが矛盾しないよう注意。

### 10.4 キャラクター一貫性を保つテクニック

#### Character DNA テンプレート

画像生成**前に**キャラクターの視覚的アイデンティティを完全に定義し、全生成で使い回す:

```
Identity: 美咲
Face: アーモンド形の目, 柔らかい顔立ち, 色白
Hair: ストレートダークブラウン, ローポニーテール
Outfit: キャメルコート, 白ファーストール, ボーダーニット, 白ショートパンツ, ブラウンブーツ
Age/body: 20代後半, 細身
Vibe: 清潔感, ストイック, 暖色系
Prohibited drift: メガネなし, 髪色変更なし, 太さ変更なし
```

研究結果: 同一セッション内で連続生成した画像は、別セッションと比べて**最大87%高い一貫性**を達成。

#### Identity Lock 技法

キャラクターを定義する**3-5個の重要パラメータ**を「ロック」する:

```
LOCKED: Straight dark brown hair in low ponytail
LOCKED: Almond-shaped eyes, fair skin
LOCKED: Camel-colored long coat
LOCKED: Slender build, late 20s
```

特性を「変更不可」として明示的にマークすると、一貫性が有意に向上する。

#### プロンプト・レイヤリング法（3層構造）

1. **マスター・アイデンティティ層**: Character DNA（全生成で固定）
2. **シーン層**: 場所、時間帯、行動（シーンごとに変更）
3. **スタイル層**: 全体の美的方向性（一貫して固定）

マスター層とスタイル層を固定したまま、シーン層だけを差し替えることで、**同一キャラクターが異なるシーンに自然に登場**する。

#### LoRA 学習による高精度キャラクター固定

- **推奨データセット**: 10-30枚の慎重に選定された参照画像
- **解像度**: 最低 512x512px、推奨 1024x1024px
- **バリエーション**: 異なるポーズ・表情・角度を含めつつアイデンティティを維持
- **少数の高品質データセットは、不一貫な大量データセットを上回る**
- **成果**: 適切な LoRA は生成間で **85-95% の顔特徴一貫性**を達成（標準プロンプティングのみでは10%未満）

### 10.5 シーン間の連続性を保つテクニック

#### フレーム・チェイニング（Frame-to-Frame Chaining）

連続するシーンを生成する際の基本テクニック:

1. 前のシーンの**最終フレーム/出力画像**を取得
2. それを次のシーンの**参照画像としてアップロード**
3. 新しいシーンのプロンプトと組み合わせて生成

→ 長いシーケンスでもシームレスな外見を維持できる。

#### First-Last Frame 指定

最初のフレームと最後のフレームを指定し、中間を自動生成する手法:
- 2枚の画像（開始フレーム + 終了フレーム）のみ提供
- モデルが中間フレームを自動生成し、論理的に整合性のある動画を出力
- **シーン間のトランジション**に有効

#### 色味・照明・スタイルの統一テクニック

1. **プロンプトテンプレート方式**: 固定部分（照明・カラーグレーディング）を維持し、変動部分（ポーズ・アングル）のみ変更
2. **2-3色の支配的トーンを決めて全出力で再利用**
3. **ポストプロダクション**: LUT 適用でシーン間の色調を統一

#### 4レイヤーアプローチ

**根本原則:** 「モデルにキャラクターの発明とアニメーションを同時にさせない。まずIDを固定し、その後アニメーションする。」

| Layer | 内容 | 目的 |
|-------|------|------|
| Layer 1 - Character DNA | 書面仕様で外見を定義 | アイデンティティの基盤 |
| Layer 2 - Character Pack | 複数アングルのビジュアル参照画像を用意 | 視覚的な一貫性の基盤 |
| Layer 3 - Shot Keyframes | アニメーション前に静止画として固定 | 構図・ポーズの確定 |
| Layer 4 - Animation | 連続性を保持したモーション生成 | 動画化 |

Character Pack の推奨構成:
- フルボディ正面（ニュートラルポーズ）
- 3/4ビューとサイドプロフィール
- クローズアップ顔 + 表情シート
- 3種のアクションポーズ
- オプション: 背面、手のクローズアップ

#### アンカーメソッド

- 各ショットは「最良のフレーム」（事前生成アンカーまたは前クリップの最強フレーム）から開始
- 衣装ごとに専用アンカーを用意
- **プロンプト**: ID を記述せずモーションを記述する
  ```
  "Subtle motion, keep character identity and outfit unchanged.
  [Action]. Camera: [move]. Style: keep same animation style..."
  ```

### 10.6 構図・ポーズを保持するテクニック

#### ControlNet プリプロセッサの使い分け

| プリプロセッサ | 保持するもの | 最適な用途 |
|-------------|-----------|----------|
| **Depth Map** | 前景/背景関係、奥行き | **被写体の置換・再描画**（本PoCに最適） |
| **OpenPose** | 人体キーポイント | ポーズ転送 |
| **Canny Edge** | 鋭いエッジ線 | イラスト化、線画着色 |
| **HED/SoftEdge** | 滑らかなライン | リカラリング、スタイライゼーション |

**重要な知見**: 初期ステップが構図を決定する。ControlNet を拡散プロセスの初期20%のステップに適用するだけでもポーズが設定される。

#### インペインティングによる選択的修正

1. ベース画像を生成
2. 不満な部分（顔の細部など）だけをマスクしてインペインティング
3. マスク領域のみを高 denoising（0.5-0.7）で再生成

→ 全体を再生成せず、問題箇所だけを修正できる。

### 10.7 パラメータチューニングの基準値

#### 目的別の推奨パラメータ

| 目的 | Denoising | CFG | Steps |
|------|-----------|-----|-------|
| **元画像の微修正** | 0.1-0.3 | 7-9 | 20 |
| **スタイル変換（構図保持）** | 0.4-0.6 | 7-12 | 25-30 |
| **キャラクター置換** | 0.6-0.8 | 7-9 | 25-30 |
| **ほぼ新規生成** | 0.9-1.0 | 7-9 | 20-30 |

#### CFG Scale ガイドライン

- CFG = 1: プロンプトがほぼ無視される
- **CFG = 7-9: 創造性と正確性の良いバランス**（推奨）
- CFG = 20: 厳密に従うが画像品質が低下

#### Steps ガイドライン

- **20ステップ**: 50ステップの95%の品質を達成
- **25-30ステップ**: プロダクション品質
- 50以上: 収穫逓減（生成時間2倍で品質改善わずか12%）

## 11. 方法論を踏まえた本PoCへの適用方針

### 現在の問題と方法論からの解決策

| 問題 | 関連する方法論 | 具体的な適用 |
|------|-------------|------------|
| キャラクター不一致 | Character DNA + Identity Lock + 3層プロンプト | 「美咲」の DNA を定義し、全カットで固定部分を維持 |
| Seeds との乖離 | マルチリファレンス + 段階的変換 | seed を @location 参照 + denoising を段階的に制御 |
| シーン間の不連続 | フレーム・チェイニング + プロンプトテンプレート | 前シーン出力を次シーンの参照に + 色味・照明の固定 |
| 人物特徴の漏れ | 参照画像の前処理（人物除去） | seed キャプチャから人物を Inpainting で事前除去 |

### 実験計画への反映

§10 の方法論で得た知見は、以下の形で実験 1-3 に反映済み:

| 方法論の知見 | 反映先 |
|-------------|--------|
| マルチリファレンス + 人物差し替え | 実験 1（Max Multi 2枚入力） |
| 段階的変換（マルチパス） | 実験 2（Iterative Editing） |
| フレーム・チェイニング | 実験 3（Anchor Chain） |
| Character DNA + Identity Lock | 実験 1-3 のプロンプト設計に組み込み |
| 人物混入対策 | 実験 1 の評価基準で検証 |

## 12. ツール選定: 画像生成API比較

### 選定背景

Runway Gen-4 Image API は `text_to_image` のみで、img2img エンドポイントも denoising strength パラメータも存在しない。§10.1 の段階的変換（マルチパスワークフロー）を実現するには、img2img + 変換強度制御に対応した別の画像生成 API が必要。

画像の段階で品質を十分に高めた上で、高コストな動画生成（Runway image_to_video）に渡す構成を目指す。

### 機能比較

| ツール | img2img | 変換強度制御 | 参照画像 | Inpainting | ControlNet | API成熟度 |
|--------|:-------:|:-----------:|:-------:|:----------:|:----------:|:---------:|
| **FLUX Kontext** | **○** | **○** strength 0-1 | **○** 複数画像 | ○ (Fill) | - | 高 |
| **Stability AI SD3.5** | **○** | **○** strength 0-1 | - | **○** | **○** Canny/Depth/Blur | 高 |
| **Leonardo AI** | **○** | **○** init_strength | **○** Char Ref | **○** | **○** 多数対応 | 中 |
| **Ideogram V3** | **○** Remix | **○** image_weight 1-100 | **○** Char/Style Ref | **○** Edit | - | 中 |
| **Recraft V4** | **○** | 不明 | ○ Style Ref | ○ | - | 高 |
| **Google Imagen 4** | 限定的 | - | 限定的 | ○ | - | 高 |
| **OpenAI GPT Image** | 限定的 | - | - | ○ | - | 高 |
| **Runway Gen-4** | - | - | **○** 1-3枚 | - | - | 中 |
| **Kling** | 限定的 | 限定的 | ○ Multi-ref | - | - | 低 |
| **Midjourney** | (UI有) | (UI有) | (UI有) | (UI有) | - | **API未提供** |

### 料金比較（1画像あたり）

| ツール | 最安 | 標準 | 高品質 |
|--------|------|------|--------|
| Leonardo AI | $0.003 | ~$0.01 | ~$0.01 |
| OpenAI GPT Image | $0.009 (Low) | $0.034 (Med) | $0.20 (High) |
| Google Imagen 4 | $0.02 (Fast) | $0.04 | $0.06 (Ultra) |
| Runway Gen-4 | $0.02 (Turbo) | $0.05 (720p) | $0.08 (1080p) |
| Stability AI SD3.5 | $0.03 (Core) | $0.065 | $0.08 (Ultra) |
| **FLUX Kontext** | **$0.04 (Pro)** | **$0.04** | **$0.08 (Max)** |
| Recraft | $0.04 (V3) | $0.04 | $0.25 (V4 Pro) |
| Ideogram V3 | ~$0.05 (Turbo) | $0.06 | $0.06 |
| Kling | ~$0.01 | ~$0.02 | 前払い最低$4,200 |
| Midjourney | N/A | N/A | N/A |

### 要件適合度

本PoCの要件: **img2img + 変換強度制御 + キャラクター参照 + フォトリアリスティック + API**

| Tier | ツール | 評価 | コスト |
|------|--------|------|--------|
| **Tier 1** | **FLUX Kontext** | img2img / strength / 参照画像すべて高水準。キャラクター一貫性が業界トップクラス | $0.04-0.08 |
| **Tier 1** | Ideogram V3 | Remix + image_weight + Char/Style Ref 対応 | ~$0.06 |
| Tier 2 | Leonardo AI | 全機能対応だが料金体系が複雑（トークン制） | ~$0.003-0.01 |
| Tier 2 | Stability AI | img2img + ControlNet は強いがキャラクター参照なし | $0.03-0.08 |
| Tier 3 | Runway Gen-4 | 参照画像は優秀だが img2img / denoising なし | $0.02-0.08 |

### 選定結果: FLUX Kontext を採用

**採用理由:**

1. **In-context editing**: 入力画像＋自然言語プロンプトで「何を変え、何を保持するか」を明示的に制御可能
2. **Multi-image 入力**（Max）: seed キャプチャ＋キャラクター参照の 2 枚を同時入力し、構図保持＋人物差し替えを1回で実現
3. **キャラクター一貫性**: 業界トップクラスのアイデンティティ保持性能
4. **コスト**: Pro $0.04/画像、Max $0.08/画像で Runway と同等〜安い
5. **API成熟度**: fal.ai 経由で安定的に利用可能

**API パラダイムの注意**: FLUX Kontext Pro/Max API は `strength` パラメータを持たない（dev のローカル実行のみ）。変換の制御は `guidance_scale`（デフォルト 3.5、範囲 1-20）とプロンプトの記述で行う。

**パイプライン構成:**

```
[Seed キャプチャ] → FLUX Kontext (in-context editing) → [高品質キーフレーム] → Runway (image_to_video) → [動画]
```

- **キーフレーム生成**: FLUX Kontext Pro/Max（in-context editing で構図保持＋人物差し替え）
- **動画生成**: Runway Gen-4（image_to_video は引き続き Runway を使用）

### 実験計画への影響

FLUX Kontext の採用により、全実験を Kontext ベースに統一（§4 参照）。

| 実験 | API | エンドポイント | 主な検証ポイント |
|------|-----|-------------|---------------|
| 実験 1: 人物直接差し替え | FLUX Kontext Max | `fal-ai/flux-pro/kontext/max/multi` | 2枚入力での構図保持＋人物差し替え |
| 実験 2: Iterative vs 1パス | FLUX Kontext Pro | `fal-ai/flux-pro/kontext` | 段階的 vs 一括の品質差 |
| 実験 3: Anchor Chain | FLUX Kontext Pro | `fal-ai/flux-pro/kontext` | 連鎖生成でのキャラクター一貫性 |

**コスト**: 実験 1: $0.12 / 実験 2: $0.16 / 実験 3: $0.08 → 合計 $0.36

## 13. 次のステップ（PoC 後）

PoC で有効なパターンが見つかった場合:

1. **Keyframe Engine の拡張**: 逐次生成モード（sequential mode）+ マルチパス対応
2. **Style Mapping の強化**: seed キャプチャとの紐付けを必須化 + 人物除去の前処理パイプライン
3. **プロンプト生成の改善**: Character DNA テンプレート + 3層構造プロンプト生成を Storyboard Engine に組み込み
4. **Character Pack 生成**: Asset Engine で複数アングル・複数ポーズのキャラクター参照画像を生成
5. **本番パイプライン統合**: `pipeline/runner.py` の keyframe ステップ更新

## 13. 調査ソース

### 段階的変換・Denoising
- [Understanding Denoising Strength in img2img - Shakker AI](https://wiki.shakker.ai/en/webui-img2img-denoising-strength-guide)
- [Denoising Strength: All You Need to Know - AIarty](https://www.aiarty.com/stable-diffusion-guide/denoising-strength-stable-diffusion.htm)
- [What is Denoising Strength? - Stable Diffusion Art](https://stable-diffusion-art.com/denoising-strength/)
- [Image to Image SD Complete Guide - Cursor IDE Blog](https://www.cursor-ide.com/blog/image-to-image-stable-diffusion-complete-guide)

### キャラクター一貫性
- [How to Keep Characters Consistent Across AI Scenes - Skywork AI](https://skywork.ai/blog/how-to-consistent-characters-ai-scenes-prompt-patterns-2025/)
- [How to Design Consistent AI Characters - Medium](https://medium.com/design-bootcamp/how-to-design-consistent-ai-characters-with-prompts-diffusion-reference-control-2025-a1bf1757655d)
- [Maintaining Character Consistency - Medium](https://medium.com/@staniszewski/maintaining-character-consistency-in-ai-generated-images-7a12dfbc67bb)
- [Character Consistency in AI - Lovart AI](https://www.lovart.ai/blog/ai-character-consistency)
- [Consistent Character AI: Pro Tips - Artlist](https://artlist.io/blog/consistent-character-ai/)
- [How to Create Consistent Characters in AI Videos - Neolemon](https://www.neolemon.com/blog/how-to-create-consistent-characters-in-ai-videos-complete-guide/)

### プロンプトエンジニアリング
- [Image to Image Prompt Engineering 2025 - Cursor IDE Blog](https://www.cursor-ide.com/blog/image-to-image-prompt-engineering-guide)
- [Mastering AI Image Generation: Hyper-Realistic Prompts - Euryka AI](https://euryka.ai/mastering-ai-image-generation-hyper-realistic-prompts/)
- [JSON Prompting for AI Image Generation - ImagineArt](https://www.imagine.art/blogs/json-prompting-for-ai-image-generation)
- [How to Write AI Image Prompts Like a Pro - LetsEnhance](https://letsenhance.io/blog/article/ai-text-prompt-guide/)
- [150+ Top Negative Prompts - PXZ AI](https://pxz.ai/blog/best-negative-prompts-for-realistic-ai-images)

### ControlNet・構図保持
- [The Ultimate Guide to ControlNet - Civitai](https://education.civitai.com/civitai-guide-to-controlnet/)
- [ControlNet: A Complete Guide - Stable Diffusion Art](https://stable-diffusion-art.com/controlnet/)

### シーン間連続性
- [Complete Guide: Next Scene Generation in ComfyUI - Civitai](https://civitai.com/articles/24629/complete-guide-next-scene-generation-from-images-in-comfyui)
- [Stable Video Infinity - GitHub](https://github.com/vita-epfl/Stable-Video-Infinity)
- [ConsistI2V - Tiger AI Lab](https://tiger-ai-lab.github.io/ConsistI2V/)
- [How to Achieve Consistent Style Across AI Video Clips - PyxelJam](https://pyxeljam.com/how-to-achieve-consistent-style-across-multiple-ai-generated-video-clips/)

### スタイル統一・LoRA
- [LoRA Training for Consistent Character - Segmind](https://blog.segmind.com/lora-training-for-consistent-character-is-dead-2/)
- [Best Practices for Training LoRA - DEV Community](https://dev.to/gary_yan_86eb77d35e0070f5/best-practices-for-training-lora-models-with-z-image-complete-2026-guide-4p7h)
- [IP-Adapters: All You Need to Know - Stable Diffusion Art](https://stable-diffusion-art.com/ip-adapter/)

### 参照画像の前処理・人物除去
- [How to Remove a Person with AI Inpainting - Stable Diffusion Art](https://stable-diffusion-art.com/how-to-remove-a-person-with-ai-inpainting/)
- [LaMa Image Inpainting - GitHub](https://github.com/advimman/lama)
- [Reference Images for Enhanced Control - Scenario](https://help.scenario.com/en/articles/use-reference-images-for-enhanced-control/)

### パラメータチューニング
- [CFG Scale Guide - getimg.ai](https://getimg.ai/guides/interactive-guide-to-stable-diffusion-guidance-scale-parameter)
- [Stable Diffusion Samplers Guide - Stable Diffusion Art](https://stable-diffusion-art.com/samplers/)
- [Sampling Steps Guide - getimg.ai](https://getimg.ai/guides/interactive-guide-to-stable-diffusion-steps-parameter)

### ツール選定
- [FLUX Kontext 公式](https://bfl.ai/models/flux-kontext)
- [BFL Pricing](https://docs.bfl.ai/quick_start/pricing)
- [FLUX Kontext Prompting Guide](https://docs.bfl.ai/guides/prompting_guide_kontext_i2i)
- [Stability AI Pricing](https://platform.stability.ai/pricing)
- [Stability AI API Reference](https://platform.stability.ai/docs/api-reference)
- [Leonardo AI API](https://leonardo.ai/api)
- [Ideogram API Pricing](https://ideogram.ai/features/api-pricing)
- [Ideogram Remix V3 API](https://developer.ideogram.ai/api-reference/api-reference/remix-v3)
- [Google Imagen 4 - Vertex AI](https://cloud.google.com/vertex-ai/generative-ai/pricing)
- [OpenAI API Pricing](https://openai.com/api/pricing/)
- [Runway API Pricing](https://docs.dev.runwayml.com/guides/pricing/)
- [Recraft API](https://www.recraft.ai/api)
- [Kling Developer Pricing](https://klingai.com/global/dev/pricing)
