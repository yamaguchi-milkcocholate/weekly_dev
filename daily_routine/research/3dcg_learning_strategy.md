# 3DCG学習戦略調査レポート

調査日: 2026-04-12

## 背景

Blenderで自然環境の3DCG制作を学習中。素人レベルのアウトプットは作れるが、「リアルを再現できる」レベルへの到達方法が今のやり方で合っているのか不安がある。

## 調査結果サマリー

### 1. プロの環境アーティストのワークフロー

**結論: プロはBlender単体ではなく、マルチツール構成が標準。**

典型的なパイプライン:
```
リファレンス収集 → 地形生成（専用ツール） → アセット準備（フォトスキャン） → シーン構築・散布 → ライティング・大気 → レンダリング・ポストプロセス
```

| 工程 | 今のやり方 | プロの標準 |
|------|-----------|-----------|
| 地形生成 | ANT Landscape + 手動Sculpt | **Gaea / World Creator**（侵食シミュレーション付き） |
| アセット | 白い球体（プレースホルダー） | **Megascans / Poly Haven**（フォトスキャンアセット） |
| マテリアル | 単色の緑 | **PBRテクスチャ**（フォトスキャン or Substance Designer） |
| 植生散布 | Geometry Nodes基礎 | **Geo-Scatter / GScatter** + 植生アセット |
| ライティング | ビューポートデフォルト | **Nishita Sky + HDRI + Sun Light** |

### 2. 環境CG向けツール・アセット

#### 地形生成ツール

| ツール | 特徴 | 無料版 | 有料版 | macOS | Blender連携 |
|--------|------|--------|--------|-------|------------|
| **Gaea** | GPU高速、精密な侵食 | Community（非商用、1K） | Pro $199 | **Windows専用**（Parallels動作報告あり、GPU制限） | 手動（3.0で公式プラグイン予定） |
| **World Creator** | リアルタイム、ブラシ操作 | なし | Indie $149 | **macOS対応** | **公式Bridge（最も簡便）** |
| **Terragen** | フォトリアルレンダリング特化、侵食あり | 非商用版あり（解像度制限） | $349〜 | **macOS対応（Intel/Apple Silicon）** | Heightmap/OBJ出力 |
| **World Machine** | 物理ベース侵食の老舗 | Basic（非商用、1K） | Indie $119 | **Windows専用**（Parallels動作可能） | 手動 |
| **TerreSculptor** | GIS対応 | **全機能無料** | - | **Windows専用** | 手動 |

**macOSユーザー向け注記:**
- ネイティブ対応で侵食シミュレーション付き: **Terragen**（無料版あり）、**World Creator**（$149）
- Windows専用ツールはParallels等で動作可能だが、GPU機能制限がある場合あり
- コストゼロの代替: **Blender Geometry Nodes + 外部Heightmap（Tangram Heightmapper等）**

#### アセットライブラリ

| ライブラリ | 価格 | 特徴 |
|-----------|------|------|
| **Poly Haven** | **完全無料（CC0）** | HDRI・マテリアル・3Dモデル。高品質 |
| **ambientCG** | **完全無料（CC0）** | PBRマテリアル・HDRI。2,800+ |
| **Megascans (Fab)** | 個別$0.99〜（一部無料） | 最大のスキャンライブラリ |
| **BlenderKit** | 48,000+無料 | Blender統合型 |

#### Blenderアドオン（スキャタリング）

| アドオン | 価格 | 特徴 |
|---------|------|------|
| **GScatter** | **無料** | Geometry Nodesベース、風アニメーション |
| **OpenScatter** | **無料** | GPLv3、傾斜・標高ベース配置 |
| **BagaPie** | **本体無料** / Assets $39〜 | スキャタリング+モデリング複合 |
| **Geo-Scatter** | $99 | 最高機能、Biomesシステム |
| **Botaniq** | $1.99〜$129 | 大規模植生ライブラリ |

#### 完全無料で揃う構成（macOS）
GScatter + BagaPie + Poly Haven + ambientCG + Blender Geometry Nodes（地形生成） + Tangram Heightmapper（実在地形） → 基本的な自然環境制作は可能

### 3. AI × 3DCG環境生成の最新動向

#### 実用段階のもの

| 技術 | 概要 |
|------|------|
| **3D Gaussian Splatting** | glTF標準化済み。実環境を1時間で3Dデジタルツイン化。不動産・建築で実用 |
| **AIテクスチャリング** | StableGen, Meshy Text to Texture等。PBR対応テクスチャをAI生成 |
| **Isaac Sim 5.x + Cosmos** | フィジカルAIのシミュレーション環境+合成データ生成 |
| **Blender MCP Server** | Claude等のLLMからBlenderを自然言語で操作 |

#### 研究〜商用初期段階

| 技術 | 概要 |
|------|------|
| **Meta WorldGen** | テキスト1文から50x50mの3Dワールドを約5分で生成 |
| **LL3M** | マルチエージェントLLMでBlender Pythonスクリプトを生成・実行 |
| **Autodesk Wonder 3D** | テキスト・画像から編集可能な3Dアセット生成 |

#### フィジカルAI向けパイプライン（2026年時点の最適構成）
```
3DGSで実環境を取得 → Isaac Sim / Omniverseで物理制約付きシミュレーション環境化 → Cosmos WFMで合成データ乗算
```

---

## 今のやり方の評価

### 問題点

1. **全部を手で一から作ろうとしている**: プロはフォトスキャンアセットを積極活用。全部自作はプロもやらない
2. **地形生成をBlender内で完結させようとしている**: 専用ツール（Gaea等）の侵食シミュレーションは、ANT Landscapeでは再現不可能
3. **見た目の品質を決める要素（ライティング・マテリアル・アセット）が後回し**: 形の学習に時間を使っているが、品質のジャンプが起きるのはライティングとアセット
4. **AI自動化との接続が見えていない**: Blender MCP Serverなど、LLMからBlenderを操作する基盤が既に存在する

### 良い点

1. Geometry Nodesの基本理解は正しい方向
2. 「Claude Codeで自動化できる部分」と「人間の判断が必要な部分」の切り分けは的確
3. データソースを渡してClaude Codeの精度を上げるアプローチは有効

---

## 提案: 学習パスの修正

> **注記（2026-04-13）**: 以下の提案はv2ロードマップとして一時採用されたが、その後の議論で廃止。
> 理由: 創作目的（SNS発信: アニメシーン、物語映像化）に対してHoudini/地形生成ツールはオーバースペック。
> Blenderの対話的操作（Claude Code + bpy）に方針転換。
> 現在の方針: `docs/memo/ai_3dcg_usecases.md` を参照。

### ~~提案するロードマップ（近道）~~ → 不採用

上記の調査結果は参考情報として有用だが、学習ロードマップとしては不採用。
「プロのVFXワークフロー」を学ぶことが目的ではなく、「Claude Codeを通じてBlenderを対話的に操作し、創作に必要な3DCGスキルを身につける」ことが目的であるため。
