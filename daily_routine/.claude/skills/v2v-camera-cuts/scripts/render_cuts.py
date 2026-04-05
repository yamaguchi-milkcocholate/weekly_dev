"""cuts.jsonの各カットを始点→終点でsmooth_step補間し、Cyclesフレームレンダリングする.

Usage:
    scripts/run_blender.sh --background <scene.blend> \
      --python poc/3dcg_poc0_c/scripts/render_cuts.py -- \
      --cuts <cuts.json> --output-dir <output_dir> \
      [--samples 32] [--width 480] [--height 270] \
      [--cut C1_entrance_dolly]
"""

import json
import math
import sys
import time
from pathlib import Path

import bpy


def smooth_step(t: float) -> float:
    """ease in-out."""
    return t * t * (3 - 2 * t)


def lerp(a: float, b: float, t: float) -> float:
    """線形補間."""
    return a + (b - a) * t


def shortest_angle_lerp(a: float, b: float, t: float) -> float:
    """角度の最短経路補間（度数法）."""
    diff = b - a
    while diff > 180:
        diff -= 360
    while diff < -180:
        diff += 360
    return a + diff * t


def setup_cycles_gpu(scene: bpy.types.Scene, samples: int) -> None:
    """GPU Cycles設定."""
    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.use_adaptive_sampling = True

    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.refresh_devices()
    for dev in prefs.devices:
        dev.use = dev.type == "METAL"


def setup_world(scene: bpy.types.Scene) -> None:
    """HDRI環境照明を設定."""
    world = scene.world
    if not world:
        world = bpy.data.worlds.new("World")
        scene.world = world

    world.use_nodes = True
    nodes = world.node_tree.nodes
    links = world.node_tree.links
    nodes.clear()

    bg_node = nodes.new("ShaderNodeBackground")
    output_node = nodes.new("ShaderNodeOutputWorld")
    links.new(bg_node.outputs["Background"], output_node.inputs["Surface"])

    hdri_dir = Path(bpy.utils.resource_path("LOCAL")) / "datafiles" / "studiolights" / "world"
    hdri_files = list(hdri_dir.glob("*.exr")) if hdri_dir.exists() else []

    if hdri_files:
        env_tex = nodes.new("ShaderNodeTexEnvironment")
        env_tex.image = bpy.data.images.load(str(hdri_files[0]))
        links.new(env_tex.outputs["Color"], bg_node.inputs["Color"])
        bg_node.inputs["Strength"].default_value = 1.5
    else:
        bg_node.inputs["Color"].default_value = (0.9, 0.9, 0.9, 1.0)
        bg_node.inputs["Strength"].default_value = 2.0

    scene.render.film_transparent = True


def render_cut(cut: dict, output_dir: Path, cam_obj: bpy.types.Object) -> None:
    """1カットの全フレームをレンダリング."""
    scene = bpy.context.scene
    scene.camera = cam_obj

    start = cut["start"]
    end = cut["end"]
    frames = cut["frames"]
    name = cut["name"]

    cut_dir = output_dir / name
    cut_dir.mkdir(parents=True, exist_ok=True)

    # 天井非表示判定
    ceiling = bpy.data.objects.get("Ceiling")
    is_overhead = start["location"][2] > 3.0 or end["location"][2] > 3.0
    if ceiling and is_overhead:
        ceiling.hide_render = True

    t_start = time.time()
    for f in range(frames):
        t_raw = f / (frames - 1)
        t = smooth_step(t_raw)

        # 位置補間
        loc = [lerp(start["location"][i], end["location"][i], t) for i in range(3)]
        cam_obj.location = loc

        # 回転補間（最短経路）
        rot_deg = [
            shortest_angle_lerp(start["rotation_deg"][i], end["rotation_deg"][i], t)
            for i in range(3)
        ]
        cam_obj.rotation_euler = [math.radians(r) for r in rot_deg]

        # レンズ補間
        cam_obj.data.lens = lerp(start["lens"], end["lens"], t)

        # レンダリング
        filepath = str(cut_dir / f"{f:04d}.png")
        scene.render.filepath = filepath
        bpy.ops.render.render(write_still=True)

        elapsed = time.time() - t_start
        avg = elapsed / (f + 1)
        remaining = avg * (frames - f - 1)
        print(f"  [{name}] {f + 1}/{frames} ({avg:.1f}s/f, 残り{remaining:.0f}s)")

    if ceiling and is_overhead:
        ceiling.hide_render = False

    total = time.time() - t_start
    print(f"  [{name}] 完了: {total:.0f}s ({total / 60:.1f}分)")


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    cuts_file = None
    output_dir = None
    samples = 32
    width = 480
    height = 270
    target_cut = None

    i = 0
    while i < len(custom_args):
        if custom_args[i] == "--cuts":
            cuts_file = Path(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--output-dir":
            output_dir = Path(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--samples":
            samples = int(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--width":
            width = int(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--height":
            height = int(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--cut":
            target_cut = custom_args[i + 1]
            i += 2
        else:
            i += 1

    if not cuts_file or not output_dir:
        print("Usage: ... -- --cuts <cuts.json> --output-dir <dir> [--samples 32] [--width 480] [--height 270] [--cut NAME]")
        sys.exit(1)

    cuts = json.loads(cuts_file.read_text())

    # 特定カットのみレンダリング
    if target_cut:
        cuts = [c for c in cuts if c["name"] == target_cut]
        if not cuts:
            print(f"カット '{target_cut}' が見つかりません")
            sys.exit(1)

    print(f"カット数: {len(cuts)}, {samples}s, {width}x{height}")

    # レンダリング設定
    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    setup_cycles_gpu(scene, samples)
    setup_world(scene)

    # レンダリング用カメラ作成
    cam_data = bpy.data.cameras.new("RenderCam")
    cam_obj = bpy.data.objects.new("RenderCam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)

    total_start = time.time()
    for cut in cuts:
        print(f"\n=== {cut['name']} ({cut['frames']}フレーム) ===")
        render_cut(cut, output_dir, cam_obj)

    total = time.time() - total_start
    print(f"\n全カット完了: {total:.0f}s ({total / 60:.1f}分)")

    # クリーンアップ
    bpy.data.objects.remove(cam_obj, do_unlink=True)
    bpy.data.cameras.remove(cam_data)


if __name__ == "__main__":
    main()
