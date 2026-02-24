# 画像・動画生成プロンプトガイドライン

AI画像生成・動画生成（Image-to-Video）における効果的なプロンプトの書き方。

**情報源:**

- [Gen-4 Video Prompting Guide](https://help.runwayml.com/hc/en-us/articles/39789879462419)
- [Creating with Gen-4 Image References](https://help.runwayml.com/hc/en-us/articles/40042718905875)
- [Creating with Gen-4.5](https://help.runwayml.com/hc/en-us/articles/46974685288467)

---

## 1. 画像生成プロンプト

### 目的

シーンの場所・状況・キャラクターの配置を指定し、静止画（キーフレーム画像）を生成する。

### 構成要素

| 要素 | 説明 | 優先度 |
| --- | --- | --- |
| 主体（Subject） | 誰が・何が映っているか | 必須 |
| 姿勢・動作 | そのシーンでの静止状態 | 必須 |
| 場所・環境 | シーンの舞台 | 必須 |
| 照明・雰囲気 | ライティングの方向性や全体の雰囲気 | 推奨 |
| 構図・カメラアングル | 画角やフレーミング | 推奨 |

### ルール

- 英語で記述する（生成モデルは英語プロンプトで最も高い精度を発揮する）
- 自然言語の完全な文章で記述する
- 1プロンプトにつき1シーンのみ記述する

### 良い例

```
A woman sits at a cozy cafe table by the window, holding a latte with both hands,
warm morning sunlight streaming through the glass, soft bokeh background
```

```
A woman stands on a crowded train platform during rush hour, looking at her smartphone,
overhead fluorescent lighting, medium shot from slightly below eye level
```

### 避けるべきパターン

```
# NG: カンマ区切りのキーワードリスト
cafe, girl, sitting, latte, window, morning light
```

```
# NG: 複数シーンの混在
She sits at a cafe, then walks to the office, then sits at her desk
```

---

## 2. 動画生成プロンプト（Image-to-Video）

### 目的

入力画像をもとに、被写体・環境・カメラの動きを指定して動画を生成する。

### 3要素構造

I2V の動画プロンプトは以下の3要素で構成する。**すべてモーション（動き）の記述に特化する。**

| 要素 | 役割 | 記述する内容 |
| --- | --- | --- |
| **Subject Motion** | 被写体の動き | キャラクターの身体的な動作・表情変化 |
| **Scene Motion** | 環境の動き | 背景や周囲のオブジェクトの動き |
| **Camera Motion** | カメラワーク | カメラの移動・回転・ズーム |

### ルール

- 英語で記述する
- 自然言語の完全な文章で記述する
- **能動態で精密な動詞を使う**（sprints, rotates, drifts, sips, glances, tilts）
- **入力画像に既にある情報は記述しない**（外見・服装・場所の描写はモーション品質の低下を招く）
- **否定表現を使わない**（"no camera movement" ではなく "The camera remains still"）
- 1ショットにつき1つの連続した動きのみ記述する

### 良い例

```
She slowly raises her coffee cup and takes a sip, then looks out the window with a gentle smile.
Steam rises from the cup. Pedestrians walk past outside the window.
Camera slowly dollies in from medium shot to close-up on her face.
```

```
She types rapidly on the keyboard, pauses, and leans back stretching her arms above her head.
Papers on the desk flutter slightly from the air conditioning.
Camera remains still, holding a medium wide shot.
```

### 避けるべきパターン

```
# NG: 外見の再記述（入力画像に既にある情報）
A young Japanese woman with brown hair wearing a beige cardigan picks up her coffee cup.
→ 修正: She picks up her coffee cup and takes a slow sip.
```

```
# NG: キーワードリスト
sipping coffee, looking window, warm lighting, cafe atmosphere
```

```
# NG: 否定表現
She sits still with no movement. No camera movement.
→ 修正: She sits quietly, occasionally blinking. The camera remains still.
```

```
# NG: 複数シーンの要求
She drinks coffee at the cafe, then walks to the station, then gets on the train.
```

---

## 3. 動詞リファレンス

汎用的な動詞（moves, does, goes）は避け、具体的な動詞を選択する。

### 人物の動作

| カテゴリ | 動詞例 |
| --- | --- |
| 歩行・移動 | walks, strolls, strides, shuffles, dashes, sprints, steps |
| 手の動作 | reaches, grabs, lifts, places, taps, scrolls, types, waves |
| 飲食 | sips, gulps, bites, chews, nibbles, pours |
| 視線・頭部 | glances, gazes, peers, turns, nods, tilts, looks up/down |
| 姿勢変化 | leans, stretches, slouches, straightens, shifts, settles |
| 表情 | smiles, grins, frowns, squints, blinks, raises eyebrows |

### 環境の動き

| カテゴリ | 動詞例 |
| --- | --- |
| 風・空気 | rustles, sways, flutters, drifts, billows |
| 光 | glimmers, flickers, reflects, shimmers, fades |
| 液体・蒸気 | rises, steams, drips, flows, ripples, splashes |
| 群衆・背景人物 | streams, passes, bustles, mills about |

### カメラワーク

| 動き | 説明 | プロンプト例 |
| --- | --- | --- |
| Dolly in/out | カメラが被写体に近づく/離れる | "Camera slowly dollies in" |
| Track | カメラが水平に移動 | "Camera tracks alongside her" |
| Pan | カメラが水平に回転 | "Camera pans left to reveal the window" |
| Tilt | カメラが垂直に回転 | "Camera tilts up from her hands to her face" |
| Crane | カメラが垂直に移動 | "Camera cranes up to an overhead view" |
| Zoom | 焦点距離を変更 | "Camera zooms in slowly" |
| Static | カメラ固定 | "Camera remains still" / "Static shot" |
| Handheld | 手持ち風の微振動 | "Subtle handheld camera movement" |
| Orbit | 被写体の周りを回る | "Camera slowly orbits around her" |

---

## 4. ショットタイプのリファレンス

画像生成プロンプトの構図指定に使用する。

| ショットタイプ | フレーミング | 適した場面 |
| --- | --- | --- |
| Extreme close-up | 顔の一部（目、口） | 感情の強調 |
| Close-up | 顔全体〜肩 | 表情、リアクション |
| Medium close-up | 胸から上 | 会話、日常動作 |
| Medium shot | 腰から上 | 標準的なシーン |
| Medium wide shot | 膝から上 | 動作のある場面 |
| Wide shot | 全身 | 場所の紹介、移動 |
| Extreme wide shot | 全身 + 広い背景 | 場所の確立、スケール感 |
| Over-the-shoulder | 肩越し | 対話、視線の先 |
| POV | 一人称視点 | 主観体験 |
| Bird's eye | 真上から | 俯瞰、空間の把握 |
| Low angle | 下から見上げ | 力強さ、存在感 |
| High angle | 上から見下ろし | 可愛らしさ、脆弱さ |

---

## 5. チェックリスト

### 画像生成プロンプト

- [ ] 英語で記述されているか
- [ ] 完全な文章になっているか（キーワードリストでないか）
- [ ] 場所・環境が明記されているか
- [ ] 1シーンのみを記述しているか
- [ ] 照明・雰囲気が含まれているか

### 動画生成プロンプト

- [ ] 英語で記述されているか
- [ ] Subject Motion（被写体の動き）が含まれているか
- [ ] Scene Motion（環境の動き）が含まれているか
- [ ] Camera Motion（カメラワーク）が含まれているか
- [ ] 入力画像に既にある情報を再記述していないか
- [ ] 能動態の精密な動詞を使用しているか
- [ ] 否定表現を使っていないか
- [ ] 1ショットにつき1つの連続した動きのみか
