"""scene.blendからカメラ位置データを抽出してJSONに保存する.

使い方:
    scripts/run_blender.sh --background <input_dir>/scene.blend \
      --python .claude/skills/floor_plan_to_video_sub_multiview/scripts/extract_cameras.py -- <output_dir>
"""

import json
import math
import sys
from pathlib import Path

import bpy


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

    cameras = []
    for obj in sorted(bpy.data.objects, key=lambda o: o.name):
        if obj.type != "CAMERA":
            continue
        cameras.append({
            "name": obj.name,
            "location": [round(v, 4) for v in obj.location],
            "rotation_euler": [round(v, 4) for v in obj.rotation_euler],
            "rotation_euler_deg": [round(math.degrees(v), 2) for v in obj.rotation_euler],
            "lens": round(obj.data.lens, 2),
        })
        print(f"  {obj.name}: loc={cameras[-1]['location']} rot_deg={cameras[-1]['rotation_euler_deg']} lens={cameras[-1]['lens']}mm")

    output_path = output_dir / "camera_positions.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(cameras, indent=2, ensure_ascii=False))
    print(f"\n保存: {output_path} ({len(cameras)}台)")


if __name__ == "__main__":
    main()
