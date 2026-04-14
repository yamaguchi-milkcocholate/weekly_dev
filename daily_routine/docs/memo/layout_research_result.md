# レイアウト提案の最新動向調査結果

調査日: 2026-03-21
調査計画: `docs/memo/layout_research_plan.md`

---

## 観点1: 空間制約のAIへの入力方法

### テキスト（プロンプト）入力

| 手法 | 会議/年 | 概要 | 特徴 |
|------|---------|------|------|
| **LayoutGPT** | NeurIPS 2023 | CSS風記述でin-contextデモを与えLLMがレイアウト生成 | 先駆的手法。物理制約違反が課題 |
| **LLplace** | 2024 | Llama3をLoRAファインチューン。部屋タイプ+オブジェクト名で3D生成 | 対話による動的編集可能。3D-Frontで既存手法超え |
| **DirectLayout** | 2025 | テキスト→BEVレイアウト→3Dリフティング→配置リファインの3段階 | 汎化可能な空間推論 |
| **PAT3D** | ICML 2025候補 | テキスト→LLMでオブジェクト生成→微分可能剛体シミュレーションで最適化 | **物理制約保証の初の枠組み。SOTA** |
| **Constraint Is All You Need** | FDG 2025 | テキスト制約→LLMが制約充足問題に変換 | 制約充足アプローチ |

### 画像入力

| 手法 | 会議/年 | 概要 | 特徴 |
|------|---------|------|------|
| **LayoutVLM** | CVPR 2025 | VLM+視覚マーク画像→微分可能最適化で物理的妥当性保証 | **Stanford。GitHub公開あり** |
| **M-RPG** | 2025 | 11種のマルチモーダル入力（図面、グラフ、画像、テキスト等）に統一対応 | 2000万枚で学習。全既存モデル超えのSOTA |
| **SceneCraft** | 2025 | 3Dレイアウト→多視点2Dプロキシマップ→拡散モデル→NeRF | テキスト+レイアウト指定に忠実 |

### 3Dデータ入力

| 手法 | 会議/年 | 概要 | 特徴 |
|------|---------|------|------|
| **SceneLinker** | IEEE VR 2026 | RGB列→ORB-SLAM3で点群→シーングラフ→Graph-VAEで生成 | 自動パイプライン。3RScan/3DSSGでSOTA |
| **MeshCoder** | 2025 | LLMで点群→構造化メッシュコード生成 | 点群直接入力 |

### シーングラフ入力

| 手法 | 会議/年 | 概要 | 特徴 |
|------|---------|------|------|
| **MMGDreamer** | AAAI 2025 | テキスト+画像混合ノードのシーングラフ→デュアルブランチ拡散モデル | マルチモーダルノード対応 |
| **GraphCanvas3D** | 2025 | 階層的エネルギーベース最適化。マルチモーダルLLMで局所・大域最適化 | **再学習不要の動的編集が可能** |

### 複数モダリティ組み合わせ

| 手法 | 会議/年 | 概要 | 特徴 |
|------|---------|------|------|
| **SKE-Layout** | CVPR 2025 | 実+合成データの混合空間知識を対照学習+マルチタスク学習で統合 | 5-30%改善 |
| **Scenethesis** | 2025 | エージェント型：LLMドラフト→ビジョン検証→最適化→ジャッジの反復 | 学習不要 |
| **ScenethesisLang** | 2025 | DSL「ScenethesisLang」で100+制約を形式記述→実行可能3Dコード | **制約充足率90%+、視覚品質42.8%改善** |
| **LaySPA** | 2025 | 強化学習ベース。ハイブリッド報酬（幾何+構造+視覚）で学習 | 汎用LLM超え、専用モデル匹敵 |

### 主要トレンド

1. **物理シミュレーション統合**: PAT3Dのように微分可能物理シミュレーションで妥当性を保証
2. **制約記述用DSL**: ScenethesisLangのように自然言語とコードの間に中間表現を置く
3. **VLM活用**: LayoutVLMのようにVLMの空間推論+微分可能最適化の組み合わせ
4. **エージェント型**: 計画→視覚検証→最適化→判定のマルチステップ構成
5. **マルチモーダル入力**: M-RPGの11モダリティ対応のように入力の柔軟性向上

---

## 観点2: 動線・生活シナリオの表現

### モーション→レイアウト

| 手法 | 会議/年 | 概要 | 動線の表現 |
|------|---------|------|------------|
| **PhysSceneGen** | SIGGRAPH 2024 | モーキャプデータ+物理シミュレータで家具レイアウト同時最適化 | モーキャプデータ（関節時系列）を直接入力。モーション追跡誤差を最小化する形で配置 |
| **SUMMON** | SIGGRAPH Asia 2022 | 動作から接触ラベル予測→オブジェクト選択・配置最適化 | 動作シーケンスから接触ラベルを時間的に一貫抽出 |

### 行動シーケンス→レイアウト

| 手法 | 会議/年 | 概要 | 動線の表現 |
|------|---------|------|------------|
| **ACTOR** | ICCV 2025 | 3D家庭環境で長期行動目標を遂行するエージェント | LLMコントローラで目標分解→価値関数で行動選択評価 |
| **OptiScene** | NeurIPS 2025 | LLMベース。SFT+DPOの2段階学習 | 高レベル空間記述→条件付き配置予測 |
| **Habitat 3.0** | ICLR 2024 | ヒューマノイド+ロボット協調シミュレーション（Meta AI） | 多様なモーションデータをキャッシュ→新環境にプロジェクション |

### エルゴノミクス制約

| 手法 | 会議/年 | 概要 | 制約 |
|------|---------|------|------|
| **LayoutVLM** | CVPR 2025 | VLM+微分可能最適化 | 非貫通、接地を微分可能目的関数として定式化 |
| **HCMs** | 2020 | ヒューマンセントリック指標 | リーチ距離（scope of touch）、視界（scope of view）から機能的アクセシビリティを定量化 |
| **Make it Home** | SIGGRAPH 2011 | アクセシビリティ・可視性・通路制約をコスト関数に | 後続研究のベースライン。人間デザイナーと有意差なし |

### 使用シーンシミュレーション

| 手法 | 会議/年 | 概要 | 方法 |
|------|---------|------|------|
| **SceneDirector** | IEEE TVCG 2024 | 1オブジェクト移動→グループ全体を空間制約保持して再配置 | リアルタイム処理 |
| **SceneFlow** | CAGD 2025 | Flow Matchingでカオス初期状態→構造化レイアウトへのフロー学習 | 非重複制約+幾何リファイン |
| **DiffuScene** | CVPR 2024 | 順不同オブジェクト属性の拡散モデル | 3D-FRONTでSOTA |
| **MiDiffusion** | 2024 | 離散（セマンティクス）+連続（幾何）の混合拡散 | 間取り+既存オブジェクトを条件に新オブジェクト生成 |

### 主要トレンド

1. **物理シミュレーション統合**: 強化学習dual-optimizationでモーション+レイアウト同時最適化
2. **LLM/VLM活用**: OptiScene、LayoutVLMのように大規模モデルの空間理解力を活用
3. **微分可能最適化**: 物理+セマンティック制約を勾配ベースで同時最適化
4. **拡散/フローモデル**: DiffuScene、SceneFlowなどが主流に

---

## 観点3: 画像認識ベースの評価

### 空間推論ベンチマーク

| ベンチマーク | 会議/年 | 概要 | 主な知見 |
|-------------|---------|------|----------|
| **SpatialBench** | CVPR 2026 | 5段階・15タスクの空間認知ベンチマーク | Gemini-2.5-Pro最高。人間96.4%に対しAIは大きなギャップ |
| **MM-Spatial** | ICCV 2025 (Apple) | 室内3D空間理解のSFTデータ+CA-VQA評価 | Chain-of-Thought空間推論でSOTA |
| **SpatialVLM** | CVPR 2024 (Google) | 10億VQAサンプルで定量的距離・サイズ推定VLM構築 | 距離推定37.2%が0.5x-2x範囲内 |

### VLMの空間推論能力比較

| 観点 | Gemini系 | GPT系 | Claude系 | オープンソース |
|------|----------|-------|----------|---------------|
| SpatialBench総合 | **最高性能**（中間レベルで低下） | GPT-5が大幅改善 | 直接比較データ限定 | Qwen3-VLが健闘 |
| 3Dレイアウト推論 | 空間+視覚統合に強い | 精密な視覚理解に強い | -- | 空きスペース推論は全モデルで弱い |
| デザイン美的評価 | -- | **GPT-4oが人間評価と良好な相関** | -- | プロプライエタリが優位 |

**重要な知見**: VLMの空間推論は50-60%精度。空きスペース推論・衝突検出・複合的空間計画は依然困難（ICLR 2025投稿の検証）

### レンダリング画像の品質評価

| 手法 | 会議/年 | 概要 |
|------|---------|------|
| **VQAScore** | ECCV 2024 (CMU) | テキスト-画像整合性の自動評価。Google DeepMindがImagen3評価に採用 |
| **AesEval-Bench** | 2026 (Microsoft) | 4次元×12指標×3タスクのグラフィックデザイン美的評価 |
| **Can GPTs Evaluate Design?** | SIGGRAPH Asia 2024 | GPT-4oが人間評価との相関でヒューリスティック指標より良好 |
| **3D-SPAN-M** | 2025 | グラフアテンションNWで3Dシーン妥当性評価。視覚+意味の両軸 |
| **ViLLA** | 2025 | ViT+LLMで間取り図から部屋分類・ゾーニング自動生成 |

### プロジェクトへの示唆

1. **レイアウト妥当性**: GPT-4o/Geminiにプロンプトベースで空間関係・配置の妥当性を評価させる
2. **テキスト-画像整合性**: VQAScoreで定量評価
3. **主観的感覚（圧迫感等）**: 専用ベンチマークがまだ少ない→カスタムプロンプトでVLM評価+人間評価との相関検証が現実的

---

## 観点4: 最新のレイアウト生成手法（2025-2026）

### LLM/VLMベース

| 手法 | 会議/年 | 概要 | 公開実装 |
|------|---------|------|----------|
| **LayoutVLM** | CVPR 2025 | VLM+微分可能最適化 | [GitHub](https://github.com/sunfanyunn/LayoutVLM) |
| **OptiScene** | NeurIPS 2025 | オープンLLM+SFT+DPO | [GitHub](https://github.com/PolySummit/OptiScene) |
| **SKE-Layout** | CVPR 2025 | 混合空間知識+対照学習 | CVPR公開 |
| **FlairGPT** | Eurographics 2025 | デザイナーWF模倣。ゾーニング→制約最適化 | [GitHub](https://github.com/gabriellelittle1/FlairGPT) |

### 拡散モデルベース

| 手法 | 会議/年 | 概要 | 公開実装 |
|------|---------|------|----------|
| **DiffuScene** | CVPR 2024 | 順不同属性セットのデノイジング拡散 | [GitHub](https://github.com/tangjiapeng/DiffuScene) |
| **Layout-Your-3D** | ICLR 2025 | 2Dブループリント→衝突回避最適化→3D | [GitHub](https://github.com/Colezwhy/Layout-Your-3D) |
| **ArtiScene** | CVPR 2025 (NVIDIA) | Text→2D画像→検出→3D組立。Training-free | [GitHub](https://github.com/NVlabs/ArtiScene) |

### エージェント型

| 手法 | 会議/年 | 概要 | 公開実装 |
|------|---------|------|----------|
| **InteriorAgent** | 3DV 2026 | デザイン原則エンコード+エルゴノミクス保証+反復制約充足 | OpenReview |
| **Holodeck 2.0** | 2025 | VLM→3D生成→空間制約反復適用。多様スタイル対応 | [v1 GitHub](https://github.com/allenai/Holodeck) |
| **I-Design** | ECCV 2024 | 5つのLLMエージェント協調（Designer/Architect/Engineer/Corrector/Refiner） | [GitHub](https://github.com/atcelen/IDesign/) |

### 重要データセット

| データセット | 概要 |
|-------------|------|
| **IL3D** (ICLR 2026投稿) | 27,816レイアウト、29,215アセット、18部屋タイプ、点群/BB/マルチビュー等 |
| **3D-SynthPlace** | 約17,000シーン（3D-Front + Holodeck合成） |

### 主要トレンド

1. **命令型→宣言型**: 座標直接指定→制約ベース宣言的手法へ。物理的妥当性が大幅向上
2. **VLM活用拡大**: テキストのみLLM→VLMへ。画像入力活用の空間推論改善
3. **嗜好最適化**: OptiSceneのDPOに代表される人間嗜好アライメント
4. **エージェント型**: マルチエージェント協調、プログラム合成+反復最適化
5. **2D中間表現**: ArtiSceneのようにText-to-Image品質を3D構築に活用
6. **オープンユニバース化**: 固定カテゴリ制限を超え任意物体の生成・配置へ

---

## 観点5: リアル制約×AI創造の事例

### 建築設計（プロ向け）

| サービス | 概要 | リアル制約の扱い |
|---------|------|-----------------|
| **Maket AI** | AI間取り自動生成。Mila共同開発 | ゾーニングコード検証、建築基準法対応、敷地制約考慮。**日本ではLib Workと提携（2025年末完成予定）** |
| **Finch 3D** | 建築家向けAI設計最適化 | 敷地条件・面積要件変更時にリアルタイム再構成 |
| **Hypar** | BIMプラットフォーム連携の設計自動化 | ゾーニング・動線・構造条件→即座に最適化 |
| **ARCHITEChTURES** | AIビル設計。IFC標準BIM出力 | 規制・設計基準完全対応。Pro $40/月 |
| **Autodesk Forma** | 旧Spacemaker。都市設計・サイトプランニング | 地形・ゾーニング・インフラを自動取得。日照・風・騒音等100+指標でリアルタイム評価 |
| **Snaptrude** | クラウド3D設計。Universal Graph Representation | ゾーニング・建築基準・気候考慮。違反検出・通知機能 |

### インテリアデザイン

| サービス | 概要 | リアル制約の扱い |
|---------|------|-----------------|
| **Planner 5D** | D&D式住宅設計+AI Designer | スケッチ/間取り図→AI解析→3D。実寸ベース家具フィット確認 |
| **Homestyler** | クラウド3Dインテリア | 間取り図→3D自動生成。30万+実ブランド家具モデル |
| **AiHouse** | 中国発。8000万+モデル。設計→製造連携 | AIレイアウト提案。設計→切り出しリスト→BOM→見積を一気通貫。日本語サイトあり |
| **Qbiq** | 商業不動産向けワークスペースプランニング | フロア制約内で人数・チーム要件最適化。設計サイクル80%短縮 |

### 日本の事例

| サービス/事例 | 概要 |
|-------------|------|
| **Lib Work × Maket AI** | 日本の建築基準法・土地形状対応の間取り自動生成（2025年末完成予定） |
| **ANDPAD 3Dスキャン + Stellarc** | iPhone LiDAR 3Dスキャン→建設特化型AI（2025年12月始動） |
| **スペースリー** | 360度撮影→VR+AI家具自動配置+AIサイズ推定。業務時間1/10短縮事例 |

### リアル制約の扱いの成熟度

| カテゴリ | 精度 | 代表例 |
|---------|------|--------|
| 建築設計（プロ向け） | **高い** | Maket, Finch 3D, Snaptrude, Forma |
| BIM連携 | **高い** | ARCHITEChTURES, Hypar |
| インテリア（寸法ベース） | 中程度 | Planner 5D, AiHouse |
| インテリア（写真ベース） | 低い | DecorAI, RoomGPT |
| 3Dスキャン→AI | **高い**（設計フィードバックループは発展途上） | ANDPAD, スペースリー |

---

## PoC3の次のアプローチへの提言

### 1. 入力形式: 構造化テキスト + 制約DSL

PoC3のJSON+SVGアプローチを発展させ、**ScenethesisLang的な制約DSL**を中間表現として導入することを推奨。

- 自然言語→制約DSL→実行可能コードの3段階にすることで、制約充足率90%+が達成されている
- PoC3の構造化データ（room_info.json）は既にこの方向に近い
- SVGよりも**シーングラフ（オブジェクト間関係の明示的記述）**の方がAIに認識されやすい

### 2. 動線・生活シナリオ: アクティビティベースの制約記述

PoC3最大の弱点に対して:

- **短期的**: HCMs（ヒューマンセントリック指標）のリーチ距離・視界・通路幅をコスト関数に組み込む（Make it Homeアプローチ）
- **中期的**: FlairGPTのようにデザイナーのワークフロー模倣（ゾーニング→制約生成→最適化）を導入
- **長期的**: PhysSceneGenのようにモーションデータからの逆推論

### 3. モデル選択

| 用途 | 推奨モデル | 理由 |
|------|-----------|------|
| レイアウト生成 | GPT-4o / Claude | FlairGPT, LayoutVLMでのGPT-4o実績。コード生成能力が重要 |
| 空間推論・評価 | Gemini-2.5-Pro | SpatialBenchで最高性能 |
| テキスト-画像整合性評価 | VQAScore | Google DeepMindがImagen3評価に採用 |

### 4. refineループの強化ポイント

現在のPoC3のrefineループに以下を追加:

1. **物理制約チェック**: 非貫通・接地を微分可能目的関数として（LayoutVLM方式）
2. **エルゴノミクス評価**: HCMsのアクセシビリティ・可視性スコアを算出
3. **VLMによる視覚評価**: レンダリング画像をVLMに評価させ、主観的品質をフィードバック
4. **制約充足判定**: ScenethesisLang的にハード制約の充足率を計測

### 5. 最も参考になる手法（優先度順）

1. **FlairGPT** (Eurographics 2025) — デザイナーWF模倣、GitHub公開、GPT-4o使用でPoC3に最も近い
2. **LayoutVLM** (CVPR 2025) — VLM+微分可能最適化、GitHub公開、Stanford
3. **ScenethesisLang** (2025) — 制約DSLアプローチ、制約充足率90%+
4. **InteriorAgent** (3DV 2026) — エージェント型、デザイン原則エンコード
5. **OptiScene** (NeurIPS 2025) — 人間嗜好アライメント、GitHub公開

---

## 参考文献（主要）

### 観点1: 空間制約の入力方法
- [LayoutGPT](https://layoutgpt.github.io/) (NeurIPS 2023)
- [LLplace](https://arxiv.org/abs/2406.03866) (2024)
- [DirectLayout](https://arxiv.org/abs/2506.05341) (2025)
- [PAT3D](https://arxiv.org/abs/2511.21978) (ICML 2025候補)
- [LayoutVLM](https://ai.stanford.edu/~sunfanyun/layoutvlm/) (CVPR 2025)
- [M-RPG](https://www.sciencedirect.com/science/article/abs/pii/S0926580525004480) (2025)
- [SceneLinker](https://scenelinker2026.github.io/) (IEEE VR 2026)
- [MMGDreamer](https://arxiv.org/abs/2502.05874) (AAAI 2025)
- [GraphCanvas3D](https://arxiv.org/html/2412.00091v2) (2025)
- [SKE-Layout](https://openaccess.thecvf.com/content/CVPR2025/papers/Wang_SKE-Layout_Spatial_Knowledge_Enhanced_Layout_Generation_with_LLMs_CVPR_2025_paper.pdf) (CVPR 2025)
- [Scenethesis](https://arxiv.org/abs/2505.02836) (2025)
- [ScenethesisLang](https://arxiv.org/abs/2507.18625) (2025)
- [LaySPA](https://arxiv.org/abs/2509.16891) (2025)

### 観点2: 動線・生活シナリオ
- [PhysSceneGen](https://dl.acm.org/doi/10.1145/3641519.3657517) (SIGGRAPH 2024)
- [SUMMON](https://dl.acm.org/doi/10.1145/3550469.3555426) (SIGGRAPH Asia 2022)
- [ACTOR](https://openaccess.thecvf.com/content/ICCV2025/papers/Liang_Towards_Human-like_Virtual_Beings_Simulating_Human_Behavior_in_3D_Scenes_ICCV_2025_paper.pdf) (ICCV 2025)
- [OptiScene](https://arxiv.org/abs/2506.07570) (NeurIPS 2025)
- [Habitat 3.0](https://arxiv.org/abs/2310.13724) (ICLR 2024)
- [LayoutVLM](https://arxiv.org/abs/2412.02193) (CVPR 2025)
- [SceneDirector](https://ieeexplore.ieee.org/document/10106472/) (IEEE TVCG 2024)
- [DiffuScene](https://github.com/tangjiapeng/DiffuScene) (CVPR 2024)

### 観点3: VLMレイアウト評価
- [SpatialBench](https://arxiv.org/abs/2511.21471) (CVPR 2026)
- [MM-Spatial](https://arxiv.org/abs/2503.13111) (ICCV 2025)
- [SpatialVLM](https://spatial-vlm.github.io/) (CVPR 2024)
- [VQAScore](https://linzhiqiu.github.io/papers/vqascore/) (ECCV 2024)
- [AesEval-Bench](https://arxiv.org/html/2603.01083v1) (2026)
- [3D-SPAN-M](https://www.sciencedirect.com/science/article/abs/pii/S0141938225000010) (2025)

### 観点4: 最新レイアウト生成手法
- [FlairGPT](https://github.com/gabriellelittle1/FlairGPT) (Eurographics 2025)
- [InteriorAgent](https://openreview.net/forum?id=ypBfokcXvA) (3DV 2026)
- [Holodeck 2.0](https://arxiv.org/abs/2508.05899) (2025)
- [I-Design](https://github.com/atcelen/IDesign/) (ECCV 2024)
- [ArtiScene](https://github.com/NVlabs/ArtiScene) (CVPR 2025, NVIDIA)
- [Layout-Your-3D](https://github.com/Colezwhy/Layout-Your-3D) (ICLR 2025)
- [3D Scene Generation Survey](https://arxiv.org/abs/2505.05474) (2025)

### 観点5: 商用サービス・事例
- [Maket AI](https://www.maket.ai/) / [Lib Work提携](https://prtimes.jp/main/html/rd/p/000000148.000022440.html)
- [Finch 3D](https://www.finch3d.com/)
- [ARCHITEChTURES](https://architechtures.com/en)
- [Autodesk Forma](https://www.autodesk.com/products/forma/overview)
- [Snaptrude](https://www.snaptrude.com/)
- [Qbiq](https://www.qbiq.ai/)
- [AiHouse](https://www.aihouse.com/global)
- [ANDPAD Stellarc](https://andpad.jp/news/20251209)
- [スペースリー](https://info.spacely.co.jp/vr-function/)

---

## PoC3の課題との照合分析

PoC3作業メモ（`poc/3dcg_poc3/memo.md`）の知見と調査結果を照合し、具体的な解決策を整理する。

### PoC3で判明した核心の課題

> 「座標上に隙間がある」≠「人が通れる」≠「生活として自然」
> — PoC3 memo, Phase 5 refineループの知見

Claude Codeは座標の数値を見て「0.4mの隙間がある→OK」と判断するが、実際に人が生活する姿を想像できない。さらに、想像できていないこと自体に気づけない（自己評価とユーザー評価のギャップが大きい）。

### 課題1: 自己評価が甘い

**PoC3の症状**: カウンター3台の配置を「OK」「注意」と評価 → ユーザー評価は「絶望的にセンスがない」

**調査で見つかった解決策**:

| 手法 | アプローチ | PoC3への適用 |
|------|-----------|-------------|
| **OptiScene** (NeurIPS 2025) | SFT+DPO（人間嗜好最適化）で人間の好みにアライン | ユーザー評価との乖離を学習的に埋める発想 |
| **VQAScore** (ECCV 2024) | VQAモデルに「この配置は生活しやすいか？」と投げて定量スコア化 | 自己評価の代わりに外部評価モデルを使う |
| **SpatialBench** (CVPR 2026) | VLMの空間推論は50-60%で人間の96%に遠い | **Claude単体での空間評価には限界がある**ことが学術的にも確認 |

**結論**: Claude単体の自己評価に頼らず、Gemini-2.5-Pro（SpatialBench最高性能）やVQAScoreなど外部評価を組み合わせる必要がある。

### 課題2: クリアランス検証の困難さ

**PoC3の症状**: クリアランスをコードで検証しようとしたが、方向計算が複雑でバグ頻発→廃止

**調査で見つかった解決策**:

| 手法 | アプローチ | PoC3への適用 |
|------|-----------|-------------|
| **LayoutVLM** (CVPR 2025) | 物理制約（非貫通・接地）を**微分可能目的関数**として定式化 | 使用空間の確保も勾配ベースで最適化。方向計算のバグを回避 |
| **HCMs** (Human-Centric Metrics) | リーチ距離(scope of touch)と視界(scope of view)をスカラー値で算出 | PoC3のフロントクリアランスよりシンプルな定義 |
| **Make it Home** (SIGGRAPH 2011) | accessibility・visibility・pathway constraintsをコスト関数の項に | 「人が立てるか・通れるか」を関数化。PoC3の手動原則と同じ発想だが定式化されている |

**結論**: フロントクリアランスの矩形衝突検出ではなく、HCMs式の「アクセシビリティスコア」（リーチ距離+視界+通路幅のスカラー値）に置き換える。方向の複雑さを抽象化できる。

### 課題3: 動線設計が矩形の配置不可領域に留まっている

**PoC3の症状**: 矩形の配置不可領域で動線を代替。人間は経路（A→B→C）で考えるが、今は静的な禁止領域しかない。

**PoC3で手動定義した5原則**:
1. ドア↔ドアの主要経路を先に確保（幅0.6m以上）
2. 各家具のfrontに人が立てるか
3. 家具間0.6m以上
4. 壁際に寄せる
5. 小型家具を中央に置かない

**調査で見つかった体系化手法**:

| 手法 | アプローチ | PoC3への適用 |
|------|-----------|-------------|
| **FlairGPT** (Eurographics 2025) | ゾーニング→オブジェクト一覧+制約生成→設計レイアウトグラフ→制約最適化 | PoC3の手動5原則をFlairGPTの構造に落とし込む |
| **ScenethesisLang** (2025) | 制約DSLとして形式記述→充足率90%+ | PoC3のlife_scenarios.jsonをDSLに昇格 |
| **PhysSceneGen** (SIGGRAPH 2024) | モーションデータから家具配置を逆推論 | 長期的にはモーション→レイアウトの方向。短期的には非現実的 |

**結論**: FlairGPT式の「ゾーニング先行」が最も現実的。家具配置の前に領域割当（ワーク/ダイニング/収納/睡眠）を決め、動線はゾーン間の接続として定義する。PoC3のlife_scenarios.jsonがそのまま入力になる。

### 課題4: 「座標を決めるのはClaude Code」の限界

**PoC3の設計**: Claude Codeが座標(cx, cy)を指定→エンジンが配置+チェック。グリッドサーチ等の探索ロジックはエンジンに持たせない。

**調査で見つかった折衷案**:

| 手法 | アプローチ | PoC3への適用 |
|------|-----------|-------------|
| **Scenethesis** (2025) | LLMが粗い配置→最適化モジュールが物理妥当性を反復保証→ジャッジが検証 | PoC3の分業に「最適化ステップ」を追加 |
| **PAT3D** (ICML 2025候補) | LLM生成→微分可能剛体シミュレーションで自動調整 | 「だいたいここ」→物理シミュが微調整 |
| **InteriorAgent** (3DV 2026) | エルゴノミクス保証+反復制約充足の最適化ツール | デザイン原則をエンコードして自動最適化 |

**結論**: 「Claude Codeが精密な座標を決める」のではなく、「Claude Codeがゾーニング+大まかな配置方針を決め、最適化エンジンが物理制約を満たす座標に調整する」という分業に変更する。PoC3のv4で発生した壁衝突4箇所のような問題は、最適化ステップが自動解消する。

---

## PoC3の次のアプローチ（具体的提案）

### パイプライン改善案

```
現在のPoC3:
  Claude Code → placement_plan.json(精密座標) → engine(配置+チェック) → SVG → Claude Code評価(テキスト)
                                                                                    ↑ここが弱い

提案パイプライン:
  Step 1: ゾーニング（FlairGPT式）
    Claude Code → zoning_plan.json（領域割当+動線定義）
    入力: room_info.json + life_scenarios.json + assets.json
    出力: 各ゾーンの矩形領域 + ゾーン間動線経路

  Step 2: 粗い配置（現在のPoC3方式を簡略化）
    Claude Code → placement_plan.json（ゾーン内の大まかな位置）
    精密座標ではなく「ゾーン内の壁際」「ゾーン内の中央寄り」程度の指定

  Step 3: 制約最適化（新規追加）
    optimizer → placement_plan.jsonの座標を微調整
    制約: 非貫通 + 接地 + HCMsアクセシビリティ + 動線確保
    手法: LayoutVLM式の微分可能最適化 or ScenethesisLang式の制約充足

  Step 4: 視覚評価（外部モデル活用）
    SVG/レンダリング画像 → Gemini-2.5-Pro API で空間推論評価
    評価観点: life_scenarios.jsonのシナリオに沿った動線チェック
    定量スコア: HCMsアクセシビリティ + VQAScore

  Step 5: refine判定
    定量スコアが閾値未満 → Step 2に戻る
    定量スコアが閾値以上 → 完了
```

### 実装の優先度

#### 即座に試せること（Step 1相当の工数）

1. **評価をGemini-2.5-Proに外注する**
   - PoC3のSVG/レンダリング画像をGemini APIに送り空間推論させる
   - SpatialBenchでGemini最高性能→Claude単体より正確な空間評価が期待
   - PoC3のlife_scenarios.jsonをプロンプトに組み込み「朝起きてキッチンに行くとき、このレイアウトで通れるか？」と質問

2. **FlairGPT式ゾーニングの手動導入**
   - 配置前にゾーニング（ワーク/ダイニング/収納/睡眠）を決める
   - placement_plan.jsonにゾーン情報を追加するだけ。コード変更は最小限

#### 短期（次のPoC相当の工数）

3. **HCMsアクセシビリティスコアの実装**
   - リーチ距離+視界+通路幅のスカラー値を算出する関数をplacement_engine.pyに追加
   - クリアランスの矩形衝突検出の代替。方向計算の複雑さを回避

4. **制約のDSL化**
   - PoC3の手動5原則+life_scenariosをScenethesisLang的な形式言語に変換
   - 制約充足率を定量的に計測可能にする

#### 中期（本格的な実装）

5. **微分可能最適化エンジン**
   - LayoutVLM式の勾配ベース最適化でplacement_engine.pyを拡張
   - Claude Codeは「大まかな配置方針」、エンジンは「制約を満たす精密座標」という分業

### モデル選択の推奨

| 用途 | 推奨モデル | 理由 |
|------|-----------|------|
| ゾーニング+配置方針 | Claude / GPT-4o | FlairGPT, LayoutVLMでのGPT-4o実績。コード生成・構造化出力能力が重要 |
| 空間推論・視覚評価 | **Gemini-2.5-Pro** | SpatialBenchで最高性能。画像ベースの空間理解に最も適する |
| テキスト-画像整合性 | VQAScore | Google DeepMindがImagen3評価に採用。定量スコアとして信頼性が高い |

### 最も参考にすべき手法（PoC3との接続性順）

1. **FlairGPT** (Eurographics 2025) — デザイナーWF模倣。ゾーニング→制約→最適化の流れがPoC3に最も近い。[GitHub公開](https://github.com/gabriellelittle1/FlairGPT)
2. **LayoutVLM** (CVPR 2025) — VLM+微分可能最適化。placement_engine.pyの拡張方向。[GitHub公開](https://github.com/sunfanyunn/LayoutVLM)
3. **ScenethesisLang** (2025) — 制約DSL。PoC3のlife_scenarios.json+手動5原則のDSL化の参考
4. **HCMs** (2020) — エルゴノミクス指標。クリアランス検証の代替として即座に導入可能
5. **Scenethesis** (2025) — エージェント型refineループ。PoC3のrefineループ強化の参考
