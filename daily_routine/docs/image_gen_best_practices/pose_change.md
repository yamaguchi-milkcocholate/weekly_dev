# Pose Change（ポーズ変更）

## 推奨手法

- **方式**: 2 段階 AI ワークフロー（分析 → 画像加工）
- **Step 1 モデル**: Gemini 3 Flash (`gemini-3-flash-preview`) — seed 分析・プロンプト生成
- **Step 2 モデル**: Gemini 3 Pro Image (`gemini-3-pro-image-preview`) — 画像加工
- **コスト**: ~$0.05/枚（Step 1: ~$0.01 + Step 2: $0.04）

## 設計思想: 制約設計によるプロンプト構築

ポーズ変更の本質は「ポーズの記述方法」ではなく「**何を変えて何を保持するかの制約設計**」にある。

### 制約設計の背景

検証（v2）の結果、以下が判明した:

- **フル制約型が最高品質**: seed 固有の制約（`While remaining seated`、`objects on the desk`）を具体的に記述することで構図・オブジェクトが高精度に保持される
- **モデル委任型は品質不足**: `Keep surrounding objects in place` 等の汎用的な制約では、机の形状変化など細部の保持が不十分
- **ハードコード制約は危険**: 立ち seed に `seated` を指定すると座りに強制変更される致命的欠陥がある

フル制約には seed 固有の記述が必要なため、ハードコードできない。したがって **2 段階 AI ワークフロー** で自動化する。

---

## 2 段階 AI ワークフロー

```
Step 1（分析・プロンプト生成）:
  モデル: gemini-3-flash-preview
  入力:  seed 画像 + メタプロンプト
  出力:  seed 固有のシーン記述を含む画像加工プロンプト（テキスト）

Step 2（画像加工）:
  モデル: gemini-3-pro-image-preview
  入力:  seed 画像 + Step 1 で生成されたプロンプト
  出力:  ポーズ変更後の画像
```

### Step 1: メタプロンプト（推奨）

最小限の指示で Gemini に分析と制約設計を委ねる。**制約を明示的に列挙しない**ことがポイント。

```
Analyze this image carefully.
Generate an image editing prompt that changes the person's pose to
[ポーズ変更指示].
The character should be: [Identity Block]
The prompt must preserve the scene composition, background, and all objects.
Output only the prompt text, nothing else.
```

### Step 1 の出力例

seed（室内・座り・デスク・ピンクキーボード）に対して、上記メタプロンプトで生成されたプロンプト:

```
A mid-20s slender Japanese woman with wavy dark brown shoulder-length hair
and fair skin, wearing a beige V-neck blouse, gray pencil skirt, and gold
necklace, takes a selfie with a smartphone in her right hand. She sits at
the white desk from the original scene, which includes the pink transparent
mechanical keyboard, pink mouse, and pen. The background remains identical,
featuring the gray sofa, TV, plant, and warm orb lighting.
High-quality realistic photo.
```

Gemini が seed の状況を自律的に分析し、位置（`sits`）・オブジェクト（`pink transparent mechanical keyboard, pink mouse, and pen`）・背景（`gray sofa, TV, plant`）を具体的に記述する。MUST / MUST NOT 等の明示的な制約がなくても、シーン記述の具体性によって Step 2 の Gemini Pro が構図を正確に保持する。

### なぜ最小指示が最良か

v3 で 4 種のメタプロンプトを比較した結果、**最小指示（M1）が最良**と判断した:

| メタプロンプト       | 方式                 | 画像品質 | 問題点                                   |
| -------------------- | -------------------- | -------- | ---------------------------------------- |
| **M1: 最小指示**     | **分析を全て委ねる** | **A**    | **なし**                                 |
| M2: 分析項目明示     | 分析すべき項目を列挙 | A        | 不要な保持指示の混入、過剰な制約のリスク |
| M3: テンプレート提示 | 穴埋め形式           | A        | テンプレートの構造に縛られ柔軟性が低下   |
| M4: Few-shot         | 例示付き             | A        | 例に引きずられる、メンテナンスコスト     |

- **M2〜M4 の問題**: 制約を明示的に列挙すると、保持対象の過剰指定・意図しない制約をモデルにかける恐れがある。例えば M2 は `The camera angle (medium shot from a slightly elevated perspective) and vertical framing MUST NOT be changed` のように本来不要な詳細まで制約化してしまう
- **M1 の強み**: Gemini が seed を自由に分析し、自然な記述でシーンを伝える。制約の過剰指定がなく、Step 2 のモデルが柔軟に解釈できる

---

## Identity Block の書き方

Phase A-1（人物差し替え）の Identity Block をそのまま使用する。

```
a young Japanese woman, mid 20s, slender build.
Wavy dark brown shoulder-length hair, soft round eyes, fair skin.
Wearing a beige V-neck blouse, light gray pencil skirt,
a delicate gold necklace, beige flat shoes.
```

---

## 動作記述の書き方

### 簡潔な動作指示（推奨）

```
taking a selfie with a smartphone in her right hand
```

Gemini 3 Pro は動作名から自然なポーズを推論できる。シンプルな指示が最も安定。

### 動作記述の例

| ポーズ   | 動作記述                                                                         |
| -------- | -------------------------------------------------------------------------------- |
| 自撮り   | `taking a selfie with a smartphone in her right hand`                            |
| 腕組み   | `crosses her arms over her chest with a confident, relaxed expression`           |
| 手を振る | `waving her right hand at the camera with a bright smile`                        |
| PC作業   | `typing on the laptop keyboard, looking at the screen with a focused expression` |
| 食事     | `holding chopsticks in her right hand, picking up food from the plate`           |

### 部位別の細分化（非推奨）

```
# NG: 過剰に具体的
she holds a smartphone in her right hand with arm extended forward,
her left hand is relaxed at her side, she tilts her head slightly
to the right, and smiles naturally at the phone camera.
```

部位ごとの指示は矛盾・不自然な姿勢・誤解釈のリスクがある。

---

## ポーズ変更と人物差し替えの同時指示

**1 パスで人物差し替え + ポーズ変更を同時に指示する方が高品質**。2 パス（差し替え → ポーズ変更）では連鎖劣化が発生する。

---

## 注意点・アンチパターン

| アンチパターン                   | 症状                           | 対策                                       |
| -------------------------------- | ------------------------------ | ------------------------------------------ |
| ハードコードされた位置制約       | 立ちseedで「座ったまま」に変更 | 2 段階ワークフローで動的に生成             |
| 画角固定指示のみ                 | 位置変更を防げない             | 2 段階ワークフローでシーン全体を記述       |
| モデル委任型の汎用的な制約       | 机の形状変化等の品質不足       | 2 段階ワークフローで seed 固有の記述を生成 |
| メタプロンプトでの過剰な制約列挙 | 意図しない制約をモデルにかける | 最小指示で Gemini に分析を委ねる           |
| 部位ごとの過剰な細分化           | 不自然な姿勢、指示間の矛盾     | 動作名を簡潔に書く                         |
| 段階的記述（First/Then/Finally） | ステップ間の意味混在で誤解釈   | 1 文で動作を記述                           |
| カメラアングルの明示（I2I 時）   | 背景構図の大幅変化             | I2I では省略、T2I でのみ使用               |
| 「a smartphone」の曖昧な記述     | 両手にスマホ 2 台が出現        | 「in her right hand」と手を明示            |

---

## テキストオーバーレイへの影響

ポーズ変更時にテキストオーバーレイ（時刻表示等）の保持は不安定。制約パターンとの明確な相関はなく、seed 画像やポーズの組み合わせに依存する。

テキストオーバーレイの保持が重要な場合は、後工程でのオーバーレイ再合成を検討する。

---

## 検証エビデンス

### Phase A-2v3: 2 段階 AI ワークフロー検証（2026-02-28）

- **Step 1 モデル**: `gemini-3-flash-preview`
- **Step 2 モデル**: `gemini-3-pro-image-preview`
- **seed 画像**: 3 枚（屋外・立ち、室内・座り・デスク、室内・立ち・下半身メイン）
- **メタプロンプト**: 4 パターン（M1 最小指示 / M2 分析項目明示 / M3 テンプレート提示 / M4 Few-shot）
- **生成数**: 12 枚（全成功）
- **コスト**: $0.60

#### メタプロンプト別評価

| パターン | 方式             | 画像品質 | Step 1 出力の特徴                                          |
| -------- | ---------------- | -------- | ---------------------------------------------------------- |
| **M1**   | **最小指示**     | **A**    | シーン記述型。制約なし。オブジェクト認識は自然な文脈で記述 |
| M2       | 分析項目明示     | A        | MUST 多用。最も詳細だが過剰な制約混入リスク                |
| M3       | テンプレート提示 | A        | P4 構造に準拠。一貫性は高いがテンプレートに縛られる        |
| M4       | Few-shot         | A        | M3 + オブジェクト詳細。例に引きずられる傾向                |

#### 主要な発見

1. **全パターンで A 品質**: 2 段階ワークフロー自体が有効。メタプロンプトの差は画像品質に大きく影響しない
2. **M1（最小指示）が最良**: 制約の過剰指定がなく、Step 2 のモデルが柔軟に解釈できる
3. **M2〜M4 の制約列挙は過剰**: 不要な保持指示（カメラアングルの詳細記述等）が混入し、意図しない制約をかけるリスクがある
4. **位置判定は全パターンで完璧**: 座り seed で `seated/sits`、立ち seed で `standing/stands` を 100% 正しく判定
5. **オブジェクト認識は十分**: M1 でもピンクキーボード・マウス・ペン等の具体的な物品名を自然に記述

- 生成サンプル: `poc/seamless/generated/phase_a2v3/`
- Step 1 出力: `poc/seamless/generated/phase_a2v3/{M1-M4}/*_step1_prompt.txt`
- 実験ログ: `poc/seamless/generated/phase_a2v3/experiment_log.json`
- 実験スクリプト: `poc/seamless/run_phase_a2v3.py`

### Phase A-2v2: 制約設計によるプロンプト構築フロー検証（2026-02-28）

- **モデル**: `gemini-3-pro-image-preview`
- **seed 画像**: 3 枚（デスク・座り、鏡・全身・立ち、カフェ・座り）
- **パターン数**: 8（P1〜P8）
- **生成数**: 24 枚（全成功）
- **コスト**: $0.96

#### パターン別評価

| パターン | 説明                     | 総合評価 | 備考                                              |
| -------- | ------------------------ | -------- | ------------------------------------------------- |
| P1       | 制約なし（ベースライン） | B+       | seed_8 で構図シフト                               |
| P2       | 位置コンテキスト統合     | C+       | **seed_4 で致命的失敗（立ち→座り）**              |
| P3       | 画角固定                 | B-       | seed_8 で立ち上がり発生                           |
| **P4**   | **フル制約**             | **A**    | 最高品質。seed 固有の記述で構図・オブジェクト保持 |
| P5       | 意図的変更許可（立ち）   | B        | 立ち上がりは意図通り                              |
| **P6**   | **別ポーズ+フル制約**    | **A+**   | 腕組みでもフル制約が機能                          |
| P7       | 別ポーズ+意図的変更      | B        | 腕組み+立ちは意図通り                             |
| P8       | モデル委任型             | B+       | 致命的失敗なしだが机の形状変化等の品質不足        |

#### 主要な発見

1. **フル制約（P4/P6）が最高品質**: seed 固有の具体的な制約で構図・オブジェクトが高精度に保持される
2. **モデル委任型（P8）は品質不足**: 致命的失敗はないが、机の形状変化など細部の保持が不十分
3. **ハードコード位置制約は致命的欠陥**: P2「While remaining seated」は立ち seed で座りに変更
4. **画角固定のみでは不十分**: P3 は seed_8 で座り→立ちが発生
5. **制約はポーズ種類に依存しない**: 腕組み（P6）でもフル制約が同等に機能
6. **自動化にはフル制約の動的生成が必要**: 2段階 AI ワークフロー（分析→加工）で解決

- 生成サンプル: `poc/seamless/generated/phase_a2v2/`
- 実験ログ: `poc/seamless/generated/phase_a2v2/experiment_log.json`
- 実験スクリプト: `poc/seamless/run_phase_a2v2.py`

### Phase A-2v1: ポーズ変更プロンプト最適化（2026-02-28、初回検証）

- **パターン数**: 7（ポーズ記述の粒度を比較）
- **主な知見**: 簡潔な動作指示が最も安定、部位別細分化・段階的記述は非推奨
- 生成サンプル: `poc/seamless/generated/phase_a2/`
- 実験スクリプト: `poc/seamless/run_phase_a2.py`

---

## 調査ソース

- [Google Developers Blog - How to prompt Gemini 2.5 Flash Image Generation](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)
- [Google Cloud - Gemini Image Generation Best Practices](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/gemini-image-generation-best-practices)
- [Google AI for Developers - Image Generation](https://ai.google.dev/gemini-api/docs/image-generation)
- [GodOfPrompt - 10 Image Editing Techniques with Google Nano Banana](https://www.godofprompt.ai/blog/editing-techniques-with-google-nano-banana)
- [GlobalGPT - How to Change Character Poses with Nano Banana](https://www.glbgpt.com/hub/how-to-make-characters-change-poses-with-nano-banana/)
- [GlobalGPT - Stick Figure Sketches for Pose Changes](https://www.glbgpt.com/hub/how-to-change-a-persons-pose-with-stick-figure-sketches-using-nano-banana/)
- [Superprompt - Google Nano Banana Complete Guide](https://superprompt.com/blog/google-nano-banana-ai-image-generation-complete-guide)
- [GensGPT - AI Hands Anatomy & Body Fixes 2026 Guide](https://www.gensgpt.com/blog/ai-hands-anatomy-body-fixes-common-errors-2026-guide)
- [The AI Tutorials - Camera Angle Prompts for Gemini](https://theaitutorials.com/every-camera-angle-prompts-for-gemini-nano-banana-pro-part-1/)
- [Filmora - AI Pose Generator Prompts](https://filmora.wondershare.com/ai-prompt/ai-pose-generator-prompt.html)
