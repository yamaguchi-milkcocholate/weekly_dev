"""scene.blendから壁・ドア・窓オブジェクトのバウンディングボックスを抽出する.

各コレクション（Walls, Doors, Windows, GlassDoors等）のオブジェクト座標を
JSON形式で出力し、部屋境界の把握に使用する。

Usage:
    scripts/run_blender.sh --background <scene.blend> \
      --python poc/3dcg_poc0_c/scripts/extract_room_bounds.py -- <output.json>
"""

import json
import sys
from pathlib import Path

import bpy


def get_object_bounds(obj: bpy.types.Object) -> dict:
    """オブジェクトのワールド座標バウンディングボックスを取得する."""
    coords = [obj.matrix_world @ v.co for v in obj.data.vertices]
    xs = [c.x for c in coords]
    ys = [c.y for c in coords]
    zs = [c.z for c in coords]
    return {
        "name": obj.name,
        "x_min": round(min(xs), 3),
        "x_max": round(max(xs), 3),
        "y_min": round(min(ys), 3),
        "y_max": round(max(ys), 3),
        "z_min": round(min(zs), 3),
        "z_max": round(max(zs), 3),
        "center_x": round((min(xs) + max(xs)) / 2, 3),
        "center_y": round((min(ys) + max(ys)) / 2, 3),
    }


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1:]
    else:
        custom_args = []

    if len(custom_args) < 1:
        print("Usage: ... -- <output.json>")
        sys.exit(1)

    output_path = Path(custom_args[0])
    output_path.parent.mkdir(parents=True, exist_ok=True)

    result = {"collections": {}, "scene_bounds": {}}

    # 全コレクションのメッシュオブジェクトを取得
    all_xs = []
    all_ys = []
    for col in bpy.data.collections:
        objects = []
        for obj in col.objects:
            if obj.type == "MESH":
                bounds = get_object_bounds(obj)
                objects.append(bounds)
                all_xs.extend([bounds["x_min"], bounds["x_max"]])
                all_ys.extend([bounds["y_min"], bounds["y_max"]])
        if objects:
            result["collections"][col.name] = objects
            print(f"[{col.name}] {len(objects)}個のオブジェクト")

    # シーン全体のバウンディングボックス
    if all_xs and all_ys:
        result["scene_bounds"] = {
            "x_min": round(min(all_xs), 3),
            "x_max": round(max(all_xs), 3),
            "y_min": round(min(all_ys), 3),
            "y_max": round(max(all_ys), 3),
            "center_x": round((min(all_xs) + max(all_xs)) / 2, 3),
            "center_y": round((min(all_ys) + max(all_ys)) / 2, 3),
        }

    # カメラ情報も取得
    cameras = []
    for obj in bpy.data.objects:
        if obj.type == "CAMERA":
            cameras.append({
                "name": obj.name,
                "location": [round(v, 3) for v in obj.location],
                "rotation_deg": [round(v * 57.2958, 1) for v in obj.rotation_euler],
                "lens": round(obj.data.lens, 1),
            })
    result["cameras"] = cameras

    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\n出力: {output_path}")
    print(f"シーン範囲: x=[{result['scene_bounds'].get('x_min')}, {result['scene_bounds'].get('x_max')}], "
          f"y=[{result['scene_bounds'].get('y_min')}, {result['scene_bounds'].get('y_max')}]")


if __name__ == "__main__":
    main()
