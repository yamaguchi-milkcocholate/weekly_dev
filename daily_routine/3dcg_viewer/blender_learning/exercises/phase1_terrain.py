"""Phase 1: Geometry Nodesで島の地形ベースを生成する.

リファレンス: 亜熱帯の島（丘陵 + 海岸線 + 海）
ワークフロー: このスクリプトでベース地形を生成 → Sculpt Modeで手動調整

使い方:
    scripts/run_blender.sh --background --python blender_level_up/exercises/phase1_terrain.py
    → blender_level_up/exercises/phase1_terrain.blend に保存される
    → Blenderで開いてSculpt Modeで調整する
"""

import bpy
import os

# --- シーン初期化 ---
bpy.ops.wm.read_factory_settings(use_empty=True)

# --- 地形メッシュ作成 ---
bpy.ops.mesh.primitive_plane_add(size=20, location=(0, 0, 0))
terrain = bpy.context.active_object
terrain.name = "Terrain"

# SubDivision（Simple）で解像度を上げる
subsurf = terrain.modifiers.new(name="Subdivide", type='SUBSURF')
subsurf.subdivision_type = 'SIMPLE'
subsurf.levels = 7  # 128x128 = 16384面
subsurf.render_levels = 7
# Apply して頂点を確定
bpy.ops.object.modifier_apply(modifier=subsurf.name)

# --- Geometry Nodes で地形高さを生成 ---
# Geometry Nodesモディファイアを追加
geo_mod = terrain.modifiers.new(name="TerrainGen", type='NODES')

# ノードグループ作成
node_group = bpy.data.node_groups.new(name="TerrainGenerator", type='GeometryNodeTree')
geo_mod.node_group = node_group

# 入出力ソケット設定
node_group.interface.new_socket("Geometry", in_out='INPUT', socket_type='NodeSocketGeometry')
node_group.interface.new_socket("Geometry", in_out='OUTPUT', socket_type='NodeSocketGeometry')

# ノード作成
input_node = node_group.nodes.new('NodeGroupInput')
input_node.location = (-600, 0)

output_node = node_group.nodes.new('NodeGroupOutput')
output_node.location = (600, 0)

# Set Position ノード
set_pos = node_group.nodes.new('GeometryNodeSetPosition')
set_pos.location = (300, 0)

# Position ノード（現在の頂点位置を取得）
position = node_group.nodes.new('GeometryNodeInputPosition')
position.location = (-400, -200)

# Noise Texture 1: 大地形（山塊）
noise1 = node_group.nodes.new('ShaderNodeTexNoise')
noise1.location = (-200, -100)
noise1.inputs['Scale'].default_value = 1.5  # 大きなうねり
noise1.inputs['Detail'].default_value = 4.0
noise1.inputs['Roughness'].default_value = 0.6
noise1.noise_dimensions = '3D'
noise1.label = "大地形ノイズ"

# Noise Texture 2: 中地形（尾根・谷）
noise2 = node_group.nodes.new('ShaderNodeTexNoise')
noise2.location = (-200, -350)
noise2.inputs['Scale'].default_value = 3.0  # 中程度のディテール
noise2.inputs['Detail'].default_value = 6.0
noise2.inputs['Roughness'].default_value = 0.5
noise2.noise_dimensions = '3D'
noise2.label = "中地形ノイズ"

# Math: 大地形 × 重み
math_mul1 = node_group.nodes.new('ShaderNodeMath')
math_mul1.location = (0, -100)
math_mul1.operation = 'MULTIPLY'
math_mul1.inputs[1].default_value = 3.0  # 高さスケール（大地形）
math_mul1.label = "大地形の高さ"

# Math: 中地形 × 重み
math_mul2 = node_group.nodes.new('ShaderNodeMath')
math_mul2.location = (0, -350)
math_mul2.operation = 'MULTIPLY'
math_mul2.inputs[1].default_value = 0.8  # 高さスケール（中地形）
math_mul2.label = "中地形の高さ"

# Math: 合算
math_add = node_group.nodes.new('ShaderNodeMath')
math_add.location = (150, -200)
math_add.operation = 'ADD'
math_add.label = "合算"

# Combine XYZ: Z方向のオフセットに変換
combine = node_group.nodes.new('ShaderNodeCombineXYZ')
combine.location = (300, -200)

# --- リンク接続 ---
links = node_group.links

# Input → Set Position → Output
links.new(input_node.outputs['Geometry'], set_pos.inputs['Geometry'])
links.new(set_pos.outputs['Geometry'], output_node.inputs['Geometry'])

# Position → Noise Textures
links.new(position.outputs['Position'], noise1.inputs['Vector'])
links.new(position.outputs['Position'], noise2.inputs['Vector'])

# Noise → Multiply → Add → Combine XYZ → Offset
links.new(noise1.outputs['Fac'], math_mul1.inputs[0])
links.new(noise2.outputs['Fac'], math_mul2.inputs[0])
links.new(math_mul1.outputs['Value'], math_add.inputs[0])
links.new(math_mul2.outputs['Value'], math_add.inputs[1])
links.new(math_add.outputs['Value'], combine.inputs['Z'])

# Combine XYZ → Set Position Offset
links.new(combine.outputs['Vector'], set_pos.inputs['Offset'])

# --- Geometry Nodesを適用して頂点を確定 ---
bpy.ops.object.modifier_apply(modifier=geo_mod.name)

# --- 海面メッシュ作成 ---
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, 1.5))
ocean = bpy.context.active_object
ocean.name = "Ocean"

# Ocean Modifier
ocean_mod = ocean.modifiers.new(name="Ocean", type='OCEAN')
ocean_mod.geometry_mode = 'GENERATE'
ocean_mod.resolution = 12
ocean_mod.wind_velocity = 4.0  # 穏やかな海
ocean_mod.depth = 200
ocean_mod.choppiness = 1.0
ocean_mod.wave_scale = 0.5

# --- カメラ配置（リファレンス画像に近い構図） ---
bpy.ops.object.camera_add(
    location=(15, -12, 8),
    rotation=(1.1, 0, 0.8),
)
camera = bpy.context.active_object
camera.name = "Camera"
bpy.context.scene.camera = camera

# --- Sun Light ---
bpy.ops.object.light_add(
    type='SUN',
    location=(0, 0, 20),
    rotation=(0.8, 0.2, -0.5),
)
sun = bpy.context.active_object
sun.name = "Sun"
sun.data.energy = 3.0

# --- 保存 ---
output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "phase1_terrain.blend")
bpy.ops.wm.save_as_mainfile(filepath=output_path)
print(f"保存完了: {output_path}")
print("次のステップ: Blenderで開いてTerrainオブジェクトをSculpt Modeで調整してください")
