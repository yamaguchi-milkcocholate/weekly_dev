# C-2: 環境生成 — 検証結果

## サマリ

| 用途 | 採用パターン | コスト | 結論 |
| --- | --- | --- | --- |
| 参照写真→環境再現 | **C2-R2** | $0.04 | 参照画像を直接Proに渡す1パスが最も忠実 |
| 環境のテキスト修正 | **C2-R2-MOD** | $0.04 | C2-R2 + テキスト修正指示で別アングル・雰囲気変更・オブジェクト追加が可能 |
| 環境記述テキスト抽出 | C2-ED | $0.01 | 生成画像から正確に自動抽出 |

**最終採用: C2-R2 を基本、テキスト修正指示で柔軟にバリエーション生成**

---

## タスク定義

参照写真（人物入り）から**環境の雰囲気を取り出し**、人物不在・C3人物配置向きの環境画像を生成する。

### 入力

| 入力 | 例 |
| --- | --- |
| env_1.png | ダイビングボート上の写真（人物2名） |
| env_2.png | カートサーキットの写真（人物1名） |

### 出力

| 出力 | 仕様 | 用途 |
| --- | --- | --- |
| 環境画像 | 人物不在、元写真の雰囲気を再現 | C3の参照画像 |
| 環境記述テキスト | 場所・天候・照明・雰囲気の記述 | C3のプロンプト |

---

## 比較結果: C2-R1 vs C2-R2 vs C2-R3

### env_1（ダイビングボート + 海）

| 評価軸 | C2-R1（Flash→テキスト） | C2-R2（直接編集型） | C2-R3（構図テンプレート） |
| --- | --- | --- | --- |
| 雰囲気再現 | ボート+海+島、良好 | ボート+ターコイズ海、**忠実** | ボート+ターコイズ海、**忠実** |
| 人物除去 | OK | OK | OK |
| 人物配置適性 | 甲板広い、やや広角すぎ | デッキ中央にスペース、良好 | デッキ中央にスペース、良好 |
| 元写真との近さ | やや遠い（広角ボート船首） | **近い**（屋根付き後部デッキ） | **近い**（屋根付き後部デッキ） |
| コスト | $0.05 | **$0.04** | **$0.04** |

### env_2（カートサーキット）

| 評価軸 | C2-R1（Flash→テキスト） | C2-R2（直接編集型） | C2-R3（構図テンプレート） |
| --- | --- | --- | --- |
| 雰囲気再現 | フェンス+バリア+管制塔+森、良好 | フェンス+バリア+旗+森、**忠実** | フェンス+バリア+管制塔+森、**最も忠実** |
| 人物除去 | OK | OK | OK |
| 人物配置適性 | 手前アスファルト、可 | 手前アスファルト、可 | **手前アスファルト広め** |
| 元写真との近さ | やや遠い（きれいすぎる） | **近い** | **最も近い** |
| コスト | $0.05 | **$0.04** | **$0.04** |

### C2-R1 Flash 生成記述

**env_1:**
> A realistic wide-angle photograph of the clean, white deck of a dive boat on a bright, sunny day. The foreground features a flat, white surface with a subtle texture, leading the eye toward a vast, calm, deep blue tropical ocean that stretches to a clear horizon. In the far distance on the left, a small tropical island with palm trees and faint resort structures is visible. ...

**env_2:**
> A wide-angle, eye-level shot of an empty outdoor racing circuit on a bright, clear day. In the foreground, a white metal horizontal railing fence separates a paved asphalt area from the track. The track itself is lined with vibrant red interlocking plastic safety barriers and stacks of tires in black, blue, and yellow. ...

### 選定結果

**C2-R2 / C2-R3 を採用**。参照画像を直接 Pro に渡すことで環境の忠実な再現が可能。C2-R1 はテキスト化の過程で細部が失われる。

- **C2-R2**: 「この写真の環境を人物なしで再現して」というシンプルな指示。最もコスト効率が良い
- **C2-R3**: 構図要件（カメラ角度、前景スペース等）を分離指示。人物配置用の構図をより明確に制御したい場合に有効
- **C2-R1**: 環境分析テキストは高品質だが、テキストのみでの再現は細部（構造物の配置、色合い）が元写真から乖離する

**判断基準**: 基本は C2-R2 で十分。構図の制御が重要な場面（全身 vs バストアップ等）では C2-R3 を使用。

---

## 後続: 環境記述テキスト自動生成（C2-ED）

生成した環境画像から C3 用の環境記述テキストを Flash で自動抽出。

### env_1（ダイビングボート）の環境記述

> Tropical marine environment viewed from the stern of a white boat during a bright summer midday. The lighting is harsh and direct, casting sharp shadows on the clean white deck. The color palette is a vibrant mix of brilliant whites, turquoise, and deep cerulean blues against a pale sky. The atmosphere is serene and expansive, featuring clear, layered tropical waters leading to a small, distant palm-fringed island on a flat horizon under scattered light clouds.

### env_2（カートサーキット）の環境記述

> This outdoor go-kart racing circuit is set against a backdrop of a lush, densely forested hillside, suggesting a summer season. The scene is captured during midday under diffuse, natural lighting from a bright but overcast sky filled with soft white and grey clouds. The color palette is characterized by the neutral grey of the asphalt track and the deep greens of the background forest, punctuated by vibrant pops of bright red from long rows of interlocking plastic safety barriers and occasional blue tarps. A white metal post-and-rail fence runs through the foreground. Key features include the winding asphalt track, tire-wall buffers, a small elevated white control booth, and the towering wall of trees. The atmosphere is calm and expectant, typical of a track during a lull in activity.

### 評価

両方とも以下の要素を正確にカバー:
- 場所の種類（tropical marine / go-kart circuit）
- 季節・時間帯（summer midday）
- 照明条件（harsh direct / diffuse natural）
- 色彩パレット（whites + turquoise + blue / grey + green + red）
- 雰囲気（serene, expansive / calm, expectant）
- 構造的特徴（white deck, island / asphalt, barriers, control booth）

---

## 全体知見

### 環境再現では参照画像の直接入力が有効

| 方式 | 環境の忠実さ | コスト |
| --- | --- | --- |
| C2-R1（Flash→テキスト→Pro） | 雰囲気は合うが細部が異なる | $0.05 |
| **C2-R2（参照画像→Pro）** | **忠実** | **$0.04** |
| **C2-R3（参照画像+構図→Pro）** | **忠実+構図制御** | **$0.04** |

C1（キャラクター生成）の「単一参照は1パスが安定」という知見と完全に一致。環境再現でも参照画像を直接 Pro に見せる方が忠実。

### C1との比較: 1パス vs 2パスの使い分け

| タスク | 入力 | 最適 |
| --- | --- | --- |
| C1: 単一参照キャラ | 人物画像1枚 | **1パス** |
| C1: 融合キャラ | 人物+服装 2枚以上 | **2パス（Flash分析）** |
| C2: 環境再現 | 環境写真1枚 | **1パス** |

**一般化**: 参照画像が1枚で「同じものを再現」するタスクは1パス直接指示が最適。Flash を挟むとテキスト化の過程で情報が落ちる。

### 人物入り参照写真の扱い

元写真に人物が含まれていても、「環境のみを再現」「人物を除去」の指示で問題なく対応できた。明示的な指示のポイント:

- `"Focus on the ENVIRONMENT only, ignore people"` — 人物を無視して環境に注目
- `"Recreate ONLY the environment/location, removing all people completely"` — 環境のみ再現
- `"The scene must have NO people, no persons, completely empty"` — 人物不在の強調

---

## テキスト修正指示による環境バリエーション（C2-R2-MOD）

C2-R2 のプロンプトに追加のテキスト指示を付与し、環境のバリエーションを生成する検証。

### 検証パターン

| 修正タイプ | env_1 の指示例 | env_2 の指示例 |
| --- | --- | --- |
| 別アングル | 水面からのローアングルで船を見上げる | トラック上のローアングル、ストレートを見渡す |
| 雰囲気変更 | サンセット（オレンジ〜ピンクの空） | 雨天（濡れたアスファルト、暗い雲） |
| オブジェクト追加 | 背景に別のダイブボート + デッキ上にダイビング機材 | バイクレース中 + 観客席 + スポンサーバナー + 大型タイミングタワー |

### 結果

| 修正タイプ | env_1（ダイビングボート） | env_2（サーキット） |
| --- | --- | --- |
| **別アングル** | OK — 水面視点、ボート+島+海の雰囲気保持 | OK — トラック上ローアングル、バリア+森+管制塔保持 |
| **雰囲気変更** | OK — サンセット空、環境構造保持、ダイビングタンクも配置 | OK — 雨天、濡れたアスファルト+水たまり、同じレイアウト |
| **オブジェクト追加** | OK — 別ボート追加、BCD+タンク+フィン整列 | **優秀** — 大型プロサーキットに変換、バイク+観客席+バナー(HONDA, MOTUL等) |

### 知見

- **3種類の修正全てが安定して機能**: 参照画像の環境を基盤に、テキスト指示で柔軟に修正可能
- **雰囲気変更が特に安定**: 環境構造を保持したまま天候・照明のみ変更できる
- **オブジェクト追加はスケール変更も可能**: 小さなカートコース → 本格プロサーキットのような大幅な拡張もテキスト指示で対応
- **C2-F1/F2（複数画像融合）は不要**: テキスト指示だけで十分なバリエーションを得られる

### プロンプト構造

C2-R2 のベースプロンプトの末尾に修正指示を追加する形式:

```
[C2-R2 ベースプロンプト]
+ [修正指示]
```

修正指示の例:
- アングル: `"Change the camera angle to a LOW ANGLE shot from ..."`
- 雰囲気: `"Change the atmosphere to SUNSET. Warm orange and pink sky ..."`
- オブジェクト: `"Add additional elements: ... Keep the same ... setting."`

---

## コスト実績

| 検証 | APIコール | コスト |
| --- | --- | --- |
| C2-R1 × 2env（Flash分析 + Pro生成） | 4 | $0.10 |
| C2-R2 × 2env（Pro生成） | 2 | $0.08 |
| C2-R3 × 2env（Pro生成） | 2 | $0.08 |
| C2-R2-MOD × 6（修正バリエーション） | 6 | $0.24 |
| C2-ED × 2env（Flash分析） | 2 | $0.02 |
| **合計** | **16** | **$0.52** |

---

## C3 への引き渡し

C2 の出力として C3 に渡すもの:

1. **環境画像**（C2-R2 / C2-R2-MOD 出力）
   - 人物不在、元写真の雰囲気を再現（またはテキスト指示で修正）
   - `c2r2_{env_name}.png` / `c2r2mod_{env_name}_{mod_type}.png`

**注意**: C2-ED（環境記述テキスト）は C3-I1 では使用しない。C3 PoC（C3_result.md）により、環境記述テキストを Flash に渡すとプロンプト肥大化で逆効果となることが確認された。C3-T（テキスト環境型 fallback）使用時のみオンデマンドで生成する。
