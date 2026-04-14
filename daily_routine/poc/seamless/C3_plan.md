# C-3: キャラ × 環境融合 — 検証計画

## タスク定義

C-1で生成したキャラクターとC-2で生成した環境を融合し、キャラクターが環境に自然に存在するシーン（keyframe）を生成する。ポーズ指定も同時に行う。

### 入力

| 入力         | ソース          | 内容                                     |
| ------------ | --------------- | ---------------------------------------- |
| キャラクター画像 | C-1出力     | 全身・正面・ニュートラル背景             |
| Identity Block  | C-1出力     | 顔・髪・体型・服装・アクセサリーの記述   |
| 環境画像        | C-2出力     | 人物不在、人物配置に適した構図           |
| 環境記述テキスト | C-2出力     | 場所・季節・時間帯・照明・雰囲気の記述   |
| ポーズ指示      | シナリオ     | 「自撮り」「歩行」「食事」など           |

| 入力パターン   | 画像数 | 内容                                         |
| -------------- | ------ | -------------------------------------------- |
| 画像入力型     | 2枚    | キャラ画像 + 環境画像                        |
| テキスト環境型 | 1枚    | キャラ画像 + 環境記述テキスト（環境画像なし） |

### 出力

| 出力                    | 仕様                                   | 用途             |
| ----------------------- | -------------------------------------- | ---------------- |
| シーン画像（keyframe）  | キャラクターが環境に自然に存在する1枚  | 動画生成の入力   |

---

## B-1 からの引き継ぎ

B-1 の S3M アプローチが最有望:
- Flash 分析（最小指示メタプロンプト）→ Pro 画像生成
- プロンプト品質が画像品質を決定する

ただし B-1 との差分:
1. **キャラクターが生成物**: B-1 では既存の参照写真（front.png）を使用。C-3 では C-1 で生成したキャラクター画像 + 自動生成 Identity Block を使用
2. **環境が生成物**: B-1 では既存の参照写真（sakura.jpg）を使用。C-3 では C-2 で生成した環境画像を使用
3. **seed 画像の役割見直し**: B-1 で seed の構図情報が Flash 出力に反映されていなかった。C-3 では seed を渡さない

---

## 用途1: 画像入力型（比較対象: C3-I1 vs C3-I2）

キャラ画像 + 環境画像の両方を入力して融合する標準フロー。

### C3-I1: S3M踏襲（最小指示Flash分析 → Pro生成）

B-1 S3Mをそのまま適用。最小指示メタプロンプトでFlashに分析を委ねる。

```
Step 1: Flash が [キャラ画像] + [環境画像] を分析 → シーンプロンプト
  メタプロンプト:
    「Analyze both images carefully.
     Image 1 shows the character. Image 2 shows the environment.
     Generate an image generation prompt that places the character
     naturally in this environment.
     The character is: {Identity Block}
     The character's pose: {pose_instruction}
     Output only the prompt text, nothing else.」

Step 2: Pro が [キャラ画像] + [環境画像] + Flash生成プロンプト で生成
```

**検証ポイント**: C-1・C-2 の生成物を入力にしても S3M 品質を維持できるか。

### C3-I2: テキストリッチ型（シナリオコンテキスト付きFlash分析 → Pro生成）

Flashへの入力情報にシナリオコンテキストと環境記述テキストを追加し、より詳細なシーンプロンプトを生成させる。

```
Step 1: Flash が [キャラ画像] + [環境画像] + コンテキスト を分析
  メタプロンプト:
    「Analyze both images carefully.
     Image 1: the character — {Identity Block}
     Image 2: the environment — {環境記述テキスト}
     Scenario context: {シナリオからのシーン説明}
     Generate an image generation prompt that:
     - Places the character naturally in this environment
     - Matches the scenario context
     - Specifies the character's pose: {pose_instruction}
     - Describes natural lighting and atmosphere
     Output only the prompt text, nothing else.」

Step 2: Pro が [キャラ画像] + [環境画像] + Flash生成プロンプト で生成
```

**検証ポイント**: Identity Block + 環境記述テキスト + シナリオコンテキストの追加がシーンの自然さに寄与するか。C3-I1との差分。

---

## 用途2: テキスト環境型

環境画像を用意せず、テキストで環境を指定して融合する用途。

### C3-T: 環境画像なし（テキスト環境記述のみ）

環境画像を渡さず、テキストのみで環境を記述して融合。

```
入力: [キャラ画像] + テキスト（Identity Block + 環境記述 + ポーズ指示）
プロンプト:
  「Image 1 shows the character: {Identity Block}
   Generate a photo of this character in the following environment:
   {環境記述テキスト}
   The character's pose: {pose_instruction}
   Photo-realistic, natural lighting.」
```

**検証ポイント**: 環境画像なしでもテキスト記述で十分な品質が出るか。画像入力型との品質差。

---

## 評価軸

| 評価軸             | 重み   | 説明                                       |
| ------------------ | ------ | ------------------------------------------ |
| 空間認識・接地感   | 最重要 | 人物が環境に自然に溶け込んでいるか         |
| キャラクター一貫性 | 高     | C-1 のキャラクターと一致しているか         |
| 環境の再現         | 高     | C-2 の環境の雰囲気が保たれているか         |
| ポーズ反映         | 中     | 指示したポーズが実現されているか           |
| リアリティ         | 高     | 全体として実写に見えるか                   |

---

## 実行計画

### 入力画像

- キャラクター画像: C-1 最良結果
- 環境画像: C-2 最良結果
- Identity Block: C1-ID で自動生成
- 環境記述テキスト: C2-ED で自動生成

### 実行順序

1. 用途1（画像入力型）: C3-I1 vs C3-I2 を実行 → 最良パターンを選定
2. 用途2（テキスト環境型）: C3-T を実行
3. 最良パターンで複数環境 × 複数ポーズの組み合わせテスト

### コスト見積もり

| パターン         | API呼び出し                  | 推定コスト       |
| ---------------- | ---------------------------- | ---------------- |
| C3-I1            | 2（Flash分析 + Pro画像生成） | $0.05            |
| C3-I2            | 2（Flash分析 + Pro画像生成） | $0.05            |
| C3-T             | 1（Pro画像生成）             | $0.04            |
| 組み合わせテスト | 最良パターン × 複数条件      | $0.10〜$0.20     |
| **合計**         |                              | **$0.24〜$0.34** |

---

## 前提条件

- Python SDK（`google-genai`）を使用
- 出力アスペクト比: `ImageConfig(aspect_ratio="9:16")`
- テキスト生成: `temperature=0.0` で決定的出力
- 画像生成モデル: `gemini-3-pro-image-preview`
- テキスト分析モデル: `gemini-3-flash-preview`
