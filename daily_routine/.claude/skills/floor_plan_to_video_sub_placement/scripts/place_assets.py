"""layout_proposal.jsonに基づきGLBアセットをBlenderシーンに自動配置する."""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

import bpy
from mathutils import Vector

# front_dirからZ軸回転(rad)へのマッピング（memo.md準拠）
FRONT_DIR_ROTATION = {
    "N": 0,
    "E": -math.pi / 2,
    "S": math.pi,
    "W": math.pi / 2,
}

# GLBのデフォルトfront方向に対する補正回転
# layout_proposal.jsonはfront=N(+Y方向)を0としている
# GLBのfrontが+Y以外の場合、そのfrontを+Yに揃える回転を適用する
# 計算: R(correction) * v_glb_front = +Y となる角度
GLB_FRONT_CORRECTION = {
    "+Y": 0,
    "-Y": math.pi,
    "+X": math.pi / 2,
    "-X": -math.pi / 2,
}


def detect_floor_z():
    """madori.blendの床面Z座標を検出.

    「床」コレクション内の最も低い平面のZ座標を返す。
    """
    floor_col = bpy.data.collections.get("床")
    if not floor_col:
        return 0.0

    z_values = []
    for obj in floor_col.objects:
        if obj.type != "MESH":
            continue
        corners = [obj.matrix_world @ Vector(c) for c in obj.bound_box]
        z_min = min(c.z for c in corners)
        z_max = max(c.z for c in corners)
        # 薄い平面（床）を検出（天井ではない）
        if (z_max - z_min) < 0.1 and z_max < 1.0:
            z_values.append(z_max)

    return max(z_values) if z_values else 0.0


def load_inputs(input_dir, output_dir):
    """入力ファイルを読み込む."""
    layout_path = input_dir / "layout_proposal.json"
    assets_path = input_dir / "assets.json"
    check_path = output_dir / "glb_check_result.json"

    layout = json.loads(layout_path.read_text(encoding="utf-8"))
    assets_data = json.loads(assets_path.read_text(encoding="utf-8"))
    check_data = json.loads(check_path.read_text(encoding="utf-8"))

    # assets.jsonをid→dictのマップに変換
    assets_by_id = {a["id"]: a for a in assets_data["assets"]}

    return layout, assets_by_id, check_data


def create_furniture_collection():
    """家具コレクションを作成して返す."""
    col_name = "家具"
    if col_name in bpy.data.collections:
        return bpy.data.collections[col_name]
    col = bpy.data.collections.new(col_name)
    bpy.context.scene.collection.children.link(col)
    return col


def import_glb_as_group(glb_path, label, furniture_col):
    """GLBをインポートし、全オブジェクトをEmptyの子にペアレント化.

    Returns: 親Emptyオブジェクト
    """
    # インポート前の既存オブジェクトを記録
    existing_objects = set(bpy.data.objects)

    # GLBインポート
    bpy.ops.import_scene.gltf(filepath=str(glb_path))

    # 新しく追加されたオブジェクトを検出
    new_objects = [obj for obj in bpy.data.objects if obj not in existing_objects]

    if not new_objects:
        print(f"  Warning: No objects imported from {glb_path}")
        return None

    # 親Emptyを作成
    empty = bpy.data.objects.new(label, None)
    empty.empty_display_type = "ARROWS"
    empty.empty_display_size = 0.001

    # 家具コレクションにEmptyをリンク（hide_setの前にリンクが必要）
    furniture_col.objects.link(empty)
    empty.hide_set(True)

    # 新オブジェクトをEmptyの子にし、家具コレクションに移動
    for obj in new_objects:
        # 既存コレクションから削除
        for col in obj.users_collection:
            col.objects.unlink(obj)
        # 家具コレクションにリンク
        furniture_col.objects.link(obj)
        # ペアレント設定（ワールド変換を維持）
        obj.parent = empty
        obj.matrix_parent_inverse = empty.matrix_world.inverted()

    return empty


def apply_transform(empty, item, glb_info, overrides, asset_info, floor_z=0):
    """Emptyにスケール・回転・位置を適用.

    Args:
        empty: 親Emptyオブジェクト
        item: layout_proposal.jsonの1アイテム
        glb_info: glb_check_result.jsonのresultsの1エントリ
        overrides: manual_overridesの1エントリ
        asset_info: assets.jsonの1エントリ（expected sizeの取得用）
        floor_z: madori.blendの床面Z座標（デフォルト0）
    """
    default_front = overrides.get("default_front", "+Y")
    use_uniform = overrides.get("use_uniform_scale", False)
    expected = asset_info["size"]
    actual = glb_info["actual_size"]

    # --- スケール ---
    if use_uniform:
        s = glb_info["uniform_scale"]
        empty.scale = (s, s, s)
    else:
        # front方向に応じてwidth/depthの軸マッピングを切り替え
        # assets.jsonのwidth=front垂直辺, depth=front平行辺
        if default_front in ("+X", "-X"):
            # GLBのfront→X軸: depth→X, width→Y
            sx = expected["depth"] / actual["x"] if actual["x"] > 0.001 else 1.0
            sy = expected["width"] / actual["y"] if actual["y"] > 0.001 else 1.0
        else:
            # GLBのfront→Y軸: width→X, depth→Y（デフォルト）
            sx = expected["width"] / actual["x"] if actual["x"] > 0.001 else 1.0
            sy = expected["depth"] / actual["y"] if actual["y"] > 0.001 else 1.0
        sz = expected["height"] / actual["z"] if actual["z"] > 0.001 else 1.0
        empty.scale = (sx, sy, sz)

    # --- 回転 ---
    front_dir = item["front_dir"]
    base_rot = FRONT_DIR_ROTATION[front_dir]
    front_correction = GLB_FRONT_CORRECTION.get(default_front, 0)

    empty.rotation_euler = (0, 0, base_rot + front_correction)

    # --- 位置 ---
    # origin=centerの場合、expected_height/2 だけ持ち上げれば底面が床に接地する
    # floor_zで床面オフセットも考慮
    origin = glb_info.get("origin_relative", "center")
    if origin == "center":
        z_correction = expected["height"] / 2 + floor_z
    elif origin == "bottom-center":
        z_correction = floor_z
    else:
        z_correction = expected["height"] / 2 + floor_z

    empty.location = (item["center"]["x"], item["center"]["y"], z_correction)


def apply_structure_materials():
    """壁・床・柱コレクションのマテリアル未設定オブジェクトに色を付与する."""
    collection_colors = {
        "壁": (0.62, 0.58, 0.50, 1.0),   # ウォームベージュ
        "床": (0.15, 0.09, 0.05, 1.0),   # ダークウッド
        "柱": (0.45, 0.42, 0.38, 1.0),   # グレーベージュ
    }
    for col_name, color in collection_colors.items():
        col = bpy.data.collections.get(col_name)
        if not col:
            continue
        mat = bpy.data.materials.new(name=f"structure_{col_name}")
        mat.use_nodes = True
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = color
        count = 0
        for obj in col.objects:
            if obj.type == "MESH" and len(obj.data.materials) == 0:
                obj.data.materials.append(mat)
                count += 1
        if count > 0:
            print(f"  [マテリアル] {col_name}: {count}個に適用")


def main():
    argv = sys.argv
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1 :]
    else:
        custom_args = []

    if len(custom_args) < 2:
        print("Usage: scripts/run_blender.sh --background <input_dir>/madori.blend --python <this_script> -- <input_dir> <output_dir>")
        sys.exit(1)
    input_dir = Path(custom_args[0])
    output_dir = Path(custom_args[1])
    output_dir.mkdir(parents=True, exist_ok=True)

    # 入力読み込み
    layout, assets_by_id, check_data = load_inputs(input_dir, output_dir)
    results = check_data["results"]
    overrides = check_data.get("manual_overrides", {})

    # 床面Z座標を検出（madori.blendの「床」コレクションから）
    floor_z = detect_floor_z()
    print(f"Floor Z: {floor_z:.4f}")

    # 家具コレクション作成
    furniture_col = create_furniture_collection()

    # 配置レポート
    report_items = []

    # layout_proposalの各アイテムを配置
    for item in layout:
        asset_id = item["id"]
        label = item["label"]

        print(f"Placing {label} ({asset_id})...")

        # アセット情報取得
        asset_info = assets_by_id.get(asset_id)
        if not asset_info:
            print(f"  Warning: Asset '{asset_id}' not found in assets.json")
            continue

        glb_info = results.get(asset_id)
        if not glb_info or "error" in glb_info:
            print(f"  Warning: No check result for '{asset_id}'")
            continue

        asset_overrides = overrides.get(asset_id, {})

        # GLBパス解決
        glb_path = input_dir / asset_info["glb"]
        if not glb_path.exists():
            print(f"  Warning: GLB not found: {glb_path}")
            continue

        # インポート＆グループ化
        empty = import_glb_as_group(glb_path, label, furniture_col)
        if empty is None:
            continue

        # 変換適用
        apply_transform(empty, item, glb_info, asset_overrides, asset_info, floor_z)

        # レポート記録
        report_items.append({
            "label": label,
            "asset_id": asset_id,
            "location": {
                "x": round(empty.location.x, 4),
                "y": round(empty.location.y, 4),
                "z": round(empty.location.z, 4),
            },
            "rotation_z_deg": round(math.degrees(empty.rotation_euler.z), 1),
            "scale": {
                "x": round(empty.scale.x, 4),
                "y": round(empty.scale.y, 4),
                "z": round(empty.scale.z, 4),
            },
        })

        print(f"  Location: ({empty.location.x:.3f}, {empty.location.y:.3f}, {empty.location.z:.3f})")
        print(f"  Rotation Z: {math.degrees(empty.rotation_euler.z):.1f}°")
        print(f"  Scale: ({empty.scale.x:.3f}, {empty.scale.y:.3f}, {empty.scale.z:.3f})")

    # 壁・床・柱にマテリアル付与
    apply_structure_materials()

    # シーン保存
    scene_path = output_dir / "scene.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(scene_path.resolve()))
    print(f"\nScene saved: {scene_path}")

    # 配置レポート保存
    report = {
        "generated_at": datetime.now(tz=timezone.utc).isoformat(),
        "total_placed": len(report_items),
        "items": report_items,
    }
    report_path = output_dir / "placement_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Report saved: {report_path}")


if __name__ == "__main__":
    main()
