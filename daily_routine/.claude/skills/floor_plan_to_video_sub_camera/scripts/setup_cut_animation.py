"""cuts.jsonの各カットをBlenderのキーフレームアニメーションとして設定する.

各カットの始点カメラにstart→endの補間アニメーションを設定し、
タイムラインで動きを確認できるようにする。
カットごとに150フレームずつ連続配置（C1: 1-150, C2: 151-300, ...）。

Usage:
    scripts/run_blender.sh --background <scene.blend> \
      --python poc/3dcg_poc0_c/scripts/setup_cut_animation.py -- \
      --cuts <cuts.json> --save <output.blend>
"""

import json
import math
import sys
from pathlib import Path

import bpy


def create_animated_camera(name: str, start: dict, end: dict, frame_start: int, frame_end: int,
                           collection: bpy.types.Collection) -> bpy.types.Object:
    """始点→終点のキーフレームアニメーション付きカメラを作成."""
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = start["lens"]
    cam_obj = bpy.data.objects.new(name, cam_data)
    collection.objects.link(cam_obj)

    # 始点キーフレーム
    cam_obj.location = start["location"]
    cam_obj.rotation_euler = [math.radians(r) for r in start["rotation_deg"]]
    cam_obj.keyframe_insert(data_path="location", frame=frame_start)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=frame_start)
    cam_data.lens = start["lens"]
    cam_data.keyframe_insert(data_path="lens", frame=frame_start)

    # 終点キーフレーム
    cam_obj.location = end["location"]
    cam_obj.rotation_euler = [math.radians(r) for r in end["rotation_deg"]]
    cam_obj.keyframe_insert(data_path="location", frame=frame_end)
    cam_obj.keyframe_insert(data_path="rotation_euler", frame=frame_end)
    cam_data.lens = end["lens"]
    cam_data.keyframe_insert(data_path="lens", frame=frame_end)

    # 補間をスムーズに（Bezier）
    for target in [cam_obj, cam_data]:
        if target.animation_data and target.animation_data.action:
            action = target.animation_data.action
            # Blender 5.0: action.layers[0].strips[0].channelbags[0].fcurves
            try:
                fcurves = action.fcurves
            except AttributeError:
                try:
                    fcurves = action.layers[0].strips[0].channelbags[0].fcurves
                except (IndexError, AttributeError):
                    fcurves = []
            for fcurve in fcurves:
                for kfp in fcurve.keyframe_points:
                    kfp.interpolation = "BEZIER"
                    kfp.easing = "EASE_IN_OUT"

    return cam_obj


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    cuts_file = None
    save_path = None
    i = 0
    while i < len(custom_args):
        if custom_args[i] == "--cuts":
            cuts_file = Path(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--save":
            save_path = Path(custom_args[i + 1])
            i += 2
        else:
            i += 1

    if not cuts_file or not save_path:
        print("Usage: ... -- --cuts <cuts.json> --save <out.blend>")
        sys.exit(1)

    cuts = json.loads(cuts_file.read_text())
    print(f"カット数: {len(cuts)}")

    # CutAnimationコレクション
    col_name = "CutAnimation"
    col = bpy.data.collections.get(col_name)
    if col:
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    else:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    # 各カットのアニメーションカメラを作成
    frame_offset = 1
    markers = []
    first_cam = None
    for cut in cuts:
        frames = cut["frames"]
        frame_start = frame_offset
        frame_end = frame_offset + frames - 1

        cam_obj = create_animated_camera(
            cut["name"],
            cut["start"],
            cut["end"],
            frame_start,
            frame_end,
            col,
        )

        if not first_cam:
            first_cam = cam_obj

        # タイムラインマーカー
        marker = bpy.context.scene.timeline_markers.new(cut["name"], frame=frame_start)
        marker.camera = cam_obj

        print(f"  {cut['name']}: フレーム {frame_start}-{frame_end}")
        frame_offset = frame_end + 1

    # シーン設定
    bpy.context.scene.frame_start = 1
    bpy.context.scene.frame_end = frame_offset - 1
    bpy.context.scene.frame_current = 1
    bpy.context.scene.render.fps = 30

    if first_cam:
        bpy.context.scene.camera = first_cam

    print(f"\n総フレーム数: {frame_offset - 1} ({(frame_offset - 1) / 30:.1f}秒)")
    print("タイムラインマーカーでカットごとにカメラが自動切替されます")

    # 保存
    save_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(save_path.resolve()))
    print(f"保存: {save_path}")


if __name__ == "__main__":
    main()
