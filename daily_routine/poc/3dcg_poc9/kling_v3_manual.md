# Kling V3 Omni V2V 活用マニュアル

作成日: 2026-04-01

## 概要

Kling V3 Omni（Kling 3.0 Omni）はKling AIのフラッグシップモデル。V2V（Video-to-Video）を含む最も多機能なモデルで、公式APIから最新モデルを直接呼び出せる。

PoC 9の検証で、Blenderウォークスルー動画 → フォトリアルインテリア動画への変換において、Luma ray-2 / Runway gen4_aleph を上回る結果を確認。

## V3 Omniの主な機能

- Text-to-Video (T2V): テキストから動画生成
- Image-to-Video (I2V): 画像から動画生成
- Video-to-Video (V2V): 既存動画をプロンプトで変換（モーション・構図を保持）
- Reference-to-Video (Ref2V): 参照動画からキャラクターの外見・声を抽出して新シーンに適用
- ネイティブ音声生成: 日本語含む5言語対応、リップシンク付き
- マルチショット: ショットごとにカメラワーク・構図を指定可能
- 最大1080p / 3〜15秒

## V2Vの2つのモード

`video_reference_type` パラメータで切り替え。

| モード | 説明 | 用途 |
|--------|------|------|
| `base` | 元動画のモーション・構図を完全維持してリスタイル | **3D→フォトリアル変換に使う** |
| `feature` | 元動画からスタイル・カメラワークを抽出して新コンテンツに適用 | スタイル転用向け |

## Reference画像の利用

V2Vモードでスタイル参照画像を渡せる（最大4枚、video併用時）。

| パラメータ | 用途 |
|-----------|------|
| `image_url` | 開始フレーム / スタイルアンカー画像（1枚） |
| `reference_images` | 複数参照画像（最大4枚、video併用時） |
| プロンプト内 `@Image1` | 参照画像をプロンプトで明示的に参照 |
| プロンプト内 `@Video1` | 入力動画をプロンプトで参照 |

→ PoC 8で生成したスタイル適用済み画像をreferenceとして渡すことで、テイストの一貫性を改善できる。

## 主要APIパラメータ

### V2V生成

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|----------|------|
| `video_url` | string (URI) | — | 入力動画（3-10秒、720-2160px、max 200MB、mp4/mov/webm） |
| `prompt` | string | — | 最大2500文字。`@Video1` `@Image1` で参照可能 |
| `image_url` | string (URI) | — | 開始フレーム / スタイル参照画像（min 300x300px、max 10MB） |
| `reference_images` | array | — | 追加参照画像（最大4枚） |
| `video_reference_type` | enum | — | `base`（モーション維持）/ `feature`（スタイル抽出） |
| `cfg_scale` | float | 0.5 | 0=最大の創造的自由、1=プロンプトに厳密に従う |
| `negative_prompt` | string | — | 除外要素。最大2500文字 |
| `duration` | string | '5' | 出力秒数（'3'〜'15'） |
| `aspect_ratio` | string | '16:9' | `auto`, `16:9`, `9:16`, `1:1` |
| `multi_prompt` | JSON array | — | マルチショット（最大6ショット、各3秒以上） |

### 動画延長（Extend）

`POST /v1/videos/extend`

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|----------|------|
| `task_id` | string | — | 延長元の完了済みタスクID（必須） |
| `prompt` | string | — | 延長部分のガイダンス。最大2500文字 |
| `negative_prompt` | string | — | 最大2500文字 |
| `cfg_scale` | float | 0.5 | 0-1 |
| `enable_audio` | boolean | false | 効果音生成の有無 |

1回の延長で5秒追加。最大3分までチェーン可能。

## 長尺動画の一貫性維持

### 方法A: Video Extend API

```
V2Vで5秒生成 → Extend APIで5秒追加 → さらに5秒追加 → ...
```

- 前回の`task_id`を渡すだけで、最後のフレームから自動で続きを生成
- 最大3分までチェーン可能
- 一貫性の劣化目安:
  - 0-30秒: 安定
  - 30-60秒: 微妙なドリフト開始（照明シフト、背景ディテール変化）
  - 60-120秒: 顕著な劣化
  - 120-180秒: 予測困難

### 方法B: Multi-Shot生成

1回のAPIコールで最大6ショット（各3秒以上、合計最大15秒）を生成。

```json
"multi_prompt": [
  {"prompt": "Camera enters corridor, photorealistic interior...", "duration": 5},
  {"prompt": "Camera reaches desk area, warm wood textures...", "duration": 5},
  {"prompt": "Camera turns to reveal bedroom...", "duration": 5}
]
```

ショット間のトランジションはモデルが自然に処理する。

### 方法C: セグメント分割 + スティッチ（最も確実）

1. Blender動画を5-10秒セグメントに分割（部屋の切り替わり等で区切る）
2. 各セグメントに同一のreference画像・prompt・seed・negative_promptを使用
3. 最終フレームを次セグメントの`image_url`（開始フレーム）に指定
4. 後処理で結合

### 一貫性維持のベストプラクティス

- **seed固定**: 全セグメントで同じseed値を使用
- **reference画像固定**: スタイル適用済み画像2-4枚をスタイルアンカーとして全セグメントに渡す
- **negative_prompt固定**: `"flicker, morphing, style change, blur, distortion"` を常に指定
- **cfg_scale**: 0.5（デフォルト）で適度な忠実度

## 推奨ワークフロー（30秒ウォークスルー）

```
Blender 30秒動画
  ↓ 5秒×6セグメントに分割
  ↓
各セグメントを Kling V3 Omni V2V (base mode)
  + reference_images: [俯瞰.png, カメラ1.png, カメラ2.png]
  + seed: 固定値
  + negative_prompt: "flicker, morphing, style change..."
  ↓
後処理で結合 → 完成
```

コスト見積もり: 30秒 × $0.168/秒 = 約$5.04（Pro 1080p）

## プロンプト設計の知見（PoC 9で検証済み）

### 効果的だった表現

- `real estate listing video` / `shot on mirrorless camera` — カメラ撮影感を強調
- `This is an INDOOR room — there must be a white ceiling overhead, not sky` — 天井の明示（3DCGで天井なしの場合に必須）
- `micro-imperfections — slight dust, fingerprints, fabric wrinkles` — CG感を消す
- 光の具体的描写: `Natural soft daylight entering from windows, creating gentle shadows and light gradients`
- 素材の質感詳細: `natural oak hardwood with visible wood grain, slight reflections, and realistic plank joints`

### 避けるべき表現

- `3D render` `CG` `game` — 入力の説明をすると出力もCG寄りになる
- 抽象的な指示のみ — 素材・照明は具体的に記述する方が品質が上がる

## 料金（公式API、2026-04-01時点）

| モード | 価格/秒 |
|--------|---------|
| Standard (720p) | $0.084 |
| Professional (1080p) | $0.168 |
| Pro + Audio | 追加あり |

## APIエンドポイント

- 公式: `https://klingai.com/dev`
- サードパーティラッパー: Freepik API、PiAPI、Replicate、fal.ai、AIML API

## 情報源

- [Freepik API - Kling V3 Omni V2V](https://docs.freepik.com/api-reference/video/kling-v3-omni/overview)
- [Replicate - Kling V3 Omni Video](https://replicate.com/kwaivgi/kling-v3-omni-video)
- [Scenario - Kling V3 Omni Guide](https://help.scenario.com/en/articles/kling-v3-omni-video-the-all-in-one-cinematic-powerhouse/)
- [Atlas Cloud - Kling Video O3 API Guide](https://www.atlascloud.ai/blog/guides/kling-video-o3-api-guide)
- [Atlas Cloud - Kling 3.0 Mass Production Guide](https://www.atlascloud.ai/blog/guides/integrating-kling-3-0-api-the-developers-guide-to-mass-ai-video-production)
