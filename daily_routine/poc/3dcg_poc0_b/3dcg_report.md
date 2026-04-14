# 3DCGレンダリング → AI動画生成 テクスチャ最適化 調査レポート

**調査日**: 2026-04-03
**目的**: Blenderで作成した3Dインテリアシーンを、AI動画生成ツール（Kling, Runway, Veo等）のV2V入力として最適化するためのテクスチャ・マテリアル・レンダリング設定を調査
**方針**: 外部ソースのみから結論を導出（自前の実験結果には依存しない）

---

## 結論: パイプラインによって最適解が異なる

テクスチャの最適解は**使用するパイプライン**によって根本的に異なる。

### パイプラインA: ComfyUI + ControlNet経由 → テクスチャ除去

マテリアル・テクスチャ・ライティングを**意図的に除去**し、構造情報（Depth/Edge/Mask）のみを出力する方式。各オブジェクトには識別用の単色Emissionシェーダーを割り当て、ComfyUIのregional conditioningでオブジェクト別にプロンプトを適用する。

> 「assign simple emission shaders with distinct colors to each object」「removing existing materials, textures, and lighting before rendering」
> — [RunComfy: AI Rendering 3D Animations with Blender and ComfyUI](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui)

### パイプラインB: 商用V2Vツール直接入力 → フルPBRレンダー

Kling, Runway, Veo等の商用V2Vツールに直接入力する場合は、**可能な限りリアルなレンダー**が最適。フラット単色は非推奨。

> 「A diffuse-only model presents a uniform, flat surface... no sense of grain, wear, sheen, or depth」
> — [Tripo3D: AI 3D Model Generator Converting Diffuse-Only to Full PBR Sets](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-converting-diffuse-only-to-full-pbr-sets)

> Roughnessチャンネルに5-10%のノイズ/smudgingマップを追加し「CG look」を排除する
> — [MyArchitectAI: Photorealistic Rendering](https://www.myarchitectai.com/blog/photorealistic-rendering)

---

## 1. テクスチャ詳細度: フラット単色 vs テクスチャ付き vs フルPBR

| アプローチ | 適用場面 | テクスチャ設定 | ソース |
|---|---|---|---|
| **マテリアル除去 + マスク色分け** | ComfyUI + ControlNet | Emissionシェーダー（識別色）、テクスチャ・ライティング除去 | [RunComfy](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui) |
| **フルPBR** | 商用V2V（Kling/Runway/Veo） | PBRマテリアル + Roughnessノイズ + 微細な不完全さ | [Tripo3D](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-converting-diffuse-only-to-full-pbr-sets), [MyArchitectAI](https://www.myarchitectai.com/blog/photorealistic-rendering) |
| **フラット単色（Diffuse-only）** | **非推奨** | 均一で平坦な表面。AIが奥行き・素材感を推定しにくい | [Tripo3D](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-converting-diffuse-only-to-full-pbr-sets) |

### フルPBRレンダーのベストプラクティス（商用V2V向け）

- Roughnessチャンネルに **5-10%のノイズ** を追加（CG look排除）
- 完璧すぎるCGを避け、微細な汚れ・色のバリエーション・小さな凹みなどの **不完全さ** を追加
- Klingは「glass, metal, fabric, water」などのマテリアル表現に強く「richer surfaces」を生成する
  — [WaveSpeedAI: Kling vs Runway比較](https://wavespeed.ai/blog/posts/kling-vs-runway-gen3-comparison-2026/)

### セマンティックカラー（壁=白、ドア=茶等）について

ComfyUI + ControlNetパイプラインでは、セマンティックカラーは「リアルっぽい色」ではなく、**マスキング用の識別色（赤・青・緑等）のEmissionシェーダー** として使用する。HexCodeを記録し、ComfyUIの「regional conditioning by color mask」ノードでオブジェクトごとにプロンプトを適用する。
— [RunComfy](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui)

---

## 2. 各AIツールのV2V入力仕様

### Kling O1 / V3

| 項目 | 仕様 |
|---|---|
| V2Vモード | Reference V2V, Video Editing, Lipsync, Motion Control |
| 入力 | MP4/MOV, 3-10秒, 最大200MB |
| 出力 | HD-4K, 5秒/10秒, 16-bit HDR対応 |
| 参照画像 | Edit: 最大4枚 / Video Generation: 最大7枚 |
| 構造保持 | カメラ動き・モーション・空間関係を保持。3D顔・体再構成で深度・パースペクティブを理解 |
| 特記 | VFXパイプライン用にEXRシーケンスエクスポート対応 |

> ソース: [fal.ai Kling O1 API](https://fal.ai/models/fal-ai/kling-video/o1/reference-to-video), [Scenario Guide](https://help.scenario.com/en/articles/kling-v3-omni-video-the-all-in-one-cinematic-powerhouse/)

### Runway Gen-4 / Gen-4.5

| 項目 | 仕様 |
|---|---|
| V2Vモード | Video-to-Video（スタイル変換）, Expand Video |
| 入力 | MP4/MOV/MKV/WebM, 640px以上, URL: 32MB / Ephemeral: 200MB |
| 構造制御 | **Structure Transformation slider**（低=構造維持、高=抽象的） |
| 制御 | Motion Brush 3.0（領域指定でモーション方向・速度制御） |
| 注意 | 入力のアスペクト比が指定と異なる場合、中央からオートクロップ |

> ソース: [Runway API Docs](https://docs.dev.runwayml.com/), [DataCamp Gen-4.5 Guide](https://www.datacamp.com/tutorial/runway-gen-4-5)

### Pika 2.5

| 項目 | 仕様 |
|---|---|
| V2Vモード | Pikaswaps（オブジェクト置換）, Pikadditions（追加）, Pikaffects（エフェクト） |
| 出力 | 最大1080p, 最大10秒 |
| 参照画像 | Scene Ingredients（スタイル・構図・キャラクターガイド） |

> ソース: [Pika Labs 2.5](https://pikaslabs.com/pika-2-5/)

### Google Veo 3.1

| 項目 | 仕様 |
|---|---|
| V2Vモード | Video Extension（**Veo生成動画のみ**）, I2V, First/Last Frame |
| 出力 | 720p-4K, 24fps, 4/6/8秒 |
| 参照画像 | 最大3枚 |
| 特記 | 映画のプロの語彙（ライティング・マテリアル・構図）に最も正確に反応 |

> ソース: [Google AI Developers](https://ai.google.dev), [Replicate Veo 3.1](https://replicate.com/blog/veo-3-1)

### 構造制御サポート状況まとめ

| ツール | 明示的Depth/Normal入力 | 構造制御方法 |
|---|---|---|
| ComfyUI + SD | **対応** (ControlNet) | Depth/Normal/Canny/OpenPose/MLSD |
| Runway Gen-4 | 非対応 | Structure Transformation slider, Motion Brush |
| Kling O1/V3 | 非対応 | Reference Video（暗黙的構造保持） |
| Veo 3.1 | 非対応 | First/Last Frame, 参照画像 |
| Pika 2.5 | 非対応 | Scene Ingredients |

**→ 明示的なControlNet（Depth/Normal/Canny）入力は ComfyUI + SD系のみ。商用ツールは入力映像の暗黙的な構造認識に依存する。**

---

## 3. レンダリング設定

### 商用V2V向け（パイプラインB）

| 設定 | 推奨 | ソース |
|---|---|---|
| レンダーエンジン | **Cycles**（物理ベースパストレーシング） | [Vagon](https://vagon.io/blog/the-best-render-settings-for-blender) |
| サンプル数 | 256-1024 + デノイジング（インテリア: 2048+推奨） | [SuperRenders](https://superrendersfarm.com/article/blender-render-settings-optimization-guide) |
| ライティング | HDRI環境光 + 3点ライティング | [Vagon](https://vagon.io/blog/the-best-render-settings-for-blender) |
| シャドウ | ソフトシャドウ推奨（ハードシャドウはAIが誤解釈する可能性） | [ReelMind](https://reelmind.ai/blog/ai-platforms-product-rendering-shadows-lighting-re-96f777) |
| AO | 有効推奨（空間のリアリティ向上、オブジェクト間の空間関係を明確化） | [GarageFarm](https://garagefarm.net/blog/ambient-occlusion-realism-through-shadows) |
| 出力フォーマット | 16-bit PNG RGBA or 32-bit EXR RGBA | [SuperRenders](https://superrendersfarm.com/article/blender-render-settings-optimization-guide) |
| Color Management | Raw（トーンマッピング回避） | [Vagon](https://vagon.io/blog/the-best-render-settings-for-blender) |
| 解像度 | 1920x1080（各ツールのV2V入力に適合） | 各ツール仕様 |
| EEVEEの位置づけ | ブロッキング・プレビュー用。最終レンダーはCycles | [iRendering](https://irendering.net/cycles-and-eevee-which-renderer-should-we-choose/) |

### ComfyUI + ControlNet向け（パイプラインA）

| 設定 | 推奨 | ソース |
|---|---|---|
| マテリアル | **全除去** → 単色Emissionシェーダー | [RunComfy](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui) |
| ライティング | **除去**（AIがプロンプトで制御） | 同上 |
| 出力パス | Depth (Z pass + Map Range), Edge (Freestyle), Mask (Emission色分け) | 同上 |
| Depth出力 | 16-bit PNG RGBA / 32-bit EXR、Color Management: Raw | [sandner.art](https://sandner.art/how-to-render-blender-3d-models-in-stable-diffusion/) |

### AOの役割（詳細）

AOは「tight spaces（狭い空間）で光が自然に遮られるシミュレーション」であり、深度感とオブジェクトの接地感を強化する。
— [GarageFarm: Ambient Occlusion Realism Through Shadows](https://garagefarm.net/blog/ambient-occlusion-realism-through-shadows)

商用V2Vでは、AO・シャドウがAIにとっての**構造の手がかり**となる。ComfyUI経由ではDepth passで構造を明示的に伝達するためAOは不要。

---

## 4. プロンプト戦略（V2V時）

### 全ツール共通の原則

プロンプトは「シーンの説明」ではなく**「ショットの指揮」**として書く。
構造: **[Camera] + [Subject/Object] + [Action] + [Environment] + [Lighting] + [Lens] + [Mood]**

### ツール別の特性

| ツール | 特性 | プロンプト戦略 | ソース |
|---|---|---|---|
| **Kling** | 「視聴覚振付師」 | 「maintaining the original camera movement」を明示。省略するとモーション変化が入る | [fal.ai Kling O1 Guide](https://fal.ai/learn/devs/kling-o1-prompt-guide) |
| **Runway** | 「運動彫刻家」 | 物理とカメラ動作に拘る。Structure Transformation sliderを低めに | [DataCamp](https://www.datacamp.com/tutorial/runway-gen-4-5) |
| **Veo 3.1** | 映画語彙に最も正確 | ライティング・マテリアル語彙を使用（'dolly in', 'shallow focus'等） | [Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) |
| **Pika** | Scene Ingredientsが強力 | 参照画像での制御が中心 | [Pika Labs](https://pikaslabs.com/pika-2-5/) |

### Reference画像

| ツール | 枚数 | 役割 | ソース |
|---|---|---|---|
| Kling | 最大7枚 | 正面画像 + 複数角度。包括的なビジュアルコンテキスト | [fal.ai](https://fal.ai/learn/devs/kling-o1-prompt-guide) |
| Veo 3.1 | 最大3枚 | スタイル・コンテンツガイド | [Google AI Developers](https://ai.google.dev) |
| Runway | 入力画像 | V2Vの最初のフレーム。キーフレーミングで中間点も制御 | [DataCamp](https://www.datacamp.com/tutorial/runway-gen-4-5) |
| Pika | 複数 | Scene Ingredientsとしてキャラクター/オブジェクトをアップロード | [Pika Labs](https://pikaslabs.com/pika-2-5/) |

**注意**: Reference画像は2-4枚が最適。多すぎるとモデルの優先度が混乱する。
— [fal.ai Kling 2.6 Pro Prompt Guide](https://fal.ai/learn/devs/kling-2-6-pro-prompt-guide)

---

## 5. 実際のワークフロー事例

### 事例1: Blender + ComfyUI + AnimateDiff

Blenderで3Dシーン構築 → マテリアル除去 → Depth/Edge/Mask 3パスレンダー → ComfyUI ControlNet + AnimateDiff → 最終動画
— [RunComfy](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui)

### 事例2: Blender → ComfyUI AI Renderer 2.0

Blenderから動画エクスポート → ComfyUI Preprocessで制御タイプ選択 → Z-Image-Fun ControlNet Union 2.1 → Wan 2.1 VACEで合成
— [RunComfy Renderer 2.0](https://www.runcomfy.com/comfyui-workflows/blender-to-comfyui-ai-renderer-2-0-workflow-cinematic-video-output)

### 事例3: 建築ビジュアライゼーション（Runway）

3Dレンダリングソフトで静止画レンダー → Runwayにアップロード → プロンプトでカメラ動き・雰囲気記述 → 動画生成。
注意: 「results aren't always predictable」「loss of important architectural details in complex scenes」
— [Archiobjects: Runway ML for Architects](https://www.archiobjects.org/runway-ml-for-architects-ai-video-generator-and-much-more/)

### 事例4: ArchiVinci（建築特化）

SketchUp/Revit/Blenderからスクリーンショット → AIがControlNetガイドでフォトリアリスティック画像生成 → Cinematic Droneモーションプリセットで動画化
— [ArchiVinci](https://www.archivinci.com/)

### 事例5: Luma AI V2V（スタイルトランスファー）

実写/3Dアニメーション → Stylized formatに変換（アニメ、シネマティック3D等）。モーション・ライティング・シーン構造を保持。
— [Luma AI V2V](https://lumalabs.ai/video-to-video)

---

## 6. 推奨パイプライン比較

### パイプラインA: ComfyUI + ControlNet（最大構造制御）

```
Blender (構造パスのみ出力)
├── Depth sequence (16-bit PNG / EXR)
├── Edge sequence (Freestyle)
└── Mask sequence (単色Emission、オブジェクト別識別色)
    ↓
ComfyUI
├── ControlNet Depth + Canny（建築はMLSD推奨）
├── Regional conditioning (マスク色別プロンプト)
├── AnimateDiff (テンポラル一貫性)
└── Upscaler
    ↓
最終動画
```

| 項目 | 内容 |
|---|---|
| テクスチャ | **除去**。マスク用単色Emissionのみ |
| 長所 | 完全な構造制御、オブジェクト別プロンプト |
| 短所 | セットアップ複雑、ローカルGPU必要 |
| ControlNet推奨 | 建築: MLSD / 多くのシーン: Depth / 人物: OpenPose |

> ソース: [RunComfy](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui), [ComfyUI AnimateDiff Guide](https://learn.runcomfy.com/3d-rendering-with-comfyui-animatediff-a-full-guide)

### パイプラインB: 商用V2V（高速ワークフロー）

```
Blender (フルPBRレンダー)
├── Cycles 256-1024 samples + Denoising
├── PBR materials (Roughnessに5-10%ノイズ)
├── HDRI + 3点ライティング
└── ソフトシャドウ + AO有効
    ↓
MP4/MOV (H.264, 1080p)
    ↓
Kling O1 / Runway Gen-4 / Veo 3.1
├── V2V mode
├── プロンプト: Camera + Subject + Action + Environment + Lighting
└── Reference images (2-4枚)
    ↓
最終動画
```

| 項目 | 内容 |
|---|---|
| テクスチャ | **フルPBR**。Roughnessに5-10%ノイズ。不完全さ追加 |
| 長所 | シンプル、高速、直感的 |
| 短所 | 構造制御が間接的、AIの解釈に依存 |

### ツール選択ガイド

| 目的 | 推奨ツール | ソース |
|---|---|---|
| マテリアル品質重視 | Kling V3/O1（glass, metal, fabricに強い） | [WaveSpeedAI](https://wavespeed.ai/blog/posts/kling-vs-runway-gen3-comparison-2026/) |
| カメラ制御重視 | Runway Gen-4.5（Motion Brush、キーフレーミング） | [DataCamp](https://www.datacamp.com/tutorial/runway-gen-4-5) |
| 映画的プロンプト制御 | Veo 3.1（映画語彙への反応が最良） | [Google Cloud Blog](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) |
| 完全な構造制御 | ComfyUI + ControlNet | [RunComfy](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui) |
| 建築特化 | ArchiVinci / Fenestra | [ArchiVinci](https://www.archivinci.com/) |

---

## データソース一覧

### テクスチャ・マテリアル

| URL | 取得内容 |
|---|---|
| [RunComfy: Blender+ComfyUI+AnimateDiff](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui) | マテリアル除去+マスク色分け方式の詳細ワークフロー |
| [Tripo3D: Diffuse-Only to Full PBR](https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-converting-diffuse-only-to-full-pbr-sets) | Diffuse-onlyとPBRの比較。フラット単色の問題点 |
| [MyArchitectAI: Photorealistic Rendering](https://www.myarchitectai.com/blog/photorealistic-rendering) | Roughnessノイズ追加等のベストプラクティス |
| [WaveSpeedAI: Kling vs Runway比較](https://wavespeed.ai/blog/posts/kling-vs-runway-gen3-comparison-2026/) | マテリアル表現の差（Klingのglass/metal/fabric優位性） |

### V2V入力仕様

| URL | 取得内容 |
|---|---|
| [fal.ai: Kling O1 API](https://fal.ai/models/fal-ai/kling-video/o1/reference-to-video) | Kling O1のV2V入力仕様 |
| [Scenario: Kling V3 Omni](https://help.scenario.com/en/articles/kling-v3-omni-video-the-all-in-one-cinematic-powerhouse/) | Kling V3のV2V 2モード（Feature/Base） |
| [Runway API Docs](https://docs.dev.runwayml.com/) | Runway Gen-4の入力フォーマット・制御パラメータ |
| [DataCamp: Runway Gen-4.5](https://www.datacamp.com/tutorial/runway-gen-4-5) | Runway Gen-4.5のStructure Transformation等 |
| [Pika Labs 2.5](https://pikaslabs.com/pika-2-5/) | Pika 2.5のV2V機能・Scene Ingredients |
| [Google AI Developers](https://ai.google.dev) | Veo 3.1の仕様 |
| [Replicate: Veo 3.1](https://replicate.com/blog/veo-3-1) | Veo 3.1のプロンプト方法 |

### レンダリング設定

| URL | 取得内容 |
|---|---|
| [Vagon: Blender Render Settings](https://vagon.io/blog/the-best-render-settings-for-blender) | Cycles推奨設定、サンプル数、ライティング |
| [SuperRenders: Optimization Guide](https://superrendersfarm.com/article/blender-render-settings-optimization-guide) | レンダー設定最適化（2026年版） |
| [iRendering: Cycles vs EEVEE](https://irendering.net/cycles-and-eevee-which-renderer-should-we-choose/) | エンジン選択ガイド |
| [GarageFarm: AO Realism](https://garagefarm.net/blog/ambient-occlusion-realism-through-shadows) | AOの仕組みと視覚効果 |
| [ReelMind: Shadows & Lighting](https://reelmind.ai/blog/ai-platforms-product-rendering-shadows-lighting-re-96f777) | AI動画生成におけるシャドウ・ライティングの役割 |

### プロンプト・Reference画像

| URL | 取得内容 |
|---|---|
| [fal.ai: Kling O1 Prompt Guide](https://fal.ai/learn/devs/kling-o1-prompt-guide) | Kling O1のV2Vプロンプト戦略 |
| [fal.ai: Kling 2.6 Pro Prompt Guide](https://fal.ai/learn/devs/kling-2-6-pro-prompt-guide) | Reference画像の最適枚数（2-4枚） |
| [Google Cloud: Veo 3.1 Prompting Guide](https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1) | Veo 3.1の映画語彙プロンプト |

### ControlNet / 構造制御

| URL | 取得内容 |
|---|---|
| [GitHub: controlnet-render-blender-addon](https://github.com/x6ud/controlnet-render-blender-addon) | BlenderからControlNetパス一括出力 |
| [sandner.art: Blender→SD Depth Map](https://sandner.art/how-to-render-blender-3d-models-in-stable-diffusion/) | Blenderからのdepth map出力手順 |
| [RunComfy: AI Renderer 2.0](https://www.runcomfy.com/comfyui-workflows/blender-to-comfyui-ai-renderer-2-0-workflow-cinematic-video-output) | Blender→ComfyUI統合ワークフロー |
| [ComfyUI: Depth ControlNet](https://docs.comfy.org/tutorials/controlnet/depth-controlnet) | Depth ControlNetチュートリアル |
| [RunComfy: AnimateDiff Full Guide](https://learn.runcomfy.com/3d-rendering-with-comfyui-animatediff-a-full-guide) | AnimateDiff + ControlNet統合ガイド |

### ワークフロー事例

| URL | 取得内容 |
|---|---|
| [Archiobjects: Runway ML for Architects](https://www.archiobjects.org/runway-ml-for-architects-ai-video-generator-and-much-more/) | 建築ビジュアライゼーション事例 |
| [ArchiVinci](https://www.archivinci.com/) | 建築特化AIパイプライン |
| [Meshy AI: 3D Modeling and Animation](https://www.meshy.ai/blog/3d-modeling-and-animation) | Meshy+Blender+Hailuo AIワークフロー |
| [Luma AI V2V](https://lumalabs.ai/video-to-video) | スタイルトランスファー事例 |
| [Mago Studio](https://www.mago.studio/) | ライブアクション→3D変換 |

### アクセス不可URL（403 Forbidden）

| URL | 期待される内容 |
|---|---|
| https://medium.com/@jdcruel/the-3d-artists-guide-to-ai-video-generation... | 3DアーティストのAI動画生成ガイド |
| https://medium.com/@creativeaininja/how-to-actually-control-next-gen-video-ai... | 次世代AI動画の制御戦略 |
| https://medium.com/@cliprise/the-state-of-ai-video-generation... | 2026年AI動画生成の現状 |
| https://help.runwayml.com/hc/en-us/articles/46974685288467 | Runway Gen-4.5使用ガイド |
