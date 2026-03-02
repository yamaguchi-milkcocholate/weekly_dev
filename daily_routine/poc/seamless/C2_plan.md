# C-2: 環境生成 — 検証計画

## タスク定義

環境画像を生成する。

### 入力

| 入力パターン     | 画像数  | 内容                                                       |
| ---------------- | ------- | ---------------------------------------------------------- |
| テキストベース   | 0枚     | テキスト記述から生成                                       |
| 単一参照         | 1枚     | 環境写真から雰囲気を保ちつつバリエーション生成             |
| 複数参照（融合） | 2枚以上 | 複数の環境写真の要素を融合（例: 建物の雰囲気 + 自然の緑） |

### 出力

| 出力             | 仕様                                       | 用途           |
| ---------------- | ------------------------------------------ | -------------- |
| 環境画像         | 人物不在、人物配置に適した構図             | C3の参照画像   |
| 環境記述テキスト | 場所・季節・時間帯・照明・雰囲気の記述     | C3のプロンプト |

---

## 用途1: テキストベース生成

環境写真なしで、テキスト記述から環境を生成する用途。

### C2-T: テキストのみ生成（参照画像なし）

テキストで環境のイメージを記述し、画像を生成。

```
入力: テキストのみ（環境記述）
プロンプト:
  「Generate a photo of the following environment:
   {環境記述テキスト（場所、季節、時間帯、雰囲気等）}
   The scene must have NO people.
   Composition: {camera_angle}, suitable for placing a full-body standing person.
   Photo-realistic, natural lighting.」
```

**検証ポイント**: テキスト記述のみで意図した環境を安定して生成できるか。

---

## 用途2: 単一参照生成（比較対象: C2-R1 vs C2-R2 vs C2-R3）

環境写真1枚を元に、**雰囲気を保ちつつ異なる環境**を生成する用途。

### C2-R1: Flash分析 → テキストのみPro生成

環境写真を Flash が分析し、テキスト記述のみで新環境を生成。Pro には参照画像を渡さない。

```
Step 1: Flash が [環境写真] を分析 → 環境記述テキスト
  メタプロンプト:
    「Analyze this image and describe the environment in detail:
     location type, vegetation, ground surface, sky, lighting conditions,
     color palette, atmosphere, depth composition.
     Then generate an image generation prompt for a SIMILAR but DIFFERENT
     environment with the same atmosphere and theme.
     The scene must have NO people.
     Output only the prompt text, nothing else.」

Step 2: Pro がテキストのみで環境画像を生成
```

**検証ポイント**: Flash分析でテキスト化し、参照画像なしでPro生成。雰囲気の再現精度。

### C2-R2: 参照画像 + 変更指示（直接編集型）

環境写真を直接入力し、バリエーション生成を指示。

```
入力: [環境写真] + テキスト
プロンプト:
  「Image 1 shows a reference environment.
   Generate a photo of a SIMILAR but DIFFERENT location
   with the same atmosphere and theme.
   Keep: lighting, color palette, overall mood, season.
   Change: specific landmarks, exact layout, architectural details.
   The scene must have NO people.
   Camera angle: {full_body_suitable / bust_up_suitable}」
```

**検証ポイント**: 「似ているが違う」環境をどこまで制御できるか。元画像をそのまま返さないか。

### C2-R3: 参照画像 + 構図テンプレート指示

環境写真の雰囲気と、構図パターン（全身向き、バストアップ向き等）を分離して指示。

```
入力: [環境写真] + テキスト
プロンプト:
  「Image 1 shows a reference environment for atmosphere and theme.
   Generate a photo of a similar outdoor/indoor environment.
   Composition requirements:
   - Camera at {eye_level / low_angle / high_angle}
   - Depth: {shallow / medium / deep} background
   - Framing: suitable for placing a full-body standing person in the center
   - Foreground: {clear path / table / railing}
   The scene must have NO people.
   Maintain the season, time of day, and overall atmosphere from image 1.」
```

**検証ポイント**: 雰囲気と構図を分離して指示できるか。後段の人物配置に適した構図を得られるか。

---

## 用途3: 複数参照・融合生成（比較対象: C2-F1 vs C2-F2）

複数の環境写真の要素を融合して新しい環境を生成する。
「この建物の雰囲気 + この自然の緑」「このカフェの内装 + この窓からの眺め」のような用途。

入力:

- Image 1: メインの環境（構図・レイアウトのベース）
- Image 2+: 融合したい要素（植生、建築様式、空の雰囲気など）

### C2-F1: 複数画像 + 融合指示（直接編集型）

全画像を直接入力し、各画像の役割を明示して1パスで融合。

```
入力: [環境写真1] + [環境写真2] + テキスト
プロンプト:
  「Image 1 shows the base environment for layout and composition.
   Image 2 shows elements to incorporate (vegetation, architecture, atmosphere).
   Generate a photo that combines the spatial layout from image 1
   with the environmental elements from image 2.
   The scene must have NO people.
   Composition: suitable for placing a full-body standing person.
   Photo-realistic, natural lighting.」
```

**検証ポイント**: 異なる環境の要素を自然に融合できるか。どちらの画像が支配的になるか。

### C2-F2: 2段階（Flash分析 → 複数画像付きPro生成）

Flash が複数画像を分析して統合環境記述を生成。Pro は参照画像も見ながら生成。

```
Step 1: Flash が [環境写真1] + [環境写真2] を分析
  メタプロンプト:
    「Analyze both images carefully.
     Image 1 shows the base environment. Image 2 shows additional elements.
     Generate an image generation prompt that creates a new environment
     combining the spatial layout from image 1
     with the environmental elements (vegetation, architecture, atmosphere)
     from image 2.
     The scene must have NO people.
     Output only the prompt text, nothing else.」

Step 2: Pro が [環境写真1] + [環境写真2] + Flash記述 で生成
  「Image 1 is the base environment. Image 2 shows elements to incorporate.
   {Flash生成記述}
   The scene must have NO people.
   Photo-realistic, natural lighting.」
```

**検証ポイント**: Flash分析を介した方が融合の精度が上がるか。C2-F1との差分。

---

## 後続: 環境記述テキスト自動生成（C2-ED）

生成した環境画像から、C3で使用する環境記述テキストを自動抽出する後続ステップ。

```
Step 1: 生成済み環境画像を入力

Step 2: Flash が [生成環境画像] を分析 → 環境記述テキスト
  「Analyze this environment image and generate a concise description
   covering: location type, season, time of day, lighting conditions,
   color palette, atmosphere, key environmental features.
   This will be used to reproduce this environment in combined scenes.
   Output only the description.」
```

**検証ポイント**: 生成環境の記述テキストを自動抽出し、C3で再利用できるか。

---

## 後続: 複数環境ジャンルでの安定性テスト（C2-D）

参照ベースの最良パターンを、異なるジャンルの環境写真で実行して汎用性を確認。

- 自然風景（桜・川）
- 室内（カフェ）
- 都市（街並み・駅前）

**検証ポイント**: ジャンルを問わず安定した品質で環境バリエーションを生成できるか。

---

## 評価軸

| 評価軸       | 説明                                                               |
| ------------ | ------------------------------------------------------------------ |
| 雰囲気の再現 | （参照ベース）元の環境写真のテーマ・季節・色彩が保たれているか     |
| 融合の自然さ | （複数参照）異なる環境の要素が自然に融合しているか                 |
| バリエーション | （参照ベース）元とは異なる場所に見えるか（コピーになっていないか） |
| 構図の適切さ | 後段の人物配置に適した構図か                                       |
| 人物不在     | 余計な人物が生成されていないか                                     |
| リアリティ   | 実写に見える自然さ                                                 |

---

## 実行計画

### 入力画像

- 環境写真: `poc/seamless/reference/sakura.jpg`（自然風景）
- 追加環境写真: 要準備（室内カフェ、都市街並み等）

### 実行順序

1. 用途1（テキストベース）: C2-T を実行
2. 用途2（単一参照）: C2-R1 vs C2-R2 vs C2-R3 を sakura.jpg で実行 → 最良パターンを選定
3. 用途3（複数参照・融合）: C2-F1 vs C2-F2 を実行 → 最良パターンを選定
4. C2-ED（環境記述テキスト自動生成）を最良結果に対して実行
5. C2-D（複数ジャンル安定性テスト）を最良パターンで実行

### コスト見積もり

| パターン   | API呼び出し                  | 推定コスト       |
| ---------- | ---------------------------- | ---------------- |
| C2-T       | 1（Pro画像生成）             | $0.04            |
| C2-R1      | 2（Flash分析 + Pro画像生成） | $0.05            |
| C2-R2      | 1（Pro画像生成）             | $0.04            |
| C2-R3      | 1（Pro画像生成）             | $0.04            |
| C2-F1      | 1（Pro画像生成）             | $0.04            |
| C2-F2      | 2（Flash分析 + Pro画像生成） | $0.05            |
| C2-ED      | 1（Flash分析）               | $0.01            |
| C2-D (×3)  | 最良パターン × 3ジャンル     | $0.12〜$0.15     |
| **合計**   |                              | **$0.39〜$0.42** |

---

## 前提条件

- Python SDK（`google-genai`）を使用
- 出力アスペクト比: `ImageConfig(aspect_ratio="9:16")`
- テキスト生成: `temperature=0.0` で決定的出力
- 画像生成モデル: `gemini-3-pro-image-preview`
- テキスト分析モデル: `gemini-3-flash-preview`
