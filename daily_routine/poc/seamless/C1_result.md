# C-1: キャラクター生成 — 検証結果

## サマリ

| 用途 | 採用パターン | コスト | 結論 |
| --- | --- | --- | --- |
| テキストベース | C1-T | $0.05 | テキストのみで十分な精度 |
| 単一参照（摂動） | C1-R1 | $0.04 | 1パス直接指示が安定 |
| 複数参照（融合） | **C1-F2** | $0.05/clothing | Flash分析が服装詳細の再現に寄与 |
| マルチアングル | **C1-F2-MA** | $0.13/clothing | Flash分析1回 + Pro 3アングルで一貫性確保 |

**最終採用: C1-F2-MA（Flash分析 → マルチアングルPro生成）**

---

## 用途1: テキストベース生成（C1-T）

Flash が model_1.png を分析してキャラクター記述を生成 → Pro がテキストのみで画像生成（参照画像なし）。

- **全身ショット**: OK
- **正面・ニュートラル背景**: OK
- **リアリティ**: 高い（実在の日本人女性に見える）
- **コスト**: $0.05（Flash分析 $0.01 + Pro画像生成 $0.04）

### Flash 生成キャラ記述

> A young adult East Asian female in her early 20s with a slender, petite build. She has an oval face with soft, rounded features and fair, light-toned skin. Her eyes are large and almond-shaped. She has long, straight, chestnut brown hair that falls past her shoulders, styled with thin, wispy bangs that reach her eyebrows.

### 評価

テキストのみでも十分な精度。参照画像なしでも全身・正面・ニュートラル背景の条件を安定して満たす。服装の制御は不可（Pro任せ）。

---

## 用途2: 参照ベース生成（C1-R1 vs C1-R2）

参照画像から「似ているが同一ではない」キャラクターを生成する。服装は評価対象外（Pro任せ）。

### 比較結果

| 評価軸 | C1-R1（直接摂動） | C1-R2（Flash分析→Pro） |
| --- | --- | --- |
| 全身条件 | OK | NG（上半身のみ） |
| 摂動の適切さ | 良好（顔立ち近い） | 過剰（金髪に変化） |
| コスト | $0.04 | $0.05 |
| API コール数 | 1 | 2 |

### C1-R2 Flash 生成記述

> A young adult woman in her early 20s with a fair complexion and an oval face shape. She has large, expressive dark brown eyes and a gentle, friendly smile. Her hair is styled in a shoulder-length wavy bob in a warm honey-blonde shade, with soft, wispy bangs. She is wearing a cozy, oversized lavender knit sweater and light-wash denim jeans.

### 選定結果

**C1-R1 を採用**。コスト面（$0.04 vs $0.05）、精度面（全身条件・摂動の適切さ）の両方で C1-R2 を上回る。C1-R2 は Flash の自由提案が制約なく発散するリスクがある（髪色変更など）。

---

## 用途3: 融合生成（C1-F1 vs C1-F2）

人物画像（model_1.png）+ 服装画像（clothing_1〜4）を融合してキャラクターを生成する。

### C1-F1: 直接融合（1パス）

Pro に人物画像 + 服装画像 + 固定プロンプトを渡して1回で生成。

### C1-F2: Flash分析 → Pro生成（2パス）

Flash が人物画像 + 服装画像を分析してテキスト記述を生成 → Pro がテキスト記述 + 参照画像で生成。

### clothing 別結果

| clothing | 内容 | C1-F1 | C1-F2 |
| --- | --- | --- | --- |
| clothing_1 | カジュアル（キャメルジャケット＋ボーダー＋白スカート＋ブーツ＋バッグ） | 全身OK、全アイテム再現 | 全身OK、スマホ混入 |
| clothing_2 | ダイビング用ドライスーツ（ピンク×黒） | 全身OK、顔やや離れる | 膝上まで |
| clothing_3 | 袴（花柄着物＋グレー袴＋ブーツ＋花飾り） | 全身OK、高精度 | 全身OK、やや斜め |
| clothing_4 | バイクレーシングスーツ（赤×青×黒、HARUKA/DAINESE） | 全身OK、ロゴ再現 | 全身OK、ロゴ再現 |

### 服装再現の精度

両パターンとも非常に高い。特殊な衣装（ドライスーツ、袴、レーシングスーツ）でも正確に取り込める。

### 比較

| 評価軸 | C1-F1 | C1-F2 |
| --- | --- | --- |
| 服装再現度 | 高い | 高い |
| 全身条件の安定性 | やや高い | clothing_2でNG |
| コスト | $0.04 | $0.05 |
| 出力品質の印象 | 良い | **より良い** |

### 選定結果

**C1-F2 を採用**。全体的な出力品質（服装ディテール・顔の自然さ）で C1-F2 が上回った。Flash のテキスト記述が Pro 生成のガイドとなり、特に複雑な服装の細部再現に寄与する。コスト差は $0.01 で許容範囲。

---

## 深掘り: C1-F2-MA（マルチアングル生成）

C3 で様々なポーズ・アングルのシーンを生成するため、正面だけでなく側面・背面の参照画像も必要。C1-F2 をベースにマルチアングル対応を追加した。

### 方式

```
Step 1: Flash が [人物画像] + [服装画像] を分析 → キャラ記述テキスト（1回のみ）
Step 2: Pro が各アングルで画像生成（Flash記述をアンカーとして共有）
  - 正面: "Full body shot from head to feet, standing, facing the camera"
  - 側面: "Full body shot from head to feet, standing, side view (profile)"
  - 背面: "Full body shot from head to feet, standing, back view (seen from behind)"
```

### コスト

- Flash 1回（$0.01）+ Pro 3回（$0.04 × 3）= **$0.13 / clothing**

### 結果（clothing_4: レーシングスーツ）

| アングル | 全身 | 服装再現 | キャラ一貫性 |
| --- | --- | --- | --- |
| 正面 | OK（靴まで） | ロゴ・配色・ニースライダー全て再現 | 三つ編み・顔立ち一致 |
| 側面 | OK（靴まで） | 側面デザイン・DAINESEロゴ再現 | 横顔・体型一致 |
| 背面 | OK（靴まで） | HARUKA/DAINESEロゴ・赤青パネル再現 | 三つ編み・体型一致 |

### 知見

- **Flash記述が3アングル間の一貫性アンカーとして機能**。同一テキスト記述を全アングルで共有することで、顔立ち・体型・服装デザインの統一を担保
- 背面のロゴ配置など元画像にない情報も、Flash記述の「DAINESE」「tricolor palette」から合理的に推測生成
- 全身条件は `"from head to feet"` + `"including shoes must be fully visible with space below the feet"` の明示的指示で安定化

---

## 全体知見

### 1パス vs 2パス（Flash分析→Pro生成）

| 用途 | 1パスの方が良い | 2パスの方が良い |
| --- | --- | --- |
| 単一参照（摂動） | **C1-R1 > C1-R2** | — |
| 複数参照（融合） | — | **C1-F2 > C1-F1** |

- **単一参照**: Flashの自由提案が発散するリスクが高い。参照画像を直接Proに見せる1パスの方が安定
- **複数参照（融合）**: 複数画像の「何をどう組み合わせるか」をFlashが言語化することで、Proの融合精度が向上。テキスト記述がマルチアングル間の一貫性アンカーとしても機能

### 全身条件の安定化

`"Full body shot"` だけでは足元が切れるリスクがある。以下の追加指示で解決:

```
"Full body shot from head to feet, ... The entire body including shoes
must be fully visible with space below the feet."
```

---

## コスト実績

| 検証 | APIコール | コスト |
| --- | --- | --- |
| C1-T, C1-R1, C1-R2 | 5 | $0.14 |
| C1-F1, C1-F2（全4 clothing） | 12 | $0.36 |
| C1-F2-MA（clothing_4, 3アングル）× 2回 | 8 | $0.26 |
| C1-ID（Identity Block + 再現テスト） | 2 | $0.05 |
| **合計** | **27** | **$0.81** |

---

## C3 への引き渡し

C1 の出力として C3 に渡すもの:

1. **キャラクター参照画像セット**（C1-F2-MA 出力）
   - 正面全身（`c1f2ma_{clothing}_front.png`）
   - 側面全身（`c1f2ma_{clothing}_side.png`）
   - 背面全身（`c1f2ma_{clothing}_back.png`）
2. **Identity Block テキスト**（C1-ID 出力 — 生成後の画像を分析した記述）
   - 顔・髪・体型・服装・アクセサリーの詳細記述
   - C1-F2-MA の Flash 記述（生成前の指示）ではなく、生成結果を分析した記述を使用

### C1-ID: Identity Block 自動生成 + 再現テスト

C1-F2-MA の生成結果（正面画像）を Flash で分析し、**生成後の画像に基づく** Identity Block を抽出。別シーンで再現テストを実施。

**重要**: C1-F2-MA の Flash 記述（Step 1）は生成**前**の指示であり、実際に Pro が生成した結果と微妙に異なる可能性がある。C3 で正確に再現するには、**生成後の画像を分析した Identity Block** が必要。

#### 生成された Identity Block

> - **Age/Gender/Ethnicity:** Young adult East Asian female, approximately early 20s.
> - **Build:** Slender, petite, and athletic.
> - **Face Features:** Heart-shaped face, large dark brown eyes, small straight nose, and a calm, neutral expression.
> - **Hair:** Dark brown/black hair with straight forehead bangs and two long, neat braids (pigtails) draped over her shoulders.
> - **Outfit:** A professional one-piece motorcycle racing leather suit in a vibrant blue, red, and black color-block pattern. The suit features "DAINESE" branding on the limbs and the name "HARUKA" printed on the chest. She wears matching heavy-duty black motorcycle racing boots.
> - **Accessories:** She is holding a black full-face motorcycle helmet with red accents and a dark tinted visor tucked under her right arm.

#### 再現テスト結果

入力: 正面画像 + Identity Block + 「カフェに座ってコーヒー」のポーズ指示

- **顔立ち・髪型**: 三つ編み、前髪、顔の特徴が一致
- **服装**: レーシングスーツの配色・ロゴが保持
- **シーン適応**: カフェの環境に自然に溶け込み、ヘルメットはテーブル上に配置
- **コスト**: $0.05（Flash分析 $0.01 + Pro再現 $0.04）

**結論**: 生成後の画像から抽出した Identity Block は、別シーンでの再現に十分機能する。C3 では参照画像 + この Identity Block を組み合わせて使用する。
