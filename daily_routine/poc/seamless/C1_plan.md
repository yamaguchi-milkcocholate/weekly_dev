# C-1: キャラクター生成 — 検証計画

## タスク定義

オリジナルキャラクターを生成する。

### 入力

| 入力パターン     | 画像数  | 内容                                   |
| ---------------- | ------- | -------------------------------------- |
| テキストベース   | 0枚     | テキスト記述から生成                   |
| 単一参照         | 1枚     | 参考キャプチャから摂動生成             |
| 複数参照（融合） | 2枚以上 | 人物画像 + 服装/アクセサリー画像を融合 |

### 出力

| 出力                    | 仕様                                   | 用途           |
| ----------------------- | -------------------------------------- | -------------- |
| キャラクター画像        | 全身・正面・ニュートラル背景           | C3の参照画像   |
| Identity Block テキスト | 顔・髪・体型・服装・アクセサリーの記述 | C3のプロンプト |

---

## 用途1: テキストベース生成

参照画像なしで、テキスト記述からキャラクターを生成する。
キャプチャがなく「こんな感じのキャラ」というテキストイメージから作りたい場合の用途。

### C1-T: テキストのみ生成（参照画像なし）

```
入力: テキストのみ（キャラクター記述）
プロンプト:
  「Generate a photo of: {キャラクター記述テキスト}
   Full body shot, standing, neutral background.
   The character should look like a real Japanese woman.」
```

**検証ポイント**: テキスト記述のみで安定したキャラクターを生成できるか。毎回異なる人物になるリスク。

---

## 用途2: 参照ベース生成（比較対象: C1-R1 vs C1-R2）

参考キャプチャを元に、**似ているが同一ではない**キャラクターを生成する。
顔立ち・体型・雰囲気は近いが、服装・髪型・アクセサリーなどに変化を加える。

### C1-R1: 参照画像 + 摂動指示（直接編集型）

参考キャプチャを直接入力し、変更箇所を指示。1パスで生成。

```
入力: [参考キャプチャ] + テキスト
プロンプト:
  「Image 1 shows a reference character.
   Generate a photo of a SIMILAR but DIFFERENT character.
   Keep: face shape, age range, body type, skin tone.
   Change: outfit to {new_outfit_description}, hairstyle to {new_hairstyle}.
   Full body shot, standing, neutral background.
   This must be a DIFFERENT person, not the same person in different clothes.」
```

**検証ポイント**: 「似ているが違う」の境界を制御できるか。同一人物に見えないか。

### C1-R2: 2段階（Flash分析 → 参照画像付きPro生成）

Flash が参考キャプチャを分析してキャラ記述を生成。Pro は参照画像も見ながら生成。

```
Step 1: Flash が [参考キャプチャ] を分析 → 新キャラクター記述
  メタプロンプト:
    「Analyze this person's physical features.
     Generate a character description for image generation.
     The new character should share similar physical features
     (face shape, age, build, skin tone) but have different styling
     (outfit, hair, accessories).
     Suggest a specific new outfit and hairstyle.
     Output only the character description, nothing else.」

Step 2: Pro が [参考キャプチャ] + Flash記述 で生成
  「Image 1 shows a reference for physical features only.
   Generate a photo of the following character (a DIFFERENT person):
   {Flash生成記述}
   Full body shot, standing, neutral background.」
```

**検証ポイント**: Flash 分析 + 参照画像の組み合わせが最適な「似ているが違う」を生成するか。

---

## 用途3: 複数参照・融合生成（比較対象: C1-F1 vs C1-F2）

人物画像と服装/アクセサリー画像を別々に入力し、自然に融合したキャラクターを生成する。
「この人にこの服を着せたい」「この人にこのアクセサリーをつけたい」という用途。

入力:

- Image 1: 人物（顔立ち・体型・雰囲気の参照）
- Image 2+: 服装、アクセサリー、靴など（着せたいアイテムの参照）

### C1-F1: 複数画像 + 融合指示（直接編集型）

全画像を直接入力し、各画像の役割を明示して1パスで融合。

```
入力: [人物画像] + [服装画像] + [アクセサリー画像(任意)] + テキスト
プロンプト:
  「Image 1 shows the person whose physical features to use
   (face, body type, skin tone, hair).
   Image 2 shows the outfit to wear.
   Image 3 shows the accessories to wear.
   Generate a photo of the person from image 1
   wearing the outfit from image 2 and accessories from image 3.
   Full body shot, standing, neutral background.
   Single person only, solo.」
```

**検証ポイント**: 人物の特徴と服装/アクセサリーをそれぞれ異なる画像から取り込めるか。融合の自然さ。

### C1-F2: 2段階（Flash分析 → 複数画像付きPro生成）

Flash が全画像を分析してキャラ記述を生成。Pro は参照画像も見ながら生成。

```
Step 1: Flash が [人物画像] + [服装画像] + [アクセサリー画像(任意)] を分析
  メタプロンプト:
    「Analyze all images carefully.
     Image 1 shows a person. Image 2 shows an outfit.
     Image 3 shows accessories (if provided).
     Generate a detailed character description that combines:
     - Physical features from image 1
     - Outfit from image 2
     - Accessories from image 3
     Output only the character description, nothing else.」

Step 2: Pro が [人物画像] + [服装画像] + [アクセサリー画像(任意)] + Flash記述 で生成
  「Image 1 shows the reference person. Image 2 shows the outfit.
   Image 3 shows the accessories.
   Generate a photo of the following character:
   {Flash生成記述}
   Full body shot, standing, neutral background.
   Single person only, solo.」
```

**検証ポイント**: Flash分析を介した方が融合の精度が上がるか。C1-F1との差分。

---

## 後続: Identity Block 自動生成（C1-ID）

C1-T / C1-R / C1-F のいずれかで生成したキャラクター画像に対して実行する後続ステップ。
生成キャラの Identity Block を自動抽出し、別シーンでの再利用性を検証する。

```
Step 1: 生成済みキャラクター画像を入力

Step 2: Flash が [生成キャラ画像] を分析 → Identity Block テキスト
  「Analyze this character and generate a concise identity description
   covering: age, gender, ethnicity, build, face features, hair, outfit,
   accessories. This will be used to reproduce this exact character
   in different scenes. Output only the description.」

Step 3: Pro が [生成キャラ画像] + Identity Block + 別ポーズ指示で生成
  → 一貫性を目視確認
```

**検証ポイント**: 生成キャラの Identity Block を自動抽出し、再現に使えるか。パイプラインでの再利用可能性。

---

## 評価軸

| 評価軸       | 説明                                                      |
| ------------ | --------------------------------------------------------- |
| 摂動の適切さ | （単一参照）参考と「似ているが違う」の適切な距離感        |
| 融合の自然さ | （複数参照）人物と服装/アクセサリーが自然に融合しているか |
| リアリティ   | 実在の人物に見える自然さ                                  |
| 再現可能性   | 生成キャラを別シーンで一貫して使えるか                    |
| 制御性       | 何を変えるかプロンプトで制御できるか                      |

---

## 実行計画

### 入力画像

- 参考キャプチャ: `seeds/captures/tamachan_life_/4.png`
- 比較用既存キャラ: `poc/seamless/reference/front.png`

### 実行順序

1. 用途1（テキストベース）: C1-T を実行
2. 用途2（単一参照）: C1-R1 vs C1-R2 を同一キャプチャで実行 → 最良パターンを選定
3. 用途3（複数参照・融合）: C1-F1 vs C1-F2 を実行 → 最良パターンを選定
4. C1-ID（Identity Block 自動生成 + 再現性テスト）を最良結果に対して実行

### コスト見積もり

| パターン | API呼び出し                     | 推定コスト       |
| -------- | ------------------------------- | ---------------- |
| C1-T     | 1（Pro画像生成）                | $0.04            |
| C1-R1    | 1（Pro画像生成）                | $0.04            |
| C1-R2    | 2（Flash分析 + Pro画像生成）    | $0.05            |
| C1-F1    | 1（Pro画像生成）                | $0.04            |
| C1-F2    | 2（Flash分析 + Pro画像生成）    | $0.05            |
| C1-ID    | 2〜3（Flash分析 + Pro画像生成） | $0.05〜$0.09     |
| **合計** |                                 | **$0.27〜$0.31** |

---

## 前提条件

- Python SDK（`google-genai`）を使用
- 出力アスペクト比: `ImageConfig(aspect_ratio="9:16")`
- テキスト生成: `temperature=0.0` で決定的出力
- 画像生成モデル: `gemini-3-pro-image-preview`
- テキスト分析モデル: `gemini-3-flash-preview`
