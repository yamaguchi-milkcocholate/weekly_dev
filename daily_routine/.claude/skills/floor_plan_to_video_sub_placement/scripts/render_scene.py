"""配置済みscene.blendを複数アングルでレンダリングする.

俯瞰・パースペクティブの2視点でレンダリングし、
Claude Codeが配置品質を評価できるようにする。

使い方:
  scripts/run_blender.sh --background <scene.blend> \
    --python .claude/skills/floor_plan_to_video_sub_placement/scripts/render_scene.py -- \
    <output_dir> [<walls.json>]
"""

import json
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def get_scene_bounds():
    """シーン内の全メッシュオブジェクトのBBoxを統合."""
    all_corners = []
    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        all_corners.extend(corners)

    if not all_corners:
        return Vector((0, 0, 0)), Vector((10, 10, 3))

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


def hide_ceiling():
    """天井オブジェクトをレンダリングから除外.

    madori.blendの床コレクションにある大きな平面（平面.033等）を非表示にする。
    """
    floor_col = bpy.data.collections.get("床")
    if not floor_col:
        return

    for obj in floor_col.objects:
        if obj.type != "MESH":
            continue
        # BBoxのZ最大値が高いもの = 天井相当
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        z_max = max(c.z for c in corners)
        z_min = min(c.z for c in corners)
        # 床面より上にある大きな平面を天井とみなす
        if z_max > 2.0 and (z_max - z_min) < 0.5:
            obj.hide_render = True
            print(f"  Hidden ceiling: {obj.name}")


def setup_lighting():
    """レンダリング用ライティングを設定."""
    # 既存のライトを確認
    existing_lights = [obj for obj in bpy.data.objects if obj.type == "LIGHT"]
    if existing_lights:
        return  # 既にライトがあればスキップ

    # サンライト追加
    light_data = bpy.data.lights.new("RenderSun", type="SUN")
    light_data.energy = 3.0
    light_obj = bpy.data.objects.new("RenderSun", light_data)
    light_obj.rotation_euler = (math.radians(50), 0, math.radians(30))
    bpy.context.scene.collection.objects.link(light_obj)


def setup_render_settings():
    """レンダリング設定."""
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x = 1200
    scene.render.resolution_y = 1200
    scene.render.image_settings.file_format = "PNG"
    scene.render.film_transparent = False

    # ワールド背景（未設定の場合）
    if not scene.world:
        world = bpy.data.worlds.new("SceneWorld")
        world.color = (0.9, 0.9, 0.9)
        scene.world = world


def render_top_view(center, size, output_path):
    """俯瞰（トップダウン）ビューをレンダリング."""
    cam_data = bpy.data.cameras.new("SceneTopCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = max(size.x, size.y) * 1.2

    cam_obj = bpy.data.objects.new("SceneTopCam", cam_data)
    cam_obj.location = (center.x, center.y, center.z + max(size) * 2)
    cam_obj.rotation_euler = (0, 0, 0)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
    print(f"  Top view: {output_path}")

    # カメラ削除
    bpy.data.objects.remove(cam_obj)
    bpy.data.cameras.remove(cam_data)


def set_wall_visibility(visible):
    """壁コレクションのレンダリング表示を切り替え."""
    wall_col = bpy.data.collections.get("壁")
    if not wall_col:
        return
    for obj in wall_col.objects:
        obj.hide_render = not visible
    print(f"  Walls {'shown' if visible else 'hidden'} for render")


def render_persp_view(center, size, output_path):
    """パースペクティブビューをレンダリング（壁非表示で家具を見渡す）."""
    cam_data = bpy.data.cameras.new("ScenePerspCam")
    cam_data.type = "PERSP"
    cam_data.lens = 28  # 広角

    dist = max(size.x, size.y) * 1.2
    # 南西の角から斜め上に配置（部屋を見渡す視点）
    cam_obj = bpy.data.objects.new("ScenePerspCam", cam_data)
    cam_obj.location = (
        center.x - dist * 0.6,
        center.y - dist * 0.8,
        center.z + size.z * 2.5,
    )

    # カメラを部屋中心に向ける
    direction = center - cam_obj.location
    rot_quat = direction.to_track_quat("-Z", "Y")
    cam_obj.rotation_euler = rot_quat.to_euler()

    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    # パースビューでは壁を非表示にして家具を見やすくする
    set_wall_visibility(False)

    bpy.context.scene.render.filepath = str(output_path)
    bpy.ops.render.render(write_still=True)
    print(f"  Perspective view: {output_path}")

    # 壁の表示を元に戻す
    set_wall_visibility(True)

    bpy.data.objects.remove(cam_obj)
    bpy.data.cameras.remove(cam_data)


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1 :]
    else:
        custom_args = []

    if len(custom_args) < 1:
        print("Usage: scripts/run_blender.sh --background <scene.blend> --python <this_script> -- <output_dir>")
        sys.exit(1)
    output_dir = Path(custom_args[0])
    scene_views_dir = output_dir / "scene_views"
    scene_views_dir.mkdir(parents=True, exist_ok=True)

    print("Setting up scene for rendering...")

    # 天井を非表示
    hide_ceiling()

    # ライティング設定
    setup_lighting()

    # レンダリング設定
    setup_render_settings()

    # シーン範囲を計算
    center, size = get_scene_bounds()
    print(f"  Scene bounds: center={center}, size={size}")

    # --- 俯瞰レンダリング ---
    render_top_view(center, size, scene_views_dir / "top.png")

    # --- パースペクティブレンダリング ---
    render_persp_view(center, size, scene_views_dir / "persp.png")

    print(f"\nScene renders saved to: {scene_views_dir}")


if __name__ == "__main__":
    main()
