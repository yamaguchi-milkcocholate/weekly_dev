# Kling V2V用 3DCGレンダリング最適化 調査結果

調査日: 2026-04-03

## 調査目的

Blenderで構築したマンション内装3Dシーン（壁・ドア・柱・床・天井）をKling V3 Omni V2Vでフォトリアル動画に変換する際、Blender側でどの程度のテクスチャ/マテリアルを設定すべきか。現状はフラットなソリッドカラー（白壁・ダークブラウンドア・グレー柱）を使用。

---

## 結論サマリ

**「中間戦略」が最適: フラットなソリッドカラーではなく、かつフルリアリスティックテクスチャでもなく、素材の種類が判別できる程度の軽いテクスチャヒントを加える。**

理由:
1. **フラットすぎるとKlingが素材を誤認する** — PoC 9で確認済みの「壁がBlenderオブジェクトのフラットな質感のまま残る」問題はこれが原因
2. **リアルすぎるテクスチャは不要** — Klingは `cfg_scale` で創造的自由度を持ち、reference画像とプロンプトでテクスチャを生成する能力がある
3. **構造的な明確さが最優先** — Klingが正しく認識すべきは「ここは壁」「ここはドア」「ここは窓」という空間構造

---

## 1. フラットカラー vs テクスチャ: どちらが良いか

### 調査結果

3D→AI変換のワークフローには大きく2つの流派が存在する:

**流派A: フラットカラー + ControlNet方式（ComfyUI等）**
- 3Dシーンからdepth map、normal map、canny edge、semantic segmentation mapを書き出し
- これらをControlNetの条件入力として使い、AIが完全にテクスチャを生成
- 各オブジェクトに「シンプルなemissionシェーダーで個別の色」を割り当て
- AIへの指示はテキストプロンプトのみで行う
- 出典: [Blender + ComfyUI workflow](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui)

**流派B: テクスチャ付きレンダリング + V2V/img2img方式**
- ある程度テクスチャを含むレンダリングを入力とし、AIがそれを「リスキン」する
- 入力画像の構図・空間構造を保持しつつ、質感を向上させる
- denoiseを低め（0.20-0.35）に設定して構造を保つ
- 出典: [Daz 3D Forums - AI as render engine](https://www.daz3d.com/forums/discussion/725176/ai-as-render-engine)

### 本プロジェクトへの適用

**Kling V3 Omni V2V (base mode) は流派Bに該当する。** Klingは入力動画のモーション・構図を「完全維持してリスタイル」する設計であり、ControlNet的な分離入力（depth map等）には対応していない。

したがって:
- **完全フラットカラーは最適ではない**: Klingに渡す入力動画自体が「意味のある画像」である必要がある。白い板が並んでいるだけだと、Klingは「何を塗り替えるべきか」の手がかりが少ない
- **素材の違いを示すテクスチャヒントが有効**: 壁は壁っぽく、ドアはドアっぽく見えるだけの最低限の質感があると、Klingの認識精度が向上する

---

## 2. 推奨マテリアル戦略

### 2.1 壁: 微細な凹凸ヒントを追加

現状: ほぼ白 (0.95, 0.95, 0.93) のフラットカラー

**推奨変更:**
- Roughness を 0.9-1.0 に設定（マット仕上げ）
- Normal mapにノイズテクスチャ（Noise texture、Scale=200-500、Strength=0.02-0.05）を接続して微細な凹凸を追加
- これにより「塗装された壁」の質感が出て、Klingが「これは壁の表面だ」と認識しやすくなる
- 色はそのまま白系で良い（Klingが壁紙や塗装の色をreferenceとプロンプトから決定）

### 2.2 ドア: 木目方向のヒントを追加

現状: ダークブラウン (0.35, 0.15, 0.02) のフラットカラー

**推奨変更:**
- 木目方向のストライプテクスチャ（Wave texture、縦方向）をBase Colorに軽く混ぜる（Mix Factor 0.1-0.2）
- Roughness を 0.4-0.6 に設定（半光沢の木材質感）
- 結果として「木のドア」であることが視覚的に判別でき、Klingがリアルな木目に変換しやすくなる

### 2.3 柱: コンクリート質感のヒント

現状: グレー (0.60, 0.60, 0.60) のフラットカラー

**推奨変更:**
- Noise textureをBase Colorに軽く混ぜて微妙な色ムラを追加
- Roughness を 0.85-0.95 に設定
- 「コンクリートや石の柱」として認識されるようになる

### 2.4 床: 木目パターンのヒント

現状: 濃いダークブラウン (0.25, 0.20, 0.12)

**推奨変更:**
- PoC 9でV2Vが木目フローリングを生成できることが確認済み
- ただし、方向性のヒント（横方向のストライプパターン）を入れるとフローリングの板目方向が安定する
- Wave textureで横方向のストライプを軽く（Mix Factor 0.1-0.15）追加

### 2.5 天井: 現状維持

- 白のフラットカラーで問題なし
- 天井は「存在すること」が重要（PoC 9で天井なし=青空問題を確認済み）
- テクスチャは不要

### 2.6 窓ガラス: 半透明マテリアル

- Alpha = 0.1-0.3（ほぼ透明）
- 窓の外の背景プレーンが見える程度に
- Klingが「窓」として認識するためには透明感が重要

---

## 3. Klingの構造/深度情報の扱い

### Klingは明示的なdepth map入力をサポートしない

調査の結果、Kling V3 Omni（2026年4月時点）は:
- **depth map、normal map、semantic segmentation map等の補助入力に対応していない**
- 入力は動画 + テキストプロンプト + 参照画像のみ
- 3D構造の理解は、入力動画の視覚的特徴から内部的に推論する

これはRunway Gen-4やLuma Ray-3も同様で、ControlNet的な明示的構造制御はComfyUI + ローカルモデル（Stable Diffusion系、Wan2.1等）のワークフローでのみ利用可能。

### Klingの内部的な3D理解

Klingは以下の技術で入力動画の空間構造を理解する:
- **3D Variational Autoencoder (VAE)**: 時空間の同期圧縮で3D構造を内部表現
- **3D Spatiotemporal Joint Attention**: 複雑なカメラワーク・物体運動の理解
- **物理シミュレーション**: 重力・慣性・バランスのシミュレーション

つまり、明示的なdepth mapを渡さなくても、入力動画の視覚情報から3D構造を推論する能力がある。ただし、その精度は入力動画の「わかりやすさ」に依存する。

---

## 4. ControlNet方式との比較と代替戦略

### Klingでは使えないが、ControlNet方式が有効なケース

品質が最高になるのは、ComfyUI + Flux/SD + ControlNet（depth + canny + normal）を使う方式。iCloneやReallusion AI Renderが採用しているアプローチで:
1. Blenderからdepth map、normal map、canny edgeを書き出し
2. ComfyUIでControlNet条件として入力
3. テキストプロンプトでスタイルを指定
4. フレームごとに高品質な画像を生成
5. 動画としてエンコード

出典: [Reallusion AI Render](https://magazine.reallusion.com/2025/08/08/iclone-delivers-production-level-control-for-ai-generation/)

**ただし、この方式はフレームごとの生成のため、時間的一貫性（フリッカー等）の課題がある。** Kling V2V (base mode) は動画全体を一括処理するため、時間的一貫性が高い。

### 本プロジェクトでの判断

| 方式 | 構造制御 | 時間一貫性 | 自動化 | 品質 |
|------|---------|-----------|--------|------|
| Kling V2V (base mode) | 中（入力動画の視覚的特徴に依存） | 高 | 高（API一発） | 高 |
| ComfyUI + ControlNet | 高（depth/normal/cannyで明示的制御） | 低〜中（要post-processing） | 中（パイプライン構築必要） | 最高 |

**現行のKling V2V方式を継続し、Blender側のマテリアル改善で品質を底上げする方針が合理的。**

---

## 5. 解像度とレンダリング設定の最適化

### 入力動画の推奨仕様

| 項目 | 推奨値 | 根拠 |
|------|--------|------|
| 解像度 | 1920x1080 (1080p) | Kling Pro出力が1080p。入力が出力以上だと品質が安定 |
| フレームレート | 30fps | Kling出力のネイティブfps |
| コーデック | H.264 (mp4) | Kling APIが受け付けるフォーマット |
| アスペクト比 | 16:9 | Klingの出力アスペクト比は入力のアスペクト比に依存 |
| 長さ | 5-10秒/セグメント | APIの入力制限（3-10秒） |
| ファイルサイズ | < 200MB | API制限 |

### Blenderレンダリング設定

| 項目 | 推奨値 | 理由 |
|------|--------|------|
| レンダリングエンジン | EEVEE | リアルタイムレンダリングで十分。Cyclesの品質差はKlingが上書きする |
| サンプル数 | 64-128 | EEVEE標準。ノイズが目立たなければOK |
| HDRI | 使用する | 環境照明があることで空間の陰影が生まれ、Klingの3D理解を助ける |
| アンビエントオクルージョン | ON | 角や隅の影がつくことでKlingが構造を認識しやすくなる |
| ブルーム / レンズ効果 | OFF | 不要。Klingが独自の光学効果を追加する |
| 影 | ON（ソフトシャドウ） | 空間の奥行き認識に重要 |

---

## 6. プロンプト設計のベストプラクティス（PoC 9知見 + 追加調査）

### 構造記述の強化

PoC 9で確認済みの有効表現に加え、以下を推奨:

```
Prompt構造: Scene → Materials → Lighting → Camera → Style

Scene:
"Photorealistic interior of a modern Japanese apartment,
one-bedroom layout with open LDK, hallway with doors,
structural concrete pillars"

Materials（★新規追加推奨）:
"Walls finished with smooth matte white paint showing subtle texture,
solid wood doors with visible grain pattern in warm brown,
exposed concrete pillars with natural grey surface,
engineered hardwood flooring with herringbone pattern"

Lighting:
"Natural soft daylight entering from windows, creating gentle shadows
and light gradients on walls and floor"

Camera:
"Smooth steadicam walkthrough at chest height, slow forward movement"

Style:
"Real estate listing video, shot on mirrorless camera,
micro-imperfections — slight dust, fingerprints, fabric wrinkles"
```

### reference画像の効果（PoC 9で確認済み）

- reference画像なし: 「ゲームっぽさ」が残る
- reference画像あり: 実写感に転換
- **Blender側テクスチャ改善 + reference画像の併用が最も効果的**

---

## 7. 実装の優先度

### Phase 1: 即効性の高い改善（推奨）

1. **壁のRoughnessとNormal微調整** — Blenderマテリアルの変更のみ。スクリプトで一括適用可能
2. **ドアのRoughnessと軽い木目** — 同上
3. **EEVEE設定のAO有効化** — レンダリング設定の変更のみ

### Phase 2: 中期的改善

4. **床の方向性テクスチャ** — Wave textureの追加
5. **窓ガラスの半透明マテリアル** — PoC 0_b Step 3（窓検出）と連携
6. **柱のコンクリート質感** — Noise textureの追加

### Phase 3: 代替アプローチ（必要に応じて）

7. **ComfyUI + ControlNet方式の検証** — Klingで品質が頭打ちになった場合の代替
8. **Blender用AIテクスチャツール（StableGen等）** — PBRテクスチャを自動生成してBlenderに適用

---

## 情報源

### Kling公式・API関連
- [Kling V3 Omni Video (Scenario)](https://help.scenario.com/en/articles/kling-v3-omni-video-the-all-in-one-cinematic-powerhouse/)
- [Kling Video Models Essentials (Scenario)](https://help.scenario.com/en/articles/kling-video-models-the-essentials/)
- [Kling 3.0 Prompting Guide (fal.ai)](https://blog.fal.ai/kling-3-0-prompting-guide/)
- [Kling O1 V2V (fal.ai)](https://fal.ai/models/fal-ai/kling-video/o1/video-to-video/edit)
- [Kling O1 VFX Studio (InVideo)](https://invideo.io/blog/kling-o1-invideo-vfx-studio/)
- [Kling O1 Guide (Higgsfield)](https://higgsfield.ai/blog/Kling-01-is-Here-A-Complete-Guide-to-Video-Model)

### 3D→AI変換ワークフロー
- [Blender + ComfyUI 3D Animation Workflow](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui)
- [Reallusion AI Render for iClone (ComfyUI Integration)](https://magazine.reallusion.com/2025/08/08/iclone-delivers-production-level-control-for-ai-generation/)
- [AI as Render Engine (Daz 3D Forums)](https://www.daz3d.com/forums/discussion/725176/ai-as-render-engine)
- [3D Model to Cinematic Video (Rendair AI)](https://rendair.ai/blog/3d-model-to-cinematic-video)

### アーキテクチャ向けAI動画
- [Top 15 AI Video Models for Architects & Designers (RenderAI)](https://renderai.app/blog/video-ai-models-for-architects-designers-marketers/)
- [ControlNet Depth (ComfyUI Docs)](https://docs.comfy.org/tutorials/controlnet/depth-controlnet)
- [Controllable Video Generation Survey (GitHub)](https://github.com/mayuelala/Awesome-Controllable-Video-Generation)

### ControlNet / Depth Map
- [ControlNet Complete Guide (Stable Diffusion Art)](https://stable-diffusion-art.com/controlnet/)
- [ComfyUI Reallusion AI Render Workflows](https://www.runcomfy.com/comfyui-workflows/reallusion-ai-render-3D-workflow-collection)
- [Depth ControlNet Tutorial (ComfyUI)](https://docs.comfy.org/tutorials/controlnet/depth-controlnet)
