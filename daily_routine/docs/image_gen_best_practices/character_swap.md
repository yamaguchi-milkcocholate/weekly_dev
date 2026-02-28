# Character Swap（人物差し替え）

## 推奨手法

- **推奨 API**: Gemini 3 Pro Image (`gemini-3-pro-image-preview`)
- **方式**: 参照画像 + テキスト指示 1 パス（Python SDK 使用）
- **コスト**: $0.04/枚

## プロンプトテンプレート（推奨）

Phase A-1 再検証で最も安定した結果を出した「全部入り」パターン。
参照画像 + Identity Block + ALL CAPS 保持 + 画像役割記述の4要素を全て含む。

```
Image 1 shows the target character. Image 2 is the scene to edit.
Replace the person in image 2 with the character from image 1:
[Identity Block].
MUST preserve the exact same background, composition, camera angle,
lighting, and overall atmosphere from image 2.
MUST NOT change any background elements, furniture, or room layout.
Single person only, solo.
```

### なぜ全部入りが最強か

各要素を抜くと以下の品質低下が発生する（再検証で確認済み）:

| 要素              | 抜いた場合の症状                                                   | 該当パターン       |
| ----------------- | ------------------------------------------------------------------ | ------------------ |
| Identity Block    | 服装が seed のまま残る（3 seed 中 1 つしか参照服装が反映されない） | R1, R3, R4         |
| ALL CAPS 保持指示 | 背景崩壊リスクが上がる（seed_4 で白背景に崩壊）                    | R2, R3, R5         |
| 画像役割記述      | 致命的ではないが安定性が下がる                                     | R2, R4             |
| 参照画像          | 毎回異なる顔が生成され、キーフレーム間の一貫性が保てない           | 初回検証 P1-P4, P6 |

### Identity Block の書き方

5-7 個の具体的な特徴記述子で構成する。15-50 語に収める。

```
a young Japanese woman, mid 20s, slender build.
Wavy dark brown shoulder-length hair, soft round eyes, fair skin.
Wearing a beige V-neck blouse, light gray pencil skirt,
a delicate gold necklace, beige flat shoes.
```

**ポイント**:

- 顔の特徴（顔の形、目、肌）+ 髪 + 服装 + アクセサリーを含める
- 抽象的な表現（`pretty eyes`）ではなく具体的な表現（`soft round eyes`）を使う
- 記述が簡素すぎると毎回異なる人物になり、詳細すぎるとモデルが混乱する

---

## API の使い方

- **Python SDK（`google-genai`）を使用すること**（REST API は非推奨）
- REST API では `aspect_ratio` を制御できず、参照画像使用時にアスペクト比が崩壊する
- SDK では `ImageConfig(aspect_ratio="9:16")` で出力アスペクト比を明示指定できる
- 画像の入力順序: [参照画像(image 1), seed画像(image 2), テキストプロンプト]

---

## 動詞選択

| 動詞                       | スコープ         | 安全性                           |
| -------------------------- | ---------------- | -------------------------------- |
| `change [対象] to...`      | 最も狭い         | 最も安全                         |
| `replace [対象] with...`   | 人物スワップ向き | 安全（まれに安全フィルター発動） |
| `transform [対象] into...` | 全体再構築リスク | 要注意                           |

**推奨**: `change` または `replace` を使用。`transform` は背景・ポーズごと再構築されるリスクがある（ただし Gemini 3 Pro では差異は小さかった）。

---

## 保持指示

### ポジティブ表現を使う（推奨）

```
Keep the exact same background, composition, camera angle,
lighting, and overall atmosphere.
```

### ネガティブ表現は避ける

```
# NG: 無視されやすい
Don't change the background or lighting.

# OK: ポジティブに言い換え
Keep the background and lighting exactly the same.
```

### ALL CAPS 強調（Gemini で有効）

```
MUST preserve the exact same background.
MUST NOT change any background elements.
```

---

## 注意点・アンチパターン

| アンチパターン             | 症状                                   | 対策                                             |
| -------------------------- | -------------------------------------- | ------------------------------------------------ |
| 服装を指定しない           | 元画像の服装がそのまま残る             | Identity Block に服装を含める                    |
| 参照画像なしでテキストのみ | 毎回異なる顔が生成される               | 参照画像を必ず添付する                           |
| REST API の使用            | 参照画像使用時にアスペクト比が崩壊する | Python SDK + `ImageConfig(aspect_ratio=)` を使う |
| `transform` の無修飾使用   | 背景・ポーズごと変わる                 | `change` / `replace` を使う                      |
| 保持指示の省略             | 意図しない要素が変更される             | ALL CAPS で `MUST` / `MUST NOT` を明記           |
| マルチパス編集             | 画質劣化、キャラドリフト               | 1 パスで全変更を指示                             |
| 代名詞での参照             | モデルが対象を見失う                   | 記述的に参照（`the woman with...`）              |
| 過剰な詳細記述             | モデル混乱、クラッタリング             | コア属性 5-7 に絞る                              |

---

## 検証エビデンス

### Phase A-1 初回検証: テキスト指示のみ（2026-02-28）

- **モデル**: `gemini-3-pro-image-preview`
- **方式**: REST API、テキスト指示のみ（参照画像は P5 のみ）
- **seed 画像**: 3 枚（デスク・上半身、鏡・全身、カフェ・上半身）
- **パターン数**: 8（P1〜P6 + P4 サブパターン 3 種）
- **生成数**: 24 枚（全成功）、**コスト**: $0.96

#### パターン別評価

| パターン | 説明                                   | 総合評価 | 備考                                                    |
| -------- | -------------------------------------- | -------- | ------------------------------------------------------- |
| P1       | ベースライン（簡潔指示、保持指示なし） | C        | 服装指定なしで元の服が残る                              |
| P2       | Identity Block + 保持指示              | A        | 安定した高品質                                          |
| P3       | 選択的編集テンプレート                 | S        | 全 seed で最も安定                                      |
| P4a      | 動詞: change                           | A        | P2 と同等                                               |
| P4b      | 動詞: replace                          | B+       | seed_1 で顔にハートマスク出現                           |
| P4c      | 動詞: transform                        | A        | 予想に反し高品質（差異は軽微）                          |
| P5       | 参照画像あり                           | B        | キャラ一致度は高いがアスペクト比崩壊（REST API の制限） |
| P6       | ALL CAPS + MUST NOT                    | S        | P3 と同等、保持精度が高い                               |

#### 主要な発見

1. **Identity Block（服装含む）が品質差の主因**: 服装指定の有無が最大の差別化要因
2. **動詞の違いは軽微**: Gemini 3 Pro では `change` / `replace` / `transform` の差は小さい
3. **P5 のアスペクト比崩壊は REST API の制限**: キャラ一致度自体は良好だった
4. **テキストのみでは毎回異なる顔になる**: キーフレーム間の一貫性に課題

- 生成サンプル: `poc/seamless/generated/phase_a1/`
- 実験スクリプト: `poc/seamless/run_phase_a1.py`

### Phase A-1 再検証: 参照画像ベース（2026-02-28）

- **モデル**: `gemini-3-pro-image-preview`
- **方式**: Python SDK（`google-genai`）、全パターンで参照画像使用、`ImageConfig(aspect_ratio="9:16")`
- **seed 画像**: 3 枚（同上）
- **パターン数**: 6（R1〜R6）
- **生成数**: 18 枚（全成功）、**コスト**: $0.72

#### パターン別評価

| パターン | 説明                                 | キャラ一致 | 服装反映 | 背景保持 | 総合  | 備考                          |
| -------- | ------------------------------------ | ---------- | -------- | -------- | ----- | ----------------------------- |
| R1       | 参照のみ（ベースライン）             | B          | C        | A        | B     | 服装が seed のまま残る        |
| R2       | 参照 + Identity Block                | A          | A        | A        | A-    | seed_1 で顔にハートマスク発生 |
| R3       | 参照 + 選択的編集テンプレート        | B+         | C        | C        | C+    | seed_4 で背景が白背景に崩壊   |
| R4       | 参照 + ALL CAPS 保持                 | A          | C        | A        | B+    | 背景保持は優秀だが服装未反映  |
| R5       | 参照 + 明示的役割記述                | A          | A        | B        | B+    | seed_1 で背景が再構築された   |
| **R6**   | **参照 + Identity Block + ALL CAPS** | **A**      | **A**    | **A**    | **S** | **全 seed で安定した高品質**  |

#### 主要な発見

1. **全部入り（R6）が最強**: 参照画像 + Identity Block + ALL CAPS + 画像役割記述の組み合わせが全 seed で最も安定
2. **SDK の `aspect_ratio` 制御は完璧**: 全 18 枚が 9:16 で生成。REST API でのアスペクト比崩壊を完全に解決
3. **Identity Block がないと服装が反映されない**: 参照画像だけでは服装は seed のまま残る傾向（R1, R3, R4）
4. **ALL CAPS 保持指示がないと背景崩壊リスク**: R3 の seed_4 で背景が完全に白背景に崩壊
5. **参照画像はキャラクター一貫性に不可欠**: テキストのみ（初回検証）と比較して、顔の一致度が大幅に向上

- 生成サンプル: `poc/seamless/generated/phase_a1_ref/`
- 実験スクリプト: `poc/seamless/run_phase_a1_ref.py`

---

## 調査ソース

- [Google Developers Blog - How to prompt Gemini 2.5 Flash Image Generation](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)
- [Black Forest Labs - FLUX.1 Kontext Prompting Guide](https://docs.bfl.ml/guides/prompting_guide_kontext_i2i)
- [Google AI for Developers - Image Generation (公式 API ドキュメント)](https://ai.google.dev/gemini-api/docs/image-generation)
- [Max Woolf - Nano Banana Prompt Engineering](https://minimaxir.com/2025/11/nano-banana-prompts/)
- [Sider.ai - Gemini Prompts for Subject Identity Consistency](https://sider.ai/blog/ai-tools/how-to-write-gemini-prompts-that-keep-subject-identity-consistent-across-edits)
- [Google Cloud - Gemini Image Generation Best Practices](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/gemini-image-generation-best-practices)
