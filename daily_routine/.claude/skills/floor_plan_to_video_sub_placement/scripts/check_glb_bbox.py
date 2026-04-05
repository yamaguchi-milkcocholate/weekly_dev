"""各GLBアセットのBBox・スケール係数・原点位置を測定し、glb_check_result.jsonに出力する."""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector


def get_combined_bbox(objects):
    """複数オブジェクトの統合ワールド座標BBoxを計算.

    Returns: {"min": Vector, "max": Vector, "size": Vector, "center": Vector}
    """
    all_corners = []
    for obj in objects:
        if obj.type != "MESH":
            continue
        corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
        all_corners.extend(corners)

    if not all_corners:
        return None

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
    size = bbox_max - bbox_min
    center = (bbox_min + bbox_max) / 2
    return {"min": bbox_min, "max": bbox_max, "size": size, "center": center}


def get_origin_info(bbox):
    """原点(0,0,0)がBBoxに対してどこにあるかを判定.

    Returns: {"origin_relative": str, "z_offset": float}
    """
    bottom_center_z = bbox["min"].z
    center_z = bbox["center"].z

    # 原点がBBox底面に近いか、中心に近いかを判定
    z_range = bbox["size"].z
    if z_range < 0.001:
        return {"origin_relative": "flat", "z_offset": 0.0}

    bottom_distance = abs(bottom_center_z)
    center_distance = abs(center_z)

    if bottom_distance < z_range * 0.1:
        origin_relative = "bottom-center"
    elif center_distance < z_range * 0.1:
        origin_relative = "center"
    else:
        origin_relative = "other"

    # z_offset: 床面(z=0)に底面を合わせるための補正値
    # 配置時に location.z = -z_offset とする
    z_offset = bottom_center_z
    return {"origin_relative": origin_relative, "z_offset": round(z_offset, 4)}


def check_single_glb(glb_path, expected_size):
    """1つのGLBを空シーンにインポートして測定.

    Returns: 測定結果のdict
    """
    # シーンをクリア
    bpy.ops.wm.read_factory_settings(use_empty=True)

    # GLBインポート
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    imported_objects = list(bpy.context.selected_objects)

    # メッシュオブジェクトのみ抽出
    mesh_objects = [obj for obj in imported_objects if obj.type == "MESH"]
    object_names = [obj.name for obj in imported_objects]

    bbox = get_combined_bbox(mesh_objects)
    if bbox is None:
        return {
            "error": "No mesh objects found",
            "imported_object_count": len(imported_objects),
            "imported_object_names": object_names,
        }

    actual_size = bbox["size"]
    origin_info = get_origin_info(bbox)

    # スケール係数算出（expected / actual）
    scale_x = expected_size["width"] / actual_size.x if actual_size.x > 0.001 else 1.0
    scale_y = expected_size["depth"] / actual_size.y if actual_size.y > 0.001 else 1.0
    scale_z = expected_size["height"] / actual_size.z if actual_size.z > 0.001 else 1.0

    return {
        "glb_path": str(glb_path),
        "actual_size": {
            "x": round(actual_size.x, 4),
            "y": round(actual_size.y, 4),
            "z": round(actual_size.z, 4),
        },
        "expected_size": {
            "width": expected_size["width"],
            "depth": expected_size["depth"],
            "height": expected_size["height"],
        },
        "scale_factor": {
            "x": round(scale_x, 4),
            "y": round(scale_y, 4),
            "z": round(scale_z, 4),
        },
        "uniform_scale": round(min(scale_x, scale_y, scale_z), 4),
        "bbox_min": {"x": round(bbox["min"].x, 4), "y": round(bbox["min"].y, 4), "z": round(bbox["min"].z, 4)},
        "bbox_max": {"x": round(bbox["max"].x, 4), "y": round(bbox["max"].y, 4), "z": round(bbox["max"].z, 4)},
        "origin_relative": origin_info["origin_relative"],
        "z_offset": origin_info["z_offset"],
        "default_front": "unknown",
        "imported_object_count": len(imported_objects),
        "imported_object_names": object_names,
    }


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1 :]
    else:
        custom_args = []

    if len(custom_args) < 2:
        print("Usage: scripts/run_blender.sh --background --python <this_script> -- <input_dir> <output_dir>")
        sys.exit(1)
    input_dir = Path(custom_args[0])
    output_dir = Path(custom_args[1])
    output_dir.mkdir(parents=True, exist_ok=True)

    # assets.json読み込み
    assets_path = input_dir / "assets.json"
    assets_data = json.loads(assets_path.read_text(encoding="utf-8"))

    results = {}
    for asset in assets_data["assets"]:
        asset_id = asset["id"]
        glb_path = Path(asset["glb"])

        if not glb_path.exists():
            print(f"Warning: GLB not found: {glb_path}")
            results[asset_id] = {"error": f"GLB not found: {glb_path}"}
            continue

        print(f"Checking {asset_id}: {glb_path}")
        result = check_single_glb(glb_path, asset["size"])
        results[asset_id] = result

        # サマリ出力
        if "error" not in result:
            actual = result["actual_size"]
            expected = result["expected_size"]
            print(f"  Actual:   {actual['x']:.3f} x {actual['y']:.3f} x {actual['z']:.3f}")
            print(f"  Expected: {expected['width']:.3f} x {expected['depth']:.3f} x {expected['height']:.3f}")
            print(f"  Uniform scale: {result['uniform_scale']:.4f}")
            print(f"  Origin: {result['origin_relative']}, z_offset: {result['z_offset']:.4f}")

    # 出力JSON
    output = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "results": results,
        "manual_overrides": {
            "_comment": "GLBのデフォルトfront方向を手動で指定。Blender GUIで確認後に編集",
            **{asset_id: {"default_front": "+Y", "use_uniform_scale": True} for asset_id in results},
        },
    }

    output_path = output_dir / "glb_check_result.json"
    output_path.write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nResult saved: {output_path}")


if __name__ == "__main__":
    main()
