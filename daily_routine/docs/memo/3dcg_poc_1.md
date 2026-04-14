# PoC Step 1: 間取り図と部屋写真から3D空間データを構成できる

> [ロードマップに戻る](./roadmap.md)

## 検証目標

間取り図（2D平面図）と部屋写真（複数枚）を一括入力として、任意のカメラ位置からレンダリング可能な3D空間データを構成できる。

---

## 3D空間データとは

壁・床・天井・家具などの3D座標と形状で構成されるデータ。任意視点からのレンダリングの基盤となる。テクスチャ（素材・色・質感）は3D空間データに付随する属性情報であり、3D空間データそのものではない。

---

## 入力データ

不動産ポータルサイトから収集した同一物件の以下を一括入力する。

| データ               | 備考                                    |
| -------------------- | --------------------------------------- |
| 2D平面図             | 1枚。空間の形状・寸法・間取り構造を含む |
| 部屋写真（家具なし） | 複数枚。網羅的でない場合あり            |
| 部屋写真（家具あり） | 複数枚。網羅的でない場合あり            |

### 前提条件

- 部屋写真は網羅的でない場合がある（全方向が撮影されているとは限らない）
- 平面図と写真を補完的に使うことで、不足情報を補えるかを検証する

---

## 検証パターン

| パターン | 入力                          | 検証の目的                                                     |
| -------- | ----------------------------- | -------------------------------------------------------------- |
| A        | 平面図 + 部屋写真（家具なし） | 空間の骨格（壁・床・天井）が3D化できるか                       |
| B        | 平面図 + 部屋写真（家具あり） | 家具が写り込んでいても空間の骨格（壁・床・天井）が3D化できるか |

---

## 検証ステップ

### Step 1: 一括入力で3D空間データが構成できるか

- [ ] パターンAの入力を一括で与えて3D空間データが出力できる
- [ ] パターンBの入力を一括で与えて3D空間データが出力できる

### Step 2: 出力された3D空間データの確認

- [ ] 壁・床・天井の位置関係が平面図と概ね一致している
- [ ] 写真が網羅的でない箇所がどう補完されているか確認できる
- [ ] パターンA（家具なし）とパターンB（家具あり）の差異を確認できる

### Step 3: 次ステップへの接続確認

- [ ] 出力された3D空間データを任意のカメラ位置からレンダリングできる形式になっている

---

## 合格基準

**この段階では品質よりも「3D空間データとして成立しているか」を確認することを優先する。**

| 確認項目           | 合格の目安                             |
| ------------------ | -------------------------------------- |
| 出力の成立         | 3D空間データとして出力できる           |
| 形状の妥当性       | 空間の骨格（壁・床・天井）が概ね正しい |
| 次ステップへの接続 | レンダリング可能な形式で出力できる     |

---

## 技術調査

間取り図+部屋写真から3D空間データを構成するための技術を以下のカテゴリに分けて整理する。

### カテゴリ1: フロアプラン→3D変換（2D平面図から3D骨格を生成）

間取り図画像を入力として、壁・床・天井の3D形状を直接生成するアプローチ。

| 技術/ツール | 概要 | OSS/商用 | 入力 | 出力 | PoCへの適合度 |
|---|---|---|---|---|---|
| [FloorplanToBlender3d](https://github.com/grebtsew/FloorplanToBlender3d) | 間取り図画像からBlenderの3Dモデルを自動生成。壁・床の検出とBlender Python APIでの3D化 | OSS (MIT) | 間取り図画像 | Blender 3Dモデル | **高** - 直接的に間取り図→3D骨格を実現 |
| [CubiCasa5k](https://github.com/CubiCasa/CubiCasa5k) | 5000枚の間取り図データセット+学習済みモデル。壁・ドア・窓等80+カテゴリの検出 | OSS (データセット) / 商用 (アプリ) | 間取り図画像 | セグメンテーションマップ | **高** - FloorplanToBlender3dと組み合わせて精度向上 |
| [HouseCrafter](https://github.com/neu-vi/houseCrafter) | 間取り図から拡散モデルでマルチビューRGB-D画像を生成し3Dシーンを再構成（ICCV 2025 Highlight） | OSS | 間取り図画像 | RGB-D画像→3Dメッシュ | **最高** - 間取り図から直接3Dシーン生成。テクスチャ付き |
| [Plan2Scene](https://3dlg-hcvc.github.io/plan2scene/) | 間取り図+写真→テクスチャ付き3Dメッシュ。GNNでテクスチャ推論 | OSS（研究） | 間取り図+部屋写真 | テクスチャ付き3Dメッシュ | **最高** - 入力パターンが本PoCと完全一致 |
| [Planner 5D](https://planner5d.com/ai) | 間取り図画像をAI認識→3Dシーン自動生成 | 商用 | 間取り図画像 | 3Dモデル | 中 - 商用のため自動パイプライン統合が難しい |
| [Floor-Plan.AI](https://floor-plan.ai/floor-plan-to-3d) | AI解析で間取り図→3D変換。壁・部屋・ドア・窓を自動検出 | 商用 | 間取り図画像 | 3Dモデル | 中 - API統合の可否要確認 |
| [DeepFloorplan](https://github.com/zlzeng/DeepFloorplan) / [TF2版](https://github.com/zcemycl/TF2DeepFloorplan) | ICCV 2019。マルチタスクNNで部屋境界・部屋タイプを同時認識。TF2版はDocker/Flask対応 | OSS (MIT) | 間取り図画像 | セグメンテーション | **高** - CubiCasa5kの代替/補完として利用可能 |
| [SceneScript](https://ai.meta.com/blog/scenescript-3d-scene-reconstruction-reality-labs-research/) (Meta, ECCV 2024) | 画像/点群からAutoregressive Structured Language Modelで室内シーンをCADライクなパラメトリック言語で出力 | OSS（研究用） | 画像/点群 | 構造化シーン記述 | **高** - 編集可能な構造化出力 |
| [ARCHITECT](https://proceedings.neurips.cc/paper_files/paper/2024/file/7cdf000d22c6cda21f3cbd7467aaf26f-Paper-Conference.pdf) (NeurIPS 2024) | テキスト/間取り図から階層的・反復的にインペインティングで家具配置 | OSS（研究） | テキスト/間取り図 | 家具配置済み3Dシーン | **高** - 間取り→家具配置の段階的パイプライン |

### カテゴリ2: マルチビュー3D再構成（部屋写真→3D空間）

複数枚の室内写真から3D空間を再構成するアプローチ。

| 技術/ツール | 概要 | OSS/商用 | 必要画像枚数 | 出力 | PoCへの適合度 |
|---|---|---|---|---|---|
| [DUSt3R](https://github.com/naver/dust3r) | カメラキャリブレーション不要のEnd-to-End 3D再構成。Transformerベース | OSS (CC BY-NC-SA 4.0) | 2枚〜 | 点群 / ポイントマップ | **高** - 少数画像対応。カメラ情報不要 |
| [MASt3R](https://github.com/naver/mast3r) | DUSt3Rの発展版。メトリック3D再構成+密な特徴マッチング。5枚程度で室内再構成可能 | OSS (CC BY-NC-SA 4.0) | 5枚〜 | 点群 / 3Dメッシュ | **最高** - 少数の室内写真からの再構成に最適 |
| [MV-DUSt3R+](https://mv-dust3rp.github.io/) | DUSt3Rのマルチビュー拡張。単一ステージでシーン再構成（CVPR 2025） | OSS（研究） | 12〜20枚 | 3Dシーン | **高** - 単一部屋0.89秒で再構成 |
| [Fast3R](https://github.com/facebookresearch/fast3r) | DUSt3Rのマルチビュー一般化。N枚を1パスで処理。DUSt3R比で誤差14倍削減（CVPR 2025） | OSS (NC) | 20枚〜1500枚 | 点群 | **高** - 大量画像の高速処理 |
| [Plane-DUSt3R](https://github.com/justacar/Plane-DUSt3R) | DUSt3R派生。非ポーズ付きスパースビューからの室内レイアウト再構成 | OSS（研究） | 少数 | 室内レイアウト | **高** - 室内レイアウト特化 |
| [COLMAP](https://github.com/colmap/colmap) | SfM+MVSの定番パイプライン。高精度だが大量画像が必要 | OSS (BSD) | 20枚〜（推奨50+） | 点群 / メッシュ | 低 - 少数写真では不足。CUDA必須 |
| [Meshroom (AliceVision)](https://github.com/alicevision/Meshroom) | GUIベースのフォトグラメトリ。COLMAPと同等の能力 | OSS (MPL2) | 20枚〜 | テクスチャ付きメッシュ | 低 - 大量画像が前提 |

### カテゴリ3: NeRF / 3D Gaussian Splatting（写真→新視点合成）

写真群から暗黙的3D表現を学習し、任意視点からのレンダリングを可能にするアプローチ。

| 技術/ツール | 概要 | OSS/商用 | 必要画像枚数 | 出力 | PoCへの適合度 |
|---|---|---|---|---|---|
| [Nerfstudio](https://docs.nerf.studio/) | NeRF/3DGSの統合フレームワーク。Splatfacto等の手法を統一的に利用可能 | OSS | 50枚〜（推奨） | NeRF / Gaussians | 中 - 大量画像が理想。室内は苦手 |
| [gsplat](https://github.com/nerfstudio-project/gsplat) | CUDA高速化されたGaussian Splatting。Nerfstudioのバックエンド | OSS | 50枚〜 | 3D Gaussians | 中 - 少数画像では品質低下 |
| [IndoorGS](https://cvpr.thecvf.com/virtual/2025/poster/33248) | 室内シーン特化のGaussian Splatting。2D線分を3D線分キューに変換して幾何構造を補強（CVPR 2025） | OSS（研究） | 数十枚 | 3D Gaussians | 中 - 室内特化だが依然大量画像が必要 |
| [InstantSplat](https://instantsplat.github.io/) | DUSt3Rで初期化→Gaussian Splattingで最適化。少数画像対応 | OSS（研究） | 少数（〜12枚） | 3D Gaussians | **高** - DUSt3Rとの組み合わせで少数画像に対応 |

### カテゴリ4: 単眼深度推定 + 3D変換（写真→深度→メッシュ）

単一画像から深度マップを推定し、3Dメッシュに変換するアプローチ。

| 技術/ツール | 概要 | OSS/商用 | 入力 | 出力 | PoCへの適合度 |
|---|---|---|---|---|---|
| [Depth Anything v2](https://github.com/DepthAnything/Depth-Anything-V2) | 高速・高精度な単眼深度推定。Marigoldの10倍高速。公式に`depth_to_pointcloud.py`同梱 | OSS (Small: Apache 2.0, Base以上: CC BY-NC-4.0) | 単一画像 | 深度マップ | **高** - 各写真の深度を高速推定。Smallモデルなら商用可 |
| [Marigold](https://github.com/prs-eth/Marigold) | Stable Diffusion由来の拡散モデル深度推定。ディテール精度が高い（CVPR 2024 Oral）。v1.1で法線推定も追加 | OSS (Apache 2.0) | 単一画像 | 深度マップ+法線 | **高** - 精密な深度推定。商用利用可 |
| [Metric3D v2](https://github.com/YvanYin/Metric3D) | メトリック（絶対スケール）深度+表面法線を同時推定。実寸法で3D化可能 | OSS (BSD) | 単一画像 | メトリック深度マップ+法線 | **高** - 実寸法取得で間取り図との統合に有利 |
| [Depth Pro](https://machinelearning.apple.com/research/depth-pro) (Apple) | カメラ内部パラメータ不要のメトリック深度推定 | OSS | 単一画像 | メトリック深度マップ | **高** - キャリブレーション不要で絶対スケール |
| [depth_to_mesh](https://github.com/hesom/depth_to_mesh) | 深度マップ→三角メッシュ変換ツール | OSS | 深度マップ | 三角メッシュ | 補助ツール |
| [Open3D](https://www.open3d.org/) | 点群/メッシュ処理の定番ライブラリ。Poisson再構成、Ball Pivoting等 | OSS (MIT) | 点群 | 3Dメッシュ | 補助ツール - 3D後処理に必須 |

### カテゴリ5: 商用3Dスキャン/生成プラットフォーム

APIやアプリとして利用可能な商用サービス。

| サービス | 概要 | 入力 | 出力 | API | PoCへの適合度 |
|---|---|---|---|---|---|
| [Matterport](https://matterport.com/) | 業界標準の3Dスキャン。2D写真からAIで3D生成可能（CoStarが2025年買収） | 写真/360カメラ/LiDAR | 3Dモデル / ドールハウスビュー | あり | 中 - 高品質だが高コスト |
| [Polycam](https://poly.cam/) | LiDAR/写真ベースの3Dスキャン。Fortune 500の半数が利用。間取り図生成機能あり | 写真/LiDAR | 3Dモデル / 間取り図 / CAD | あり | 中 - 現場撮影前提 |
| [Luma AI](https://lumalabs.ai/) | NeRFベースの3Dキャプチャ。スマホ撮影→フォトリアルな3Dモデル | 写真/動画 | 3Dモデル / NeRF | あり | 中 - 動画入力が前提 |
| [Meshy](https://www.meshy.ai/) | AI画像→3Dモデル生成。テクスチャ付きメッシュ出力。API提供 | 単一画像/テキスト | テクスチャ付き3Dメッシュ | [あり](https://docs.meshy.ai/) | 低 - オブジェクト単位で空間向きではない |
| [Rodin (Hyper3D)](https://hyperhuman.deemos.com/) | 最高品質のAI 3D生成。Quad Mesh+PBRテクスチャ自動生成 | 画像/テキスト | Quad Mesh + PBR | あり | 低 - オブジェクト単位 |
| [Kaedim](https://www.kaedim3d.com/) | 2Dスケッチ/画像→3Dモデル。AAA制作スタジオが利用 | 画像/スケッチ | 3Dモデル | あり | 低 - オブジェクト単位 |

### カテゴリ6: 3D処理・統合ライブラリ

パイプライン構築に使用する基盤ライブラリ。

| ライブラリ | 用途 | 備考 |
|---|---|---|
| [Open3D](https://www.open3d.org/) | 点群/メッシュ処理、可視化、表面再構成 | Python/C++。Poisson再構成、ICP位置合わせ等 |
| [PyTorch3D](https://pytorch3d.org/) | 微分可能3Dレンダリング、メッシュ操作 | PyTorchエコシステム。GPU対応 |
| [trimesh](https://trimsh.org/) | メッシュI/O、穴埋め、ブーリアン演算 | 軽量。OBJ/STL/PLY等に対応 |
| [Blender Python API (bpy)](https://docs.blender.org/api/current/) | プログラマティックな3Dモデリング・レンダリング | FloorplanToBlender3dの基盤 |

### カテゴリ7: LLM/VLMベースの3D空間理解・生成

汎用LLM・VLM（Vision-Language Model）を活用して空間を理解・生成するアプローチ。専用CVモデルと異なり、自然言語での指示や推論が可能。

| 技術/ツール | 概要 | LLM/VLMの役割 | PoCへの適合度 |
|---|---|---|---|
| [Gemini 3 Spatial Understanding](https://github.com/google-gemini/cookbook/blob/main/examples/Spatial_understanding_3d.ipynb) | 画像から3D座標`[x,y,z,w,h,d,roll,pitch,yaw]`をメートル単位で直接出力。複数視点からの3D推論 | **Gemini 3自体がVLM**。空間理解をネイティブサポート | **最高** - API利用可。間取り図+写真の空間理解に直接適用可能 |
| [WorldGen](https://www.meta.com/blog/worldgen-3d-world-generation-reality-labs-generative-ai-research/) (Meta) | テキスト1つから50x50mのナビゲーション可能な3Dワールドを約5分で生成 | LLMがテキスト→空間レイアウト推論 | 中 - 研究段階。未公開 |
| [LayoutVLM](https://openaccess.thecvf.com/content/CVPR2025/papers/Sun_LayoutVLM_Differentiable_Optimization_of_3D_Layout_via_Vision-Language_Models_CVPR_2025_paper.pdf) (CVPR 2025) | VLMでシーンレイアウト記述→微分可能最適化で3Dレイアウト生成 | VLMが初期レイアウト+空間関係を推論 | **高** - VLMベースのレイアウト生成 |
| [3DGraphLLM](https://github.com/CognitiveAISystems/3DGraphLLM) (ICCV 2025) | 3Dシーングラフの学習可能表現をLLMに入力し、3D vision-languageタスクを実行 | LLMが3Dシーングラフを推論 | 中 - 3D理解だが生成向きではない |
| [GPT4Scene](https://gpt4scene.github.io/) | GPT-4oにBEV画像+空間マーカーを入力し3Dシーン理解。精度42.3%→62.7%に向上 | GPT-4oが3D空間推論 | 中 - 理解寄り。生成には別途パイプライン必要 |
| [Scene-LLM](https://openaccess.thecvf.com/content/WACV2025/papers/Fu_Scene-LLM_Extending_Language_Model_for_3D_Visual_Reasoning_WACV_2025_paper.pdf) (WACV 2025) | エゴセントリック+シーンレベルの3Dデータを統一的に処理するVLM | LLMが3D視覚推論 | 中 - 理解寄り |

#### Gemini 3の空間認識を活用したアプローチの詳細

Gemini 3は本PoCにとって最も直接的に活用できるLLM/VLMである。

- **入力**: 間取り図画像+部屋写真（複数枚）をマルチモーダル入力として一括送信
- **空間推論**: 壁・床・天井・家具の3D位置座標をメートル単位で推定可能
- **出力**: JSON形式で構造化された3D座標データ（→Open3D等で3Dメッシュに変換）
- **API**: `gemini-3-pro` / `gemini-3-flash-preview` で利用可能。低レイテンシ
- **利点**:
  - 専用モデルの学習・環境構築が不要
  - 自然言語で「この間取り図の壁の3D座標を出力して」と指示可能
  - 写真が網羅的でない場合も、間取り図と組み合わせて推論で補完できる可能性
  - パイプラインへのAPI統合が容易
- **懸念**:
  - 3D座標出力の精度（メッシュ生成に足る精度があるか要検証）
  - 大きな空間・複雑な間取りでの性能限界
  - API利用コスト

---

## 技術方針

### 基本方針

間取り図の自動認識はAIに任せず、人が壁の端点を直接指定する。AIは写真からの細部・テクスチャ補強のみを担う。

```
人間が担う部分（確実・高精度）
└── 壁の端点をクリックして指定
└── ドア・窓の位置・サイズを指定
└── 部屋写真の撮影位置を指定

AIが担う部分（得意領域のみ）
└── 写真 + 撮影位置から細部・テクスチャを補強
```

---

### パイプライン

#### Step 1: 人が壁の端点を指定してアーキテクチャを作成

- 間取り図画像を表示し、人が壁の端点をクリックして指定する
- 端点を線で繋いで壁を生成する
- ドア・窓の位置・サイズも同様に指定する
- 出力: 2.5D構造データ（壁の端点リスト + 高さ）

```json
{
  "walls": [
    {"start": [0, 0], "end": [5.2, 0], "height": 2.4},
    {"start": [5.2, 0], "end": [5.2, 3.8], "height": 2.4}
  ],
  "doors": [
    {"wall_index": 1, "offset": 0.8, "width": 0.9, "height": 2.0}
  ],
  "windows": [
    {"wall_index": 0, "offset": 1.2, "width": 1.6, "height": 1.1, "sill_height": 0.9}
  ]
}
```

#### Step 2: Blenderで3Dメッシュを生成

- Step 1の構造データを入力としてBlenderで処理する
- 壁の端点を押し出し（Extrude）して壁面ポリゴンを生成する
- 床・天井も同様に生成する
- ドア・窓の開口部を切り抜く
- 出力: テクスチャなし3Dメッシュ（骨格）
- ツール: Blender（bpy）
  - 押し出し・開口部処理が得意
  - レンダリングエンジン内蔵（Cycles / EEVEE）
  - ヘッドレスで動かせる（CLI対応）

#### Step 3: 写真 + 撮影位置で3Dメッシュを補強

- 人が部屋写真を撮影し、撮影位置（x, y, 向き）を指定する
- MASt3Rが写真と撮影位置から細部・テクスチャを補強する
- 出力: テクスチャ付き3Dメッシュ

---

### Geminiを使わない理由

PoCでGemini 3による間取り図の自動認識を試みたが、内壁・ドア位置・部屋分割の再現が不可能だった。原因として以下が考えられる。

- 日本の間取り図特有の記号・線種・日本語テキストへの非対応
- 汎用VLMは間取り図のようなドメイン特化図面の解釈が苦手

人が端点を直接指定することでこの問題を根本的に回避する。

---

### 参考ツール

- [Blender Python API](https://docs.blender.org/api/current/)
- [MASt3R](https://github.com/naver/mast3r)

---

### ライセンスに関する注記

| ツール | ライセンス | 商用利用 |
|---|---|---|
| Blender Python API (bpy) | GPL-2.0 | 可（スクリプト利用） |
| MASt3R | CC BY-NC-SA 4.0 | **不可**（PoC検証のみ） |
| Open3D / trimesh | MIT | 可 |

PoC段階ではNC（非商用）ライセンスのツールも検証に利用可能。プロダクション移行時はライセンスを再検討する。

---

## 検証結果（2026-03-07）

- Gemini API（gemini-2.5-flash / gemini-3-pro-image-preview）で間取り図→2D壁座標のJSON抽出を実施
- 外壁の大まかな形状は捉えるが、内部間仕切り・ドア・窓の位置精度が大幅に不足（実用水準に遠い）
- モデル間の差異は小さく、プロンプト改善では根本的な精度向上は見込めない
- **結論: Gemini APIによる間取り図→構造化データ抽出は不適。OSSパイプライン（DeepFloorplan/CubiCasa5k + FloorplanToBlender3d 等）へのフォールバックを推奨**
- 検証コード: `poc/3dcg_poc1/`、可視化: `poc/3dcg_poc1/generated/visualize_2d.png`

---

## 成果物

- パターンA・Bそれぞれの3D空間データ出力結果
- 写真が網羅的でない場合の補完状況の考察
- 家具なし・ありの差異の考察
- 次のステップ（任意カメラ位置からのレンダリング）への接続方針
