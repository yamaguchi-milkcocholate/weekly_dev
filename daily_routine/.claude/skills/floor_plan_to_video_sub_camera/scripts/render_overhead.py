"""scene.blendの俯瞰レンダリングを生成する（汎用版）.

シーンの空間範囲を自動計算し、間取り全体が収まる俯瞰画像を生成する。
天井はz高さヒューリスティックで自動検出・非表示。

Usage:
    scripts/run_blender.sh --background <scene.blend> \
      --python .claude/skills/floor_plan_to_video_sub_camera/scripts/render_overhead.py -- \
      --output <output.png> [--resolution 1920] [--room-bounds <room_bounds.json>]
"""

import json
import sys
from pathlib import Path

import bpy


def compute_scene_bounds() -> dict:
    """全メッシュオブジェクトからシーン範囲を計算する."""
    x_min, x_max = float("inf"), float("-inf")
    y_min, y_max = float("inf"), float("-inf")
    z_max = 0.0

    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        for v in obj.data.vertices:
            wv = obj.matrix_world @ v.co
            x_min = min(x_min, wv.x)
            x_max = max(x_max, wv.x)
            y_min = min(y_min, wv.y)
            y_max = max(y_max, wv.y)
            z_max = max(z_max, wv.z)

    return {
        "x_min": x_min, "x_max": x_max,
        "y_min": y_min, "y_max": y_max,
        "z_max": z_max,
        "center_x": (x_min + x_max) / 2,
        "center_y": (y_min + y_max) / 2,
        "width": x_max - x_min,
        "height": y_max - y_min,
    }


def hide_ceiling_objects(wall_z_max: float) -> list:
    """天井オブジェクトをz高さヒューリスティックで検出し非表示にする."""
    hidden = []
    for col_name in ("Structure", "Walls"):
        col = bpy.data.collections.get(col_name)
        if not col:
            continue
        for obj in col.objects:
            if obj.type != "MESH":
                continue
            z_min = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
            if z_min > wall_z_max * 0.9:
                obj.hide_render = True
                hidden.append(obj)
                print(f"[天井非表示] {obj.name} (z_min={z_min:.2f})")

    # フォールバック: "Ceiling"という名前のオブジェクト
    ceiling = bpy.data.objects.get("Ceiling")
    if ceiling and ceiling not in hidden:
        ceiling.hide_render = True
        hidden.append(ceiling)
        print(f"[天井非表示] {ceiling.name}")

    return hidden


def get_wall_z_max() -> float:
    """壁の最大高さを取得する."""
    z_max = 2.4  # デフォルト
    for col_name in ("Walls",):
        col = bpy.data.collections.get(col_name)
        if not col:
            continue
        for obj in col.objects:
            if obj.type == "MESH":
                for v in obj.data.vertices:
                    wv = obj.matrix_world @ v.co
                    z_max = max(z_max, wv.z)
    return z_max


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    output_path = None
    resolution = 1920
    room_bounds_path = None
    i = 0
    while i < len(custom_args):
        if custom_args[i] == "--output":
            output_path = Path(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--resolution":
            resolution = int(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--room-bounds":
            room_bounds_path = Path(custom_args[i + 1])
            i += 2
        else:
            i += 1

    if not output_path:
        print("Usage: ... -- --output <output.png> [--resolution 1920] [--room-bounds <bounds.json>]")
        sys.exit(1)

    output_path.parent.mkdir(parents=True, exist_ok=True)

    # シーン範囲を取得
    if room_bounds_path and room_bounds_path.exists():
        bounds_data = json.loads(room_bounds_path.read_text())
        sb = bounds_data["scene_bounds"]
        scene_width = sb["x_max"] - sb["x_min"]
        scene_height = sb["y_max"] - sb["y_min"]
        center_x = sb["center_x"]
        center_y = sb["center_y"]
        print(f"room_bounds.jsonから範囲取得: {scene_width:.1f}x{scene_height:.1f}m")
    else:
        bounds = compute_scene_bounds()
        scene_width = bounds["width"]
        scene_height = bounds["height"]
        center_x = bounds["center_x"]
        center_y = bounds["center_y"]
        print(f"シーンから範囲計算: {scene_width:.1f}x{scene_height:.1f}m")

    # ortho_scaleをシーン範囲から自動計算（マージン20%）
    ortho_scale = max(scene_width, scene_height) * 1.2

    # アスペクト比をシーン範囲に合わせる
    if scene_height > scene_width:
        aspect_ratio = scene_height / scene_width
    else:
        aspect_ratio = scene_width / scene_height
    resolution_y = int(resolution * aspect_ratio) if scene_height > scene_width else resolution
    resolution_x = resolution if scene_height > scene_width else int(resolution * aspect_ratio)

    # 俯瞰カメラを作成
    cam_data = bpy.data.cameras.new("OverheadCam")
    cam_data.type = "ORTHO"
    cam_data.ortho_scale = ortho_scale
    cam_obj = bpy.data.objects.new("OverheadCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)

    # シーン中心の真上から見下ろす
    cam_obj.location = (center_x, center_y, 25.0)
    cam_obj.rotation_euler = (0.0, 0.0, 0.0)

    bpy.context.scene.camera = cam_obj

    # 天井を非表示
    wall_z_max = get_wall_z_max()
    hidden_objects = hide_ceiling_objects(wall_z_max)

    # 既存ライトを削除
    for obj in list(bpy.data.objects):
        if obj.type == "LIGHT":
            bpy.data.objects.remove(obj, do_unlink=True)

    # 真上にサンライトを配置（影なし）
    sun_data = bpy.data.lights.new("OverheadSun", "SUN")
    sun_data.energy = 5.0
    sun_data.use_shadow = False
    sun_obj = bpy.data.objects.new("OverheadSun", sun_data)
    sun_obj.location = (center_x, center_y, 30)
    sun_obj.rotation_euler = (0, 0, 0)
    bpy.context.scene.collection.objects.link(sun_obj)

    # 環境光を追加（均一照明）
    world = bpy.data.worlds.get("World")
    if not world:
        world = bpy.data.worlds.new("World")
    bpy.context.scene.world = world
    world.use_nodes = True
    bg_node = world.node_tree.nodes.get("Background")
    if bg_node:
        bg_node.inputs["Strength"].default_value = 5.0
        bg_node.inputs["Color"].default_value = (1.0, 1.0, 1.0, 1.0)

    # EEVEE で高速レンダリング
    bpy.context.scene.render.engine = "BLENDER_EEVEE"
    bpy.context.scene.render.resolution_x = resolution_x
    bpy.context.scene.render.resolution_y = resolution_y
    bpy.context.scene.render.resolution_percentage = 100
    bpy.context.scene.render.film_transparent = False
    bpy.context.scene.render.image_settings.file_format = "PNG"
    bpy.context.scene.render.filepath = str(output_path.resolve())

    # レンダリング実行
    bpy.ops.render.render(write_still=True)
    print(f"俯瞰レンダリング出力: {output_path} ({resolution_x}x{resolution_y})")

    # クリーンアップ
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)
    bpy.data.objects.remove(sun_obj, do_unlink=True)
    bpy.data.lights.remove(sun_data)
    for obj in hidden_objects:
        obj.hide_render = False


if __name__ == "__main__":
    main()
