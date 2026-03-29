"""Blender .blendファイルから間取りSVG + walls.json + メタデータを抽出する."""
import json
import sys
from pathlib import Path

import bpy
from mathutils import Vector


def get_world_bbox(obj):
    """オブジェクトのワールド座標バウンディングボックスを取得."""
    corners = [obj.matrix_world @ Vector(corner) for corner in obj.bound_box]
    xs = [c.x for c in corners]
    ys = [c.y for c in corners]
    return {
        "name": obj.name,
        "x1": round(min(xs), 3),
        "x2": round(max(xs), 3),
        "y1": round(min(ys), 3),
        "y2": round(max(ys), 3),
    }


TARGET_COLLECTIONS = ["壁", "柱", "床", "その他"]

STYLE = {
    "壁": {"fill": "#333333", "opacity": "0.85"},
    "柱": {"fill": "#C62828", "opacity": "0.70"},
    "その他": {"fill": "#1E88E5", "opacity": "0.60"},
    "床": {"fill": "#FAFAFA", "opacity": "0.40"},
}

MARGIN = 0.5  # メートル


def main():
    argv = sys.argv
    # Blenderの"--"以降の引数を取得
    if "--" in argv:
        custom_args = argv[argv.index("--") + 1 :]
    else:
        custom_args = []

    output_dir = Path(custom_args[0]) if custom_args else Path("poc/3dcg_poc3/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 1. BBox収集 ---
    walls_data = {}
    all_bboxes = []

    for col_name in TARGET_COLLECTIONS:
        col = bpy.data.collections.get(col_name)
        if not col:
            print(f"Warning: Collection '{col_name}' not found")
            walls_data[col_name] = []
            continue

        entries = []
        for obj in col.objects:
            if obj.type != "MESH":
                continue
            bbox = get_world_bbox(obj)
            entries.append(bbox)
            all_bboxes.append(bbox)
        walls_data[col_name] = entries

    if not all_bboxes:
        print("Error: No mesh objects found")
        return

    # --- 2. 全体範囲の計算 ---
    all_x1 = min(b["x1"] for b in all_bboxes)
    all_x2 = max(b["x2"] for b in all_bboxes)
    all_y1 = min(b["y1"] for b in all_bboxes)
    all_y2 = max(b["y2"] for b in all_bboxes)

    vb_x = all_x1 - MARGIN
    vb_w = (all_x2 - all_x1) + 2 * MARGIN
    # Y軸反転: svg_y = -blender_y
    vb_y = -(all_y2 + MARGIN)
    vb_h = (all_y2 - all_y1) + 2 * MARGIN

    display_width = 800
    display_height = round(display_width * (vb_h / vb_w))

    # --- 3. SVG生成 ---
    svg_lines = []
    svg_lines.append('<?xml version="1.0" encoding="UTF-8"?>')
    svg_lines.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{display_width}" height="{display_height}" '
        f'viewBox="{vb_x:.3f} {vb_y:.3f} {vb_w:.3f} {vb_h:.3f}">'
    )

    # 背景
    svg_lines.append(f'  <rect x="{vb_x}" y="{vb_y}" width="{vb_w}" height="{vb_h}" fill="white"/>')

    # グリッド線（1m間隔）
    svg_lines.append('  <g stroke="#E0E0E0" stroke-width="0.02" opacity="0.5">')
    import math

    grid_x_start = math.floor(all_x1)
    grid_x_end = math.ceil(all_x2)
    grid_y_start = math.floor(all_y1)
    grid_y_end = math.ceil(all_y2)

    for gx in range(grid_x_start, grid_x_end + 1):
        svg_y1 = -all_y2 - MARGIN
        svg_y2 = -all_y1 + MARGIN
        svg_lines.append(f'    <line x1="{gx}" y1="{svg_y1:.3f}" x2="{gx}" y2="{svg_y2:.3f}"/>')

    for gy in range(grid_y_start, grid_y_end + 1):
        svg_y_grid = -gy
        svg_lines.append(
            f'    <line x1="{all_x1 - MARGIN:.3f}" y1="{svg_y_grid}" '
            f'x2="{all_x2 + MARGIN:.3f}" y2="{svg_y_grid}"/>'
        )

    svg_lines.append("  </g>")

    # 描画順: 床 → その他 → 壁 → 柱（上に重なる順）
    draw_order = ["床", "その他", "壁", "柱"]

    for col_name in draw_order:
        style = STYLE[col_name]
        svg_lines.append(f'  <g id="{col_name}" fill="{style["fill"]}" opacity="{style["opacity"]}">')
        for entry in walls_data.get(col_name, []):
            x = entry["x1"]
            w = entry["x2"] - entry["x1"]
            # Y軸反転
            svg_y = -entry["y2"]
            h = entry["y2"] - entry["y1"]
            svg_lines.append(
                f'    <rect x="{x:.3f}" y="{svg_y:.3f}" width="{w:.3f}" height="{h:.3f}">'
                f'<title>{entry["name"]}</title></rect>'
            )
        svg_lines.append("  </g>")

    svg_lines.append("</svg>")

    svg_path = output_dir / "floor_plan.svg"
    svg_path.write_text("\n".join(svg_lines), encoding="utf-8")
    print(f"SVG saved: {svg_path}")

    # --- 4. walls.json 出力 ---
    # nameフィールドを除去してBBox座標のみ保存
    walls_json = {}
    for col_name, entries in walls_data.items():
        walls_json[col_name] = [
            {"name": e["name"], "x1": e["x1"], "x2": e["x2"], "y1": e["y1"], "y2": e["y2"]}
            for e in entries
        ]

    walls_path = output_dir / "walls.json"
    walls_path.write_text(json.dumps(walls_json, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"walls.json saved: {walls_path}")

    # --- 5. メタデータ出力 ---
    meta = {
        "svg_viewbox": {
            "x": round(vb_x, 3),
            "y": round(vb_y, 3),
            "w": round(vb_w, 3),
            "h": round(vb_h, 3),
        },
        "svg_display": {"width": display_width, "height": display_height},
        "source_blend": "poc/3dcg_poc3/input/madori.blend",
    }
    meta_path = output_dir / "floor_plan_meta.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Metadata saved: {meta_path}")


if __name__ == "__main__":
    main()
