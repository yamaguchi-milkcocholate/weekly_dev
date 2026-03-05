# Environment Generation（環境生成）

## このドキュメントについて

パイプラインの **Asset 層** で実行される環境画像生成のベストプラクティス。
参照写真から人物を除去して環境のみを再現し、後続の Keyframe 層（キャラクター合成）に渡す環境画像を生成する。

### パイプライン上の位置

```
Storyboard → [Asset: 環境生成 ← このドキュメント] → Keyframe（キャラクター合成）
                                                        ↑ 環境画像を入力として使用
```

- **入力**: 参照写真（人物入り可）または Storyboard の image_prompt テキスト
- **出力**: 人物不在の環境画像（Keyframe 層でキャラクターと合成される）

### 用語定義

| コード        | 正式名                           | 説明                                                                                   |
| ------------- | -------------------------------- | -------------------------------------------------------------------------------------- |
| **C2-R2**     | Reference-to-Recreation（1パス） | 参照画像を Pro に直接渡して環境を再現する。**基本手法**                                |
| **C2-R2-MOD** | C2-R2 + Modification             | C2-R2 のベースプロンプト末尾に修正指示を追加し、画角・雰囲気・オブジェクト等を変更する |
| **C2-ED**     | Environment Description          | 生成済み環境画像を Flash で分析し、環境記述テキストを自動抽出する                      |

> **命名規則**: `C2` = 環境生成タスク、`R2` = 手法バリアント2（参照画像1パス）、`MOD` = 修正指示付き、`ED` = 環境記述抽出。
> 他のベストプラクティスドキュメントでも同じ命名規則を使用する（例: C1 = キャラクター生成、C3 = キャラクター×環境合成）。

---

## 推奨手法

- **推奨 API**: Gemini 3 Pro Image (`gemini-3-pro-image-preview`) + Flash (`gemini-3-flash-preview`)
- **方式**: 1パス — 参照写真を直接 Pro に渡して環境を再現（C2-R2）
- **コスト**: $0.04/環境（Pro 画像生成1回）

---

## 用途別の推奨パターン

| 用途                                       | 推奨パターン  | 方式                             | コスト    |
| ------------------------------------------ | ------------- | -------------------------------- | --------- |
| 参照写真→環境再現                          | **C2-R2**     | 参照画像 + 環境再現指示（1パス） | **$0.04** |
| 環境の修正（雰囲気・オブジェクト・画角等） | **C2-R2-MOD** | C2-R2 + 修正指示                 | **$0.04** |
| 環境記述テキスト抽出                       | C2-ED         | Flash分析                        | $0.01     |

基本は C2-R2。修正指示を追加するだけで雰囲気変更・オブジェクト追加が可能。画角変更も可能だが、室内シーンでは記述品質に依存する（→ 後述「modification プロンプトの書き方ガイド」セクション）。

---

## プロンプトテンプレート

### 環境再現（C2-R2）— 基本

参照写真（人物入り）から環境のみを再現する。

```
Image 1 shows a photo with people in a specific environment.
Recreate ONLY the environment/location from this image,
removing all people completely.
Keep: the exact same location type, structures, weather, lighting,
color palette, atmosphere, time of day.
Remove: all people, all persons.
The scene must have NO people, no persons, completely empty.
Composition: eye level camera, suitable for placing
a full-body standing person in the center of the frame.
Photo-realistic, natural lighting.
```

### 環境の修正（C2-R2-MOD）

C2-R2 のベースプロンプト末尾に修正指示を追加する形式。
修正指示の書き方は後述「modification プロンプトの書き方ガイド」セクションを参照。

#### 別アングル

> **注意**: 画角変更は屋外シーンでは安定するが、室内シーンではシーンベースの記述が必要。

```
[C2-R2 ベースプロンプト]
View the scene from the entrance doorway, looking into the room.
The camera is at standing eye level in the doorway, showing the
full room layout from this new perspective. Keep the same atmosphere.
```

#### 雰囲気変更

```
[C2-R2 ベースプロンプト]
Change the atmosphere to golden hour sunset lighting.
Warm orange light streaming through the windows, casting
long soft shadows. Keep the same location and layout.
```

#### オブジェクト追加

```
[C2-R2 ベースプロンプト]
Add additional elements: a bookshelf against the wall and
potted plants on the windowsill. Keep the same overall setting
and atmosphere.
```

#### スケール変更（小→大）

```
[C2-R2 ベースプロンプト]
Transform this into a larger, more professional version of
the same type of space with additional equipment and furniture.
Keep the same background and atmosphere.
```

**ポイント**:

- `Keep the same ...` で保持する要素を明示
- `Change ... to ...` で変更箇所を具体的に指定
- `Add additional elements: ...` でオブジェクトを列挙
- `Transform this into ...` でスケール変更
- 画角変更は「シーンベースの視点指定」が効果的 — 詳細は後述「modification プロンプトの書き方ガイド」セクション

### 環境記述テキスト抽出（C2-ED）

**生成された環境画像**を Flash で分析し、Keyframe 層でのキャラクター合成用に環境記述テキストを生成する。

```
Analyze this environment image and generate a concise description
covering: location type, season, time of day, lighting conditions,
color palette, atmosphere, key environmental features.
This will be used to reproduce this environment in combined scenes.
Output only the description.
```

- **temperature=0.0** で決定的出力にする

---

## 人物入り参照写真の扱い

元写真に人物が含まれていても、Pro は環境のみの再現に対応できる。以下の指示を組み合わせる:

| 指示                                           | 目的                                   |
| ---------------------------------------------- | -------------------------------------- |
| `Focus on the ENVIRONMENT only, ignore people` | 人物を無視して環境に注目させる         |
| `Recreate ONLY the environment/location`       | 環境のみの再現を明示                   |
| `removing all people completely`               | 人物除去を指示                         |
| `NO people, no persons, completely empty`      | 人物不在を強調（冗長だが安定化に寄与） |

---

## 1パス vs 2パス

参照画像を直接 Pro に渡す1パス（C2-R2）が基本。Flash でテキスト化してから Pro に渡す2パスは、細部（構造物の配置、色合い）が失われるため非推奨。

---

## modification プロンプトの書き方ガイド

C2-R2-MOD の `modification` テキストは、プロンプトの書き方によって反映度が大きく変わる。
以下のガイドラインに従って記述すること。

### 基本原則

- **プロンプト構成は C2-R2-MOD を使用する**: ベースプロンプト末尾に modification を追加する形式が最も安定
- **modification の記述品質が成否を決める**: 構成の変更ではなく、テキストの具体性が重要

### 効果的な記述パターン

| パターン                   | 記述方針                                                           | 効果 |
| -------------------------- | ------------------------------------------------------------------ | ---- |
| **シーンベースの視点指定** | 空間内の具体的な位置（家具・入口など）を起点にカメラ位置を描写する | 高い |
| **雰囲気変更**             | 照明・天候・時間帯を具体的に描写し、色味や影の変化を記述する       | 高い |
| **オブジェクト追加**       | 追加するモノを具体的に列挙し、配置場所を指定する                   | 高い |
| **保持要素の明示**         | `"Keep the same ..."` で変更しない要素を明示する                   | 安定 |

### 避けるべき記述パターン

| パターン                                                                             | 問題                                   |
| ------------------------------------------------------------------------------------ | -------------------------------------- |
| **幾何学的・抽象的なアングル指定**（例: `"45-degree angle"`, `"side-angle view"`）   | 参照画像の構図に負けやすい（特に室内） |
| **「Recompose」のみの構図変更**                                                      | 抽象的すぎて参照画像の構図が優先される |
| **矛盾する複数指示**（例: `"Keep the exact same layout. Change the camera angle."`） | 保持と変更が矛盾                       |

### 画角変更のコツ

画角・構図の変更は modification の中で最も反映されにくい。以下のテクニックで改善できる:

1. **空間内の具体的な位置を指定する**: 「45度から」ではなく「入口のドアから見た位置で」「窓際のソファに座った視点で」
2. **何が見えるかを描写する**: 「サイドアングル」ではなく「棚の側面と窓の外が見える」
3. **カメラの高さを具体的に指定する**: 「ローアングル」ではなく「椅子に座った目線の高さで」

**良い例:**

```
View the room from the doorway entrance, looking in.
The camera is at standing eye level, showing the full room
layout with the desk on the left and the window straight ahead.
Keep the same atmosphere and lighting.
```

**悪い例:**

```
Recompose the scene as a side-angle view.
Shot from a 45-degree side angle at eye level.
```

### 屋外 vs 室内

| 環境タイプ | 画角変更の難易度 | 理由                               |
| ---------- | ---------------- | ---------------------------------- |
| 屋外       | 低い             | 構造が少なく構図の自由度が高い     |
| 室内       | **高い**         | 壁・家具の配置が構図を強く拘束する |

室内の画角変更では、上記のシーンベース記述を特に意識すること。

---

## 注意点・アンチパターン

| アンチパターン                        | 症状                         | 対策                                                               |
| ------------------------------------- | ---------------------------- | ------------------------------------------------------------------ |
| 参照写真の環境再現に Flash 分析を挟む | 細部が失われ元写真から乖離   | 1パス直接指示（C2-R2）を使う                                       |
| `"NO people"` のみで人物除去を指示    | まれに人物が残る             | `"no persons, completely empty"` を追加して強調                    |
| 構図指示なしで環境再現                | 構図が元写真と大きく変わる   | 最低限 `eye level camera` + `suitable for placing a person` を追加 |
| 環境記述テキストを人手で作成          | 実際の画像と微妙に乖離       | C2-ED で生成画像から自動抽出                                       |
| 幾何学的なアングル指定で画角変更      | 室内シーンで構図が変わらない | シーンベースの視点指定を使う                                       |

---

## Keyframe 層への引き渡し

環境生成の出力として Keyframe 層に渡すもの:

1. **環境画像**（C2-R2 出力）— 人物不在、元写真の雰囲気を再現

**注意**: C2-ED（環境記述テキスト）は Keyframe 層の画像参照方式では使用しない。環境記述テキストを渡すとプロンプト肥大化で逆効果となることが確認されている。テキストのみで環境を指定する fallback 方式でのみ使用する。

---

## 検証エビデンス

詳細は各検証レポートを参照。

| 検証                      | 主要な結論                                               | レポート                                    |
| ------------------------- | -------------------------------------------------------- | ------------------------------------------- |
| 環境生成手法の比較        | 参照画像を直接渡す1パス（C2-R2）が最も忠実               | `poc/seamless/C2_result.md`                 |
| modification 反映度の改善 | プロンプト構成よりも modification テキストの具体性が重要 | `poc/seamless/generated/c2_mod_comparison/` |
