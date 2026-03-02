# Phase C: 画像編集タスク検証計画

## 目的

パイプラインで必要な3つの画像タスクについて、それぞれ最適なプロンプト・画像入力パターンを探る。

| タスク | 入力 | 出力 |
|--------|------|------|
| C-1: キャラクター生成 | 参考キャプチャ + 摂動指示 | オリジナルキャラクター |
| C-2: 環境生成 | 任意の環境写真 + 摂動指示 | バリエーション環境 |
| C-3: キャラ×環境融合 | キャラクター + 環境 + ポーズ指示 | 統合シーン（keyframe） |

C-3 は B-1 の S3M アプローチで方向性が見えているため、C-1・C-2 を先行検証し、C-3 は C-1・C-2 の出力を用いて最終統合する。

---

## 過去の検証から得た横断的知見（参考）

- **プロンプト品質 > モデル選択**: 同一プロンプトなら Pro が Flash より良い。見た目の差はプロンプトの差
- **最小指示原則**: Flash メタプロンプトは指示を最小にして自律分析させる方が良い
- **2段階AIワークフロー**: Flash 分析 → Pro 生成の組み合わせが有効
- **タスク固有の逆転**: 人物差替と背景変更で Identity Block の要不要が逆転する
- **Python SDK 必須**: `ImageConfig(aspect_ratio="9:16")` でアスペクト比を制御

ただし C-1・C-2 は「再現」ではなく「バリエーション生成」という新しいタスクであり、過去知見はそのまま適用できない。

---

## C-1: キャラクター生成

### タスク定義

オリジナルキャラクターを生成する。2つの用途がある:

- **テキストベース**: キャプチャなし。「こんな感じのキャラ」というテキストイメージから生成
- **参照ベース**: 参考キャプチャを元に、似ているが同一ではないキャラクターを生成

生成されたキャラクターは以降のシーン生成で一貫して使用するため、**再利用可能なアイデンティティ**が必要。

### 検証ポイント

1. **摂動の制御**（参照ベース）: 何を変えて何を保持するか、プロンプトでどこまで制御できるか
2. **一貫性の確保**: 生成したキャラクターを別のシーンでも再現できるか（Identity Block の自動生成）
3. **画像入力の効果**（参照ベース）: 参照画像を渡すとコピーになりすぎないか

### 用途1: テキストベース生成

参照画像なしで、テキスト記述からキャラクターを生成する用途。

#### C1-T: テキストのみ生成（参照画像なし）

テキストでキャラクターのイメージを記述し、画像を生成。

```
入力: テキストのみ（キャラクター記述）
プロンプト:
  「Generate a photo of: {キャラクター記述テキスト}
   Full body shot, standing, neutral background.
   The character should look like a real Japanese woman.」
```

**検証ポイント**: テキスト記述のみで安定したキャラクターを生成できるか。毎回異なる人物になるリスク。

### 用途2: 参照ベース生成（比較対象: C1-R1 vs C1-R2）

参考キャプチャを元に、**似ているが同一ではない**キャラクターを生成する用途。

#### C1-R1: 参照画像 + 摂動指示（直接編集型）

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

#### C1-R2: 2段階（Flash分析 → 参照画像付きPro生成）

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

### 後続: Identity Block 自動生成（C1-ID）

C1-T / C1-R1 / C1-R2 のいずれかで生成したキャラクター画像に対して実行する後続ステップ。
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

### 評価軸

| 評価軸 | 説明 |
|--------|------|
| 摂動の適切さ | （参照ベース）参考と「似ているが違う」の適切な距離感 |
| リアリティ | 実在の人物に見える自然さ |
| 再現可能性 | 生成キャラを別シーンで一貫して使えるか |
| 制御性 | 何を変えるかプロンプトで制御できるか |

---

## C-2: 環境生成

### タスク定義

環境画像を生成する。2つの用途がある:

- **テキストベース**: 環境写真なし。「桜並木の川沿い」などテキストで環境を指定して生成
- **参照ベース**: 任意の環境写真（テーマパーク、自然風景、カフェ、街並み等）を元に、雰囲気やテーマを保ちつつ異なる環境を生成

共通要件:
- 後段の C-3 で人物を配置するため、**人物が不在の環境**を生成する
- 構図パターン（全身引き、バストアップに適した距離感等）を指定できること

### 検証ポイント

1. **雰囲気の制御**: テキスト / 参照画像から意図した雰囲気を再現できるか
2. **構図パターンの維持**: カメラアングル・距離感を指定できるか
3. **人物不在の制御**: 人物のいない環境のみを生成できるか
4. **多様なソースへの対応**: テーマパーク、自然、室内など異なるジャンルで安定するか

### 入力画像セット（参照ベース用）

検証には異なるジャンルの環境写真を用意する。

- 自然風景: `reference/sakura.jpg`（既存 — 桜・菜の花・川）
- 追加で2〜3種類の環境写真を用意（室内カフェ、都市街並み、テーマパーク等）

### 用途1: テキストベース生成

環境写真なしで、テキスト記述から環境を生成する用途。

#### C2-T: テキストのみ生成（参照画像なし）

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

### 用途2: 参照ベース生成（比較対象: C2-R1 vs C2-R2 vs C2-R3）

環境写真を元に、**雰囲気を保ちつつ異なる環境**を生成する用途。

#### C2-R1: Flash分析 → テキストのみPro生成

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

#### C2-R2: 参照画像 + 変更指示（直接編集型）

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

#### C2-R3: 参照画像 + 構図テンプレート指示

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

### 後続: 複数環境ジャンルでの安定性テスト（C2-D）

参照ベースの最良パターンを、異なるジャンルの環境写真で実行して汎用性を確認。

- 自然風景（桜・川）
- 室内（カフェ）
- 都市（街並み・駅前）

**検証ポイント**: ジャンルを問わず安定した品質で環境バリエーションを生成できるか。

### 評価軸

| 評価軸 | 説明 |
|--------|------|
| 雰囲気の再現 | （参照ベース）元の環境写真のテーマ・季節・色彩が保たれているか |
| バリエーション | （参照ベース）元とは異なる場所に見えるか（コピーになっていないか） |
| 構図の適切さ | 後段の人物配置に適した構図か |
| 人物不在 | 余計な人物が生成されていないか |
| リアリティ | 実写に見える自然さ |

---

## C-3: キャラ × 環境融合

### タスク定義

C-1 で生成したキャラクターと C-2 で生成した環境を融合し、キャラクターが環境に自然に存在するシーン（keyframe）を生成する。ポーズ指定も同時に行う。2つの用途がある:

- **画像入力型**: キャラ画像 + 環境画像の両方を入力して融合（C-1・C-2 の出力を使う標準フロー）
- **テキスト環境型**: キャラ画像 + テキスト環境記述で融合（環境画像を用意せず、テキストで環境を指定する場合）

### B-1 からの引き継ぎ

B-1 の S3M アプローチが最有望:
- Flash 分析（最小指示メタプロンプト）→ Pro 画像生成
- プロンプト品質が画像品質を決定する

ただし B-1 との差分:
1. **キャラクターが生成物**: B-1 では既存の参照写真（front.png）を使用。C-3 では C-1 で生成したキャラクター画像 + 自動生成 Identity Block を使用
2. **環境が生成物**: B-1 では既存の参照写真（sakura.jpg）を使用。C-3 では C-2 で生成した環境画像を使用
3. **seed 画像の役割見直し**: B-1 で seed の構図情報が Flash 出力に反映されていなかった。パイプラインでは seed（参考キャプチャ）は C-1・C-2 の入力に使い、C-3 には渡さない可能性

### 用途1: 画像入力型（比較対象: C3-I1 vs C3-I2）

キャラ画像 + 環境画像の両方を入力して融合する標準フロー。

#### C3-I1: S3M 踏襲（最小指示Flash分析 → Pro生成）

B-1 S3M をそのまま適用。最小指示メタプロンプトで Flash に分析を委ねる。

```
Step 1: Flash が [キャラ画像] + [環境画像] を分析 → シーンプロンプト
  メタプロンプト:
    「Analyze both images carefully.
     Image 1 shows the character. Image 2 shows the environment.
     Generate an image generation prompt that places the character
     naturally in this environment.
     The character is: {自動生成Identity Block}
     The character's pose: {pose_instruction}
     Output only the prompt text, nothing else.」

Step 2: Pro が [キャラ画像] + [環境画像] + Flash生成プロンプト で生成
```

**検証ポイント**: C-1・C-2 の生成物を入力にしても S3M 品質を維持できるか。

#### C3-I2: テキストリッチ型（シナリオコンテキスト付きFlash分析 → Pro生成）

Flash への入力情報にシナリオコンテキストを追加し、より詳細なシーンプロンプトを生成させる。

```
Step 1: Flash が [キャラ画像] + [環境画像] + コンテキスト を分析
  メタプロンプト:
    「Analyze both images carefully.
     Image 1: the character — {自動生成Identity Block}
     Image 2: the environment
     Scenario context: {シナリオからのシーン説明}
     Generate an image generation prompt that:
     - Places the character naturally in this environment
     - Matches the scenario context
     - Specifies the character's pose: {pose_instruction}
     - Describes natural lighting and atmosphere
     Output only the prompt text, nothing else.」

Step 2: Pro が [キャラ画像] + [環境画像] + Flash生成プロンプト で生成
```

**検証ポイント**: シナリオコンテキストの追加がシーンの自然さに寄与するか。C3-I1 との差分。

### 用途2: テキスト環境型

環境画像を用意せず、テキストで環境を指定して融合する用途。

#### C3-T: 環境画像なし（テキスト環境記述のみ）

環境画像を渡さず、テキストのみで環境を記述して融合。

```
入力: [キャラ画像] + テキスト（環境記述 + ポーズ指示）
プロンプト:
  「Image 1 shows the character: {自動生成Identity Block}
   Generate a photo of this character in the following environment:
   {環境記述テキスト}
   The character's pose: {pose_instruction}
   Photo-realistic, natural lighting.」
```

**検証ポイント**: 環境画像なしでもテキスト記述で十分な品質が出るか。画像入力型との品質差。

### 評価軸

| 評価軸 | 重み | 説明 |
|--------|------|------|
| 空間認識・接地感 | 最重要 | 人物が環境に自然に溶け込んでいるか |
| キャラクター一貫性 | 高 | C-1 のキャラクターと一致しているか |
| 環境の再現 | 高 | C-2 の環境の雰囲気が保たれているか |
| ポーズ反映 | 中 | 指示したポーズが実現されているか |
| リアリティ | 高 | 全体として実写に見えるか |

---

## 実行計画

### Phase 1: C-1 キャラクター生成

入力: 既存の参考キャプチャ（`seeds/captures/tamachan_life_/4.png`）
参照: `poc/seamless/reference/front.png`（比較用の既存キャラ）

1. 用途1（テキストベース）: C1-T を実行
2. 用途2（参照ベース）: C1-R1 vs C1-R2 を同一キャプチャで実行 → 最良パターンを選定
3. C1-ID（Identity Block 自動生成 + 再現性テスト）を最良結果に対して実行

### Phase 2: C-2 環境生成

入力: `poc/seamless/reference/sakura.jpg` + 追加環境写真（要準備）

1. 用途1（テキストベース）: C2-T を実行
2. 用途2（参照ベース）: C2-R1 vs C2-R2 vs C2-R3 を sakura.jpg で実行 → 最良パターンを選定
3. C2-D（複数ジャンル安定性テスト）を最良パターンで実行

### Phase 3: C-3 キャラ×環境融合

入力: Phase 1 最良のキャラクター画像 + Phase 2 最良の環境画像

1. 用途1（画像入力型）: C3-I1 vs C3-I2 を実行 → 最良パターンを選定
2. 用途2（テキスト環境型）: C3-T を実行
3. 最良パターンで複数環境 × 複数ポーズの組み合わせテスト

### コスト見積もり

| Phase | パターン数 | API呼び出し/パターン | 推定コスト |
|-------|-----------|---------------------|-----------|
| C-1 (Phase 1) | 3 + 1(D) | 1〜2 | $0.12〜$0.25 |
| C-2 (Phase 2) | 3 + 1(D) | 1〜2 | $0.12〜$0.25 |
| C-3 (Phase 3) | 3 + 追加 | 2 | $0.15〜$0.30 |
| **合計** | | | **$0.39〜$0.80** |

---

## 前提条件

- **Python SDK（`google-genai`）を使用**
- 出力アスペクト比は `ImageConfig(aspect_ratio="9:16")`
- テキスト生成は `temperature=0.0` で決定的出力
- 画像生成モデル: `gemini-3-pro-image-preview`
- テキスト分析モデル: `gemini-3-flash-preview`

## 成果物

- 検証スクリプト: `poc/seamless/run_phase_c.py`
- 検証設定: `poc/seamless/config_c.py`
- 生成サンプル: `poc/seamless/generated/phase_c/`
- ベストプラクティス（検証完了後）:
  - `docs/image_gen_best_practices/character_generation.md`
  - `docs/image_gen_best_practices/environment_generation.md`
  - `docs/image_gen_best_practices/scene_integration.md`（B-1知見を統合）
