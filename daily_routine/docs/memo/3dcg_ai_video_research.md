# 3DCGレンダリング → AI動画生成 最適化調査レポート

調査日: 2026-04-03

---

## Q1: フラット単色 vs テクスチャ付き vs フルPBR — どれが最適か？

### 調査結果の要約

**結論: 用途とパイプラインによって最適解が異なる。大きく2つのアプローチが存在する。**

#### アプローチA: ストリップダウン方式（推奨度: 高 — ComfyUI/ControlNet経由の場合）

Blender + ComfyUI + AnimateDiff/ControlNetのパイプラインでは、**テクスチャ・マテリアル・ライティングを意図的に除去し、構造情報のみを出力する**方式が確立されている。

- **出力するもの**: Depth pass（Zパス）、Outline pass（Freestyleエッジ）、Mask pass（オブジェクトごとに単色Emissionシェーダーを割り当て）
- **出力しないもの**: カラーテクスチャ、PBRマテリアル、ライティング、シャドウ
- **色分けマスクの使い方**: 各オブジェクトに「distinct colors（個別の単色）のEmissionシェーダー」を割り当て、HexCodeを記録。ComfyUIの「regional conditioning by color mask」ノードでオブジェクトごとにプロンプトを適用する

> ソース: RunComfy "AI Rendering 3D Animations with Blender and ComfyUI" — 「assign simple emission shaders with distinct colors to each object」「removing existing materials, textures, and lighting before rendering」

この方式では**セマンティックカラー（意味を持つ色分け）は有効**だが、壁=白・ドア=茶といった「リアルっぽい色」ではなく、**マスキング用の識別色（赤・青・緑等）** として使用する。

#### アプローチB: フルレンダー方式（推奨度: 高 — 商用V2Vツール直接利用の場合）

Kling O1、Runway Gen-4、Veo 3.1等の商用V2Vツールに直接入力する場合は、**可能な限りリアルなレンダーを入力する**方がよい結果が得られる。

- Klingは「glass, metal, fabric, water」などのマテリアル表現に強く、「richer surfaces」を生成する（Kling vs Runway比較テスト）
- PBRマテリアルはNormal, Roughness, Metallic, Heightマップにより「light to interact with it correctly across all lighting conditions」を実現し、AI動画生成ツールが構造を正しく認識するための手がかりを提供する
- フラット単色（Diffuse-only）は「uniform, flat surface」となり「looks like a plastic toy under any dynamic lighting」— AIツールが奥行きや素材感を推定しにくい

> ソース: Tripo3D PBR解説 — 「A diffuse-only model presents a uniform, flat surface... no sense of grain, wear, sheen, or depth」

#### フォトリアリスティック品質のためのベストプラクティス

- Roughnessチャンネルに5-10%のノイズ/smudgingマップを追加し「CG look」を排除する
- 完璧すぎるCGを避け、微細な汚れ・色のバリエーション・小さな凹みなどの不完全さを追加する
- 異なるライティング条件でマテリアルをテストする

> ソース: MyArchitectAI / Tripo3D — 「Drop a 5–10% noise or subtle smudging map into the roughness channel of every glossy material」

### ソースURL一覧

| URL | 内容 |
|-----|------|
| https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui | Blender+ComfyUIワークフロー: マテリアル除去＋マスク色分け方式の詳細 |
| https://www.tripo3d.ai/blog/explore/ai-3d-model-generator-converting-diffuse-only-to-full-pbr-sets | Diffuse-onlyとPBRの比較、PBRの優位性 |
| https://medium.com/@alexy.mansuy/understanding-pbr-materials-in-3d-rendering-a-beginners-introduction-58d94d10a42b | PBRマテリアルの基礎説明 |
| https://www.myarchitectai.com/blog/photorealistic-rendering | フォトリアリスティック3Dレンダリングのベストプラクティス |
| https://wavespeed.ai/blog/posts/kling-vs-runway-gen3-comparison-2026/ | Kling vs Runway比較: マテリアル表現の差 |

### アクセス不可URL

| URL | 状況 |
|-----|------|
| https://medium.com/@jdcruel/the-3d-artists-guide-to-ai-video-generation-production-integration-and-advanced-workflows-part-d9c5e4005a3d | 403 Forbidden |
| https://medium.com/@creativeaininja/how-to-actually-control-next-gen-video-ai-runway-kling-veo-and-sora-prompting-strategies-92ef0055658b | 403 Forbidden |
| https://medium.com/@cliprise/the-state-of-ai-video-generation-in-february-2026-every-major-model-analyzed-6dbfedbe3a5c | 403 Forbidden |

---

## Q2: 各AIツールのV2V（Video-to-Video）入力仕様

### Kling O1 / V3

| 項目 | 仕様 |
|------|------|
| V2Vモード | Reference Video-to-Video、Video Editing、Lipsync、Motion Control |
| 入力動画長 | 3〜10秒 |
| 入力フォーマット | MP4, MOV |
| ファイルサイズ上限 | 200MB |
| 出力解像度 | HD〜4K（720〜2160px）、ネイティブ1080p/4K 30fps |
| 出力長 | 5秒または10秒 |
| アスペクト比 | Auto, 16:9, 9:16, 1:1 |
| 参照画像 | Edit: 最大4枚、Video Generation: 最大7枚 |
| 構造保持 | カメラ動き・モーション・空間関係を保持。3D顔・体再構成技術で深度・パースペクティブを理解 |
| HDR | 16-bit HDR対応 |
| 特記事項 | VFXパイプライン用にEXRシーケンスエクスポート対応（Nuke/AE/DaVinci連携） |

> ソース: fal.ai Kling O1 API docs, Higgsfield Kling O1 Guide, Scenario Guide

### Runway Gen-3 Alpha / Gen-4 / Gen-4.5

| 項目 | 仕様 |
|------|------|
| V2Vモード | Video-to-Video（スタイル変換）、Expand Video |
| 入力フォーマット | MP4(H.264/H.265/AV1), MOV(H.264/H.265/ProRes), MKV, WebM |
| ファイルサイズ上限 | URL: 32MB, Data URI: 16MB, Ephemeral uploads: 200MB |
| 出力解像度 | Gen-3: 1280x768 / 768x1280、Gen-4 Turbo: 1280x720, 1584x672, 1104x832等 |
| 推奨入力解像度 | 640x640以上、4K以下 |
| 構造制御 | Structure Transformation slider（低=構造維持、高=抽象的） |
| 制御モード | Motion Brush 3.0（領域指定でモーション方向・速度制御） |
| プロンプト構造 | [Camera] + [Subject] + [Action] + [Environment] + [Lighting] + [Lens] + [Mood] |
| 特記事項 | 入力のアスペクト比が指定と異なる場合、中央からオートクロップされる |

> ソース: Runway API Documentation (docs.dev.runwayml.com), Runway Help Center, DataCamp Gen-4.5 guide

### Pika 2.5

| 項目 | 仕様 |
|------|------|
| V2Vモード | Pikaswaps（オブジェクト置換）、Pikadditions（オブジェクト追加）、Pikaffects（クリエイティブエフェクト） |
| 出力解像度 | 最大1080p |
| 出力長 | 最大10秒 |
| 出力フォーマット | MP4 |
| 構造保持 | テンポラル一貫性保持: ライティング連続性、Progressive generation（3-5秒ずつ延長） |
| 参照画像 | Scene Ingredientsとしてアップロード可能（スタイル・構図・キャラクターガイド） |

> ソース: Pika Labs 2.5 Guide (pikaslabs.com), Flowith Blog, Segmind Blog

### Google Veo 3.1

| 項目 | 仕様 |
|------|------|
| V2Vモード | Video Extension（Veoで生成した動画の延長）、Image-to-Video、First/Last Frame制御 |
| 入力制約 | Video Extensionは**Veo生成動画のみ**（2日以内、720p、141秒以下） |
| 出力解像度 | 720p（デフォルト）、1080p（8秒のみ）、4K（8秒のみ） |
| 出力フレームレート | 24fps |
| 出力フォーマット | MP4 |
| 参照画像 | 最大3枚のリファレンス画像（VideoGenerationReferenceImage） |
| 構造保持 | lastFrameパラメータで開始・終了フレーム指定可能 |
| アスペクト比 | 16:9, 9:16 |
| 持続時間 | 4, 6, 8秒 |
| プロンプト構造 | Camera + Subject + Action + Setting + Style & Audio |
| 特記事項 | 「ショットを指揮するように」プロンプトを書くのが最善。Veo 3はプロの写真・映画で訓練されており、ライティング・マテリアル語彙に最も正確に反応する |

> ソース: Google AI Developers docs (ai.google.dev), Google Cloud Blog Veo 3.1 Prompting Guide

### OpenAI Sora 2

| 項目 | 仕様 |
|------|------|
| V2Vモード | Remix（既存動画の部分調整） |
| 出力解像度 | 最大1080p |
| 出力長 | 最大20秒 |
| アスペクト比 | ワイドスクリーン、縦、正方形 |
| 特記事項 | **2026年9月24日にAPI廃止予定**。3Dパッチベースの潜在拡散トランスフォーマー。データセットから3Dグラフィックス生成を自動学習 |

> ソース: OpenAI Sora docs, Wikipedia Sora article, WaveSpeedAI Blog

---

## Q3: ControlNet / 構造制御の活用

### 各ツールでの構造制御サポート状況

| ツール | Depth Map | Normal Map | Canny Edge | その他 |
|--------|-----------|------------|------------|--------|
| ComfyUI + SD | ControlNet Depth | ControlNet Normal (MiDaS/BAE) | ControlNet Canny | OpenPose, MLSD, Scribble等 |
| Runway Gen-4 | Motion Brush 3.0 | - | - | Structure Transformation slider |
| Kling O1 | - | - | - | Reference Video（動きの構造を暗黙的に保持） |
| Veo 3.1 | - | - | - | First/Last Frame、参照画像 |
| Pika 2.5 | - | - | - | Scene Ingredients |

**注意**: Kling, Runway, Veo, Pika等の商用ツールは明示的なDepth/Normal入力をサポートしていない。構造制御はV2V入力動画の暗黙的な構造認識、または参照画像による間接的な制御に頼る。**明示的なControlNet（Depth/Normal/Canny）が使えるのはComfyUI + Stable Diffusion系のパイプラインのみ**。

### Blenderからの構造情報出力方法

#### Depth Map

1. View Layer Properties で「Mist pass」または「Z pass」を有効化
2. Compositing workspace でノードセットアップ:
   - Map Range ノードで深度値を正規化
   - Gamma調整で深度の分布を制御
3. 出力: **16-bit PNG RGBA**（バンディング回避）または **32-bit EXR RGBA**
4. Color Management を **Raw** に設定（バンディング対策）
5. 必要に応じて色を反転（Ctrl+I）

#### Normal Map

- Cycles の Normal pass をレンダーレイヤーで有効化
- 表面法線をRGB画像として出力（R=X, G=Y, B=Z）

#### Edge / Outline

- Freestyle を使用してラインアートエッジを生成
- 白背景に白ラインでレンダー、線の太さ調整可能

#### Blender ControlNetアドオン

- **controlnet-render-blender-addon** (x6ud): ワンクリックでDepth/Normal/Edgeを一括出力
- Blender 3.5対応、Stable Diffusion web UI + sd-webui-controlnet 連携
- Rendering workspace のNパネルからアクセス

> ソース: GitHub x6ud/controlnet-render-blender-addon, sandner.art Blender SD guide, Blender docs

### ComfyUIとの統合ワークフロー

**Blender → ComfyUI パイプライン（RunComfy Blender to ComfyUI AI Renderer 2.0）:**

1. **Blender Phase**: Depth, Outline, Mask の画像シーケンスをレンダー
2. **ComfyUI Preprocess**: 動画フレームから制御タイプ（depth/canny/pose）を選択・生成
3. **ControlNet適用**: Z-Image-Fun ControlNet Union 2.1（canny, depth, pose等を同時サポート）
4. **生成**: AnimateDiff でテンポラル一貫性を確保しつつ生成

推奨ControlNet使い分け:
- **Depth**: 多くのシーンで良好な結果
- **OpenPose**: キャラクター/人物
- **MLSD**: 建築
- **Canny/Normal**: 実験的に併用

> ソース: RunComfy workflows, ComfyUI docs, CivitAI AnimateDiff guide

### ソースURL一覧

| URL | 内容 |
|-----|------|
| https://github.com/x6ud/controlnet-render-blender-addon | Blender→ControlNet一括出力アドオン |
| https://sandner.art/how-to-render-blender-3d-models-in-stable-diffusion/ | Blender→SD depth map出力手順の詳細 |
| https://docs.blender.org/manual/en/latest/render/layers/passes.html | Blenderレンダーパス公式ドキュメント |
| https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui | Blender+ComfyUI+AnimateDiffワークフロー |
| https://www.runcomfy.com/comfyui-workflows/blender-to-comfyui-ai-renderer-2-0-workflow-cinematic-video-output | Blender→ComfyUI Renderer 2.0ワークフロー |
| https://docs.comfy.org/tutorials/controlnet/depth-controlnet | ComfyUI Depth ControlNetチュートリアル |
| https://comfyui-wiki.com/en/tutorial/advanced/how-to-use-depth-controlnet-with-sd1.5 | SD1.5 Depth ControlNetガイド |
| https://learn.runcomfy.com/3d-rendering-with-comfyui-animatediff-a-full-guide | ComfyUI + AnimateDiff 3Dレンダリング完全ガイド |

---

## Q4: Ambient Occlusion, ライティング, シャドウの影響

### 調査結果の要約

#### AO・シャドウがAI動画生成に与える影響

- AOは「tight spaces（狭い空間）で光が自然に遮られるシミュレーション」であり、深度感とオブジェクトの接地感を強化する
- AI動画生成モデルは暗部の情報（AO、シャドウ）を**構造の手がかり**として利用する。AOがあるとオブジェクト間の空間関係がより明確になる
- ただし、ComfyUI/ControlNetパイプラインではAOを含むレンダーではなく、Depth passやNormal passで構造を明示的に伝達するため、AOの影響は間接的

#### パイプライン別推奨設定

**商用V2Vツール直接入力の場合:**
- ライティング: 自然光ベースのHDRI環境光 + 3点ライティングが安定
- AO: 有効推奨（空間のリアリティ向上）
- シャドウ: ソフトシャドウ推奨（ハードシャドウはAIが誤解釈する場合がある）
- 推奨レンダーエンジン: **Cycles**（物理ベースのパストレーシング）
  - 256〜1024サンプル + デノイジング有効
  - 建築インテリア: 2048サンプル以上推奨
  - 屋外: 128〜256サンプル + デノイジングで十分
- EEVEEの位置づけ: ブロッキング・プレビュー用。最終レンダーはCycles

**ComfyUI/ControlNetパイプラインの場合:**
- ライティング・AO・シャドウは**除去**する（マテリアルも含め）
- 構造情報はDepth/Normal/Cannyで明示的に伝達
- AIが「生成する」光と影がプロンプトで制御される

#### レンダリング出力フォーマット推奨

- 静止画: 16-bit PNG RGBA（バンディング回避）
- 高品質: 32-bit EXR RGBA（後処理の柔軟性最大）
- Color Management: Raw（トーンマッピング回避）
- Film > Transparent: ON（背景透過が必要な場合）

> ソース: Vagon Blender render settings, SuperRenders optimization guide, ReelMind shadows/lighting article

### ソースURL一覧

| URL | 内容 |
|-----|------|
| https://garagefarm.net/blog/ambient-occlusion-realism-through-shadows | AOの仕組みと視覚効果の解説 |
| https://reelmind.ai/blog/ai-platforms-product-rendering-shadows-lighting-re-96f777 | AI動画生成におけるシャドウ・ライティングの役割 |
| https://vagon.io/blog/the-best-render-settings-for-blender | Blenderレンダー設定ベストプラクティス |
| https://superrendersfarm.com/article/blender-render-settings-optimization-guide | Blenderレンダー設定最適化ガイド2026 |
| https://irendering.net/cycles-and-eevee-which-renderer-should-we-choose/ | Cycles vs EEVEE選択ガイド |

---

## Q5: プロンプトとReference画像の役割

### V2V変換時のプロンプト戦略

#### 全ツール共通の原則

- プロンプトは「シーンの説明」ではなく「ショットの指揮」として書く
- 構造: **[Camera] + [Subject/Object] + [Action] + [Environment] + [Lighting] + [Lens] + [Mood]**
- 「single take」「real time」等の連続性指定を含める

#### ツール別プロンプト戦略

**Kling V3/O1:**
- 「Audio-visual choreographer（視聴覚振付師）」として扱う
- V2Vプロンプト: 「Transform the scene into [target style/environment] while maintaining the original motion and composition」
- 「maintaining the original camera movement」を明示する（省略するとモーション変化が入る）
- Elements機能で参照画像をアップロードし一貫性を確保
- 具体的に: シーン設定 → 被写体 → モーション → テクニカル詳細

**Runway Gen-4/4.5:**
- 「Kinetic sculptor（運動彫刻家）」として扱う — 物理とカメラ動作に拘る
- 「motion vectors and forces（動きのベクトルと力）」の観点で考える
- 高パフォーマンスプロンプト: camera + subject/object + action + environment + supporting details
- Structure Transformation sliderを低めに設定して構造維持

**Veo 3.1:**
- 映画のプロの語彙に最も正確に反応（ライティングデザイン、マテリアルレンダリング、構図フレーミング）
- 5要素: Camera + Subject + Action + Setting + Style & Audio
- カメラ指定: 'dolly in', 'zoom out', 'pan left', 'tilt up'
- レンズ指定: 'shallow focus', 'deep focus', 'macro lens', 'wide-angle lens'

**Pika 2.5:**
- 参照画像（Scene Ingredients）での制御が強力
- ワードローブ・小道具のプロンプトへの反応が良好

### Reference画像の効果的な使い方

- **Kling**: 正面画像 + 複数角度の参照画像（frontal_image_url + reference_image_urls）で包括的なビジュアルコンテキストを提供。最大4要素同時指定
- **Veo 3.1**: 最大3枚のリファレンス画像でスタイル・コンテンツガイド。「ingredients to video」でシーン・キャラクター・オブジェクト・スタイルの一貫性維持
- **Runway**: 入力画像をV2Vの最初のフレームとして使用。キーフレーミングで中間点も制御可能
- **Pika**: Scene Ingredientsとしてキャラクター/オブジェクトをアップロード

### ソースURL一覧

| URL | 内容 |
|-----|------|
| https://fal.ai/learn/devs/kling-2-6-pro-prompt-guide | Kling 2.6 Proプロンプトガイド |
| https://fal.ai/learn/devs/kling-o1-prompt-guide | Kling O1プロンプトガイド |
| https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-veo-3-1 | Veo 3.1公式プロンプトガイド（※WebFetchではJSのみ取得、検索結果から情報取得） |
| https://replicate.com/blog/veo-3-1 | Veo 3.1プロンプト方法（Replicate） |
| https://help.runwayml.com/hc/en-us/articles/46974685288467-Creating-with-Gen-4-5 | Runway Gen-4.5使用ガイド（※403） |
| https://www.datacamp.com/tutorial/runway-gen-4-5 | Runway Gen-4.5チュートリアル |
| https://pikaslabs.com/pika-2-5/ | Pika 2.5ガイド |

---

## Q6: 実際のワークフロー事例

### 事例1: Blender + ComfyUI + AnimateDiff パイプライン

**ソース**: RunComfy "AI Rendering 3D Animations with Blender and ComfyUI"

1. Blenderで3Dシーンを構築（カメラアニメーション含む）
2. マテリアル・テクスチャ・ライティングを除去
3. 3種のパスをレンダー:
   - Depth sequence（Z pass + Map Range正規化）
   - Outline sequence（Freestyle白線）
   - Mask sequence（オブジェクト別単色Emission）
4. ComfyUIにロード
5. ControlNet Depth + ControlNet Cannyで構造制御
6. AnimateDiffでテンポラル一貫性のある動画生成
7. Regional conditioningでオブジェクト別プロンプト適用

### 事例2: Blender → ComfyUI AI Renderer 2.0

**ソース**: RunComfy "Blender to ComfyUI AI Renderer 2.0"

1. Blenderから動画をエクスポート
2. ComfyUI Preprocessで制御タイプ（depth/canny/pose）を選択・生成
3. Z-Image-Fun ControlNet Union 2.1で複数制御を同時適用
4. Wan 2.1 VACEで最終シーケンスを合成
5. Z-Image Turboパスで単一フレームの素早いプロンプト検証

### 事例3: 3Dモデル → Meshy AI → Blender → Hailuo AI

**ソース**: Meshy Blog

1. Meshy AIで3D要素を生成
2. Blenderでカスタム3D環境を構築
3. Hailuo AIでシネマティックアニメーションに変換

### 事例4: 建築ビジュアライゼーション（Runway for Architects）

**ソース**: Archiobjects "Runway ML for architects"

1. 建築用3Dレンダリングソフト（Blender, SketchUp等）で静止画レンダー
2. Runwayにアップロード
3. テキストプロンプトでカメラ動き・雰囲気を記述
4. Gen-3 Alpha / Gen-4で動画生成
5. 用途: プロジェクトアニメーション、航空ビュー、環境探索（朝光vs夕日）、SNSプロモーション

**注意点**: 「results aren't always predictable」「physics errors occur」「loss of important architectural details in complex scenes」

### 事例5: ArchiVinci（建築特化パイプライン）

**ソース**: ArchiVinci

1. SketchUp/Revit/Blender等から3Dモデルスクリーンショットをアップロード
2. AIがControlNetガイドでフォトリアリスティック画像を生成
3. Cinematic Droneモーションプリセットで動画化
4. テクスチャ・マテリアル・ライティングの詳細は自動保持

### 事例6: Luma AI / Mago Studio（スタイルトランスファー）

**ソース**: Luma Labs, Mago Studio

- Luma AI V2V: 実写/3DアニメーションをStylized formatに変換（アニメ、シネマティック3D等）、モーション・ライティング・シーン構造を保持
- Mago Studio: ライブアクション→3Dアニメーション変換、キャラクター一貫性・ライティングロジック・ショット間一貫性を維持
- 「playblasts to final shots」のフィードバックループ短縮に活用

### ソースURL一覧

| URL | 内容 |
|-----|------|
| https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui | Blender+ComfyUI+AnimateDiffパイプライン詳細 |
| https://www.runcomfy.com/comfyui-workflows/blender-to-comfyui-ai-renderer-2-0-workflow-cinematic-video-output | Blender→ComfyUI Renderer 2.0 |
| https://www.meshy.ai/blog/3d-modeling-and-animation | Meshy+Blender+Hailuo AIワークフロー |
| https://www.archiobjects.org/runway-ml-for-architects-ai-video-generator-and-much-more/ | Runway ML建築活用事例 |
| https://www.archivinci.com/ | ArchiVinci建築AI |
| https://rendair.ai/blog/3d-model-to-cinematic-video | Rendair AI 3Dモデル→動画ワークフロー |
| https://lumalabs.ai/video-to-video | Luma AI V2Vスタイルトランスファー |
| https://www.mago.studio/ | Mago Studio 3Dアニメーション変換 |
| https://mnml.ai/ | mnml.ai 建築AIレンダリング |
| https://www.fenestra.app/solutions/ai-architectural-animation-generator | Fenestra建築アニメーション生成 |

---

## 総合まとめ: 推奨パイプライン

### パイプラインA: 最大制御（ComfyUI経由）

```
Blender (構造パスのみ)
├── Depth sequence (16-bit PNG / EXR)
├── Edge sequence (Freestyle)
└── Mask sequence (単色Emission)
    ↓
ComfyUI
├── ControlNet Depth + Canny
├── Regional conditioning (マスク色別プロンプト)
├── AnimateDiff (テンポラル一貫性)
└── Upscaler (Topaz等)
    ↓
最終動画
```

**テクスチャ設定**: マテリアル除去。マスク用単色Emissionのみ。
**長所**: 完全な構造制御、オブジェクト別プロンプト
**短所**: セットアップ複雑、ローカルGPU必要

### パイプラインB: 高速ワークフロー（商用V2V）

```
Blender (フルPBRレンダー)
├── Cycles 256-1024 samples + Denoising
├── PBR materials (Roughnessにノイズ追加)
├── HDRI + 3点ライティング
└── ソフトシャドウ + AO有効
    ↓
MP4/MOV 出力 (H.264, 1080p)
    ↓
Kling O1 / Runway Gen-4 / Veo 3.1
├── V2V mode (構造保持設定)
├── プロンプト: Camera + Subject + Action + Environment + Lighting
└── Reference images (スタイル一貫性)
    ↓
最終動画
```

**テクスチャ設定**: フルPBR。「CG look」排除のためRoughnessに5-10%ノイズ。不完全さ追加。
**長所**: シンプル、高速、直感的
**短所**: 構造制御が間接的、AIの解釈に依存

### ツール選択ガイド

| 目的 | 推奨ツール |
|------|-----------|
| マテリアル品質重視 | Kling V3/O1（glass, metal, fabricに強い） |
| カメラ制御重視 | Runway Gen-4.5（Motion Brush、キーフレーミング） |
| 映画的プロンプト制御 | Veo 3.1（映画語彙への反応が最良） |
| 建築ウォークスルー | Runway Gen-4 / Fenestra / ArchiVinci |
| 完全な構造制御 | ComfyUI + ControlNet（Depth/Normal/Canny） |
| クリエイティブエフェクト | Pika 2.5（Pikaswaps, Pikaffects） |
