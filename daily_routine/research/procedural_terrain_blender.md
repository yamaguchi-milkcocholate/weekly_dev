# Blenderでプロシージャル自然地形を生成する手法 調査レポート

調査日: 2026-04-08

## 1. 主な手法の一覧と比較

### 1-1. Plane + Subdivision + Displace Modifier

最もシンプルな古典的手法。Planeメッシュにsubdivisionを適用し、Displace ModifierでHeightmapや内蔵プロシージャルテクスチャ(Clouds, Musgrave等)を使って変形する。

| 項目 | 評価 |
|------|------|
| 手軽さ | ★★★★★ 数分で地形が出る |
| リアルさ | ★★☆☆☆ 単一ノイズでは不自然 |
| 柔軟性 | ★★★☆☆ テクスチャの重ね掛けで改善可能 |
| bpy自動化 | ★★★★★ modifier追加・パラメータ設定がすべてbpyで可能 |
| 非破壊性 | ★★★★☆ modifier stackで調整可能 |

**手順:**
1. Plane追加 → Subdivision Surface Modifier (Simple, Level 6-8)
2. Displace Modifier追加 → 内蔵テクスチャ(Clouds/Voronoi)指定
3. 複数のDisplace Modifierを重ねて複雑な地形を表現
4. Blender 5.0+ではAdaptive Subdivisionが使えるため、レンダリング時に自動で必要な解像度に分割

**長所:** 理解しやすい、bpyで完全制御可能、レンダリング品質調整が容易
**短所:** 侵食表現が困難、大規模地形ではメモリ消費大

### 1-2. A.N.T. Landscape アドオン

Blender内蔵のプロシージャル地形生成アドオン。数学的ノイズ関数ベースで多様な地形パターンを生成。

| 項目 | 評価 |
|------|------|
| 手軽さ | ★★★★★ UIから即座に地形生成 |
| リアルさ | ★★★☆☆ 複数ノイズタイプと侵食機能あり |
| 柔軟性 | ★★★★☆ 豊富なパラメータ |
| bpy自動化 | ★★★★☆ bpy.ops.mesh.landscape()で呼び出し可能 |
| 非破壊性 | ★★☆☆☆ メッシュ生成後は破壊的操作 |

**主なパラメータ:**
- `noise_type`: ノイズの種類(hetero_terrain, fBm, Turbulence, Distorted Noise等)
- `basis_type`: 基底関数(Perlin, Voronoi, Cell Noise等)
- `subdivision_x/y`: メッシュ解像度
- `mesh_size_x/y`: 地形の実サイズ
- `noise_size`: ノイズスケール
- `noise_depth`: ノイズのオクターブ数
- `amplitude`, `frequency`, `lacunarity`, `dimension`, `offset`, `gain`: フラクタルパラメータ
- `random_seed`: 乱数シード
- `distortion`: ノイズの歪み量

**長所:** すぐ使える、侵食(erosion)機能内蔵、seed変更で無限バリエーション
**短所:** Geometry Nodesと比べて拡張性が低い、非破壊ワークフローではない

### 1-3. Geometry Nodes による地形生成

Blender 3.0以降の主力手法。ノードベースでプロシージャル地形を構築。Houdiniに匹敵するプロシージャルエンジンとして進化中。

| 項目 | 評価 |
|------|------|
| 手軽さ | ★★★☆☆ ノード構築の学習コストあり |
| リアルさ | ★★★★★ ノイズ重ね・擬似侵食が自由自在 |
| 柔軟性 | ★★★★★ あらゆる加工をノードで表現 |
| bpy自動化 | ★★★★★ ノードツリーをbpyで完全構築可能 |
| 非破壊性 | ★★★★★ 完全非破壊、パラメータ変更で即更新 |

**基本構成:**
```
Grid (高解像度) → Set Position (Z = Noise Texture * Height Factor)
```

**高度な構成:**
```
Grid → Noise Layer 1 (大地形: Scale大, 振幅大)
     → Noise Layer 2 (中地形: Scale中, 振幅中)
     → Noise Layer 3 (細部: Scale小, 振幅小)
     → Voronoi (尾根線)
     → 擬似侵食 (勾配計算 + 高さ補正)
     → Set Position
```

**長所:** 完全非破壊、LOD対応、マテリアルとの連携、bpyで全ノード構築可能
**短所:** 学習コストが最も高い、複雑なノードツリーは管理が大変

### 1-4. Sculpt（スカルプト）で手動造形

Blenderのスカルプトモードで直感的に地形を彫る手法。

| 項目 | 評価 |
|------|------|
| 手軽さ | ★★★★☆ 直感的操作 |
| リアルさ | ★★★★☆ アーティストの腕次第 |
| 柔軟性 | ★★★★★ 自由度は最高 |
| bpy自動化 | ★☆☆☆☆ 手動操作前提のため自動化不向き |
| 非破壊性 | ★☆☆☆☆ 完全に破壊的操作 |

**長所:** 特定の形状(特定の湾の形等)を意図的に作れる
**短所:** 再現性なし、バリエーション生成不可、Claude Code連携不可

### 1-5. 外部ツール（Gaea, World Machine等）→ Blenderインポート

専用地形生成ツールでHeightmapを生成し、Blenderに持ち込む手法。

| 項目 | 評価 |
|------|------|
| 手軽さ | ★★☆☆☆ 別ツール習得が必要 |
| リアルさ | ★★★★★ 物理ベース侵食シミュレーション |
| 柔軟性 | ★★★★☆ ツール内では自由度高い |
| bpy自動化 | ★★☆☆☆ インポート部分のみ自動化可能 |
| 非破壊性 | ★★☆☆☆ 再生成→再インポートが必要 |

**主な外部ツール:**
- **Gaea** (QuadSpinner): ノードベース地形生成。物理ベース侵食が強力。Gaea 3.0でBlenderプラグイン予定
- **World Machine**: 業界標準の地形生成ツール。Heightmap(EXR/PNG)エクスポート
- **World Creator**: リアルタイム地形生成。GPU加速

**Heightmapインポート手順:**
1. 外部ツールでHeightmap(16bit PNG or EXR)をエクスポート
2. BlenderでPlane + Subdivision + Displace Modifier
3. HeightmapをDisplaceのTexture Imageとして指定

**長所:** 最高品質の侵食表現、プロの映像制作で標準
**短所:** ツール間の往復、ライセンスコスト、自動化パイプライン構築が複雑

### 手法比較まとめ

| 手法 | リアルさ | bpy自動化 | 学習コスト | おすすめ用途 |
|------|---------|----------|-----------|------------|
| Displace Modifier | ★★ | ★★★★★ | 低 | プロトタイプ、背景地形 |
| A.N.T. Landscape | ★★★ | ★★★★ | 低 | 素早い地形生成、seed探索 |
| Geometry Nodes | ★★★★★ | ★★★★★ | 高 | 本格的プロシージャル地形 |
| Sculpt | ★★★★ | ★ | 中 | 特定形状の手動造形 |
| 外部ツール | ★★★★★ | ★★ | 高 | 映像制作、最高品質 |

---

## 2. リアルな山・谷・海岸線をプロシージャルで作るテクニック

### 2-1. 複数ノイズの重ね合わせ（ノイズレイヤリング）

自然地形は単一のノイズでは表現できない。複数のスケール・種類のノイズを重ねることで自然な外観を得る。

**推奨レイヤリング構成:**

| レイヤ | ノイズ種類 | Scale | 役割 |
|--------|----------|-------|------|
| 1. 大地形 | Perlin / fBm | 0.5-2.0 | 山塊・谷の大きな起伏 |
| 2. 尾根線 | Voronoi (Distance to Edge) | 1.0-3.0 | 山の稜線・尾根の構造 |
| 3. 中ディテール | Ridged Multifractal | 3.0-10.0 | 中規模の凹凸・岩場 |
| 4. 細部テクスチャ | Perlin (高周波) | 10.0-50.0 | 地表の細かい凹凸 |
| 5. 歪み | Domain Warping | - | ノイズの入力座標を別ノイズで歪める→自然な不規則性 |

**Voronoiノイズの活用:**
- Voronoiの「Distance to Edge」モードは、セル境界にリッジ(稜線)を形成
- これが山の尾根線に見えるため、山岳地形のベースとして非常に有効
- Voronoi → Perlinの加算で「尾根のある山」が自然に表現される

**Domain Warping（ドメインワーピング）:**
- ノイズの入力座標を別のノイズで変形させるテクニック
- 自然界の地形が持つ「不規則な曲がり」を再現
- Geometry NodesではPosition → Noise Texture → Add → Noise Texture2で実現

### 2-2. 侵食（Erosion）の表現

侵食は地形のリアルさを決定的に左右する要素。完全な物理シミュレーションはBlender単体では困難だが、擬似的な表現は可能。

**擬似侵食テクニック:**

1. **Finite Derivative Approximation（勾配ベース侵食）**
   - 各点のノイズの勾配（傾斜）を計算
   - 急斜面ほど高さを減少させる → 谷が形成される
   - Geometry NodesのSample Nearest + 隣接点比較で実装可能

2. **Ridged Multifractal Noise**
   - `abs(noise)` を反転させたノイズ → 谷に沿った鋭い稜線を生成
   - 侵食によって形成される尾根・谷に似た形状を直接生成

3. **高さに応じたノイズ変調**
   - 標高が高いほど侵食が強い（急峻な地形）
   - 標高が低いほど堆積が進む（なだらかな地形）
   - Map Range + Mix で高さ依存のノイズブレンドを実現

4. **A.N.T. Landscapeの内蔵侵食**
   - Erosion Mixerがheightmapをブレンドして侵食効果を付与
   - 手軽だがカスタマイズ性は低い

### 2-3. 海岸線の作り方

「山が海に落ち込む湾」を表現するには:

1. **海面の設定**
   - 単純なPlaneを海面高さに配置（Z=0に設定するのが一般的）
   - Ocean Modifierで波のあるリアルな海面を生成可能
   - 地形メッシュの海面以下の部分が「海底」になる

2. **海岸線の制御**
   - 地形の高さが海面と交差する等高線が海岸線になる
   - ノイズのオフセットを調整して海岸線の位置を制御
   - Clamp/Map Rangeで海面付近の高さを平坦化 → 砂浜の表現

3. **湾の形状制御**
   - 大スケールのノイズで凹んだ領域 = 湾
   - マスクテクスチャを使って特定領域を凹ませる
   - Geometry NodesではDistance + Gradient Textureで湾の形をガイド

### 2-4. 崖・急斜面の表現

- **Voronoi (Smooth F1)** で台地状の構造を生成 → 急な段差が崖になる
- **Power/Clamp** でノイズ値のコントラストを上げる → 平坦部と急斜面の差が生まれる
- **法線に基づくマテリアル分岐:** 法線のZ成分で崖面（急斜面）と平地を判定し、異なるマテリアルを適用

---

## 3. プロの環境アーティストのワークフロー

### 3-1. 段階的アプローチ（大→中→小）

プロの環境アーティストは以下の3段階で地形を構築する:

**Phase 1: シルエット / 大地形 (Primary Forms)**
- 山塊、谷、湾の全体的な形状を定義
- 低周波ノイズ(Scale 0.5-2.0)で大まかな起伏
- この段階で「山が海に落ち込む湾」の全体像を決める
- カメラアングルから見たシルエットを重視

**Phase 2: 中間ディテール (Secondary Forms)**
- 尾根、谷筋、台地、崖の構造
- 中周波ノイズ(Scale 3.0-10.0)を追加
- 侵食表現の適用
- 地形の「読みやすさ」を確認

**Phase 3: 表面ディテール (Tertiary Forms)**
- 岩の凹凸、小石、地表の細かいテクスチャ
- 高周波ノイズ(Scale 10.0+)
- カメラ近くのみ高解像度（LOD最適化）

### 3-2. ハイブリッドワークフロー

最も効率的なワークフローは複数手法の組み合わせ:

1. **A.N.T. Landscapeまたは外部ツール**で大まかな地形のベース生成
2. **Sculpt Mode**で意図的な形状調整（湾の形、山の位置等）
3. **Geometry Nodes**で侵食・ディテール・マテリアル分岐を追加
4. **Ocean Modifier**で海面を追加
5. **Particle System / Geometry Nodes Scatter**で植生配置

### 3-3. 参考写真の活用

- 参考写真をBlenderのBackground Imageとして設定
- カメラアングルを参考写真に合わせてからシルエットを調整
- 地形の形状よりも「光の当たり方」「影の落ち方」が印象を決める

---

## 4. bpyスクリプトでの自動化可能性

### 4-1. 手法別の自動化適性

| 手法 | Python自動化 | 具体的な方法 |
|------|-------------|-------------|
| Displace Modifier | 完全自動化可能 | `bpy.ops.object.modifier_add(type='DISPLACE')` + テクスチャパラメータ設定 |
| A.N.T. Landscape | 完全自動化可能 | `bpy.ops.mesh.landscape(noise_type=..., random_seed=...)` |
| Geometry Nodes | 完全自動化可能 | `bpy.data.node_groups.new()` でノードツリー構築 |
| Sculpt | 自動化困難 | ブラシストロークの自動化は非現実的 |
| 外部ツール | インポート部分のみ | Heightmap読み込み → Displace適用 |

### 4-2. Geometry Nodesのbpy構築パターン

```python
import bpy
import mathutils

# 1. Grid メッシュ作成
bpy.ops.mesh.primitive_grid_add(x_subdivisions=256, y_subdivisions=256, size=100)
terrain = bpy.context.active_object

# 2. Geometry Nodes Modifier追加
mod = terrain.modifiers.new(name="TerrainGen", type='NODES')

# 3. ノードツリー作成
node_tree = bpy.data.node_groups.new(name="TerrainNodes", type='GeometryNodeTree')
mod.node_group = node_tree

# 4. ノード追加
group_input = node_tree.nodes.new('NodeGroupInput')
group_output = node_tree.nodes.new('NodeGroupOutput')
noise_node = node_tree.nodes.new('ShaderNodeTexNoise')
set_position = node_tree.nodes.new('GeometryNodeSetPosition')
combine_xyz = node_tree.nodes.new('ShaderNodeCombineXYZ')
multiply = node_tree.nodes.new('ShaderNodeMath')
multiply.operation = 'MULTIPLY'

# 5. パラメータ設定
noise_node.inputs['Scale'].default_value = 2.0
noise_node.inputs['Detail'].default_value = 8.0
multiply.inputs[1].default_value = 10.0  # 高さスケール

# 6. ノード接続
links = node_tree.links
links.new(group_input.outputs[0], set_position.inputs['Geometry'])
links.new(noise_node.outputs['Fac'], multiply.inputs[0])
links.new(multiply.outputs[0], combine_xyz.inputs['Z'])
links.new(combine_xyz.outputs[0], set_position.inputs['Offset'])
links.new(set_position.outputs[0], group_output.inputs[0])
```

### 4-3. A.N.T. Landscapeのbpy呼び出し

```python
import bpy

# A.N.T. Landscapeアドオン有効化
bpy.ops.preferences.addon_enable(module='ant_landscape')

# 地形生成（主要パラメータ）
bpy.ops.mesh.landscape(
    ant_terrain_name="MountainBay",
    mesh_size_x=100.0,
    mesh_size_y=100.0,
    subdivision_x=256,
    subdivision_y=256,
    noise_type='hetero_terrain',   # 異質地形ノイズ
    basis_type='PERLIN_ORIGINAL',   # 基底関数
    random_seed=42,
    noise_size=1.5,
    noise_depth=8,
    amplitude=1.0,
    frequency=2.0,
    dimension=1.0,
    lacunarity=2.0,
    offset=0.5,
)
```

### 4-4. seedベースのバリエーション生成

```python
# 複数バリエーション一括生成
for seed in range(10):
    bpy.ops.mesh.landscape(
        ant_terrain_name=f"Terrain_{seed:03d}",
        random_seed=seed,
        noise_type='hetero_terrain',
        subdivision_x=256,
        subdivision_y=256,
        noise_size=1.5,
        noise_depth=8,
    )
    # レンダリングして比較画像を出力
    bpy.context.scene.render.filepath = f"//renders/terrain_{seed:03d}.png"
    bpy.ops.render.render(write_still=True)
    # 生成したメッシュを削除（次のバリエーション用）
    bpy.ops.object.delete()
```

### 4-5. geonodesライブラリの活用

[geonodes](https://github.com/al1brn/geonodes) ライブラリを使えば、Geometry Nodesツリーをより直感的なPythonコードで構築できる。bpy直接操作より可読性が高い。

---

## 5. 最もおすすめのアプローチ

### 推奨: Geometry Nodes（bpyでノードツリー構築）

Claude Code + bpyスクリプトとの相性を考えると、**Geometry Nodesをbpyで構築する手法**が最適。

**理由:**

1. **完全自動化可能**: ノードツリーの作成・接続・パラメータ設定がすべてbpy APIで制御可能
2. **完全非破壊**: パラメータ変更で即座に地形が更新される。試行錯誤に最適
3. **バリエーション生成**: Group Inputにパラメータを露出させれば、スクリプトからパラメータを振って複数バリエーションを出せる
4. **段階的構築**: ノイズレイヤーを1つずつ追加してプレビューしながら構築できる
5. **マテリアル連携**: 高さ・法線情報をシェーダーに渡して自動マテリアル分岐が可能
6. **拡張性**: 植生配置、岩の配置、海面との交差処理もすべてGeometry Nodesで統合可能

### 「山が海に落ち込む湾」の推奨実装戦略

```
Step 1: 大地形のベース
  - Grid (256x256) + Noise Texture (Scale=1.5, Detail=8) → Set Position Z
  - 全体の山・谷の起伏を定義

Step 2: 尾根線の追加
  - Voronoi Texture (Distance to Edge) を加算
  - 山の稜線構造が出現

Step 3: 湾の形状ガイド
  - Distance from Center + Gradient → 中央付近を凹ませて湾を形成
  - または手動でカーブを配置し、カーブからの距離で湾をマスク

Step 4: 擬似侵食
  - 勾配計算 → 急斜面の高さを減少
  - Ridged Multifractal で谷筋を強調

Step 5: 海面
  - Plane (Z=0) + Ocean Modifier で海面配置
  - 地形の海面以下の部分 = 海底

Step 6: 表面ディテール
  - 高周波ノイズで岩の凹凸追加
  - 法線ベースのマテリアル分岐（崖=岩、平地=草）

Step 7: 植生・岩配置
  - Distribute Points on Faces でインスタンス配置
  - 高さ・傾斜でフィルタリング
```

### 次善策: A.N.T. Landscape + Geometry Nodes ハイブリッド

Geometry Nodesの学習コストが高い場合は:

1. A.N.T. Landscapeでベース地形を素早く生成（seedを振って探索）
2. 気に入った地形にGeometry Nodes Modifierで追加ディテール
3. Ocean Modifierで海面

この手法はbpy.ops.mesh.landscape()一発でベース地形が出るため、プロトタイプが速い。

---

## 参考リンク

- [Blender 5 revolutionizes environment creation with procedural tools](https://foro3d.com/en/2026/january/blender-5-revolutionizes-environment-creation-with-procedural-tools.html)
- [How To Create Procedural Landscapes in Blender 4.3 - MipMap](https://mipmap.substack.com/p/how-to-create-procedural-landscapes)
- [Digital terrain generation in Blender and Rhino](https://medium.com/@Jamesroha/digital-terrain-generation-in-blender-and-rhino-a-practical-student-guide-7c765a7e0e28)
- [Procedural Terrain 2.0 - Geometry Nodes Terrain Generator (BlenderKit)](https://www.blenderkit.com/addons/9ef8471a-d401-4404-98f9-093837891b43/)
- [A.N.T. Landscape Blender Extensions](https://extensions.blender.org/add-ons/antlandscape/)
- [Terrain Mixer Blender Extension](https://extensions.blender.org/add-ons/terrainmixer/)
- [Terrain Nodes add-on](https://vsb.gumroad.com/l/yOnrv)
- [World Blender - Geometry Node Landscape Generator](https://superhivemarket.com/products/world-blender-2025)
- [geonodes - Python library for Geometry Nodes](https://github.com/al1brn/geonodes)
- [sdawzy/procedural-terrain-generation-blender (GitHub)](https://github.com/sdawzy/procedural-terrain-generation-blender)
- [Blender Geometry Nodes to Unreal Engine 5 guide](https://medium.com/@Jamesroha/blender-geometry-nodes-to-unreal-engine-5-the-procedural-environment-art-guide-05cf8d8b4701)
- [A Clean Gaea-to-Blender Pipeline (BlenderNation)](https://www.blendernation.com/2025/12/29/a-clean-gaea-to-blender-pipeline-for-terrain-fog-and-final-renders/)
- [Gaea 3.0 (QuadSpinner)](https://quadspinner.com/Gaea3)
- [Noise Texture Node - Blender 5.1 Manual](https://docs.blender.org/manual/en/latest/modeling/geometry_nodes/texture/noise.html)
- [Ocean Modifier - Blender 5.1 Manual](https://docs.blender.org/manual/en/latest/modeling/modifiers/physics/ocean.html)
- [Perlin Noise for Procedural Terrain Generation](https://www.jdhwilkins.com/mountains-cliffs-and-caves-a-comprehensive-guide-to-using-perlin-noise-for-procedural-generation)
- [Red Blob Games: Making maps with noise](https://www.redblobgames.com/maps/terrain-from-noise/)
- [Building Better Terrain (Blog)](http://thingonitsown.blogspot.com/2018/11/building-better-terrain.html)
- [Blender Python Procedural Level Generation (GitHub)](https://github.com/aaronjolson/Blender-Python-Procedural-Level-Generation)
- [Blender: Procedural Generation with Python API](https://hamy.xyz/blog/blender-procedural-generation-python)
- [Terrain Creation Workflow Proposal (Blender Developer Forum)](https://devtalk.blender.org/t/terrain-creation-workflow-proposal/22681)
