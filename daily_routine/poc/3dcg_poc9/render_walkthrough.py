"""PoC 9: カメラ間ウォークスルー動画レンダリング.

2つのカメラ間を線形補間してウォークスルーアニメーションを生成する。
EEVEE + HDRI環境照明でレンダリングし、フレーム連番画像を出力する。
ffmpegで動画に結合する。

Usage:
    scripts/run_blender.sh --background poc/3dcg_poc9/input/scene.blend \
        --python poc/3dcg_poc9/render_walkthrough.py -- \
        --cam-start カメラ1 --cam-end カメラ2 \
        --frames 120 --output-dir poc/3dcg_poc9/output/frames
"""

import argparse
import math
import sys
from pathlib import Path

import bpy
from mathutils import Euler, Vector


def lerp(a: float, b: float, t: float) -> float:
    """線形補間."""
    return a + (b - a) * t


def lerp_vector(a: Vector, b: Vector, t: float) -> Vector:
    """Vector の線形補間."""
    return Vector((lerp(a.x, b.x, t), lerp(a.y, b.y, t), lerp(a.z, b.z, t)))


def lerp_euler(a: Euler, b: Euler, t: float) -> Euler:
    """Euler角の線形補間（最短経路）."""
    def shortest_angle(from_a: float, to_b: float) -> float:
        diff = to_b - from_a
        while diff > math.pi:
            diff -= 2 * math.pi
        while diff < -math.pi:
            diff += 2 * math.pi
        return from_a + diff * t

    return Euler((
        shortest_angle(a.x, b.x),
        shortest_angle(a.y, b.y),
        shortest_angle(a.z, b.z),
    ))


def smooth_step(t: float) -> float:
    """スムーズな加減速（ease in-out）."""
    return t * t * (3 - 2 * t)


def setup_hdri_world(scene: bpy.types.Scene) -> None:
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


def apply_temp_materials() -> None:
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


def detect_and_hide_ceiling() -> None:
    """壁より高い床オブジェクト（天井）を検出して非表示にする."""
    wall_z_max = 0
    wall_col = bpy.data.collections.get("壁")
    if wall_col:
        for obj in wall_col.objects:
            if obj.type == "MESH":
                for v in obj.data.vertices:
                    wv = obj.matrix_world @ v.co
                    wall_z_max = max(wall_z_max, wv.z)

    floor_col = bpy.data.collections.get("床")
    if floor_col:
        for obj in floor_col.objects:
            if obj.type == "MESH":
                z_min = min((obj.matrix_world @ v.co).z for v in obj.data.vertices)
                if z_min > wall_z_max * 0.9:
                    obj.hide_render = True
                    print(f"[天井非表示] {obj.name} (z={z_min:.2f})")


def composite_background(filepath: str, bg_color: tuple = (0.92, 0.92, 0.92)) -> None:
    """レンダリング画像の透過部分を単色背景に合成する."""
    img = bpy.data.images.load(filepath)
    pixels = list(img.pixels)
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


def render_walkthrough(
    cam_start_name: str,
    cam_end_name: str,
    total_frames: int,
    output_dir: Path,
    resolution_x: int = 1280,
    resolution_y: int = 720,
) -> None:
    """2カメラ間のウォークスルーをレンダリング."""
    scene = bpy.context.scene

    # カメラ取得
    cam_start = bpy.data.objects.get(cam_start_name)
    cam_end = bpy.data.objects.get(cam_end_name)
    if cam_start is None or cam_start.type != "CAMERA":
        print(f"ERROR: カメラ '{cam_start_name}' が見つかりません")
        sys.exit(1)
    if cam_end is None or cam_end.type != "CAMERA":
        print(f"ERROR: カメラ '{cam_end_name}' が見つかりません")
        sys.exit(1)

    print(f"Start: {cam_start_name} loc={cam_start.location}, rot={cam_start.rotation_euler}")
    print(f"End:   {cam_end_name} loc={cam_end.location}, rot={cam_end.rotation_euler}")

    # アニメーション用カメラを作成
    cam_data = bpy.data.cameras.new("WalkthroughCam")
    cam_data.lens = cam_start.data.lens  # 焦点距離を開始カメラに合わせる
    cam_obj = bpy.data.objects.new("WalkthroughCam", cam_data)
    scene.collection.objects.link(cam_obj)
    scene.camera = cam_obj

    # レンダリング設定（HDRI照明 + 一時マテリアル + 天井非表示）
    setup_hdri_world(scene)
    apply_temp_materials()
    detect_and_hide_ceiling()

    scene.render.resolution_x = resolution_x
    scene.render.resolution_y = resolution_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    output_dir.mkdir(parents=True, exist_ok=True)

    # 開始・終了の位置・回転を記録
    loc_start = cam_start.location.copy()
    loc_end = cam_end.location.copy()
    rot_start = cam_start.rotation_euler.copy()
    rot_end = cam_end.rotation_euler.copy()

    print(f"\nレンダリング開始: {total_frames}フレーム → {output_dir}")

    for frame in range(total_frames):
        t = frame / max(total_frames - 1, 1)
        t_smooth = smooth_step(t)

        # カメラ位置・回転を補間
        cam_obj.location = lerp_vector(loc_start, loc_end, t_smooth)
        cam_obj.rotation_euler = lerp_euler(rot_start, rot_end, t_smooth)

        # レンダリング
        scene.frame_set(frame + 1)
        filepath = str(output_dir / f"frame_{frame:04d}.png")
        scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)

        # 透過部分を単色背景に合成
        composite_background(filepath)

        if frame % 10 == 0 or frame == total_frames - 1:
            print(f"  フレーム {frame + 1}/{total_frames} 完了")

    print(f"\nレンダリング完了: {total_frames}フレーム")


def main() -> None:
    # Blenderの引数 '--' 以降を取得
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1:]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="ウォークスルー動画レンダリング")
    parser.add_argument("--cam-start", type=str, required=True, help="開始カメラ名")
    parser.add_argument("--cam-end", type=str, required=True, help="終了カメラ名")
    parser.add_argument("--frames", type=int, default=120, help="総フレーム数（デフォルト120=5秒@24fps）")
    parser.add_argument("--output-dir", type=Path, required=True, help="フレーム出力ディレクトリ")
    parser.add_argument("--resolution-x", type=int, default=1280, help="横解像度")
    parser.add_argument("--resolution-y", type=int, default=720, help="縦解像度")
    args = parser.parse_args(argv)

    render_walkthrough(
        cam_start_name=args.cam_start,
        cam_end_name=args.cam_end,
        total_frames=args.frames,
        output_dir=args.output_dir,
        resolution_x=args.resolution_x,
        resolution_y=args.resolution_y,
    )


if __name__ == "__main__":
    main()
