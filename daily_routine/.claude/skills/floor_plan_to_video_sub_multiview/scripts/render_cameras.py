"""カメラ位置JSONを読み込み、各カメラからマテリアルプレビュー相当で画像を出力する.

使い方:
    scripts/run_blender.sh --background <input_dir>/scene.blend \
      --python .claude/skills/floor_plan_to_video_sub_multiview/scripts/render_cameras.py -- <output_dir>
"""

import json
import sys
from pathlib import Path

import bpy


def setup_hdri_world(scene):
    """EEVEE + HDRI環境照明を設定する（Material Preview相当）."""
    scene.render.engine = "BLENDER_EEVEE"

    world = scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    bg_node = nodes.new("ShaderNodeBackground")
    bg_node.inputs["Strength"].default_value = 1.0
    bg_node.inputs["Color"].default_value = (0.8, 0.8, 0.8, 1.0)

    output_node = nodes.new("ShaderNodeOutputWorld")
    links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

    # Blender内蔵のStudio HDRIを検索して使用
    hdri_dir = Path(bpy.utils.resource_path("LOCAL")) / "datafiles" / "studiolights" / "world"
    hdri_files = list(hdri_dir.glob("*.exr")) if hdri_dir.exists() else []

    if hdri_files:
        env_tex = nodes.new("ShaderNodeTexEnvironment")
        img = bpy.data.images.load(str(hdri_files[0]))
        env_tex.image = img
        links.new(env_tex.outputs["Color"], bg_node.inputs["Color"])
        bg_node.inputs["Strength"].default_value = 1.5
        print(f"HDRI使用: {hdri_files[0].name}")
    else:
        bg_node.inputs["Color"].default_value = (0.9, 0.9, 0.9, 1.0)
        bg_node.inputs["Strength"].default_value = 2.0
        print("HDRI未検出: 明るいグレー背景で代替")

    # HDRIは照明のみに使用し、背景には映さない（透過→コンポジットで単色合成）
    scene.render.film_transparent = True

    scene.eevee.use_shadows = True
    scene.eevee.use_raytracing = False



def apply_temp_materials():
    """マテリアルのないオブジェクトへ一時マテリアルを付与する."""
    collection_colors = [
        ("壁", (0.85, 0.85, 0.82, 1.0)),
        ("柱", (0.75, 0.75, 0.73, 1.0)),
        ("床", (0.4, 0.38, 0.35, 1.0)),
        ("その他", (0.7, 0.7, 0.7, 1.0)),
    ]
    for col_name, color in collection_colors:
        col = bpy.data.collections.get(col_name)
        if not col:
            continue
        mat = bpy.data.materials.new(name=f"_temp_{col_name}")
        mat.use_nodes = True
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color
        count = 0
        for obj in col.objects:
            if obj.type == "MESH" and len(obj.data.materials) == 0:
                obj.data.materials.append(mat)
                count += 1
        print(f"[一時マテリアル] {col_name}: {count}個に適用")


def detect_ceiling_objects():
    """壁より高い床オブジェクト（天井）を検出する."""
    wall_z_max = 0
    wall_col = bpy.data.collections.get("壁")
    if wall_col:
        for obj in wall_col.objects:
            if obj.type == "MESH":
                for v in obj.data.vertices:
                    wv = obj.matrix_world @ v.co
                    wall_z_max = max(wall_z_max, wv.z)

    ceiling_objs = []
    floor_col = bpy.data.collections.get("床")
    if floor_col:
        for obj in floor_col.objects:
            if obj.type == "MESH":
                z_min = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
                if z_min > wall_z_max * 0.9:
                    ceiling_objs.append(obj)
                    print(f"[天井検出] {obj.name} (z={z_min:.2f})")

    return wall_z_max, ceiling_objs


def _composite_background(filepath, bg_color=(0.92, 0.92, 0.92)):
    """レンダリング画像の透過部分を単色背景に合成する."""
    img = bpy.data.images.load(filepath)
    pixels = list(img.pixels)
    # pixels は [R, G, B, A, R, G, B, A, ...] のフラット配列
    for i in range(0, len(pixels), 4):
        a = pixels[i + 3]
        if a < 1.0:
            pixels[i] = pixels[i] * a + bg_color[0] * (1.0 - a)
            pixels[i + 1] = pixels[i + 1] * a + bg_color[1] * (1.0 - a)
            pixels[i + 2] = pixels[i + 2] * a + bg_color[2] * (1.0 - a)
            pixels[i + 3] = 1.0
    img.pixels[:] = pixels
    img.save_render(filepath)
    bpy.data.images.remove(img)


def render_all_cameras(cameras, output_dir, wall_z_max, ceiling_objs):
    """各カメラでレンダリングを実行する."""
    scene = bpy.context.scene

    for cam_data in cameras:
        name = cam_data["name"]
        cam_obj = bpy.data.objects.get(name)
        if not cam_obj:
            print(f"[スキップ] カメラ {name} が見つかりません")
            continue

        cam_obj.location = cam_data["location"]
        cam_obj.rotation_euler = cam_data["rotation_euler"]
        scene.camera = cam_obj

        # 俯瞰カメラ（壁より上）の場合、天井を非表示
        is_overhead = cam_obj.location.z > wall_z_max
        if is_overhead:
            for ceil_obj in ceiling_objs:
                ceil_obj.hide_render = True

        filepath = str(output_dir / f"{name}.png")
        scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)

        # 透過背景をライトグレーに合成して上書き保存
        _composite_background(filepath, bg_color=(0.92, 0.92, 0.92))
        print(f"[出力] {name} → {filepath}{'（天井非表示）' if is_overhead else ''}")

        # 天井を元に戻す
        if is_overhead:
            for ceil_obj in ceiling_objs:
                ceil_obj.hide_render = False


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1 :]
    else:
        custom_args = []

    if len(custom_args) < 1:
        print("Usage: scripts/run_blender.sh --background <scene.blend> --python <this_script> -- <output_dir>")
        sys.exit(1)

    output_dir_root = Path(custom_args[0])
    camera_json = output_dir_root / "camera_positions.json"
    output_dir = output_dir_root / "renders"
    output_dir.mkdir(parents=True, exist_ok=True)

    # カメラ位置読み込み
    cameras = json.loads(camera_json.read_text())
    print(f"カメラ数: {len(cameras)}")

    # レンダリング設定
    scene = bpy.context.scene
    scene.render.resolution_x = 960
    scene.render.resolution_y = 540
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    # EEVEE + HDRI環境照明
    setup_hdri_world(scene)

    # 一時マテリアル付与
    apply_temp_materials()

    # 天井検出
    wall_z_max, ceiling_objs = detect_ceiling_objects()

    # レンダリング実行
    render_all_cameras(cameras, output_dir, wall_z_max, ceiling_objs)

    print(f"\n完了: {len(cameras)}枚の画像を {output_dir} に出力")


if __name__ == "__main__":
    main()
