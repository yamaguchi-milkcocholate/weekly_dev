# PoC Step 6: 検討メモ

## 要件の再整理（2026-03-29）

### 最終出力の定義

- 最終出力はAI生成の画像/動画（3Dレンダリングそのものではない）
- ただし、3Dで定義した位置関係（家具配置・壁との距離・カメラアングル）は正確に維持する必要がある
- 3Dは「構造情報を与える手段」であり、最終出力ではない

### 3つの要件

1. **構造の忠実性** — 3Dで定義した空間・配置を崩さない（妥協しない）
2. **スタイルの一貫性** — 複数シーン（複数カメラアングル）で同じ部屋に見える
3. **リアルな質感** — テクスチャ・照明・雰囲気がユーザーのイメージ画像を反映している

### 入出力

```
3Dレンダリング画像（複数カメラアングル分）
    ×
ユーザーのイメージ画像（雰囲気の基準）
    ↓
AI生成（画像 or 動画）
    ↓
全シーンで位置関係が正確 かつ スタイルが統一されている
```

---

## 技術選定方針（2026-03-29）

### 選定基準

大手サービスを中心に選定する。理由：

- ドキュメント・SDKの充実
- 品質の安定性
- 事業の継続性

### 構造維持に関する考え方

- Depth Map等の**明示的な構造制約API**を持つサービスもあれば、持たないサービスもある
- ただし、明示的APIがなくても**モデルが内部的に空間を理解して構造を維持する**能力を持つサービスもある
- 「API対応の有無」だけで判断せず、**実際の出力品質で評価する**

### PoC検証対象サービス

| サービス                   | 提供元  | 主な機能      |   構造制約API    |     スタイル参照      | 一貫性の仕組み         |
| -------------------------- | ------- | ------------- | :--------------: | :-------------------: | ---------------------- |
| **Runway gen4_image**      | Runway  | 画像/動画生成 | なし（内部理解） | References（最大3枚） | References機能で高い   |
| **LUMA Photon**            | Luma AI | 画像/動画生成 | なし（内部理解） | style_ref（最大4枚）  | character_ref          |
| **Gemini 3.1 Flash Image** | Google  | 画像生成      | なし（内部理解） |  プロンプト+参照画像  | 会話コンテキストで維持 |

### 各サービスのAPI・コスト概要

**Runway**（1 credit = $0.01）

- API: REST + Python/Node.js SDK
- 画像:
  - gen4_image: 5〜8 credits/枚（$0.05〜0.08）解像度別
  - gen4_image_turbo: 2 credits/枚（$0.02）
- 動画:
  - gen4_turbo: 5 credits/秒（$0.50/10秒）
  - gen4.5: 12 credits/秒（$1.20/10秒）
  - gen4_aleph: 15 credits/秒（$1.50/10秒）※動画→動画対応
  - act_two: 5 credits/秒（$0.50/10秒）※キャラクター特化
- 強み: References機能によるマルチショット一貫性

**LUMA**

- API: REST + Python/Node.js SDK
- 画像:
  - Photon 1080p: ~$0.015/枚
  - Photon Flash 1080p: ~$0.004/枚
- 動画（5秒、16:9）:
  - Ray 2 540p: $0.40 / 720p: $0.71 / 1080p: $0.86
  - Ray Flash 2 540p: $0.14 / 720p: $0.24 / 1080p: $0.39
- 動画修正（Modify）: Ray 2は通常の約2.5倍、Ray Flash 2は同比率
- アップスケール: $0.06〜0.11/秒
- 強み: style_ref（最大4枚、weight指定）による明示的スタイル制御

**Gemini（Google）**

- API: Google AI Studio / Vertex AI経由
- 画像（Gemini 3.1 Flash Image）:
  - 0.5K: $0.045/枚、1K: $0.067/枚、2K: $0.101/枚、4K: $0.151/枚
- 動画: 非対応（動画はVeoが別系統）
- 強み: マルチモーダル理解力が高い。参照画像+テキスト指示による対話的な画像編集が可能。Googleの事業基盤
- 備考: ControlNet的な明示的構造制御はないが、画像入力からの構造理解はモデルの理解力に依存。GPT Image（OpenAI）と同系統のアプローチ

### 除外したサービス・方向性

- **Google Veo** — 構造制約・スタイル参照・マルチショット一貫性のいずれも未対応。コストも高い
- **Kling** — 一旦保留。Element Binding等の一貫性機能は有望だが、優先度を下げる
- **3Dメッシュへのテクスチャ生成** — 目的は3D空間の忠実再現ではないため不適合
- **インテリア特化AI（RoomGPT等）** — API統合・細かい制御が困難

---

## 実装メモ

### APIクライアント

Runway・LUMAについては `poc/video_ai/clients/` に既存のAPIクライアント実装がある（動画生成AI比較検証PoCで使用）。
ファイルをそのまま流用するのではなく、書き方を参考にしてStep 6用に新しくクライアントを作成する。

- Runway参考: `poc/video_ai/clients/runway.py`
- LUMA参考: `poc/video_ai/clients/luma.py`
- Gemini参考: `poc/image_gen/clients/gemini.py`（langchain-google-genai経由、gemini-3-pro-image-preview）
- 共通インターフェース参考: `poc/video_ai/clients/base.py`

---

## PoC検証計画

### Phase 1: 同一入力での比較検証

3Dレンダリング画像（テクスチャなし）+ イメージ画像を各サービスに入力し、以下を比較：

1. **構造維持**: 家具の位置・壁との距離が崩れていないか
2. **スタイル反映**: イメージ画像の雰囲気が反映されているか
3. **生成品質**: リアルさ・自然さ

### Phase 2: マルチショット一貫性の検証

Phase 1で有望なサービスについて、複数カメラアングルの画像を生成し一貫性を検証。

### Phase 3: 動画生成の検証

カメラパスに沿った動画生成の品質・一貫性を検証。

---

## 検証ログ（2026-03-29）

### 実験1: カメラ4 × 3社比較（2画像入力: レンダリング画像 + スタイル参照画像）

| サービス | 構造維持 | スタイル反映 | リアルさ | 生成時間 | コスト |
|---------|---------|------------|---------|---------|-------|
| Gemini 3.1 Flash Image | 低（階段・窓を追加） | 高 | 高 | 27.8秒 | $0.067 |
| Runway gen4_image | 中（ゴルフバッグが衣類ラックに変化） | 高 | 高 | 20.7秒 | $0.05 |
| LUMA Photon | 中〜高（壁構造は維持、家具配置もよい） | 高 | 最も写実的 | 34.3秒 | $0.015 |

**問題**: 3社ともスタイル参照画像の構造的要素（階段、窓など）を取り込んでしまい、元のレンダリングの空間構造が崩れる。

### 実験2: スタイルをテキストで与える方式（Gemini）

**仮説**: スタイル参照画像を入れると、AIがその画像の構造的要素も取り込んでしまう。テキストでスタイルを指示すれば、入力画像の構造維持に集中できるのではないか。

**方法**: レンダリング画像1枚のみを入力し、スタイルはテキストプロンプトで記述。

スタイルテキスト例:
> Bright, airy natural interior with warm wood tones (oak/birch), soft natural daylight, linen/cotton textures, beige/cream/warm white palette, indoor green plants, Scandinavian-inspired minimalist aesthetic, pendant lighting with warm tone, light hardwood flooring, woven area rug

**結果（カメラ4）**: 構造維持が大幅に改善。壁の形状・家具配置がほぼ忠実に維持された。不要な建築要素（階段・窓）の追加がなくなった。

**結果（カメラ6・俯瞰）**: 俯瞰でも間取り形状・家具配置がよく維持された。窓が若干追加されるが、2画像入力時ほどの構造変更はない。

### 知見: スタイル指定方式による構造維持への影響

| 方式 | 構造維持 | スタイル精度 | 備考 |
|------|:-------:|:----------:|------|
| 2画像入力（レンダリング + スタイル画像） | 低〜中 | 高（画像から直接転写） | スタイル画像の構造要素を取り込んでしまう |
| 1画像入力 + テキストスタイル | **高** | 中（テキスト記述に依存） | 構造維持に大幅改善。スタイルの再現精度はテキストの質に依存 |

**結論**: 構造維持を最優先する場合、**スタイルはテキストで与える方式が有効**。スタイル参照画像はテキスト化の参考として使い、直接AIに渡さない。

### 実験3: テキストスタイル方式 × 3社比較（6カメラ全実行）

北欧ナチュラルスタイルをテキストで記述し、レンダリング画像1枚のみ入力で3社を比較。

| サービス | 構造維持 | 評価 |
|---------|:-------:|------|
| **Gemini 3.1 Flash Image** | **高** | 壁の位置・家具配置・カメラアングルがほぼ忠実。不要な要素の追加も少ない |
| Runway gen4_image | **低** | 家具が消える・別のものに変わる。カメラ6は間取りが完全に別物 |
| LUMA Photon | **低** | 家具の左右入れ替え、間取りの変形が発生。構造維持と呼べるレベルではない |

**結論: 構造維持においてGeminiが圧倒的に優位。Runway・LUMAはテキストスタイル方式でも構造が崩壊する。**

### 実験4: Gemini × 4スタイル比較（テキストスタイル方式）

Geminiでスタイルを変えても構造維持が安定するかを検証。

| スタイル | 参考画像 | カメラ | 構造維持 |
|---------|---------|--------|:-------:|
| 北欧ナチュラル | style_ref.png | 1〜6全カメラ | 高 |
| インダストリアル | style_ref1.png | 4, 6 | 高 |
| ダークラグジュアリー | style_ref2.png | 4, 6 | 高 |
| ヴィンテージカフェ | style_ref3.png | 1〜6全カメラ | 高 |

**結論: Geminiはスタイルを大きく変えても構造維持の品質が安定している。**

---

## Step 6 暫定結論（2026-03-29）

### 採用方式

**Gemini 3.1 Flash Image + テキストスタイル方式**

```
スタイル参照画像（ユーザー提供）
    ↓
LLMでテキスト記述に変換（色調・素材・照明・雰囲気）
    ↓
3Dレンダリング画像（1枚）+ テキストスタイルプロンプト
    ↓
Gemini 3.1 Flash Image で生成
    ↓
構造が忠実 × スタイルが反映された画像
```

### 選定理由

- **構造維持**: 3社中唯一、壁・家具配置・カメラアングルを忠実に維持できた
- **スタイル柔軟性**: テキスト記述を変えるだけで多様なスタイルに対応（4スタイルで検証済み）
- **コスト**: $0.067/枚（1K解像度）
- **速度**: 約20秒/枚
- **API統合**: httpx直接REST APIで簡潔に実装可能

### 残課題

- **画像ベースのスタイル取り込み**: テキストのみではstyle_refの詳細なイメージ（具体的な素材感・色の微妙なニュアンス・照明の質感等）を忠実に移すことができない。画像ベースでスタイルを取り込みつつ構造を崩さない方法の検証が必要
- スタイル参照画像からテキスト記述への自動変換パイプライン
- マルチショット一貫性の定量評価（目視では良好だが、カメラ間でレンガ色味等に微差あり）
- 解像度向上（現在960x540入力 → 高解像度入力での検証）

---

## 調査: Geminiにおける構造維持+スタイル転写のベストプラクティス（2026-03-30）

### 調査背景

テキストスタイル方式は構造維持に優れるが、スタイル参照画像の詳細なニュアンスを忠実に再現できない。Geminiに2画像（構造+スタイル）を入力しつつ構造を崩さない方法を調査。

### 前回の2画像入力で構造が崩れた原因（推定）

- プロンプトで「何を維持するか」を十分に明示していなかった
- スタイル画像の構造的要素（階段・窓等）を取り込まないよう指示していなかった
- スタイル画像とレンダリング画像の役割分離が不明確だった

### Google公式の推奨事項

出典: Google Developers Blog, Google DeepMind Prompt Guide, Google Cloud Blog

1. **各画像の役割をプロンプトで明示する**: `image 1`, `image 2` のインデックスで参照し、各画像から何を取り出すべきかを具体的に記述
2. **「何を維持するか」を先に、「何を変えるか」を後に記述**: 構造保持の指示をスタイル変更の指示より先に配置
3. **スコープを極めて狭く具体的に指定**: `"Restyle only the jacket fabric to denim; keep face, lighting, and background untouched."` のように変更箇所を限定
4. **スタイルを具体的なトークンで固定**: medium（画材）, palette（色彩）, texture（質感）, lighting（照明）等に分解して指示
5. **キーワード羅列ではなく文章で記述**: 説明的な文章の方が一貫性のある出力が得られる
6. **画像を先、テキストを後に配置**: `[img1, img2, "prompt"]` の順で contents 配列を構成
7. **アスペクト比を明示的に制御**: 最後の画像のアスペクト比が採用される仕様。`ImageConfig` で明示指定が安全

### GPT Image / OpenAI Cookbookからの知見（Geminiにも適用可能）

出典: OpenAI Cookbook gpt-image-1.5 Prompting Guide

1. **不変条件リストの明示**: `Do NOT change: composition, subject placement, proportions, spatial layout` / `ONLY change: color palette, texture, artistic style`
2. **geometry lock の明示**: `Preserve the car's geometry, change only the texture.` のように構造のロックを明示
3. **JSON Style Guideによる構造化**: スタイルをJSONオブジェクトで定義し、コンテンツ指示と分離。曖昧さの排除と一貫性確保に有効

### 構造維持+スタイル転写の推奨プロンプト構造

```
[Image 1: レンダリング画像]
[Image 2: スタイル参照画像]

Image 1 is an untextured 3D render showing the spatial layout of an interior room.
Image 2 is a style reference showing the desired atmosphere, materials, and textures.

PRESERVE from Image 1 (do NOT change):
- Exact wall positions, room shape, and floor plan
- All furniture positions and relative placement
- Camera angle and perspective
- Room proportions and spatial relationships

APPLY from Image 2 (style elements ONLY):
- Color palette and color temperature
- Material textures (wall finish, floor material, fabric textures)
- Lighting mood and atmosphere
- Decorative style and aesthetic

Do NOT transfer from Image 2:
- Architectural elements (windows, doors, stairs, columns)
- Furniture types or arrangements
- Room shape or proportions
- Any structural elements

Generate a photorealistic interior photograph that looks like Image 1's room
decorated in Image 2's style.
```

### 補足テクニック

- **3ステップ・スタイル複製ワークフロー**: (1) Geminiでスタイル参照画像を分析→視覚特徴をJSON形式で構造化抽出 (2) 抽出データをプロンプトに組み込み (3) 構造画像+強化プロンプトで生成。テキストスタイル方式の精度向上版
- **反復ターンでの不変条件再宣言**: マルチターンで調整する場合、毎回保持すべき要素を再度明示（ドリフト防止）
- **スタイル強度の言語的制御**: `"subtle"`, `"light touch"`, `"strong"` 等で転写強度を調整

### 実験5: 2画像入力+強化プロンプト × モデル比較（カメラ4 × 4スタイル）

調査で得たベストプラクティスを適用した強化プロンプト（PRESERVE/APPLY/Do NOT transfer構造）で検証。

**Gemini 3.1 Flash Image:**

| スタイル | 構造維持 | 備考 |
|---------|:-------:|------|
| 北欧ナチュラル（style_ref） | 低 | 階段を追加。スタイル画像の構造要素を取り込む |
| インダストリアル（style_ref1） | 中 | 窓を追加 |
| ダークラグジュアリー（style_ref2） | 高 | 壁・家具配置が忠実 |
| ヴィンテージカフェ（style_ref3） | 高 | 壁構造・家具配置が忠実 |

**Gemini 3.0 Pro Image:**

| スタイル | 構造維持 | 備考 |
|---------|:-------:|------|
| 北欧ナチュラル（style_ref） | **低** | 階段は消えたが、**中央の壁が消失し奥に空間が発生**。構造崩壊 |
| インダストリアル（style_ref1） | 高 | コンクリート壁・家具配置が忠実 |
| ダークラグジュアリー（style_ref2） | **高** | 壁の凹凸・テーブル・衣類ラックが忠実。最も良い結果 |
| ヴィンテージカフェ（style_ref3） | **低** | ヘリンボーン床は良いが、**中央の壁が消失し奥行きが発生**。構造崩壊 |

### 知見: 2画像入力の根本的限界

- 強化プロンプトでもモデル変更でも、**スタイル画像の内容によって構造維持がばらつく**
- 明るく開放的なスタイル画像（style_ref, style_ref3）→ モデルが「開放感」という空間的性質もスタイルとして取り込み、壁を消す
- ダーク・閉鎖的なスタイル画像（style_ref2）→ 閉鎖的な空間が自然なため壁が維持される
- これはプロンプトの問題ではなく、**モデルが「スタイル」と「空間構造」を内部で完全に分離できない**という根本的な限界
- プロンプト改善で多少の改善はあり得るが、スタイル画像に依存する不安定さは排除できない

### 最終結論: テキストスタイル方式を採用

2画像入力方式はスタイル参照画像の空間的性質を取り込んでしまい、構造維持が不安定。
**テキストスタイル方式がStep 6の採用方式として確定。**

---

## 採用パイプライン（確定・2026-03-30）

```
スタイル参照画像（ユーザー提供）
    ↓
Claude Codeがスタイルをテキスト記述に変換（スキルとして定義）
    ↓
テキスト + レンダリング画像パスを引数にPythonスクリプト実行
    ↓
Gemini 3.1 Flash Image（1画像入力 + テキストスタイル）で生成
    ↓
構造が忠実 × スタイルが反映された画像
```

### 方式の詳細

- **スタイルテキスト化**: Claude Codeのマルチモーダル能力でstyle_ref画像を分析し、色調・素材・照明・雰囲気をテキストに変換。4スタイルで実績あり。Claude Codeのスキルとして定義し、再利用可能にする
- **画像生成**: Pythonスクリプトがテキストとレンダリング画像パスを受け取り、Gemini APIで生成。`uv run python poc/3dcg_poc6/run_experiment.py` で実行
- **モデル**: Gemini 3.1 Flash Image（$0.067/枚）。構造維持の安定性を確認済み
- **プロンプト**: テキストスタイル方式で検証済みの構造維持プロンプト（CRITICAL RULES + Style to apply）

### 残課題

- 解像度向上（現在960x540入力 → 高解像度入力での検証）

---

## 実験6: Gemini 3.0 Pro Image × テキストスタイル方式（6カメラ全実行・2026-03-30）

### 背景

スキル `3dcg-style-apply` を作成し、テキストスタイル方式のパイプラインを実装。style_ref.png（北欧ナチュラル）で6カメラ全実行。

### モデル

Gemini 3.0 Pro Image（`gemini-3-pro-image-preview`）。Flash Imageよりも高品質。

### 実行1: 初回プロンプト

**プロンプト**: 従来の CRITICAL RULES + Style to apply 構造

**スタイルテキスト**:
> Bright, airy Scandinavian-inspired interior with warm natural tones. White-painted smooth walls with soft warm undertones. Light natural oak hardwood flooring with subtle grain. Warm, diffused natural lighting creating soft shadows throughout the space. Simple wooden furniture in light oak and birch tones. A large indoor tree as a green focal point. Geometric patterned area rug in muted earth tones. Sheer linen curtains in neutral cream. Minimal decorative elements with natural materials. Overall warm, inviting atmosphere with clean and uncluttered feel.

**結果**:

| 指標 | スコア |
|------|--------|
| 構造維持 | 91.8 |
| スタイル反映 | 96.7 |
| 生成品質 | 95.5 |
| 加重平均 | 94.4 |
| 一貫性（総合） | 88 |

**問題点**:
1. **椅子の不一致**: カメラによって黒メッシュチェア、木製チェアなどデザインがバラバラ
2. **余計なオブジェクト追加**: カーテン、棚、バスケット、追加の植物など、元レンダリングにないものが出現
3. カメラ1の構造維持が75と低い（廊下奥に窓・カーテンが追加）

### 実行2: プロンプト強化 + スタイルテキスト修正

**変更1 — プロンプト強化**: 5つの明確なルール（STRICT RULES）を導入
- OBJECT FIDELITY: 全オブジェクトを同一位置・サイズ・形状で維持
- NO ADDITIONS: 元レンダリングにないオブジェクトの追加を禁止
- SPATIAL LOCK: 壁・部屋形状・カメラアングルをピクセル正確に維持
- CONSISTENT IDENTITY: 同一オブジェクトは全カメラで同じ外観
- TEXTURE ONLY: テクスチャ・マテリアル・照明の適用のみ（"re-skinning"）

**変更2 — スタイルテキスト修正**: オブジェクト追加を誘発する単語を除去
- 除去: "A large indoor tree", "area rug", "curtains" 等
- 残す: 素材・色・照明・雰囲気の記述のみ

修正後スタイルテキスト:
> Bright, airy Scandinavian-inspired interior with warm natural tones. White-painted smooth walls with soft warm undertones. Light natural oak hardwood flooring with subtle grain. Warm, diffused natural lighting creating soft shadows throughout the space. Light oak and birch wood tones on furniture surfaces. Matte black finish on metal and mesh elements. Soft neutral color grading with warm highlights. Clean, uncluttered atmosphere.

**結果（6カメラ全実行）**:

| 指標 | 実行1 | 実行2 | 変化 |
|------|-------|-------|------|
| 構造維持 | 91.8 | **97.8** | +6.0 |
| スタイル反映 | 96.7 | 95.8 | -0.9 |
| 生成品質 | 95.5 | **96.8** | +1.3 |
| 加重平均 | 94.4 | **96.8** | +2.4 |
| 一貫性（総合） | 88 | **90** | +2 |

**改善点**:
1. 椅子が全カメラで黒メッシュオフィスチェアに統一された
2. 余計なオブジェクト（カーテン・植物・棚）の追加がほぼ解消
3. カメラ1の構造維持が75→98に大幅改善
4. カメラ4は構造維持100（完全一致）

### 知見: プロンプトとスタイルテキストの設計原則

1. **プロンプトは「禁止」を明確に**: 「〜するな」を具体的に列挙する方が「〜せよ」より効果的
2. **スタイルテキストにオブジェクト名を書かない**: "plant", "rug", "curtain" 等のオブジェクト名はGeminiにそれらを追加させてしまう。素材・色・照明・雰囲気の記述に限定する
3. **"re-skinning"メタファー**: テクスチャ適用であることを比喩で明示すると、モデルの行動が制約される
4. **CONSISTENT IDENTITY**: オブジェクトの外観一貫性を明示的に指示することで、カメラ間のバラつきが減る
