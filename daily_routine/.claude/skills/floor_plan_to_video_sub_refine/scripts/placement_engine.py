"""配置エンジン: placement_plan.jsonの座標に家具を配置し、重なりチェックとSVG出力を行う。

座標を決めるのはClaude Code。エンジンは配置と検証のみ。
"""

import json
import subprocess
import sys
from collections import deque
from pathlib import Path


def svg_to_png(svg_path, png_path, width=1600):
    """SVGをPNGに変換する（rsvg-convert使用）"""
    try:
        subprocess.run(
            ["rsvg-convert", "-w", str(width), "-o", str(png_path), str(svg_path)],
            check=True,
            capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        print(f"  WARNING: PNG変換失敗（{e}）。SVGのみ出力します。")


def rect(cx, cy, w, h):
    return (cx - w / 2, cx + w / 2, cy - h / 2, cy + h / 2)


def overlap(a, b):
    return a[0] < b[1] and a[1] > b[0] and a[2] < b[3] and a[3] > b[2]


def get_body_size(size, front_dir):
    w, d = size["width"], size["depth"]
    if front_dir in ("N", "S"):
        return w, d
    return d, w


def by(y):
    return -y


# === 動線検証 ===

GRID_SIZE = 0.1  # 10cm単位


def _cell(x, y, x_min, y_min):
    """実座標をグリッドセル(col, row)に変換"""
    return int((x - x_min) / GRID_SIZE), int((y - y_min) / GRID_SIZE)


def _rect_cells(r, x_min, y_min, cols, rows):
    """矩形(x1,x2,y1,y2)が占有するセルのイテレータ"""
    c1 = max(0, int((r[0] - x_min) / GRID_SIZE))
    c2 = min(cols - 1, int((r[1] - x_min) / GRID_SIZE))
    r1 = max(0, int((r[2] - y_min) / GRID_SIZE))
    r2 = min(rows - 1, int((r[3] - y_min) / GRID_SIZE))
    for row in range(r1, r2 + 1):
        for col in range(c1, c2 + 1):
            yield row, col


def check_walkability(room_info, walls_data, placements, grid_x_min, grid_y_min, cols, rows):
    """歩行可能領域の連結性と幅を検証する。

    障害物 = 壁 + 柱 + 家具のみ。
    固定設備(キッチン等)やno_place(通路等)は歩行可能空間として扱う。
    """
    # グリッド初期化: 全てFalse(歩行不可)
    grid = [[0] * cols for _ in range(rows)]  # 0=歩行不可, 1=歩行可能

    # Step 1: room/fixture領域を歩行可能にする
    for item in room_info:
        if item["type"] in ("room", "fixture", "no_place"):
            r = item["real_m"]
            for row, col in _rect_cells(
                (r["x_min"], r["x_max"], r["y_min"], r["y_max"]),
                grid_x_min, grid_y_min, cols, rows,
            ):
                grid[row][col] = 1

    # Step 2: 壁・柱を障害物に戻す
    for w in walls_data.get("壁", []):
        for row, col in _rect_cells((w["x1"], w["x2"], w["y1"], w["y2"]), grid_x_min, grid_y_min, cols, rows):
            grid[row][col] = 0
    for p in walls_data.get("柱", []):
        for row, col in _rect_cells((p["x1"], p["x2"], p["y1"], p["y2"]), grid_x_min, grid_y_min, cols, rows):
            grid[row][col] = 0

    # Step 3: 配置家具を障害物に戻す
    for p in placements:
        body = rect(p["cx"], p["cy"], p["bw"], p["bh"])
        for row, col in _rect_cells(body, grid_x_min, grid_y_min, cols, rows):
            grid[row][col] = 0

    # Step 4: 各セルの通路幅を計算
    MIN_PASSAGE = 0.6  # 人が通れる最小幅(m)
    min_cells = int(MIN_PASSAGE / GRID_SIZE)  # 最小幅に必要なセル数

    cell_width = [[0.0] * cols for _ in range(rows)]
    narrowest_cells = []
    min_width = float("inf")
    min_width_pos = (0, 0)

    for r in range(rows):
        for c in range(cols):
            if grid[r][c] == 0:
                continue
            # 水平方向の連続歩行可能セル数
            h_count = 0
            for dc in range(c, cols):
                if grid[r][dc] == 1:
                    h_count += 1
                else:
                    break
            for dc in range(c - 1, -1, -1):
                if grid[r][dc] == 1:
                    h_count += 1
                else:
                    break
            # 垂直方向
            v_count = 0
            for dr in range(r, rows):
                if grid[dr][c] == 1:
                    v_count += 1
                else:
                    break
            for dr in range(r - 1, -1, -1):
                if grid[dr][c] == 1:
                    v_count += 1
                else:
                    break
            w = min(h_count, v_count) * GRID_SIZE
            cell_width[r][c] = w
            if w < MIN_PASSAGE:
                narrowest_cells.append((r, c))
            if w < min_width:
                min_width = w
                min_width_pos = (
                    grid_x_min + c * GRID_SIZE,
                    grid_y_min + r * GRID_SIZE,
                )

    # Step 5: 通行可能グリッド（幅0.6m以上のセルのみ通行可能）
    passable = [[grid[r][c] == 1 and cell_width[r][c] >= MIN_PASSAGE for c in range(cols)] for r in range(rows)]

    # Step 6: 連結性チェック（flood fill on passable grid）
    # 起点: no_placeエントリの中心（ドア前通路）
    door_points = []
    for item in room_info:
        if item["type"] == "no_place":
            r = item["real_m"]
            cx = (r["x_min"] + r["x_max"]) / 2
            cy = (r["y_min"] + r["y_max"]) / 2
            c, rr = _cell(cx, cy, grid_x_min, grid_y_min)
            if 0 <= rr < rows and 0 <= c < cols and passable[rr][c]:
                door_points.append((item["label"], rr, c))

    visited = [[False] * cols for _ in range(rows)]
    connected_doors = []
    disconnected_doors = []

    if door_points:
        start_label, start_r, start_c = door_points[0]
        queue = deque([(start_r, start_c)])
        visited[start_r][start_c] = True
        while queue:
            r, c = queue.popleft()
            for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nr, nc = r + dr, c + dc
                if 0 <= nr < rows and 0 <= nc < cols and not visited[nr][nc] and passable[nr][nc]:
                    visited[nr][nc] = True
                    queue.append((nr, nc))

        for label, dr, dc in door_points:
            if visited[dr][dc]:
                connected_doors.append(label)
            else:
                disconnected_doors.append(label)

    # 歩行可能面積
    walkable_count = sum(1 for r in range(rows) for c in range(cols) if grid[r][c] == 1)
    total_room_count = sum(
        1 for r in range(rows) for c in range(cols)
        if any(
            item["real_m"]["x_min"] <= grid_x_min + c * GRID_SIZE <= item["real_m"]["x_max"]
            and item["real_m"]["y_min"] <= grid_y_min + r * GRID_SIZE <= item["real_m"]["y_max"]
            for item in room_info
            if item["type"] in ("room", "fixture")
        )
    )

    return {
        "grid": grid,
        "visited": visited,
        "narrowest_cells": set((r, c) for r, c in narrowest_cells),
        "connected_doors": connected_doors,
        "disconnected_doors": disconnected_doors,
        "min_width": min_width if min_width != float("inf") else 0,
        "min_width_pos": min_width_pos,
        "walkable_area": walkable_count * GRID_SIZE * GRID_SIZE,
        "total_area": total_room_count * GRID_SIZE * GRID_SIZE,
        "grid_x_min": grid_x_min,
        "grid_y_min": grid_y_min,
        "cols": cols,
        "rows": rows,
    }


def walkability_svg(result):
    """動線検証結果をSVGの矩形群として返す"""
    parts = ["  <!-- === 動線（歩行可能領域） === -->"]
    grid = result["grid"]
    visited = result["visited"]
    narrow = result["narrowest_cells"]
    x0 = result["grid_x_min"]
    y0 = result["grid_y_min"]
    rows = result["rows"]
    cols = result["cols"]
    gs = GRID_SIZE

    # 行ごとに連続する同色セルをまとめて描画
    for r in range(rows):
        c = 0
        while c < cols:
            if grid[r][c] == 0:
                c += 1
                continue
            # セルの色を決定
            if not visited[r][c]:
                color, opacity = "#F44336", "0.25"  # 到達不能（赤）
            elif (r, c) in narrow:
                color, opacity = "#FF9800", "0.30"  # 狭い（オレンジ）
            else:
                color, opacity = "#4CAF50", "0.15"  # 正常（緑）

            # 同色の連続セルをまとめる
            start_c = c
            while c < cols and grid[r][c] == 1:
                if not visited[r][c]:
                    this_color = "#F44336"
                elif (r, c) in narrow:
                    this_color = "#FF9800"
                else:
                    this_color = "#4CAF50"
                if this_color != color:
                    break
                c += 1

            rx = x0 + start_c * gs
            ry = y0 + r * gs
            rw = (c - start_c) * gs
            parts.append(
                f'  <rect x="{rx:.2f}" y="{by(ry + gs):.2f}" '
                f'width="{rw:.2f}" height="{gs:.2f}" '
                f'fill="{color}" opacity="{opacity}" />'
            )

    return "\n".join(parts)


def run(output_dir):
    output_dir = Path(output_dir)

    with open(output_dir / "placement_plan.json") as f:
        plan = json.load(f)
    with open(output_dir / "assets.json") as f:
        assets_data = json.load(f)
    with open(output_dir / "room_info.json") as f:
        room_info = json.load(f)
    with open(output_dir / "walls.json") as f:
        walls_data = json.load(f)
    with open(output_dir / "floor_plan_complete.svg") as f:
        base_svg = f.read()

    # 障害物: 壁+柱+配置不可
    obstacles = []
    for w in walls_data.get("壁", []):
        obstacles.append(("壁:" + w["name"], (w["x1"], w["x2"], w["y1"], w["y2"])))
    for p in walls_data.get("柱", []):
        obstacles.append(("柱:" + p["name"], (p["x1"], p["x2"], p["y1"], p["y2"])))
    # 配置不可領域（50%ルールは別扱い）
    no_place_50 = []
    for item in room_info:
        if item["type"] == "no_place":
            r = item["real_m"]
            nr = (r["x_min"], r["x_max"], r["y_min"], r["y_max"])
            if "50%" in item["label"]:
                no_place_50.append(("配置不可(50%):" + item["label"], nr))
            else:
                obstacles.append(("配置不可:" + item["label"], nr))

    asset_defs = {a["id"]: a for a in assets_data["assets"]}
    placements = []
    all_ok = True

    print("=== 配置+検証 ===\n")

    for step in plan["placement_order"]:
        asset_id = step["id"]
        instance = step["instance"]
        label = f"{asset_id}_{instance}"
        asset_def = asset_defs[asset_id]
        front_dir = step["front_dir"]
        bw, bh = get_body_size(asset_def["size"], front_dir)
        cx, cy = step["cx"], step["cy"]

        body = rect(cx, cy, bw, bh)

        # 重なりチェック
        issues = []
        for obs_label, obs_rect in obstacles:
            if overlap(body, obs_rect):
                issues.append(obs_label)
        # 50%ルール: 通路全体の面積のうち50%以上が空いていればOK
        for np_label, np_rect in no_place_50:
            if overlap(body, np_rect):
                # 通路と家具の重なり面積を計算
                ox1 = max(body[0], np_rect[0])
                ox2 = min(body[1], np_rect[1])
                oy1 = max(body[2], np_rect[2])
                oy2 = min(body[3], np_rect[3])
                overlap_area = max(0, ox2 - ox1) * max(0, oy2 - oy1)
                total_area = (np_rect[1] - np_rect[0]) * (np_rect[3] - np_rect[2])
                if total_area > 0 and overlap_area / total_area > 0.5:
                    issues.append(f"{np_label}(占有{overlap_area/total_area:.0%})")
        for p in placements:
            p_body = rect(p["cx"], p["cy"], p["bw"], p["bh"])
            if overlap(body, p_body):
                issues.append(p["label"])

        status = "OK" if not issues else "NG: " + ", ".join(issues[:3])
        if issues:
            all_ok = False

        placements.append({
            "label": label, "id": asset_id,
            "cx": cx, "cy": cy, "bw": bw, "bh": bh,
            "front_dir": front_dir, "reason": step["reason"],
            "color": {
                "bed": "#FF8A65", "closet": "#9575CD", "desk": "#FFB74D",
                "chair": "#FFD54F", "dining_table": "#AED581", "counter": "#4FC3F7",
            }.get(asset_id, "#999"),
            "issues": issues,
        })

        print(f"  [{label}] ({cx:.2f}, {cy:.2f}) {bw:.1f}x{bh:.1f}m → {status}")

    print(f"\n全体: {'PASS' if all_ok else 'FAIL'}")

    # === 動線検証 ===
    # グリッド範囲を計算
    room_fixture_items = [item for item in room_info if item["type"] in ("room", "fixture", "no_place")]
    if room_fixture_items:
        gx_min = min(item["real_m"]["x_min"] for item in room_fixture_items)
        gx_max = max(item["real_m"]["x_max"] for item in room_fixture_items)
        gy_min = min(item["real_m"]["y_min"] for item in room_fixture_items)
        gy_max = max(item["real_m"]["y_max"] for item in room_fixture_items)
        gcols = int((gx_max - gx_min) / GRID_SIZE) + 1
        grows = int((gy_max - gy_min) / GRID_SIZE) + 1

        walk_result = check_walkability(room_info, walls_data, placements, gx_min, gy_min, gcols, grows)

        print("\n=== 動線検証 ===")
        if walk_result["disconnected_doors"]:
            print(f"  連結性: FAIL（到達不能: {', '.join(walk_result['disconnected_doors'])}）")
        else:
            print(f"  連結性: PASS（全{len(walk_result['connected_doors'])}箇所のドアが接続）")
        if walk_result["min_width"] < 0.6:
            print(f"  最狭部: {walk_result['min_width']:.2f}m（{walk_result['min_width_pos'][0]:.1f}, {walk_result['min_width_pos'][1]:.1f}付近）→ WARNING: 0.6m未満")
        else:
            print(f"  最狭部: {walk_result['min_width']:.2f}m → OK")
        if walk_result["total_area"] > 0:
            ratio = walk_result["walkable_area"] / walk_result["total_area"] * 100
            print(f"  歩行可能面積: {walk_result['walkable_area']:.1f}㎡ / 全領域 {walk_result['total_area']:.1f}㎡（{ratio:.0f}%）")
    else:
        walk_result = None

    # === SVG生成 ===
    insert_pos = base_svg.rfind("</svg>")
    parts = [base_svg[:insert_pos]]

    # 動線（歩行可能領域）を家具の下に描画
    if walk_result:
        parts.append(walkability_svg(walk_result))

    parts.append("  <!-- === 配置結果 === -->")

    for p in placements:
        pr = rect(p["cx"], p["cy"], p["bw"], p["bh"])
        stroke = "#F44336" if p["issues"] else "#333"
        stroke_w = "0.04" if p["issues"] else "0.02"
        parts.append(
            f'  <rect x="{pr[0]:.3f}" y="{by(pr[3]):.3f}" '
            f'width="{p["bw"]:.3f}" height="{p["bh"]:.3f}" '
            f'fill="{p["color"]}" fill-opacity="0.7" stroke="{stroke}" '
            f'stroke-width="{stroke_w}" rx="0.03" />'
        )
        parts.append(
            f'  <text x="{p["cx"]:.2f}" y="{by(p["cy"])+0.07:.2f}" '
            f'text-anchor="middle" font-size="0.15" fill="#333" '
            f'font-weight="bold">{p["label"]}</text>'
        )

    # 凡例
    parts.append('  <g transform="translate(5.0, -3.5)">')
    parts.append('    <text x="0" y="0" font-size="0.20" font-weight="bold" fill="#333">配置結果</text>')
    for j, (c, l) in enumerate([
        ("#FF8A65", "ベッド"), ("#9575CD", "クローゼット"), ("#FFB74D", "デスク x2"),
        ("#FFD54F", "チェア x2"), ("#AED581", "ダイニング"), ("#4FC3F7", "カウンター x3"),
        ("#4CAF50", "歩行可能"), ("#FF9800", "狭い(0.6m未満)"), ("#F44336", "到達不能"),
    ]):
        parts.append(f'    <rect x="0" y="{0.12+j*0.23}" width="0.2" height="0.15" fill="{c}" fill-opacity="0.7" stroke="#999" stroke-width="0.01" />')
        parts.append(f'    <text x="0.3" y="{0.24+j*0.23}" font-size="0.13" fill="#333">{l}</text>')
    parts.append("  </g>")
    parts.append("</svg>")

    with open(output_dir / "layout_proposal.svg", "w") as f:
        f.write("\n".join(parts))

    layout = [
        {"id": p["id"], "label": p["label"],
         "center": {"x": p["cx"], "y": p["cy"]},
         "body_size": {"w": p["bw"], "h": p["bh"]},
         "front_dir": p["front_dir"], "reason": p["reason"],
         "issues": p["issues"]}
        for p in placements
    ]
    with open(output_dir / "layout_proposal.json", "w") as f:
        json.dump(layout, f, ensure_ascii=False, indent=2)

    # PNG変換（Claude Codeの空間認識用）
    svg_path = output_dir / "layout_proposal.svg"
    png_path = output_dir / "layout_proposal.png"
    svg_to_png(svg_path, png_path)

    print(f"\nSaved: layout_proposal.svg, layout_proposal.png, layout_proposal.json")


if __name__ == "__main__":
    run(sys.argv[1] if len(sys.argv) > 1 else "poc/3dcg_poc3/output")
