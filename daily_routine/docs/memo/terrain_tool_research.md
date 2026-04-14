# 地形・景観生成ツール調査レポート

**調査日**: 2026-04-13
**目的**: Blenderより優れたプロフェッショナル地形・背景生成ツールの調査。Blenderとの統合性、AIによる自動操作の可能性を重視。

---

## 1. 地形制作の基本プロセス

地形制作は以下の6フェーズを辿る。各フェーズで適したツールが異なる。

### Phase 1: ベース地形の生成

「どんな地形か」の大枠を決める段階。

- ノイズ関数（Perlin, Worley等）を組み合わせて基本的な起伏を生成
- または実在の地形データ（DEM/SRTM衛星データ）をベースにする
- 出力は**ハイトマップ**（グレースケール画像。白=高い、黒=低い）

### Phase 2: 侵食シミュレーション ★最重要

「自然に見せる」ための最も重要な段階。Phase 1の地形はノイズの塊でしかなく不自然。物理シミュレーションをかけることでリアルになる。

- **水流侵食（Hydraulic Erosion）**: 雨が降り、水が流れ、谷を削り、堆積物を運ぶ。これだけで劇的にリアルになる
- **熱侵食（Thermal Erosion）**: 急斜面が崩れて堆積する現象。崖の足元のガレ場ができる
- **風侵食（Aeolian Erosion）**: 砂漠の砂丘や風化表現

**これがWorld Machine / Gaea / Houdiniが得意とする領域で、Blenderが最も弱い部分。**

### Phase 3: テクスチャリング（地表マテリアル）

侵食結果から自動的にマスク（スプラットマップ）を生成し、地表素材を割り当てる。

- 傾斜角 → 急斜面は岩肌、緩斜面は草地
- 高度 → 高い場所は雪、低い場所は森
- 水流の跡 → 川床は砂利
- 曲率 → 尾根は風化した岩、谷は湿った土

侵食シミュレーションの副産物としてマスク群が得られるため、Phase 2と密接に連携する。

### Phase 4: 植生配置

スプラットマップに基づいて木・草・岩を散布する。

- 草地マスク上に草を散布
- 森林帯マスク上に木を配置（密度・種類をルールで制御）
- 岩肌マスク上に岩のデブリを配置

### Phase 5: 大気・ライティング

空・雲・霧・光を作る段階。

- 大気散乱シミュレーション（空が青い理由を物理的に計算）
- ボリュメトリック雲
- ゴッドレイ、霧、ヘイズ

### Phase 6: レンダリング / 動画化

最終出力。

### プロセス全体図

```
ノイズ / 実データ
    ↓ ハイトマップ
侵食シミュレーション        ← ★品質の鍵。Blenderにはない
    ↓ 侵食済みハイトマップ + 副産物マスク群
テクスチャリング             ← マスクから半自動
    ↓ マテリアル付き地形メッシュ
植生・岩の散布               ← ルールベースで半自動
    ↓ 完成シーン
大気・ライティング           ← Terragenの独壇場
    ↓
レンダリング / 動画化
```

### Blender単体の限界

| Phase | Blender単体 | 専用ツール |
|-------|------------|-----------|
| ベース地形 | ノイズテクスチャ+Displacement → 可能 | 同等 |
| **侵食** | **手段がほぼない**（アドオン頼み、品質低い） | 物理ベースで高品質 |
| テクスチャリング | 手動でマスク作成 → 非常に手間 | 侵食の副産物で自動生成 |
| 植生散布 | ジオメトリノードで可能 | SpeedTree等の方が品質高い |
| 大気 | Volume Scatter → 簡易的 | Terragenが桁違い |

**最大のボトルネックは「侵食シミュレーション」。** これがあるかないかで地形のリアリズムが決定的に変わる。

---

## 2. ツール別詳細

### Tier 1: AIパイプライン最適（Python API + ヘッドレス + CLI完備）

#### Houdini (SideFX) ★★★★★

- **得意分野**: プロシージャル地形生成、侵食シミュレーション、植生配置、水流シミュレーション（全部入り）
- **価格**: Indie $269/年、Core $2,000/年、FX $4,500/年
- **Blender連携**:
  - **Houdini Engine for Blender**: 公式プラグインでHoudini Digital Assets（HDA）をBlender内で実行可能
  - USD/Alembic/FBX/OBJエクスポート
  - PDG（Procedural Dependency Graph）でパイプライン自動化
- **AI自動化**: **最も適している**
  - `hython`（Houdini Python）でフル機能のPython API、ヘッドレス実行可能
  - `hbatch/hscript`でコマンドラインバッチ処理
  - HOM（Houdini Object Model）で完全なPythonスクリプティング
  - PDG/TOPsでワークフロー自動化・依存関係管理
  - Claude Codeがhythonスクリプトを生成・実行するワークフローが直接実現可能
- **採用実績**: 「ドューン」「アバター」「ロード・オブ・ザ・リング」「Horizon Zero Dawn」等

#### Terragen (Planetside Software) ★★★★☆

- **得意分野**: 大気散乱・雲・惑星規模の地形・フォトリアルな空（圧倒的）
- **価格**: Creative $349 / Professional $699
- **Blender連携**:
  - ハイトマップ（EXR/TIFF 16bit/32bit）エクスポート → Blender displacement
  - OBJ/FBXで地形メッシュ移行可能
  - 直接的なBlenderプラグインはないが、ワークフロー互換性は良好
- **AI自動化**:
  - CLIモード `terragen4 -p project.tgd -r` でヘッドレスレンダリング可能
  - .tgdファイルがXMLベースのためスクリプトでパラメータ書き換え可能
  - バッチレンダリング完全自動化可能
- **採用実績**: 「インターステラー」「ブレードランナー2049」「ゲーム・オブ・スローンズ」

#### Unreal Engine 5 (Epic Games) ★★★★☆

- **得意分野**: Nanite/Lumenによるリアルタイムフォトリアル、大規模オープンワールド地形
- **価格**: 無料（年商100万ドル超で5%ロイヤリティ）
- **Blender連携**: USD/FBX/Alembic対応、非公式Bridgeツール多数
- **AI自動化**:
  - `unreal` Pythonモジュールで完全なエディタ自動化
  - コマンドレットでヘッドレスバッチ処理対応
  - PCG（Procedural Content Generation）フレームワークでルールベース環境自動生成
  - NNE（Neural Network Engine）でリアルタイムML推論
- **採用実績**: 「マンダロリアン」（バーチャルプロダクション）

### Tier 2: 自動化可能（CLI + ファイル操作）

#### Gaea (QuadSpinner) ★★★☆☆

- **得意分野**: プロシージャル地形生成・侵食シミュレーション（World Machineの現代版、GPU高速）
- **価格**: Community 無料（1024x1024制限）/ Indie $99/年 / Professional $199/年 / Enterprise $299/年（CLI対応）
- **Blender連携**: ハイトマップ（EXR/TIFF）/OBJエクスポート
- **AI自動化**:
  - Enterprise版で `Gaea.Build.exe --file project.tor` でヘッドレスビルド
  - .torファイル（XMLベース）のパラメータをスクリプト操作可能
  - パラメータ空間の探索 → CLIビルド → 評価ループが可能

#### World Machine ★★★☆☆

- **得意分野**: 侵食シミュレーションの品質が最高峰
- **価格**: Standard $119 / Professional $299
- **Blender連携**: ハイトマップ/OBJ/スプラットマップエクスポート
- **AI自動化**:
  - Professional版でCLIバッチ処理対応
  - XMLベースのプロジェクトファイル操作で自動化可能

#### SpeedTree (Epic Games) ★★★☆☆

- **得意分野**: 樹木・植物のプロシージャルモデリング・風アニメーション（業界標準）
- **価格**: UE使用者は無料 / Indie $19/月 / Cinema $149/月
- **Blender連携**: FBX/Alembicエクスポート
- **AI自動化**: パラメトリック生成のためAIがパラメータ指定 → バッチ処理で植生ライブラリ自動構築可能
- **採用実績**: 「アバター」「The Last of Us」「Horizon」等

### Tier 3: 手動操作中心（自動化困難）

#### World Creator (BiteTheBytes)

- **得意分野**: リアルタイムGPU地形スカルプト
- **価格**: Indie $149 / Professional $299（買い切り）
- **課題**: インタラクティブ操作前提でCLIが弱い。AIパイプライン統合は困難

#### Vue (e-on software / Bentley Systems)

- **得意分野**: 統合的な自然景観（地形+植生+大気+水）、エコシステム（植生自動配置）
- **課題**: Bentley買収後の方向性が不明確、コミュニティ縮小傾向、Blender直接統合なし

#### Instant Terra (Wysilab)

- **得意分野**: ゲーム向けリアルタイム地形生成
- **価格**: Indie $149/年 / Pro $449/年
- **課題**: CLI対応だが柔軟性がHoudini/Gaeaほど高くない

---

## 3. 新興AIネイティブツール

| ツール | アプローチ | 備考 |
|--------|-----------|------|
| **Promethean AI** | 自然言語で3D環境構築指示 | UE連携、一般公開が限定的 |
| **NVIDIA Omniverse** | USD基盤+AI生成テクスチャ/マテリアル | Blender Connectorあり、Python API充実 |
| **AI Heightmap生成** (SD/ControlNet) | テキストプロンプト → ハイトマップ → Blender displacement | Claude Codeとの統合が最も容易 |
| **3D Gaussian Splatting** (Luma AI等) | 実写環境キャプチャ → 3D化 | Blenderプラグイン増加中 |

---

## 4. AIパイプライン統合の総合評価

| ツール | Python API | CLI/ヘッドレス | Blender連携 | 推奨度 |
|--------|-----------|---------------|------------|--------|
| **Houdini** | 完全（hython/HOM） | 完全 | Houdini Engine（公式） | ★★★★★ |
| **UE5** | 完全（unreal module） | 完全 | USD/FBX | ★★★★☆ |
| **Terragen** | 間接的（XML操作） | 完全（CLI） | ハイトマップ | ★★★★☆ |
| **Gaea Enterprise** | 間接的 | CLI対応 | ハイトマップ/OBJ | ★★★☆☆ |
| **World Machine Pro** | 間接的 | バッチ対応 | ハイトマップ/OBJ | ★★★☆☆ |
| **SpeedTree Cinema** | 限定的 | バッチ対応 | FBX/Alembic | ★★★☆☆ |

---

## 5. 推奨パイプライン構成

「Claude Code as Processing Engine」のコンセプトに最適な構成:

```
Claude Code（指示・パラメータ生成）
    ↓
Houdini hython / Gaea CLI    ← 地形生成・侵食
    ↓ ハイトマップ / USD
SpeedTree CLI                 ← 植生生成
    ↓ FBX/Alembic
Blender (bpy)                 ← シーン統合・オブジェクト配置・レンダリング
    ↓
Terragen CLI                  ← 大気・空・遠景の最終レンダリング
    ↓
Kling V2V等                   ← フォトリアル動画化
```

### 最初の一歩

1. **Gaea（無料版）** で侵食シミュレーションを試す → ハイトマップをBlenderに持ち込み、品質差を体感する
2. **Houdini Indie ($269/年)** でPython API駆動の地形生成パイプラインを構築する
3. 大気・空の品質が必要になった段階で **Terragen** を導入する
