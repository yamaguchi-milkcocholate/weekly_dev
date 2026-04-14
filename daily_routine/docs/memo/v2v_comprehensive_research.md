# V2V（Video-to-Video）3DCG→フォトリアル変換 包括的調査レポート

調査日: 2026-04-08

## 調査目的

Kling V3 Omni以外のV2V手法を広範囲に調査し、3DCGレンダリング（Blender）からフォトリアルなインテリアウォークスルー動画への変換に最適な手法を特定する。

---

## 1. ツール/手法別 詳細レビュー

### 1.1 Runway Gen-4 / Gen-4.5

**概要**: 2025年3月リリースのGen-4、2025年12月のGen-4.5。商用V2Vプラットフォームの最有力候補。

**3DCG→フォトリアル変換の実績**:
- KPF（建築事務所）がRunwayを使用して建築プロジェクトのアニメーション化を内製化した実績あり
- Gen-4は空間理解が大幅に向上し、異なるカメラアングル・照明条件でも一貫した環境を維持
- 4K解像度出力対応（Gen-3は1080pまで）

**構図・カメラパス維持の精度**: 高い。Temporal Attention Layerにより、フレームN がフレームN-1のコンテキストを認識し、フリッカーを防止。Advanced Camera Controlsで方向・強度の設定が可能。

**V2V機能の詳細**:
- テキストプロンプトまたは入力画像を使って動画のスタイルを変更
- Motion Brush: 動画内の特定領域の動きを制御
- Keyframe制御: 開始/終了フレーム指定が可能

**インテリア・建築での使用事例**: KPFによる建築ビジュアライゼーション。ただしV2Vで3Dレンダリングを直接入力した公開事例は限定的。

**長所**:
- 最もクリーンな出力品質、ディテールが最も精細
- プロフェッショナルなプロダクションパイプラインとの統合
- キャラクター一貫性ワークフロー
- 参照画像ベースの連続性制御

**短所**:
- 動画長が最大10秒と短い
- 料金が高い（$0.05/credit、Standard 10秒で$1.00）
- 3DCGレンダリング入力に特化した機能はない
- ControlNet的な構造制御なし（入力動画のスタイル変換のみ）

**フレーム間一貫性**: Temporal Attention Layerで良好。ただしスタイル変換の強度が高いと構造が崩れる場合あり。

**参考料金**: Standard $0.25/10s、Pro $0.50/10s

---

### 1.2 Pika Labs (Pika 2.2)

**概要**: 2025年にPika 2.2をリリース。10秒生成、1080p、キーフレーム遷移、Pikaframes機能を搭載。

**3DCG→フォトリアル変換の実績**: 3DCG入力に特化した公開事例は少ない。主にクリエイティブ・ソーシャルメディア向け。

**構図・カメラパス維持の精度**: 中程度。背景置換、オブジェクト追加、スタイル変換が主な機能で、構造厳密な維持は不得意。

**V2V機能の詳細**:
- 参照画像+テキストプロンプトで動画のスタイル変換
- 背景置換、オブジェクト追加
- Diffusion model + GAN + 3D Conv + Transformerベースのtemporal modeling

**インテリア・建築での使用事例**: 建築特化の事例は確認できず。

**長所**:
- 高速・低コスト
- テンプレート・エフェクトが豊富
- ソーシャルメディア向けコンテンツに最適

**短所**:
- 最大4秒と非常に短い
- スタイライズドな結果になりがち
- 構造維持の精度がRunway・Klingに劣る
- 建築・インテリア特化機能なし

**フレーム間一貫性**: アーティファクトが時折発生。品質はRunway・Klingに劣る。

---

### 1.3 Luma Dream Machine / Ray3

**概要**: 2025年リリースのRay3は世界初の「推論型（reasoning）」動画モデル。物理的に正確な動画生成が可能。

**3DCG→フォトリアル変換の実績**: 3D空間認識が最も優れたモデルの一つ。深度認識型のV2Vで、角度変更時もモーション・照明・空間一貫性を維持。

**構図・カメラパス維持の精度**: 非常に高い。Ray3は3D空間と物理法則を理解しており、他のモデルが「次のフレームを推測」するのに対し、空間構造を理解した上で生成する。

**V2V機能の詳細**:
- Ray3 Modify（2025年12月）: 開始/終了フレーム制御をV2Vワークフローに初導入
- 遷移制御、キャラクター行動制御、空間連続性の維持
- 長いカメラ移動パス、リビール、複雑なシーンブロッキングに対応

**インテリア・建築での使用事例**: 3D空間認識と照明理解が強いため、建築ウォークスルーとの相性は理論上良好。ただし建築特化の公開事例は限定的。

**長所**:
- 3D空間認識・物理法則理解が最も優れている
- 照明と空間一貫性が高い
- Ray3 Modifyの開始/終了フレーム制御が長尺ウォークスルーに有効
- 自然で滑らかなカメラモーション

**短所**:
- V2Vでの3Dレンダリング入力に関する公開事例が少ない
- 構造制御（ControlNet的な機能）がない
- 商用サービスのため費用がかかる

**フレーム間一貫性**: Ray3の推論能力により、最も自然な時間的一貫性を実現。

---

### 1.4 Google Veo 2 / Veo 3

**概要**: Veo 2（2024年12月）は4K対応、Veo 3（2025年5月）は同期音声生成、Veo 3.1（2025年10月）はマルチモーダル入力対応。

**3DCG→フォトリアル変換の実績**: スタイル参照画像によるスタイル適用が可能。写実的シネマトグラフィー、アニメーション、絵画的スタイル等に対応。

**V2V対応状況**:
- Veo 3.1でスタイル転写機能を含む高度な編集ツールを追加
- 複数の参照画像、動画フレーム、キーフレームのアップロードに対応
- ただし、専用のV2V APIとしての提供は他社より遅れている

**長所**:
- Googleの大規模インフラによる高品質生成
- マルチモーダル入力（参照画像+動画フレーム+テキスト）
- 音声同期生成（Veo 3）

**短所**:
- V2V機能としての成熟度はRunway・Klingに劣る
- APIアクセスが限定的
- 3DCG入力に特化した機能やガイダンスなし

---

### 1.5 ComfyUI + AnimateDiff + ControlNet

**概要**: オープンソースのV2Vパイプライン。ControlNetで構造制御、AnimateDiffで時間的一貫性、IPAdapterでスタイル転写を組み合わせる。

**3DCG→フォトリアル変換の実績**: 3DCGとの相性が最も良い手法の一つ。3Dレンダリングからdepth/canny/normalを抽出し、ControlNetの条件入力として使用することで、構造を完全にロックしながらスタイルを変換できる。

**ワークフロー構成**:
```
Blender → depth map/canny edge/normal map書き出し
    ↓
ComfyUI:
  1. 動画フレーム抽出 + 背景除去
  2. ControlNet（depth + canny or line art）で構造ガイド
  3. AnimateDiff（temporal difference model）で滑らかな時間遷移
  4. IPAdapter で参照画像からスタイル転写
  5. 多段アップスケール（モデルベース + 従来手法）
  6. フレーム補間
```

**ControlNet条件の種類**:
| 条件タイプ | 用途 | 建築パースでの有効性 |
|-----------|------|---------------------|
| Canny | 輪郭・開口部形状保護 | 高（窓・ドアの形状維持） |
| Depth | スケール感・空間関係 | 非常に高（奥行き感の維持） |
| Normal | 法線方向・表面角度 | 高（壁面の方向性維持） |
| MLSD | 直線構造 | 非常に高（建築の直線保持） |
| Segmentation | セマンティック分割 | 高（壁/床/天井の識別） |

**パラメータ例**:
- denoise strength: 0.20〜0.35（構造保持を重視する場合）
- ControlNet weight: 0.7〜1.0
- AnimateDiff context length: 16フレーム
- 100フレーム以上は分割レンダリング推奨

**長所**:
- 構造制御の精度が最も高い（ControlNetによるピクセルレベルの制御）
- 完全にローカル実行可能
- 無料（GPU必要）
- カスタマイズ性が非常に高い
- LoRA併用で特定スタイルの再現が可能

**短所**:
- セットアップの複雑さ（ノード接続、モデル管理）
- 長尺動画のレンダリングに時間がかかる
- 100フレーム以上の一括処理でシステムが不安定
- AnimateDiffのモーション品質は商用サービスに劣る
- VRAM 12GB以上推奨

**フレーム間一貫性**: AnimateDiffのtemporal modelingで一定の一貫性を確保するが、長尺での一貫性は課題。分割レンダリング時のセグメント間接合にも注意が必要。

---

### 1.6 ComfyUI + Wan2.1/2.2 VACE（最重要候補）

**概要**: Alibaba開発のWan2.1（2025年2月）、Wan2.2（2025年7月）。Apache 2.0ライセンスのオープンソースV2Vモデル。14Bパラメータの高品質バージョンと1.3Bの軽量バージョン。VACE（Video-Aware Composable Editing）により、柔軟なV2V編集が可能。

**3DCG→フォトリアル変換の実績**: VACEモデルは入力動画＋参照スタイル画像から、視覚特性を反映した完全再レンダリング動画を出力可能。ControlNet的な条件入力（Depth, Canny, OpenPose, MLSD）にも対応。

**ワークフロー構成（Blender to ComfyUI AI Renderer 2.0）**:
```
Track 1: Preprocess（制御動画の生成）
  Blender出力 → Depth Anything V2/Canny/OpenPose → 制御動画シーケンス

Track 2: AI Renderer 2.0（Wan2.1 VACE 14Bベース）
  制御動画 + 参照スタイル画像（最大3枚） → Wan2.1 VACE → フォトリアル動画

補助: Z-Image Turbo path（単一フレームでの高速イテレーション）
```

**必要モデル**:
- `wan2.1_vace_14B_fp16.safetensors`（メインモデル）
- `umt5_xxl_fp8_e4m3fn_scaled.safetensors`（テキストエンコーダ）
- `wan_2.1_vae.safetensors`（VAE）
- `Depth Anything 3 DA3-BASE`（深度推定）
- Z-Image Turbo（単一フレーム拡散）

**前処理オプション**:
- CannyEdgePreprocessor: エッジ検出
- DepthAnything_V2: 深度推定
- OpenPose: 人体ポーズ検出
- MLSD: 直線検出

**Wan2.2の追加改善**:
- Mixture-of-Experts（MoE）アーキテクチャ: 高ノイズ専門家（初期=構造レイアウト）+ 低ノイズ専門家（後期=ディテール精緻化）
- 映画的要素の統合: ライティング、カラーグレーディング、カメラ言語
- Pose/Depth/MLSD/Canny/Trajectory制御対応
- 720P出力（14Bバージョン）

**長所**:
- オープンソース（Apache 2.0）でローカル実行可能
- ControlNet的な条件入力で構造を厳密に制御可能
- 参照スタイル画像による柔軟なスタイル転写
- ComfyUIのネイティブサポート（ワークフローテンプレートあり）
- Z-Image Turbo pathで単一フレームの高速イテレーションが可能
- Wan2.2のMoEアーキテクチャで構造+ディテールの両立

**短所**:
- 14Bモデルは大量のVRAMが必要（24GB以上推奨）
- セットアップの複雑さ（モデルダウンロード、ノード構成）
- 720Pが最大解像度（アップスケール必要）
- 長尺動画の処理には時間がかかる

**フレーム間一貫性**: VACEモデルは動画全体をコンテキストとして認識するため、フレーム間の一貫性が高い。制御動画（depth/canny）による構造ロックも一貫性向上に寄与。

---

### 1.7 Deforum

**概要**: Stable Diffusionのimg2img機能を利用してフレームシーケンスを生成し、動画化するオープンソースツール。2D/3Dモードで深度ワーピングを使用。

**3DCG→フォトリアル変換の実績**: 3Dモードで深度ワーピング（MiDaS/AdaBins使用）を使い、コヒーレントな出力を生成。ただしフレーム間の一貫性は限定的。

**長所**:
- フリー・オープンソース
- 2D/3Dモード切替可能
- ComfyUIノードとして統合可能（2025年更新）

**短所**:
- フレーム間のフリッカーが深刻
- 最新のV2Vモデル（Wan2.1等）に品質で大きく劣る
- 建築・インテリアでの実用性は低い
- 開発が活発でなくなりつつある

**評価**: 2025-2026時点では旧世代の手法。Wan2.1/AnimateDiffに置き換えられつつある。

---

### 1.8 EbSynth / EbSynth V2

**概要**: ニューラルネットワークを使わない、example-based synthesis（EBS）アルゴリズムによるスタイル伝播ツール。キーフレームのスタイルを動画全体に伝播する。2025年9月にV2リリース。

**3DCG→フォトリアル変換の実績**: Blender Cyclesでレンダリングした1フレームをスタイル化し、残りのフレームにスタイルを伝播する手法が確立されている。

**ワークフロー構成（Stable Diffusion + EbSynth）**:
```
1. 入力動画をフレーム分解
2. キーフレーム（例: 10フレームごと）をStable Diffusion + ControlNetでスタイル変換
3. 変換済みキーフレームをEbSynthに入力
4. EbSynthが中間フレームにスタイルを伝播
5. フレームを動画に再結合
```

**EbSynth V2の新機能（2025年9月）**:
- リアルタイムプレビュー
- タイムラインインターフェース
- レイヤーサポート
- ブラシツールによるリタッチ

**長所**:
- ニューラルネットワーク不要（GPU不要でも動作）
- キーフレーム間のスタイル一貫性が非常に高い
- 処理速度が速い
- V2でプロダクション向けワークフロー強化

**短所**:
- 大きな動きやオクルージョンでゴースティングが発生
- キーフレームのスタイル品質に完全に依存
- キーフレーム間の間隔が大きいとアーティファクト発生
- 生成型AIではないため、存在しないディテールの追加は不可
- 建築ウォークスルーのような連続的なカメラ移動では限界あり

**フレーム間一貫性**: キーフレーム近傍では非常に高い。キーフレームから離れるほど品質が低下。

---

### 1.9 Neural Style Transfer（古典的手法）

**概要**: Gatys et al. (2015) 以来の古典的ニューラルスタイル転写を動画に応用する手法。

**動画応用の課題**:
- フレーム単位で適用するとフリッカーが深刻
- オプティカルフローで時間的一貫性を確保する手法（Ruder et al.）が提案されたが、大きな動きやオクルージョンでゴースティング発生
- 最新のアプローチはオプティカルフローに頼らず、時空間ニューラルネットワークで暗黙的にモーションを学習

**最新動向（2025）**:
- StyDiff: 拡散モデルベースのスタイル転写。SSIM/LPIPS で従来手法を上回る
- PMBNet: Progressive Multi-Branch構造でフリッカーを低減
- PickStyle: Context-Style Adaptersで時間的一貫性を確保しつつスタイル適用
- 強化学習ベースのスタイル転写（Stanford CS224R研究）

**評価**: 学術的には進展があるが、実用的にはWan2.1 VACE等のモデルに統合される形で発展。単体での使用は推奨しない。

---

### 1.10 ReRender A Video

**概要**: SIGGRAPH Asia 2023論文。ControlNet + Stable Diffusion + GMFlow + EbSynthを組み合わせたゼロショットV2V変換フレームワーク。

**ワークフロー（3ステップ）**:
```
Step 1: 最初のキーフレームをリレンダリング
Step 2: 全キーフレームを階層的クロスフレーム制約でリレンダリング
Step 3: patch-basedブレンディングで全フレームに伝播
```

**長所**:
- 再学習・最適化不要（ゼロショット）
- ControlNet/LoRAとの互換性あり
- グローバルスタイル + ローカルテクスチャの時間的一貫性を低コストで実現
- オープンソース（GitHub公開）

**短所**:
- Stable Diffusion 1.5ベースで品質に限界
- 最新モデル（Wan2.1等）と比較すると品質が劣る
- 大きなカメラ移動での破綻
- 建築特化のチューニングなし

**評価**: 2023年時点では先進的だったが、2025-2026年ではWan2.1 VACE等に品質で劣る。ただしアプローチ（キーフレームレンダリング + 伝播）は有効な考え方。

---

### 1.11 Rendair AI

**概要**: 建築・インテリアに特化したAIレンダリングプラットフォーム。50万ユーザー以上。

**機能**:
- Sketch to Render: 2Dスケッチからフォトリアルレンダリング
- 3D Base to Render: 3Dモデルのスクリーンショット/ビューポート出力をフォトリアルに変換
- Inpaint: マテリアル変更等の部分修正
- 4Kアップスケール
- Video Generation: 静止レンダリングから動画ウォークスルー生成

**3DCG→フォトリアル変換のワークフロー**:
```
1. Blender/SketchUp等でビューポートスクリーンショットを取得
2. Rendair「3D Base to Render」にアップロード
3. テキストプロンプトで雰囲気・素材・照明を指定
4. AIがフォトリアルレンダリングを生成
5. （オプション）複数パースを動画にマージ
```

**料金**: Creator $15/月（500クレジット、25動画レンダー）

**長所**:
- 建築・インテリアに完全特化
- 直感的なUI
- 3Dモデルからの直接変換に最適化
- 低コスト

**短所**:
- V2Vとしてはフレーム単位の変換の印象（連続動画の一貫性は不明）
- APIアクセスが限定的（パイプライン統合が困難）
- 動画品質はKling/Runway等に劣る可能性
- カスタマイズ性が低い

---

### 1.12 StreamDiffusion / Daydream Scope

**概要**: リアルタイム拡散生成パイプライン。StreamDiffusionV2はMLSys 2026に採択。Daydream Scopeはリアルタイムワークフローの開発環境。

**性能**:
- RTX 4090 + TensorRT: StreamDiffusionV2で58-64 FPS
- 初回フレーム: 0.5秒以内
- SDXL対応（2025年11月）
- IPAdapter Standard（スタイル制御）、IPAdapter FaceID（キャラクター制御）対応

**リアルタイム変換の実用性**:
- ライブストリーミング向けに最適化
- 5つの自己回帰型パイプラインをサポート（StreamDiffusion V2, LongLive, Krea Realtime, RewardForcing, MemFlow）
- Krea Realtimeが最もフォトリアルな結果、StreamDiffusion V2がバランス最良

**長所**:
- リアルタイム処理（インタラクティブプレビューに最適）
- オープンソース
- 複数パイプラインの選択肢

**短所**:
- リアルタイム性に最適化されており、品質はオフライン処理に劣る
- 建築・インテリア特化のチューニングなし
- 高性能GPU必要（H100×4で最高性能）
- 長尺の一貫性維持は課題

**本プロジェクトへの適用**: リアルタイムプレビュー用途なら有効。最終出力用途には品質不足。

---

### 1.13 Unreal Engine 5 + AI

**概要**: UE5のNanite/Lumenによるリアルタイムレンダリングをベースに、AI動画生成モデル（Flux Pro/Runway Gen-4等）と組み合わせるパイプライン。

**ワークフロー**:
```
UE5でシーン構築（Nanite + Lumen）
  ↓
カメラパスを設定してレンダリング
  ↓
出力動画をRunway Gen-4/Flux Pro等でスタイル変換
  ↓
フォトリアル動画出力
```

**長所**:
- UE5のリアルタイムレンダリングで高品質なベース素材を生成
- Nanite/Lumenにより既にフォトリアルに近いベースが得られる
- MetaHuman Animator 2.0でリアルタイム顔アニメーション
- 業界予測: 2027年までに高級商業制作市場の40%を獲得

**短所**:
- UE5の学習コスト・セットアップコストが非常に高い
- Blenderとのワークフロー統合が困難
- 本プロジェクトのBlenderベースパイプラインとの互換性が低い

**評価**: 本プロジェクトへの直接適用は困難だが、将来的な選択肢として注視。

---

### 1.14 Blender + ComfyUI統合パイプライン

**概要**: 本プロジェクトに最も直接的に適用可能なパイプライン。Blenderで3Dシーンを構築・レンダリングし、ComfyUIでAIによるフォトリアル変換を行う。

**NVIDIAの推奨パイプライン（CES 2026発表）**:
```
Blueprint 1: 3Dオブジェクト生成（アセット作成）
Blueprint 2: 3Dガイド付き画像生成（Blenderでシーン設定 → フォトリアルキーフレーム生成）
Blueprint 3: 動画生成（開始/終了キーフレームで動画生成 + RTX Videoで4Kアップスケール）
```

使用モデル: LTX-2（Lightricks）、最大20秒の4K動画生成。

**Blender to ComfyUI AI Renderer 2.0ワークフロー**:
```
Preprocess Track:
  Blender出力 → Depth Anything 3 / Canny / OpenPose → 制御動画

AI Renderer Track（Wan2.1 VACE 14B = SkyReels V3 R2Vマージ）:
  制御動画 + 参照スタイル画像（最大3枚） → フォトリアル動画

Z-Image Turbo Path（補助）:
  単一フレームでの高速イテレーション → スタイル確認
```

**長所**:
- 本プロジェクトのBlenderパイプラインに直接統合可能
- Wan2.1 VACE + ControlNet条件でstructure-awareな変換
- Z-Image Turbo pathで迅速なスタイルイテレーション
- 参照スタイル画像の複数指定でスタイル一貫性を向上

**短所**:
- セットアップの複雑さ
- 高性能GPU必要
- 長尺動画の分割処理が必要

---

### 1.15 LivePortrait

**概要**: Kuaishou（快手）開発のポートレートアニメーションフレームワーク。暗黙的キーポイントベースのアプローチで、計算効率と制御性のバランスを実現。

**性能**: RTX 4090で12.8ms/フレーム。リアルタイム処理可能。

**本プロジェクトへの適用**: ポートレート/顔アニメーションに特化しており、建築インテリアのV2V変換には不向き。対象外。

---

## 2. 3DCG→フォトリアル変換に最適な手法のランキング

### Tier 1: 最有力候補（本プロジェクトに推奨）

| 順位 | 手法 | 総合スコア | 構造維持 | 品質 | 実装容易性 | コスト |
|------|------|----------|---------|------|----------|--------|
| 1 | **ComfyUI + Wan2.1/2.2 VACE** | ★★★★★ | ★★★★★ | ★★★★ | ★★★ | ★★★★★ |
| 2 | **Kling V3 Omni V2V（現行）** | ★★★★ | ★★★★ | ★★★★★ | ★★★★★ | ★★★ |
| 3 | **Blender→ComfyUI Renderer 2.0** | ★★★★ | ★★★★★ | ★★★★ | ★★ | ★★★★★ |

### Tier 2: 有力な代替手段

| 順位 | 手法 | 総合スコア | 構造維持 | 品質 | 実装容易性 | コスト |
|------|------|----------|---------|------|----------|--------|
| 4 | Runway Gen-4/4.5 V2V | ★★★★ | ★★★ | ★★★★★ | ★★★★ | ★★ |
| 5 | Luma Ray3 Modify | ★★★★ | ★★★★ | ★★★★ | ★★★★ | ★★ |
| 6 | ComfyUI + AnimateDiff + ControlNet | ★★★ | ★★★★★ | ★★★ | ★★ | ★★★★★ |

### Tier 3: 補助的・限定的用途

| 順位 | 手法 | 用途 |
|------|------|------|
| 7 | EbSynth V2 | キーフレーム伝播の補助ツールとして |
| 8 | Rendair AI | 静止画レンダリングの迅速なプロトタイピング |
| 9 | Google Veo 3.1 | 将来的なV2V機能の成熟を待つ |
| 10 | ReRender A Video | アプローチ参考（キーフレーム+伝播の考え方） |

### Tier 4: 非推奨（本プロジェクトの用途では）

| 手法 | 理由 |
|------|------|
| Pika Labs | 4秒制限・構造維持が弱い |
| Deforum | 旧世代、品質不足 |
| StreamDiffusion | リアルタイム向け、オフライン品質不足 |
| Neural Style Transfer（古典的） | 最新手法に統合済み |
| LivePortrait | ポートレート特化、建築に不適 |
| UE5 + AI | Blenderパイプラインとの互換性なし |

---

## 3. 構図維持の精度比較

| 手法 | 構図維持方式 | 構図維持精度 | 備考 |
|------|------------|-----------|------|
| **ComfyUI + Wan2.1 VACE (Depth)** | Depth map条件入力 | ★★★★★ | 3Dシーンから直接depth exportが可能で最も精密 |
| **ComfyUI + ControlNet (MLSD+Depth)** | 複数ControlNet条件 | ★★★★★ | 複数条件の組み合わせで建築に最適 |
| **Kling V3 Omni (base)** | 入力動画のモーション維持 | ★★★★ | cfg_scale 0.5-0.8で調整可能。構造は概ね維持するが、ピクセルレベルの制御は不可 |
| **Runway Gen-4** | Temporal Attention Layer | ★★★☆ | スタイル変換強度が高いと構造が崩れる場合あり |
| **Luma Ray3** | 3D空間推論 | ★★★★ | 物理的整合性は高いが、入力構造の厳密な再現は保証されない |
| **EbSynth** | テクスチャ合成伝播 | ★★★★ | キーフレーム近傍は高精度、距離が離れると低下 |
| **ReRender A Video** | GMFlow + ControlNet | ★★★ | 大きなカメラ移動で破綻しやすい |

**結論**: 3DCGレンダリングからの変換では、**Blenderから直接depth map/canny edgeを書き出せる**ことが最大の強み。このデータをControlNet条件として使えるComfyUI系のパイプライン（Wan2.1 VACE / AnimateDiff）が構図維持で圧倒的に有利。

---

## 4. 推奨ワークフロー（本プロジェクトへの適用案）

### 案A: Wan2.1 VACE + Blenderパイプライン統合（最推奨）

Kling V3 Omni V2Vの代替として、ComfyUI + Wan2.1 VACEを導入する案。

```
[Phase 1: Blenderレンダリング（既存パイプライン）]
  scene.blend → Cyclesレンダリング → カメラカット動画（cut_*.mp4）
  追加: depth pass / canny edge pass も同時書き出し

[Phase 2: スタイルイテレーション（新規）]
  Z-Image Turbo path で単一フレームのスタイルを確認
  参照スタイル画像を選定（最大3枚）
  プロンプトを調整

[Phase 3: V2V変換（ComfyUI）]
  制御動画（depth/canny） + 参照スタイル画像 + プロンプト
    → Wan2.1 VACE 14B
    → フォトリアル動画出力（720P）

[Phase 4: 後処理]
  RTX Video / Real-ESRGAN で4Kアップスケール
  ffmpegで最終動画結合
```

**メリット**:
- 構造維持が最も確実（Blender直接書き出しのdepth/canny使用）
- ランニングコストゼロ（ローカル実行）
- スタイル制御の自由度が高い
- Kling V3 Omniで課題だった「天井が空になる」問題をdepth条件で回避可能

**デメリット**:
- 初期セットアップの工数
- 高性能GPU必要（VRAM 24GB+推奨）
- 長尺動画の処理時間

### 案B: ハイブリッド方式（推奨）

KlingとWan2.1 VACEを使い分ける方式。

```
[迅速なプロトタイピング]
  Kling V3 Omni V2V（現行パイプライン）
  → 高速にフォトリアル動画を確認
  → クライアントへの初回提示用

[品質が求められる最終出力]
  ComfyUI + Wan2.1 VACE（depth/canny条件付き）
  → 構造維持を厳密に制御
  → スタイル参照画像で統一感を確保
  → 4Kアップスケールで最終品質

[特定カットの品質追求]
  Runway Gen-4/Luma Ray3 で特定カットのみ再生成
  → 商用V2Vの高品質出力を活用
```

**メリット**:
- 用途に応じて最適な手法を選択
- Kling V3 Omni の高速性を活かしつつ、品質が必要な場面ではWan2.1 VACEを使用
- リスク分散（単一ツールへの依存を回避）

### 案C: Kling V3 Omni V2V最適化（保守的）

現行パイプラインを維持しつつ、既知の課題を改善する案。

```
[改善1: Blender側のテクスチャヒント強化]
  既存の調査（kling_v2v_3dcg_optimization.md）に基づき、
  素材の種類が判別できる程度のテクスチャヒントを追加

[改善2: マルチアングル事前スタイル確認]
  Gemini 3.0 Pro Image（既存の3dcg-style-applyスキル）で
  各カメラアングルのスタイルを事前確認

[改善3: cfg_scale調整]
  構造が崩れるカットのcfg_scaleを0.7-0.8に上げる
```

---

## 5. 3DCG→AI補助ワークフローの原則（PERSC JOURNAL参照）

日本語の建築ビジュアル制作記事から抽出した重要な設計原則:

### 基本原則: 「正確さが必要な工程は3DCG、雰囲気が必要な工程はAI」

- **3DCGの担当**: 寸法・構図・ライティングの確定
- **AIの担当**: 質感・演出・バリエーション生成

### 最適なインプット: 「構図とライティングが正しい60点の画像」

- フラットすぎず、リアルすぎず
- AIが「何を塗り替えるべきか」を認識できる程度の情報量

### 建築パースに有効なControlNet条件

| 条件 | 用途 | 建築での重要度 |
|------|------|-------------|
| Canny | 開口部・建具の形状保護 | 高 |
| Depth | スケール感・空間関係の維持 | 非常に高 |
| MLSD | 直線構造の厳密な保持 | 非常に高 |

### 主要な破綻パターンと対策

| 問題 | 対策 |
|------|------|
| 形状破綻（窓が歪む） | ControlNet edge検出で保護 |
| スケール不整合（家具が巨大化） | 正確なオブジェクト配置のラフレンダリング |
| 光環境矛盾（影の方向が逆） | IC-Light等のリライティング |
| 再現性欠如（カット間のスタイル不統一） | Seed固定 or LoRA学習 |

### 効率化の現実

- **効果が大きい**: テクスチャ調整、バリエーション生成（半日→数分）
- **効果が限定的**: モデリング、カメラ設定等の基盤工程
- **「修正ガチャ」回避**: 全体80点達成後に部分修正、という割り切りが重要

---

## 6. 情報源一覧

### 商用V2Vプラットフォーム
- [Runway Gen-4 Guide 2026](https://aitoolsdevpro.com/ai-tools/runway-guide/)
- [Runway Gen-4.5 紹介（Medium）](https://medium.com/@CherryZhouTech/runway-introduces-groundbreaking-gen-4-5-video-generation-model-6b664f945760)
- [Runway V2V公式ドキュメント](https://help.runwayml.com/hc/en-us/articles/33350169138323-Creating-with-Video-to-Video-on-Gen-3-Alpha-and-Turbo)
- [RunwayML Review 2025](https://skywork.ai/blog/runwayml-review-2025-ai-video-controls-cost-comparison/)
- [Luma Ray3公式](https://lumalabs.ai/ray)
- [Luma Ray3 Modify 発表](https://lumalabs.ai/news/ray3-modify)
- [Luma AI Review 2026](https://techjarvisai.com/luma-ai-review/)
- [Luma V2V公式](https://lumalabs.ai/video-to-video)
- [Pika 2.1 Review](https://www.simalabs.ai/resources/pika-2-1-review-best-1080p-ai-video-generator-2025)
- [Runway vs Kling vs Pika 比較](https://www.multic.com/guides/runway-vs-kling-vs-pika/)
- [Kling AI Review 2026](https://max-productive.ai/ai-tools/kling-ai/)

### Google Veo
- [Veo 3 解説](https://www.seeles.ai/resources/blogs/veo3-ai-video-generator)
- [Google Vids 2026 Update](https://www.veo3ai.io/blog/google-vids-2026-update-veo-3-1-ai-music-avatars)
- [Veo公式（Google DeepMind）](https://deepmind.google/models/veo/)

### ComfyUI + Wan2.1/2.2
- [Wan2.1 ComfyUI Workflow - Complete Guide](https://comfyui-wiki.com/en/tutorial/advanced/video/wan2.1/wan2-1-video-model)
- [Wan2.1 VACE ComfyUI公式ドキュメント](https://docs.comfy.org/tutorials/video/wan/vace)
- [VACE Wan2.1 V2V Workflow](https://www.runcomfy.com/comfyui-workflows/vace-wan2-1-video-to-video-workflow)
- [Wan2.1 VACE V2V解説](https://comfyui.org/en/mastering-video-to-video-translation-wan2-1)
- [Wan2.1 Video Style Transfer Guide](https://learn.thinkdiffusion.com/wan-2-1-video-style-transfer-guide/)
- [Wan2.2 GitHub](https://github.com/Wan-Video/Wan2.2)
- [Wan2.2 ComfyUI公式](https://docs.comfy.org/tutorials/video/wan/wan2_2)
- [Wan2.2 Fun VACE Style Transfer](https://www.stablediffusiontutorials.com/2025/09/wan2.2-vace-fun.html)
- [Wan2.1 VACE 14B（Hugging Face）](https://huggingface.co/Wan-AI/Wan2.1-VACE-14B)
- [Wan2.1 Fun Control Workflows](https://comfyui-wiki.com/en/tutorial/advanced/video/wan2.1/fun-control)

### ComfyUI + AnimateDiff + ControlNet
- [ComfyUI AnimateDiff and ControlNet Workflow](https://www.runcomfy.com/comfyui-workflows/comfyui-animatediff-and-controlnet-workflow-video2video)
- [Transform Videos with AnimateDiff and ControlNet](https://learn.runcomfy.com/transform-videos-with-animatediff-controlnet-in-comfyui)
- [ComfyUI-AnimateDiff-Evolved (GitHub)](https://github.com/Kosinkadink/ComfyUI-AnimateDiff-Evolved)

### Blender + ComfyUI
- [AI Rendering 3D Animations with Blender and ComfyUI](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui)
- [Blender to ComfyUI AI Renderer 2.0](https://www.runcomfy.com/comfyui-workflows/blender-to-comfyui-ai-renderer-2-0-workflow-cinematic-video-output)
- [NVIDIA RTX AI Video Generation Guide](https://www.nvidia.com/en-us/geforce/news/rtx-ai-video-generation-guide/)
- [NVIDIA RTX + LTX-2 + ComfyUI (CES 2026)](https://blogs.nvidia.com/blog/rtx-ai-garage-ces-2026-open-models-video-generation/)

### EbSynth
- [EbSynth公式](https://ebsynth.com/)
- [EbSynth GitHub](https://github.com/jamriska/ebsynth)
- [EbSynth V2リリース](https://digitalproduction.com/2025/09/24/ebsynth-v2-real-time-preview-timeline-layers/)
- [EbSynth + Stable Diffusion Tutorial](https://www.creativeshrimp.com/ebsynth-tutorial.html)
- [AI Room Makeover: ControlNet + Stable Diffusion + EbSynth](https://www.spatialintelligence.ai/p/controlling-artistic-chaos-with-controlnet)

### ReRender A Video
- [ReRender A Video (GitHub)](https://github.com/williamyang1991/Rerender_A_Video)
- [Video ControlNet論文 (arXiv)](https://arxiv.org/abs/2305.19193)

### Rendair AI / 建築特化
- [Rendair AI公式](https://rendair.ai/)
- [Rendair AI料金](https://rendair.ai/pricing)
- [Best AI Rendering Tools for Architects 2026](https://blog.chaos.com/best-ai-rendering-tools-for-architects-compared)
- [23 Best AI Rendering Software 2026](https://blog.designfiles.co/ai-rendering-software/)

### StreamDiffusion
- [StreamDiffusionV2 Project Page](https://streamdiffusionv2.github.io/)
- [Daydream Scope + StreamDiffusion SDXL](https://www.morningstar.com/news/business-wire/20251106860538/daydream-launches-scope-and-expands-streamdiffusion-with-sdxl-support-advancing-the-open-source-real-time-ai-video-ecosystem)
- [Daydream Scope Review 2026](https://topvidtools.com/2026/03/17/daydream-scope-review/)

### 3DCG→AI ワークフロー（日本語）
- [3DCG→AI補助ワークフロー（PERSC JOURNAL）](https://persc.jp/blog/3dcg-ai-workflow/)
- [生成AIでインテリア画像からウォークスルー動画自動作成（新建ハウジング）](https://www.s-housing.jp/archives/370856)
- [建築・インテリア向けAIレンダリング（GarageFarm）](https://garagefarm.net/jp-blog/ai-rendering-in-architecture-and-interior-design)

### 学術・ベンチマーク
- [VBench: Video Generation Benchmark (CVPR 2024)](https://github.com/Vchitect/VBench)
- [VBench-2.0 (2025)](https://arxiv.org/html/2503.21755v1)
- [PickStyle: V2V Style Transfer (2025)](https://openreview.net/forum?id=NRWI7NRaFD)
- [StyDiff (Scientific Reports 2025)](https://www.nature.com/articles/s41598-025-17899-x)
- [FRESCO: Zero-Shot Video Translation (CVPR 2024)](https://github.com/williamyang1991/FRESCO)

### Unreal Engine + AI
- [UE5 + AI Video Pipeline（ReelMind）](https://reelmind.ai/blog/unreal-engine-photorealistic-tutorial-bridging-game-engines-and-ai-video)
- [AI to Unreal 3D Camera Tracking](https://dev.epicgames.com/community/learning/tutorials/Zbyk/unreal-engine-metahuman-ai-to-unreal-3d-camera-tracking-generative-video)
