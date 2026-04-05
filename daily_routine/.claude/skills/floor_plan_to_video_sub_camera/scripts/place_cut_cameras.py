"""cuts.jsonの始点・終点カメラをBlenderに配置して保存する.

Usage:
    scripts/run_blender.sh --background <scene.blend> \
      --python poc/3dcg_poc0_c/scripts/place_cut_cameras.py -- \
      --cuts <cuts.json> --save <output.blend>
"""

import json
import math
import sys
from pathlib import Path

import bpy


def create_camera(name: str, location: list, rotation_deg: list, lens: float,
                  collection: bpy.types.Collection) -> bpy.types.Object:
    """カメラオブジェクトを作成してコレクションに追加."""
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens
    cam_obj = bpy.data.objects.new(name, cam_data)
    cam_obj.location = location
    cam_obj.rotation_euler = [math.radians(r) for r in rotation_deg]
    collection.objects.link(cam_obj)
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

    # CutCamerasコレクション
    col_name = "CutCameras"
    col = bpy.data.collections.get(col_name)
    if col:
        for obj in list(col.objects):
            bpy.data.objects.remove(obj, do_unlink=True)
    else:
        col = bpy.data.collections.new(col_name)
        bpy.context.scene.collection.children.link(col)

    # カメラ配置
    for cut in cuts:
        cam_s = create_camera(
            f"{cut['name']}_s",
            cut["start"]["location"],
            cut["start"]["rotation_deg"],
            cut["start"]["lens"],
            col,
        )
        cam_e = create_camera(
            f"{cut['name']}_e",
            cut["end"]["location"],
            cut["end"]["rotation_deg"],
            cut["end"]["lens"],
            col,
        )
        print(f"  {cut['name']}: s={cut['start']['location']} → e={cut['end']['location']}")

    # 保存
    save_path.parent.mkdir(parents=True, exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(save_path.resolve()))
    print(f"保存: {save_path}")


if __name__ == "__main__":
    main()
