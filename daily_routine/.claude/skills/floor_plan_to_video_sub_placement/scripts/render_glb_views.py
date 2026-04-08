"""各GLBアセットをトップダウン+パースペクティブでレンダリングする.

軸方向を示す色付き矢印（赤=+X, 緑=+Y）を配置し、
Claude Codeがfront方向を判定できるようにする。

使い方:
  scripts/run_blender.sh --background --python \
    .claude/skills/floor_plan_to_video_sub_placement/scripts/render_glb_views.py -- \
    <assets.json> <output_dir>
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def clear_scene():
    """シーンを完全にクリア."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    # デフォルトコレクションを確保
    if not bpy.context.scene.collection.children:
        pass  # use_empty=True で空のシーンになる


def setup_lighting():
    """環境光+サンライトを設定."""
    # ワールド背景を白に（Blender 5.0+: use_nodes非推奨、直接色設定）
    world = bpy.data.worlds.new("White")
    world.color = (1, 1, 1)
    bpy.context.scene.world = world

    # サンライト
    light_data = bpy.data.lights.new("Sun", type="SUN")
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("Sun", light_data)
    light_obj.rotation_euler = (math.radians(45), 0, math.radians(45))
    bpy.context.scene.collection.objects.link(light_obj)

    # 反対側からの補助光
    fill_data = bpy.data.lights.new("Fill", type="SUN")
    fill_data.energy = 1.0
    fill_obj = bpy.data.objects.new("Fill", fill_data)
    fill_obj.rotation_euler = (math.radians(60), 0, math.radians(-135))
    bpy.context.scene.collection.objects.link(fill_obj)


def create_axis_arrows(bbox_size):
    """軸方向を示す色付き矢印を作成.

    赤矢印 = +X方向, 緑矢印 = +Y方向。
    矢印はBBoxの外側に配置し、家具と重ならないようにする。
    """
    arrow_length = max(bbox_size) * 0.8
    arrow_radius = arrow_length * 0.06
    cone_radius = arrow_radius * 4
    cone_height = arrow_length * 0.2
    offset = max(bbox_size) * 0.8  # BBox外に配置

    arrows = []

    for axis, color, direction in [
        ("X", (1, 0, 0, 1), Vector((1, 0, 0))),
        ("Y", (0, 0.7, 0, 1), Vector((0, 1, 0))),
    ]:
        # 矢印の始点（BBox外）
        start = direction * (-offset)

        # シリンダー（矢印の棒部分）
        bpy.ops.mesh.primitive_cylinder_add(
            radius=arrow_radius,
            depth=arrow_length,
            location=(
                start.x + direction.x * arrow_length / 2,
                start.y + direction.y * arrow_length / 2,
                0,
            ),
        )
        shaft = bpy.context.active_object
        shaft.name = f"arrow_{axis}_shaft"

        # 回転: デフォルトはZ軸方向なので、X/Y軸に合わせる
        if axis == "X":
            shaft.rotation_euler = (0, math.radians(90), 0)
        elif axis == "Y":
            shaft.rotation_euler = (math.radians(-90), 0, 0)

        # コーン（矢印の先端）
        bpy.ops.mesh.primitive_cone_add(
            radius1=cone_radius,
            radius2=0,
            depth=cone_height,
            location=(
                start.x + direction.x * (arrow_length + cone_height / 2),
                start.y + direction.y * (arrow_length + cone_height / 2),
                0,
            ),
        )
        cone = bpy.context.active_object
        cone.name = f"arrow_{axis}_cone"

        if axis == "X":
            cone.rotation_euler = (0, math.radians(90), 0)
        elif axis == "Y":
            cone.rotation_euler = (math.radians(-90), 0, 0)

        # マテリアル設定（Emission で確実に色を出す）
        mat = bpy.data.materials.new(f"arrow_{axis}_mat")
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links
        # デフォルトのPrincipled BSDFを削除
        for node in nodes:
            nodes.remove(node)
        # Emission + Output のみ
        output_node = nodes.new("ShaderNodeOutputMaterial")
        emission_node = nodes.new("ShaderNodeEmission")
        emission_node.inputs["Color"].default_value = color
        emission_node.inputs["Strength"].default_value = 5.0
        links.new(emission_node.outputs["Emission"], output_node.inputs["Surface"])
        shaft.data.materials.append(mat)
        cone.data.materials.append(mat)

        arrows.extend([shaft, cone])

    return arrows


def setup_camera_top(bbox_center, bbox_size):
    """トップダウンカメラを設定."""
    cam_data = bpy.data.cameras.new("TopCam")
    cam_data.type = "ORTHO"
    # BBox全体が収まるよう、余白付きでortho_scaleを設定
    cam_data.ortho_scale = max(bbox_size[0], bbox_size[1]) * 3.0

    cam_obj = bpy.data.objects.new("TopCam", cam_data)
    cam_obj.location = (bbox_center.x, bbox_center.y, bbox_center.z + max(bbox_size) * 3)
    cam_obj.rotation_euler = (0, 0, 0)  # 真下を向く（デフォルト-Z方向）
    bpy.context.scene.collection.objects.link(cam_obj)
    return cam_obj


def setup_camera_persp(bbox_center, bbox_size):
    """パースペクティブカメラを設定（斜め上45°から）."""
    cam_data = bpy.data.cameras.new("PerspCam")
    cam_data.type = "PERSP"
    cam_data.lens = 35

    dist = max(bbox_size) * 3.0
    cam_obj = bpy.data.objects.new("PerspCam", cam_data)
    cam_obj.location = (
        bbox_center.x + dist * 0.7,
        bbox_center.y - dist * 0.7,
        bbox_center.z + dist * 0.7,
    )
    # カメラをBBox中心に向ける
    direction = bbox_center - cam_obj.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()

    bpy.context.scene.collection.objects.link(cam_obj)
    return cam_obj


def setup_render_settings():
    """レンダリング設定."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 800
    scene.render.resolution_y = 800
    scene.render.film_transparent = True
    scene.render.image_settings.file_format = "PNG"


def get_imported_bbox(objects):
    """インポートされたオブジェクト群の統合BBoxを計算."""
    all_corners = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        all_corners.extend(corners)

    if not all_corners:
        return Vector((0, 0, 0)), Vector((1, 1, 1))

    bbox_min = Vector((
        min(c.x for c in all_corners),
        min(c.y for c in all_corners),
        min(c.z for c in all_corners),
    ))
    bbox_max = Vector((
        max(c.x for c in all_corners),
        max(c.y for c in all_corners),
        max(c.z for c in all_corners),
    ))
    center = (bbox_min + bbox_max) / 2
    size = bbox_max - bbox_min
    return center, size


def render_single_glb(glb_path, asset_id, output_dir):
    """1つのGLBを2アングルでレンダリング."""
    clear_scene()
    setup_lighting()
    setup_render_settings()

    # GLBインポート
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    imported_objects = list(bpy.context.selected_objects)

    if not imported_objects:
        print(f"  Warning: No objects imported from {glb_path}")
        return

    # BBox計算
    bbox_center, bbox_size = get_imported_bbox(imported_objects)

    # 軸矢印を追加
    create_axis_arrows(bbox_size)

    # --- トップダウンレンダリング ---
    cam_top = setup_camera_top(bbox_center, bbox_size)
    bpy.context.scene.camera = cam_top

    top_path = output_dir / f"{asset_id}_top.png"
    bpy.context.scene.render.filepath = str(top_path)
    bpy.ops.render.render(write_still=True)
    print(f"  Top view: {top_path}")

    # --- パースペクティブレンダリング ---
    cam_persp = setup_camera_persp(bbox_center, bbox_size)
    bpy.context.scene.camera = cam_persp

    persp_path = output_dir / f"{asset_id}_persp.png"
    bpy.context.scene.render.filepath = str(persp_path)
    bpy.ops.render.render(write_still=True)
    print(f"  Perspective view: {persp_path}")


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1 :]
    else:
        custom_args = []

    if len(custom_args) < 2:
        print("Usage: scripts/run_blender.sh --background --python <this_script> -- <assets.json> <output_dir>")
        sys.exit(1)
    assets_path = Path(custom_args[0])
    output_dir = Path(custom_args[1])

    glb_views_dir = output_dir / "glb_views"
    glb_views_dir.mkdir(parents=True, exist_ok=True)

    # assets.json読み込み
    assets_data = json.loads(assets_path.read_text(encoding="utf-8"))

    for asset in assets_data["assets"]:
        asset_id = asset["id"]
        glb_path = assets_path.parent / asset["glb"]

        if not glb_path.exists():
            print(f"Warning: GLB not found: {glb_path}")
            continue

        print(f"Rendering {asset_id}: {glb_path}")
        render_single_glb(glb_path, asset_id, glb_views_dir)

    print(f"\nAll renders saved to: {glb_views_dir}")


if __name__ == "__main__":
    main()
