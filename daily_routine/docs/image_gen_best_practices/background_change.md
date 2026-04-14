# Background Change（背景変更）

## 推奨手法

- **推奨 API**: Gemini 3 Pro Image (`gemini-3-pro-image-preview`)
- **方式**: 背景参照画像 + テキスト指示 1 パス（Python SDK 使用）
- **コスト**: $0.04/枚

## プロンプトテンプレート（推奨）

seed 画像 + 背景参照画像の **2枚入力**。画像役割の明示 + 簡潔な保持指示の組み合わせ。

```
Image 1 is the scene to edit.
Image 2 shows the target background environment.
Replace the background in image 1 with the environment from image 2.
Keep the person exactly as they appear in image 1.
Single person only, solo.
```

### 入力構成

```
[seed画像(image 1)] + [背景参照画像(image 2)] + テキスト
```

- image 1: 編集対象の seed 画像
- image 2: ターゲット背景の参照画像
- **キャラクター参照は入力しない**（人物差替のトリガーになるため）

### なぜこの構成が最良か

背景変更タスクの鍵は、モデルを**編集モード**で動作させること。以下の理由で最も安定する:

1. **画像役割の明示**: 2枚の画像の用途をモデルが迷わない
2. **`Replace the background`**: 背景の置換という編集指示が明確
3. **Identity Block を含まない**: 人物をテキストで記述しないため、人物が再生成されない
4. **キャラクター参照画像を含まない**: 参照画像を渡すだけでもモデルが人物差替を実行するリスクがある
5. **テキストオーバーレイの保持**: 元画像のテキスト要素も維持される傾向

---

## 核心原理: 編集モード vs 生成モード

背景変更タスクでは、モデルの動作モードが品質を決定する。

### 編集モード（目標）

```
seed画像をベースに背景部分だけを書き換える（inpainting的処理）
→ 人物は seed のピクセルをそのまま保持
→ 足元の接地面、奥行き、照明が背景と一体で生成される
→ 空間認識◎（その場にいる写真に見える）
```

**トリガー**: `Replace the background in image 2`（背景を置換する）

### 生成モード（回避すべき）

```
人物と背景を別々に生成して合成する
→ 人物がテキスト記述から新規生成される
→ 接地感・奥行き・照明が不整合
→ 空間認識✗（バーチャル背景のように壁紙を貼り付けた感じ）
```

**トリガー**: Identity Block、キャラクター参照画像の入力、`Place the person into`、`She is now standing`

---

## 人物差し替え（B1）との使い分け

背景変更と人物差し替えでは、最適な手法が**正反対**になる。

|                   | 人物差し替え（B1）                | 背景変更（B3）                    |
| ----------------- | --------------------------------- | --------------------------------- |
| Identity Block    | **必須**（服装反映に必要）        | **NG**（人物が再生成される）      |
| ALL CAPS 保持指示 | **有効**（背景保持に効果）        | 不要                              |
| 参照画像の用途    | キャラ参照 → 人物の顔を一致させる | 背景参照のみ（キャラ参照は NG）   |
| モデルの動作      | 人物を生成、背景を保持            | 背景を生成、人物を保持            |

**理由**: 人物差し替えでは「人物を新しく生成する」のが目的なので Identity Block が有効。背景変更では「人物をそのまま保持する」のが目的なので、人物をテキストで記述すると逆に再生成されてしまう。

---

## 動詞選択

| 動詞                         | 効果                                     | 評価     |
| ---------------------------- | ---------------------------------------- | -------- |
| `Replace the background`     | 背景の置換。編集モードを維持             | **推奨** |
| `Change only the background` | スコープ限定。編集モードを維持           | 良好     |
| `Place the person into`      | 人物を環境に配置。合成モードに切り替わる | **NG**   |

---

## 背景記述

### 参照画像で伝える（推奨）

```
Replace the background in image 2 with the environment from image 3.
```

参照画像を渡すだけで十分。テキストでの背景詳細記述は必須ではない。

### テキスト補足は任意（やや効果あり）

```
Replace the background in image 2 with the environment from image 3:
a scenic riverside path lined with blooming cherry blossom trees.
```

画像とテキストの補完効果はあるが、テキスト補足なし（B2）でも十分な品質が出る。テキスト補足を加えると一部の seed で構図変化が起きるリスクもある（seed_8 で確認）。

---

## 注意点・アンチパターン

| アンチパターン              | 症状                                                                    | 対策                                                             |
| --------------------------- | ----------------------------------------------------------------------- | ---------------------------------------------------------------- |
| Identity Block を含める     | 人物が完全に再生成される（ポーズ・服装・構図が全て変化）                | 人物をテキストで記述しない。`Keep the person as they are` で十分 |
| `Place the person into`     | 合成モードに切り替わり、空間認識が崩壊（バーチャル背景感）              | `Replace the background` を使う                                  |
| 人物の新しい状況を記述      | `She is now standing...` でポーズが変更される                           | 人物の状況は記述しない                                           |
| ALL CAPS 人物保持指示       | `MUST preserve the person` が Identity Block 同様に再生成トリガーになる | 簡潔な `Keep the person exactly as they appear` で十分           |
| 照明変更の明示的許可        | `Adjust the lighting` が人物の再構築を引き起こす                        | 照明指示は省略する（モデルが自然に調整する）                     |
| キャラクター参照画像を入力  | モデルが人物差替を実行してしまう（服装・体型・顔が参照画像に置換）      | 背景変更では seed + 背景参照の2枚のみ入力する                    |
| 画像役割の省略              | モデルが画像の用途を混同する                                            | 各画像の役割を冒頭で明示する                                     |
| seed のポーズと背景の不整合 | 座りデスクシーン + 屋外背景 → 不自然な合成感                            | ポーズと背景の状況的整合性を事前に考慮する                       |

---

## 検証エビデンス

### Phase A-3: 背景変更プロンプト最適化（2026-02-28）

- **モデル**: `gemini-3-pro-image-preview`
- **方式**: Python SDK（`google-genai`）、全パターンでキャラ参照 + seed + 背景参照の3枚入力
- **seed 画像**: 3 枚（デスク・座り、鏡・立ち、カフェ・座り）
- **背景参照**: 桜並木の河津桜風景（`poc/seamless/reference/sakura.jpg`）
- **パターン数**: 8（B1〜B8）
- **生成数**: 24 枚（全成功）
- **コスト**: $0.96

#### パターン別評価（seed_4 を主軸、空間認識を最重要基準）

| パターン | 説明                 | 空間認識 | 人物保持                   | 総合  | 備考                                           |
| -------- | -------------------- | -------- | -------------------------- | ----- | ---------------------------------------------- |
| B1       | 簡潔指示             | S        | ◎ seed服装・ポーズ保持     | A+    | テキストオーバーレイは消失                     |
| **B2**   | **画像役割記述**     | **S**    | **◎ seed服装・ポーズ保持** | **S** | **テキストオーバーレイ保持（seed_1, seed_8）** |
| B3       | 背景テキスト補足     | A        | ◎ seed保持                 | A     | seed_4 でテキスト保持。seed_8 で構図変化       |
| B4       | ALL CAPS 全部入り    | D        | ✗ 完全再生成               | D     | Identity Block で人物が新規生成。棒立ち        |
| B5       | 選択的編集（only）   | A        | ◎ seed保持                 | A+    | seed_4, seed_8 でテキスト保持                  |
| B6       | 照明変更許可         | D        | ✗ 完全再生成               | D     | B4 同様。照明指示も逆効果                      |
| B7       | 環境コンテキスト統合 | C        | △ 一部保持                 | D     | `standing` 記述でポーズ変更が発生              |
| B8       | 全部入り+環境統合    | C        | ✗ 完全再生成               | D     | 最大情報量が最悪の結果                         |

#### 主要な発見

1. **編集モード vs 生成モードが品質を決定**: `Replace the background`（編集）と `Place the person into` / Identity Block（生成）で空間認識に決定的な差が出る
2. **Identity Block は背景変更では逆効果**: 人物差し替え（A-1）では「全部入り最強」だったが、背景変更では人物が完全に再生成されてしまう。タスクによって最適手法が正反対
3. **画像役割記述が安定性を向上**: 3枚入力時は各画像の役割を明示すると、テキストオーバーレイ保持を含めて全体的に安定する（B2 > B1）
4. **背景参照画像は全パターンで有効**: 桜+菜の花+川+山の空間構成が概ね再現された
5. **seed のポーズと背景の整合性が重要**: 座りデスク（seed_1, seed_8）+ 屋外背景は状況的に不自然。seed_4（立ち・外出）+ 屋外背景は自然に機能する
6. **簡潔な指示が最も安定**: 人物保持の指示は `Keep the person exactly as they appear` で十分。ALL CAPS や詳細な保持リストは不要

- 生成サンプル: `poc/seamless/generated/phase_a3/`
- 実験ログ: `poc/seamless/generated/phase_a3/experiment_log.json`
- 実験スクリプト: `poc/seamless/run_phase_a3.py`
- 実験設定: `poc/seamless/config_a3.py`

### Phase B-1: パイプライン検証で判明した追加知見（2026-03-02）

A-3 のベストプラクティスをパイプラインに組み込む過程で、以下が判明した。

#### キャラクター参照画像が人物差替を誘発する

A-3 では3枚入力（キャラ参照 + seed + 背景参照）で検証し、B2 プロンプトは `Keep the person exactly as they appear in image 2` で人物保持を指示していた。しかし B-1 パイプライン検証で同じ構成を再実行したところ、**モデルがキャラクター参照画像を使って人物を差し替えてしまう**ケースが確認された。

プロンプトにはテキストで Identity Block を含めていないが、**キャラクター参照画像を入力するだけで生成モードのトリガーになりうる**。

2枚入力（seed + 背景参照のみ）に変更したところ、人物差替は発生しなくなった。上記の推奨テンプレートは B-1 知見を反映した2枚入力版に更新済み。

#### preview モデルの再現性に関する注意

A-3 検証時（2026-02-28）と B-1 検証時（2026-03-02）で、同一条件（同じモデル・プロンプト・入力画像）にもかかわらず品質に差が確認された。`-preview` モデルは予告なくモデルの重みが更新される可能性があり、過去の検証結果が将来も再現される保証はない。ベストプラクティスの**原理（編集モード vs 生成モード）**は安定しているが、具体的な品質水準は変動しうる。

---

## 調査ソース

- Phase A-1（人物差し替え）検証結果: `docs/image_gen_best_practices/character_swap.md`
- Phase A-2（ポーズ変更）検証結果: `docs/image_gen_best_practices/pose_change.md`
- [Google Developers Blog - How to prompt Gemini 2.5 Flash Image Generation](https://developers.googleblog.com/en/how-to-prompt-gemini-2-5-flash-image-generation-for-the-best-results/)
- [Google AI for Developers - Image Generation](https://ai.google.dev/gemini-api/docs/image-generation)
