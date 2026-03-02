# Environment Generation（環境生成）

## 推奨手法

- **推奨 API**: Gemini 3 Pro Image (`gemini-3-pro-image-preview`) + Flash (`gemini-3-flash-preview`)
- **方式**: 1パス — 参照写真を直接 Pro に渡して環境を再現（C2-R2 / C2-R3）
- **コスト**: $0.04/環境（Pro 画像生成1回）
- **環境記述テキスト抽出**: 生成後の画像を Flash で分析して $0.01 追加

---

## 用途別の推奨パターン

| 用途 | 推奨パターン | 方式 | コスト |
| --- | --- | --- | --- |
| 参照写真→環境再現 | **C2-R2** | 参照画像 + 環境再現指示（1パス） | **$0.04** |
| 環境のテキスト修正 | **C2-R2-MOD** | C2-R2 + 修正指示（アングル/雰囲気/オブジェクト追加） | **$0.04** |
| 環境記述テキスト抽出 | C2-ED | Flash分析 | $0.01 |

**基本は C2-R2。テキスト修正指示を追加するだけで別アングル・雰囲気変更・オブジェクト追加が可能。**

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

### 環境のテキスト修正（C2-R2-MOD）

C2-R2 のベースプロンプト末尾に修正指示を追加する形式。

#### 別アングル

```
[C2-R2 ベースプロンプト]
Change the camera angle to a LOW ANGLE shot from the water surface
looking UP at the boat deck. Show the boat from outside,
floating on the turquoise ocean.
```

#### 雰囲気変更

```
[C2-R2 ベースプロンプト]
Change the atmosphere to SUNSET. Warm orange and pink sky,
golden hour lighting reflecting on the ocean surface.
Keep the same boat and location.
```

#### オブジェクト追加

```
[C2-R2 ベースプロンプト]
Add additional elements: another large dive boat anchored
in the background, and scuba diving equipment (tanks, BCDs, fins)
neatly arranged on the deck. Keep the same tropical ocean setting.
```

#### スケール変更（小→大）

```
[C2-R2 ベースプロンプト]
Transform this into a LARGER professional racing circuit with:
motorcycles racing on the track, grandstands with empty seats
on the side, sponsor banners on the barriers, and a larger
timing tower. Keep the forested hillside background.
```

**ポイント**:
- `Keep the same ...` で保持する要素を明示
- `Change ... to ...` で変更箇所を具体的に指定
- `Add additional elements: ...` でオブジェクトを列挙
- `Transform this into ...` でスケール変更

### 環境記述テキスト抽出（C2-ED）

**生成された環境画像**を Flash で分析し、C3 用の環境記述テキストを生成する。

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

| 指示 | 目的 |
| --- | --- |
| `Focus on the ENVIRONMENT only, ignore people` | 人物を無視して環境に注目させる |
| `Recreate ONLY the environment/location` | 環境のみの再現を明示 |
| `removing all people completely` | 人物除去を指示 |
| `NO people, no persons, completely empty` | 人物不在を強調（冗長だが安定化に寄与） |

---

## 1パス vs 2パス（Flash分析→Pro生成）

| 方式 | 環境の忠実さ | コスト | 推奨場面 |
| --- | --- | --- | --- |
| **1パス（C2-R2/R3）** | **忠実** | **$0.04** | **参照写真がある場合（基本）** |
| 2パス（C2-R1） | 雰囲気は合うが細部が異なる | $0.05 | 参照写真を Pro に渡したくない場合のみ |

**C1（キャラクター生成）の知見と一致**: 参照画像が1枚で「同じものを再現」するタスクは、1パスで直接 Pro に見せる方が忠実。Flash のテキスト化を挟むと細部（構造物の配置、色合い）が失われる。

---

## 注意点・アンチパターン

| アンチパターン | 症状 | 対策 |
| --- | --- | --- |
| 参照写真の環境再現に Flash 分析を挟む | 細部が失われ元写真から乖離 | 1パス直接指示（C2-R2/R3）を使う |
| `"NO people"` のみで人物除去を指示 | まれに人物が残る | `"no persons, completely empty"` を追加して強調 |
| 構図指示なしで環境再現 | 構図が元写真と大きく変わる | 最低限 `eye level camera` + `suitable for placing a person` を追加 |
| 環境記述テキストを人手で作成 | 実際の画像と微妙に乖離 | C2-ED で生成画像から自動抽出 |

---

## C3 への引き渡し

C2 の出力として C3 に渡すもの:

1. **環境画像**（C2-R2 or C2-R3 出力）
   - 人物不在、元写真の雰囲気を再現
2. **環境記述テキスト**（C2-ED 出力）
   - 場所・季節・時間帯・照明・雰囲気の記述
   - C3 のプロンプトに組み込んで環境の再現を補助

---

## 検証エビデンス

### Phase C-2: 環境生成検証（2026-03-02）

- **モデル**: `gemini-3-pro-image-preview`（画像生成）、`gemini-3-flash-preview`（テキスト分析）
- **方式**: Python SDK（`google-genai`）、`ImageConfig(aspect_ratio="9:16")`
- **検証パターン**: 3種（C2-R1, C2-R2, C2-R3） + C2-ED
- **入力画像**: env_1.png（ダイビングボート+海）、env_2.png（カートサーキット）
- **生成数**: 6枚（3パターン × 2env）+ 環境記述テキスト2件、**コスト**: $0.28

#### 主要な発見

1. **参照画像を直接渡す1パスが環境再現に最適**: Flash テキスト化を挟むと細部が失われる
2. **C1と同じ傾向 — 単一参照は1パス**: 「同じものを再現」するタスクでは Flash 分析は不要
3. **人物入り写真からの環境抽出は安定**: `"ignore people"` + `"NO people"` の指示で人物除去可能
4. **C2-ED は正確に環境記述を抽出**: ダイビングボート、サーキットという特殊環境でも正確にカバー

- 検証レポート: `poc/seamless/C2_result.md`
- 検証計画: `poc/seamless/C2_plan.md`
- 生成サンプル: `poc/seamless/generated/phase_c2/`
- 実験スクリプト: `poc/seamless/run_phase_c2.py`
- 設定ファイル: `poc/seamless/config_c2.py`
