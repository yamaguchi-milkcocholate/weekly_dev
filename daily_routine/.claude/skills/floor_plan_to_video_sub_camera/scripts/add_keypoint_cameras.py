"""キーポイントカメラをscene.blendに配置して保存する（レンダリングなし）.

Usage:
    scripts/run_blender.sh --background <scene.blend> \
      --python poc/3dcg_poc0_c/scripts/add_keypoint_cameras.py -- \
      --keypoints <keypoints.json> --save <output.blend>
"""

import json
import math
import sys
from pathlib import Path

import bpy


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    keypoints_path = None
    save_path = None
    i = 0
    while i < len(custom_args):
        if custom_args[i] == "--keypoints":
            keypoints_path = Path(custom_args[i + 1])
            i += 2
        elif custom_args[i] == "--save":
            save_path = Path(custom_args[i + 1])
            i += 2
        else:
            i += 1

    if not keypoints_path or not save_path:
        print("Usage: ... -- --keypoints <keypoints.json> --save <output.blend>")
        sys.exit(1)

    keypoints = json.loads(keypoints_path.read_text())

    # Keypointsコレクション作成
    col_name = "Keypoints"
    col = bpy.data.collections.get(col_name)
    if not col:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    for kp in keypoints:
        name = kp["name"]
        loc = kp["location"]
        rot_deg = kp["rotation_deg"]
        lens = kp.get("lens", 24)

        # 既存カメラがあれば削除
        existing = bpy.data.objects.get(name)
        if existing:
            bpy.data.objects.remove(existing, do_unlink=True)

        cam_data = bpy.data.cameras.new(name)
        cam_data.lens = lens
        cam_obj = bpy.data.objects.new(name, cam_data)
        col.objects.link(cam_obj)

        cam_obj.location = loc
        cam_obj.rotation_euler = [math.radians(r) for r in rot_deg]

        print(f"[配置] {name}: loc={loc}, rot={rot_deg}, lens={lens}mm"
              f" — {kp.get('description', '')}")

    bpy.ops.wm.save_as_mainfile(filepath=str(save_path.resolve()))
    print(f"\n保存: {save_path}")
    print(f"キーポイントカメラ {len(keypoints)}台を「{col_name}」コレクションに配置")


if __name__ == "__main__":
    main()
