# Character Generation（キャラクター生成）

## 推奨手法

- **推奨 API**: Gemini 3 Pro Image (`gemini-3-pro-image-preview`) + Flash (`gemini-3-flash-preview`)
- **方式**: 2パス — Flash 融合分析 → Pro マルチアングル生成（C1-F2-MA）
- **コスト**: $0.13/clothing（Flash 1回 $0.01 + Pro 3アングル $0.04×3）
- **Identity Block 抽出**: 生成後の画像を Flash で分析して $0.01 追加

---

## 用途別の推奨パターン

| 用途 | 推奨パターン | 方式 | コスト |
| --- | --- | --- | --- |
| テキストのみ生成 | C1-T | Flash分析 → Pro生成（参照画像なし） | $0.05 |
| 単一参照（摂動） | C1-R1 | 1パス直接指示 | $0.04 |
| 複数参照（融合） | C1-F2 | Flash分析 → Pro生成 | $0.05 |
| マルチアングル融合 | **C1-F2-MA** | Flash分析1回 → Pro 3アングル | **$0.13** |

**本番パイプラインでは C1-F2-MA を推奨**。C3（シーン生成）に正面・側面・背面の参照画像セットを渡すため。

---

## 1パス vs 2パス（Flash分析→Pro生成）の使い分け

| 用途 | 最適 | 理由 |
| --- | --- | --- |
| 単一参照（摂動） | **1パス** | Flash の自由提案が発散するリスクが高い（髪色変更等） |
| 複数参照（融合） | **2パス** | 複数画像の「何をどう組み合わせるか」を Flash が言語化することで融合精度が向上 |
| マルチアングル | **2パス** | Flash 記述がアングル間の一貫性アンカーとして機能 |

**判断基準**: 入力画像が1枚なら1パス、2枚以上なら2パス（Flash分析）が安定する。

---

## プロンプトテンプレート

### Flash 融合分析（Step 1）

人物画像 + 服装画像を分析し、キャラクター記述テキストを生成する。

```
Analyze all images carefully.
Image 1 shows a person. Image 2 shows an outfit.
Generate a detailed character description that combines:
- Physical features from image 1
- Outfit from image 2
Output only the character description, nothing else.
```

- **temperature=0.0** で決定的出力にする
- 服装以外に髪型・アクセサリーも含まれる場合は `Image 3 shows accessories.` を追加

### Pro マルチアングル生成（Step 2）

Flash 記述 + 参照画像でアングル別に生成する。

```
Image 1 shows the reference person. Image 2 shows the outfit.
Generate a photo of the following character:
[Flash生成記述]
Full body shot from head to feet, standing, [アングル指示], neutral background.
The entire body including shoes must be fully visible with space below the feet.
Single person only, solo.
```

#### アングル指示

| アングル | 指示文 |
| --- | --- |
| 正面 | `facing the camera` |
| 側面 | `side view (profile)` |
| 背面 | `back view (seen from behind)` |

### Identity Block 抽出（生成後）

**生成された画像**を Flash で分析し、C3 用の Identity Block を生成する。

```
Analyze this character and generate a concise identity description
covering: age, gender, ethnicity, build, face features, hair, outfit,
accessories. This will be used to reproduce this exact character
in different scenes. Output only the description.
```

**重要**: 生成**前**の Flash 記述ではなく、生成**後**の画像を分析した Identity Block を使用する。Pro の生成結果は Flash の指示と微妙に異なる可能性があるため。

### 単一参照・摂動生成（C1-R1）

参照画像から「似ているが同一ではない」キャラクターを生成する。

```
Image 1 shows a reference character.
Generate a photo of a SIMILAR but DIFFERENT character.
Keep: face shape, age range, body type, skin tone.
Change: outfit to a different casual style, hairstyle to a slightly different style.
Full body shot from head to feet, standing, neutral background.
The entire body including shoes must be fully visible with space below the feet.
This must be a DIFFERENT person, not the same person in different clothes.
```

---

## 全身条件の安定化

`"Full body shot"` だけでは足元が切れるリスクがある。以下を明示的に追加する:

```
Full body shot from head to feet, standing, [direction], neutral background.
The entire body including shoes must be fully visible with space below the feet.
```

**必須要素**:
- `from head to feet` — 頭からつま先までの範囲を明示
- `including shoes must be fully visible` — 靴の描画を保証
- `with space below the feet` — 足元に余白を確保し切れを防止

---

## Identity Block の設計

### 生成フロー

```
C1-F2-MA で正面画像を生成
    ↓
Flash が正面画像を分析 → Identity Block テキスト
    ↓
C3 で [参照画像] + [Identity Block] + [環境画像] でシーン生成
```

### Identity Block に含める要素

| 要素 | 例 |
| --- | --- |
| 年齢・性別・民族 | Young adult East Asian female, early 20s |
| 体型 | Slender, petite, and athletic |
| 顔の特徴 | Heart-shaped face, large dark brown eyes, small straight nose |
| 髪型 | Dark brown/black hair with straight bangs and two long braids |
| 服装 | Racing leather suit in blue, red, and black with "HARUKA" and "DAINESE" branding |
| アクセサリー | Black full-face motorcycle helmet with red accents |

### Flash 記述（生成前）vs Identity Block（生成後）の違い

| | Flash 記述（Step 1） | Identity Block（C1-ID） |
| --- | --- | --- |
| タイミング | 生成前 | 生成後 |
| 分析対象 | 入力画像（model + clothing） | 生成された画像 |
| 用途 | Pro への生成指示 | C3 での再現指示 |
| 正確性 | 意図ベース | 事実ベース |

---

## 注意点・アンチパターン

| アンチパターン | 症状 | 対策 |
| --- | --- | --- |
| `Full body shot` のみで全身指示 | 足元（靴）が切れる | `from head to feet` + `space below the feet` を追加 |
| 単一参照で Flash 分析を挟む | Flash が髪色・雰囲気を自由に変更し発散 | 1パス直接指示（C1-R1）を使う |
| Flash 記述をそのまま Identity Block に使用 | 生成結果との微妙な乖離が蓄積 | 生成後の画像を分析して Identity Block を抽出 |
| 服装変更を Pro 任せにする | 毎回異なる服装が生成される | 服装画像を入力するか、具体的にテキスト指定 |
| `Full body shot, standing` のみでアングル指示 | 常に正面になる | `side view (profile)` / `back view (seen from behind)` を明示 |
| マルチアングルで Flash 分析を毎回実行 | コスト増、アングル間の記述ブレ | Flash 1回で記述を共有し、アングル指示のみ変更 |

---

## C3 への引き渡し

C1 の出力として C3 に渡すもの:

1. **キャラクター参照画像セット**（C1-F2-MA 出力）
   - 正面全身: `c1f2ma_{clothing}_front.png`
   - 側面全身: `c1f2ma_{clothing}_side.png`
   - 背面全身: `c1f2ma_{clothing}_back.png`
2. **Identity Block テキスト**（C1-ID 出力）
   - 生成後の画像を分析した記述（生成前の Flash 記述ではない）

---

## 検証エビデンス

### Phase C-1: キャラクター生成検証（2026-03-02）

- **モデル**: `gemini-3-pro-image-preview`（画像生成）、`gemini-3-flash-preview`（テキスト分析）
- **方式**: Python SDK（`google-genai`）、`ImageConfig(aspect_ratio="9:16")`
- **検証パターン**: 6種（C1-T, C1-R1, C1-R2, C1-F1, C1-F2, C1-F2-MA） + C1-ID
- **入力画像**: model_1.png（人物参照）、clothing_1〜4.png（服装参照）
- **生成数**: 27枚、**コスト**: $0.81

#### 主要な発見

1. **1パス vs 2パスは用途で最適解が異なる**: 単一参照は1パス、複数参照は2パスが安定
2. **Flash 記述がマルチアングル一貫性のアンカーになる**: 同一テキスト記述を共有することで3アングルの統一を担保
3. **全身条件は明示的指示が必要**: `Full body shot` だけでは不十分、`from head to feet` + `space below the feet` で安定化
4. **Identity Block は生成後の画像から抽出すべき**: 生成前の Flash 記述は意図ベース、生成後の分析は事実ベース
5. **特殊衣装でも高精度に融合可能**: ドライスーツ、袴、レーシングスーツなど特殊な衣装でも正確に取り込める

- 検証レポート: `poc/seamless/C1_result.md`
- 検証計画: `poc/seamless/C1_plan.md`
- 生成サンプル: `poc/seamless/generated/phase_c1/`
- 実験スクリプト: `poc/seamless/run_phase_c1.py`
- 設定ファイル: `poc/seamless/config_c1.py`
