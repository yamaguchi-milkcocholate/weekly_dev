"""potrace生成SVGのパス分析・フィルタリングツール.

使い方:
    # パスにIDを付与し、BBox情報をJSON出力
    uv run scripts/svg_path_analyzer.py index input.svg -o output_dir

    # アノテーション付きプレビューPNG生成
    uv run scripts/svg_path_analyzer.py annotate indexed.svg -o output_dir

    # 指定パスを削除した新SVGを生成
    uv run scripts/svg_path_analyzer.py remove indexed.svg --ids path_003,path_010,path_045 -o output_dir

    # 指定パスのみを保持した新SVGを生成
    uv run scripts/svg_path_analyzer.py keep indexed.svg --ids path_001,path_002 -o output_dir

    # 複合パスをサブパスに分解し幾何特性を分析
    uv run scripts/svg_path_analyzer.py decompose indexed.svg -o output_dir [--target path_001]

"""

import argparse
import base64
import json
import re
import subprocess
import sys
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)


def parse_path_bbox(d_attr: str, transform: str | None = None) -> dict | None:
    """pathのd属性からバウンディングボックスを近似計算する.

    potraceのパスはM/c/l/z等で構成される。
    全座標トークンを収集してmin/maxを取る簡易実装。
    transformがある場合はscale/translateを適用する。
    """
    # 数値トークンを全て抽出
    tokens = re.findall(r"-?\d+(?:\.\d+)?", d_attr)
    if len(tokens) < 2:
        return None

    # M (moveto) の座標を基準に、相対座標を絶対座標に変換
    coords_x: list[float] = []
    coords_y: list[float] = []

    # コマンドごとにパースする簡易実装
    # potraceのパス: M x y (絶対) + c/l (相対) + z
    commands = re.findall(r"([MmCcLlHhVvZz])|(-?\d+(?:\.\d+)?)", d_attr)

    current_x = 0.0
    current_y = 0.0
    cmd = "M"
    nums: list[float] = []

    for match in commands:
        letter, number = match
        if letter:
            # 前のコマンドの座標を処理
            _process_nums(cmd, nums, coords_x, coords_y, current_x, current_y)
            if nums:
                # 最後の座標ペアをcurrent位置に更新
                if cmd.islower() and len(nums) >= 2:
                    current_x += nums[-2]
                    current_y += nums[-1]
                elif cmd.isupper() and len(nums) >= 2:
                    current_x = nums[-2]
                    current_y = nums[-1]
            cmd = letter
            nums = []
        elif number:
            nums.append(float(number))

    # 最後のコマンド処理
    _process_nums(cmd, nums, coords_x, coords_y, current_x, current_y)

    if not coords_x or not coords_y:
        return None

    min_x, max_x = min(coords_x), max(coords_x)
    min_y, max_y = min(coords_y), max(coords_y)

    # transform適用
    if transform:
        scale_m = re.search(r"scale\(([-\d.]+),([-\d.]+)\)", transform)
        translate_m = re.search(r"translate\(([-\d.]+),([-\d.]+)\)", transform)
        sx, sy = 1.0, 1.0
        tx, ty = 0.0, 0.0
        if scale_m:
            sx, sy = float(scale_m.group(1)), float(scale_m.group(2))
        if translate_m:
            tx, ty = float(translate_m.group(1)), float(translate_m.group(2))

        # transform: translate then scale
        points = [
            (min_x * sx + tx, min_y * sy + ty),
            (max_x * sx + tx, max_y * sy + ty),
        ]
        min_x = min(p[0] for p in points)
        max_x = max(p[0] for p in points)
        min_y = min(p[1] for p in points)
        max_y = max(p[1] for p in points)

    return {
        "x": round(min_x, 2),
        "y": round(min_y, 2),
        "width": round(max_x - min_x, 2),
        "height": round(max_y - min_y, 2),
        "cx": round((min_x + max_x) / 2, 2),
        "cy": round((min_y + max_y) / 2, 2),
    }


def _process_nums(
    cmd: str,
    nums: list[float],
    coords_x: list[float],
    coords_y: list[float],
    cur_x: float,
    cur_y: float,
) -> None:
    """コマンドに応じて座標リストに追加する."""
    if not nums:
        return
    if cmd in ("M", "L"):
        for i in range(0, len(nums) - 1, 2):
            coords_x.append(nums[i])
            coords_y.append(nums[i + 1])
    elif cmd in ("m", "l"):
        cx, cy = cur_x, cur_y
        for i in range(0, len(nums) - 1, 2):
            cx += nums[i]
            cy += nums[i + 1]
            coords_x.append(cx)
            coords_y.append(cy)
    elif cmd == "c":
        cx, cy = cur_x, cur_y
        for i in range(0, len(nums) - 5, 6):
            # 制御点と終点の全てを含める
            coords_x.extend([cx + nums[i], cx + nums[i + 2], cx + nums[i + 4]])
            coords_y.extend([cy + nums[i + 1], cy + nums[i + 3], cy + nums[i + 5]])
            cx += nums[i + 4]
            cy += nums[i + 5]
    elif cmd == "C":
        for i in range(0, len(nums) - 5, 6):
            coords_x.extend([nums[i], nums[i + 2], nums[i + 4]])
            coords_y.extend([nums[i + 1], nums[i + 3], nums[i + 5]])


# --- decompose用の分類閾値 ---
SYMBOL_AREA_THRESHOLD = 500  # BBox面積がこれ未満 → symbol（文字・記号）
WALL_CURVE_RATIO_MAX = 0.3  # 曲線率がこれ以下 → wall（壁）
DOOR_ARC_CURVE_RATIO_MIN = 0.7  # 曲線率がこれ以上 → door_arc（ドア弧）


def split_subpaths(d_attr: str) -> list[dict]:
    """複合パスのd属性をサブパスに分割し、相対movetoを絶対座標に変換する.

    potraceの出力は M x y ... z (m dx dy ... z)* の構造を持つ。
    z後のmは直前サブパスの始点からの相対位置になる（SVG仕様）。
    """
    # M/mの出現位置でチャンクに分割
    chunks = re.findall(r"[Mm][^Mm]*", d_attr)
    if not chunks:
        return []

    subpaths: list[dict] = []
    # 最初のサブパスの始点を追跡
    subpath_start_x = 0.0
    subpath_start_y = 0.0

    for i, chunk in enumerate(chunks):
        chunk = chunk.strip()
        cmd_char = chunk[0]
        # M/m直後の最初の2数値が始点座標
        nums = re.findall(r"-?\d+(?:\.\d+)?", chunk)
        if len(nums) < 2:
            continue

        if cmd_char == "M":
            origin_x = float(nums[0])
            origin_y = float(nums[1])
        else:  # m（相対）
            origin_x = subpath_start_x + float(nums[0])
            origin_y = subpath_start_y + float(nums[1])

        # 相対mを絶対Mに書き換え
        if cmd_char == "m":
            # m dx dy を M abs_x abs_y に置換（最初の2数値のみ）
            rest = chunk[1:].strip()
            # 最初の2数値を絶対座標に置換
            match = re.match(r"(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)(.*)", rest, re.DOTALL)
            if match:
                new_d = f"M{origin_x} {origin_y}{match.group(3)}"
            else:
                new_d = f"M{origin_x} {origin_y}"
        else:
            new_d = chunk

        subpaths.append(
            {
                "d": new_d.strip(),
                "origin_x": origin_x,
                "origin_y": origin_y,
            }
        )

        # 次のサブパスのためにこのサブパスの始点を記録
        # z後のcurrent pointはこのサブパスの始点に戻る
        subpath_start_x = origin_x
        subpath_start_y = origin_y

    return subpaths


def count_segments(d_attr: str) -> dict:
    """サブパスのd属性から直線/曲線セグメント数をカウントする."""
    commands = re.findall(r"([MmCcLlHhVvZz])([^MmCcLlHhVvZz]*)", d_attr)

    line_count = 0
    curve_count = 0

    for cmd, args in commands:
        nums = re.findall(r"-?\d+(?:\.\d+)?", args)
        if cmd in ("l", "L"):
            # 2数値で1セグメント
            line_count += max(len(nums) // 2, 0)
        elif cmd in ("h", "H", "v", "V"):
            line_count += max(len(nums), 0)
        elif cmd in ("c", "C"):
            # 6数値で1セグメント
            curve_count += max(len(nums) // 6, 0)
        # M/m/Z/z はセグメントカウントに含めない

    total = line_count + curve_count
    curve_ratio = curve_count / total if total > 0 else 0.0

    return {
        "line": line_count,
        "curve": curve_count,
        "total": total,
        "curve_ratio": round(curve_ratio, 3),
    }


def classify_subpath(segments: dict, bbox_area: float) -> str:
    """セグメント情報とBBox面積からカテゴリを判定する."""
    if bbox_area < SYMBOL_AREA_THRESHOLD:
        return "symbol"
    if segments["curve_ratio"] <= WALL_CURVE_RATIO_MAX:
        return "wall"
    if segments["curve_ratio"] >= DOOR_ARC_CURVE_RATIO_MIN:
        return "door_arc"
    return "fixture"


def analyze_subpath(d_attr: str, index: int, transform: str | None = None) -> dict:
    """1サブパスの幾何特性を統合分析する."""
    bbox = parse_path_bbox(d_attr, transform)
    segments = count_segments(d_attr)

    bbox_area = 0.0
    if bbox:
        bbox_area = round(bbox["width"] * bbox["height"], 2)

    category = classify_subpath(segments, bbox_area)
    is_closed = d_attr.rstrip().endswith("z") or d_attr.rstrip().endswith("Z")

    # 始点座標を抽出
    nums = re.findall(r"-?\d+(?:\.\d+)?", d_attr)
    origin_x = float(nums[0]) if len(nums) >= 1 else 0.0
    origin_y = float(nums[1]) if len(nums) >= 2 else 0.0

    return {
        "index": index,
        "origin": {"x": origin_x, "y": origin_y},
        "is_closed": is_closed,
        "segments": segments,
        "bbox": bbox,
        "bbox_area": bbox_area,
        "category": category,
    }


def cmd_decompose(svg_path: Path, output_dir: Path, target_id: str = "path_001") -> None:
    """複合パスをサブパスに分解し、個別の<path>要素として再構成する."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    g_elem = root.find(f".//{{{SVG_NS}}}g")
    if g_elem is None:
        print("ERROR: <g> element not found")
        sys.exit(1)

    transform = g_elem.get("transform", "")

    # 対象パスを検索
    target_elem = None
    target_index = -1
    for i, path_elem in enumerate(g_elem.findall(f"{{{SVG_NS}}}path")):
        if path_elem.get("id") == target_id:
            target_elem = path_elem
            target_index = i
            break

    if target_elem is None:
        print(f"ERROR: {target_id} not found")
        sys.exit(1)

    d_attr = target_elem.get("d", "")
    fill = target_elem.get("fill", "#000000")

    # サブパスに分割
    subpath_list = split_subpaths(d_attr)
    print(f"{target_id} を {len(subpath_list)} サブパスに分解")

    # 各サブパスを分析
    analyses: list[dict] = []
    for i, sp in enumerate(subpath_list):
        analysis = analyze_subpath(sp["d"], i, transform if transform else None)
        sub_id = f"{target_id}_sub_{i + 1:03d}"
        analysis["id"] = sub_id
        analyses.append(analysis)

    # カテゴリ集計
    category_summary: dict[str, int] = {}
    for a in analyses:
        cat = a["category"]
        category_summary[cat] = category_summary.get(cat, 0) + 1

    print("カテゴリ分布:")
    for cat, cnt in sorted(category_summary.items()):
        print(f"  {cat}: {cnt}")

    # SVG再構成: 対象パスを削除し、サブパスを個別<path>要素として挿入
    g_elem.remove(target_elem)

    # 対象パスの位置に逆順で挿入（挿入後の順序が正しくなるように）
    for i, (sp, analysis) in enumerate(reversed(list(zip(subpath_list, analyses)))):
        new_path = ET.Element(f"{{{SVG_NS}}}path")
        new_path.set("id", analysis["id"])
        new_path.set("d", sp["d"])
        new_path.set("fill", fill)
        new_path.set("data-category", analysis["category"])
        g_elem.insert(target_index, new_path)

    # annotations グループがあれば削除
    anno_g = root.find(f".//{{{SVG_NS}}}g[@id='annotations']")
    if anno_g is not None:
        root.remove(anno_g)

    # 出力
    output_dir.mkdir(parents=True, exist_ok=True)
    out_svg = output_dir / f"{svg_path.stem}_decomposed.svg"
    tree.write(out_svg, encoding="unicode", xml_declaration=True)
    print(f"SVG: {out_svg}")

    # プレビューPNG
    preview = output_dir / f"{svg_path.stem}_decomposed_preview.png"
    _svg_to_png(out_svg, preview)
    print(f"Preview: {preview}")

    # 分析レポートJSON
    report = {
        "source": str(svg_path),
        "target_path": target_id,
        "total_subpaths": len(analyses),
        "category_summary": category_summary,
        "thresholds": {
            "symbol_area": SYMBOL_AREA_THRESHOLD,
            "wall_curve_ratio_max": WALL_CURVE_RATIO_MAX,
            "door_arc_curve_ratio_min": DOOR_ARC_CURVE_RATIO_MIN,
        },
        "subpaths": analyses,
    }
    json_path = output_dir / f"{svg_path.stem}_decomposed_analysis.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Analysis: {json_path}")


# --- scan用の定数 ---
SCAN_BINARY_THRESHOLD = 128  # 二値化閾値
SCAN_CLUSTER_RADIUS = 15  # 特徴点クラスタリング半径（px）


def _skeletonize(binary: np.ndarray) -> np.ndarray:
    """二値画像をスケルトン化（Zhang-Suenアルゴリズム簡易版）する."""
    skel = binary.copy()
    changed = True
    while changed:
        changed = False
        for step in range(2):
            markers = np.zeros_like(skel)
            rows, cols = skel.shape
            for y in range(1, rows - 1):
                for x in range(1, cols - 1):
                    if skel[y, x] == 0:
                        continue
                    # 8近傍 (P2〜P9): 上から時計回り
                    p2 = skel[y - 1, x]
                    p3 = skel[y - 1, x + 1]
                    p4 = skel[y, x + 1]
                    p5 = skel[y + 1, x + 1]
                    p6 = skel[y + 1, x]
                    p7 = skel[y + 1, x - 1]
                    p8 = skel[y, x - 1]
                    p9 = skel[y - 1, x - 1]

                    neighbors = [p2, p3, p4, p5, p6, p7, p8, p9]
                    b = sum(neighbors)  # 黒隣接数

                    # 0→1の遷移数
                    transitions = 0
                    for i in range(8):
                        if neighbors[i] == 0 and neighbors[(i + 1) % 8] == 1:
                            transitions += 1

                    if b < 2 or b > 6:
                        continue
                    if transitions != 1:
                        continue

                    if step == 0:
                        if p2 * p4 * p6 != 0:
                            continue
                        if p4 * p6 * p8 != 0:
                            continue
                    else:
                        if p2 * p4 * p8 != 0:
                            continue
                        if p2 * p6 * p8 != 0:
                            continue

                    markers[y, x] = 1
                    changed = True
            skel[markers == 1] = 0
    return skel


def _detect_keypoints(skeleton: np.ndarray) -> list[dict]:
    """スケルトン画像から端点・交差点を検出する."""
    rows, cols = skeleton.shape
    keypoints: list[dict] = []

    for y in range(1, rows - 1):
        for x in range(1, cols - 1):
            if skeleton[y, x] == 0:
                continue

            # 8近傍の接続数を計算
            neighbors = [
                skeleton[y - 1, x],  # N
                skeleton[y - 1, x + 1],  # NE
                skeleton[y, x + 1],  # E
                skeleton[y + 1, x + 1],  # SE
                skeleton[y + 1, x],  # S
                skeleton[y + 1, x - 1],  # SW
                skeleton[y, x - 1],  # W
                skeleton[y - 1, x - 1],  # NW
            ]
            connections = sum(neighbors)

            if connections == 1:
                keypoints.append({"x": int(x), "y": int(y), "type": "endpoint", "connections": int(connections)})
            elif connections >= 3:
                keypoints.append({"x": int(x), "y": int(y), "type": "junction", "connections": int(connections)})

    return keypoints


def _cluster_keypoints(keypoints: list[dict], radius: int) -> list[dict]:
    """近接する特徴点をクラスタリングして代表点を返す."""
    if not keypoints:
        return []

    used = [False] * len(keypoints)
    clusters: list[dict] = []

    for i, kp in enumerate(keypoints):
        if used[i]:
            continue

        # このkpを中心にradius内の特徴点を集める
        cluster_x = [kp["x"]]
        cluster_y = [kp["y"]]
        cluster_connections = [kp["connections"]]
        used[i] = True

        for j in range(i + 1, len(keypoints)):
            if used[j]:
                continue
            dx = keypoints[j]["x"] - kp["x"]
            dy = keypoints[j]["y"] - kp["y"]
            if dx * dx + dy * dy <= radius * radius:
                cluster_x.append(keypoints[j]["x"])
                cluster_y.append(keypoints[j]["y"])
                cluster_connections.append(keypoints[j]["connections"])
                used[j] = True

        # 代表点: 重心座標、最大接続数
        avg_x = int(round(sum(cluster_x) / len(cluster_x)))
        avg_y = int(round(sum(cluster_y) / len(cluster_y)))
        max_conn = max(cluster_connections)

        kp_type = "endpoint" if max_conn == 1 else "junction"
        clusters.append({"x": avg_x, "y": avg_y, "type": kp_type, "connections": max_conn})

    return clusters


def cmd_scan(png_path: Path, output_dir: Path) -> None:
    """PNG画像から壁の特徴点（端点・交差点）を検出する."""
    # 画像読み込み・二値化
    img = Image.open(png_path).convert("L")
    width, height = img.size
    print(f"画像サイズ: {width}x{height}")

    arr = np.array(img)
    binary = (arr < SCAN_BINARY_THRESHOLD).astype(np.uint8)
    print(f"黒ピクセル数: {binary.sum()} / {width * height}")

    # スケルトン化
    print("スケルトン化中...")
    skeleton = _skeletonize(binary)
    skel_pixels = skeleton.sum()
    print(f"スケルトンピクセル数: {skel_pixels}")

    # 特徴点検出
    raw_keypoints = _detect_keypoints(skeleton)
    print(f"生の特徴点数: {len(raw_keypoints)}")

    # クラスタリング
    clustered = _cluster_keypoints(raw_keypoints, SCAN_CLUSTER_RADIUS)
    print(f"クラスタリング後: {len(clustered)}")

    # ID付与
    for i, kp in enumerate(clustered):
        kp["id"] = f"kp_{i + 1:03d}"

    # カテゴリ集計
    endpoints = sum(1 for kp in clustered if kp["type"] == "endpoint")
    junctions = sum(1 for kp in clustered if kp["type"] == "junction")
    print(f"端点: {endpoints}, 交差点: {junctions}")

    # JSON出力
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "source": str(png_path),
        "image_size": {"width": width, "height": height},
        "skeleton_pixels": int(skel_pixels),
        "total_keypoints": len(clustered),
        "summary": {"endpoint": endpoints, "junction": junctions},
        "keypoints": clustered,
    }
    json_path = output_dir / f"{png_path.stem}_keypoints.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Keypoints JSON: {json_path}")

    # プレビュー画像生成（元画像に特徴点をマーキング）
    preview = img.convert("RGB")
    draw = ImageDraw.Draw(preview)
    marker_radius = max(3, min(width, height) // 200)

    for kp in clustered:
        x, y = kp["x"], kp["y"]
        color = (255, 0, 0) if kp["type"] == "endpoint" else (0, 0, 255)
        draw.ellipse(
            [x - marker_radius, y - marker_radius, x + marker_radius, y + marker_radius],
            fill=color,
            outline=color,
        )

    preview_path = output_dir / f"{png_path.stem}_keypoints_preview.png"
    preview.save(preview_path)
    print(f"Preview: {preview_path}")


def cmd_template(png_path: Path, output_dir: Path) -> None:
    """PNG画像を背景として埋め込んだSVGテンプレートを生成する."""
    # 画像サイズ取得
    with Image.open(png_path) as img:
        width, height = img.size

    # base64エンコード
    png_bytes = png_path.read_bytes()
    b64_data = base64.b64encode(png_bytes).decode("ascii")

    # SVG構築
    XLINK_NS = "http://www.w3.org/1999/xlink"
    ET.register_namespace("xlink", XLINK_NS)

    root = ET.Element(f"{{{SVG_NS}}}svg")
    root.set("viewBox", f"0 0 {width} {height}")
    root.set("width", str(width))
    root.set("height", str(height))

    # 背景画像（Blenderでは無視される）
    image_elem = ET.SubElement(root, f"{{{SVG_NS}}}image")
    image_elem.set("x", "0")
    image_elem.set("y", "0")
    image_elem.set("width", str(width))
    image_elem.set("height", str(height))
    image_elem.set("href", f"data:image/png;base64,{b64_data}")
    image_elem.set("opacity", "0.3")

    # カテゴリ別グループ
    for group_id in ("walls", "doors", "fixtures"):
        g = ET.SubElement(root, f"{{{SVG_NS}}}g")
        g.set("id", group_id)

    # 出力
    output_dir.mkdir(parents=True, exist_ok=True)
    out_svg = output_dir / f"{png_path.stem}_template.svg"

    tree = ET.ElementTree(root)
    tree.write(out_svg, encoding="unicode", xml_declaration=True)
    print(f"Template SVG: {out_svg}")
    print(f"Image size: {width}x{height}")

    # プレビューPNG
    preview = output_dir / f"{png_path.stem}_template_preview.png"
    _svg_to_png(out_svg, preview)
    print(f"Preview: {preview}")


def cmd_index(svg_path: Path, output_dir: Path) -> None:
    """各pathにIDを付与し、BBox情報をJSON出力する."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # viewBox取得
    viewbox = root.get("viewBox", "")

    # <g>内のpath要素を取得
    g_elem = root.find(f".//{{{SVG_NS}}}g")
    if g_elem is None:
        print("ERROR: <g> element not found")
        sys.exit(1)

    transform = g_elem.get("transform", "")
    paths = g_elem.findall(f"{{{SVG_NS}}}path")
    print(f"Found {len(paths)} paths")

    path_info: list[dict] = []
    for i, path_elem in enumerate(paths):
        path_id = f"path_{i + 1:03d}"
        path_elem.set("id", path_id)
        d_attr = path_elem.get("d", "")
        bbox = parse_path_bbox(d_attr, transform if transform else None)
        info = {"id": path_id, "bbox": bbox}
        path_info.append(info)

    # ID付与済みSVG保存
    output_dir.mkdir(parents=True, exist_ok=True)
    indexed_svg = output_dir / f"{svg_path.stem}_indexed.svg"
    tree.write(indexed_svg, encoding="unicode", xml_declaration=True)
    print(f"Indexed SVG: {indexed_svg}")

    # BBox JSON保存
    json_path = output_dir / f"{svg_path.stem}_paths.json"
    json_path.write_text(
        json.dumps(
            {"source": str(svg_path), "viewBox": viewbox, "transform": transform, "paths": path_info},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"Path info: {json_path}")

    # プレビューPNG生成
    preview = output_dir / f"{svg_path.stem}_indexed_preview.png"
    _svg_to_png(indexed_svg, preview)

    # アノテーション付きプレビューも自動生成
    cmd_annotate(indexed_svg, output_dir)


def cmd_annotate(svg_path: Path, output_dir: Path) -> None:
    """パスIDをラベル表示したアノテーションSVGとPNGを生成する."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # viewBox解析
    viewbox = root.get("viewBox", "0 0 100 100")
    vb_parts = viewbox.split()
    vb_w = float(vb_parts[2])
    vb_h = float(vb_parts[3])

    g_elem = root.find(f".//{{{SVG_NS}}}g")
    if g_elem is None:
        print("ERROR: <g> element not found")
        sys.exit(1)

    transform = g_elem.get("transform", "")
    paths = g_elem.findall(f"{{{SVG_NS}}}path")

    # アノテーション用グループを追加（元のgの外に）
    anno_g = ET.SubElement(root, f"{{{SVG_NS}}}g")
    anno_g.set("id", "annotations")

    # ラベルサイズをviewBoxに応じて調整
    font_size = max(vb_w, vb_h) * 0.012
    colors = ["#E53935", "#1E88E5", "#43A047", "#FB8C00", "#8E24AA", "#00ACC1"]

    for i, path_elem in enumerate(paths):
        path_id = path_elem.get("id", f"path_{i + 1:03d}")
        d_attr = path_elem.get("d", "")
        bbox = parse_path_bbox(d_attr, transform if transform else None)
        if not bbox:
            continue

        color = colors[i % len(colors)]

        # パスにストロークを付与して視認性向上
        path_elem.set("stroke", color)
        path_elem.set("stroke-width", str(font_size * 0.3))
        path_elem.set("stroke-opacity", "0.5")

        # ラベル背景
        rect = ET.SubElement(anno_g, f"{{{SVG_NS}}}rect")
        label_w = font_size * len(path_id) * 0.6
        label_h = font_size * 1.4
        rect.set("x", str(bbox["cx"] - label_w / 2))
        rect.set("y", str(bbox["cy"] - label_h / 2))
        rect.set("width", str(label_w))
        rect.set("height", str(label_h))
        rect.set("fill", "white")
        rect.set("fill-opacity", "0.85")
        rect.set("stroke", color)
        rect.set("stroke-width", str(font_size * 0.1))

        # ラベルテキスト
        text = ET.SubElement(anno_g, f"{{{SVG_NS}}}text")
        text.set("x", str(bbox["cx"]))
        text.set("y", str(bbox["cy"] + font_size * 0.35))
        text.set("text-anchor", "middle")
        text.set("font-size", str(font_size))
        text.set("font-family", "monospace")
        text.set("fill", color)
        text.text = path_id

    # アノテーションSVG保存
    output_dir.mkdir(parents=True, exist_ok=True)
    anno_svg = output_dir / f"{svg_path.stem}_annotated.svg"
    tree.write(anno_svg, encoding="unicode", xml_declaration=True)
    print(f"Annotated SVG: {anno_svg}")

    # PNG変換
    preview = output_dir / f"{svg_path.stem}_annotated.png"
    _svg_to_png(anno_svg, preview, density=200)
    print(f"Annotated PNG: {preview}")


def cmd_remove(svg_path: Path, ids: list[str], output_dir: Path) -> None:
    """指定IDのパスを削除した新SVGを生成する."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    g_elem = root.find(f".//{{{SVG_NS}}}g")
    if g_elem is None:
        print("ERROR: <g> element not found")
        sys.exit(1)

    ids_set = set(ids)
    removed = 0
    for path_elem in g_elem.findall(f"{{{SVG_NS}}}path"):
        pid = path_elem.get("id", "")
        if pid in ids_set:
            g_elem.remove(path_elem)
            removed += 1

    print(f"Removed {removed}/{len(ids_set)} paths")

    # annotations グループがあれば対応ラベルも削除
    anno_g = root.find(f".//{{{SVG_NS}}}g[@id='annotations']")
    if anno_g is not None:
        root.remove(anno_g)

    # 保存
    output_dir.mkdir(parents=True, exist_ok=True)
    out_svg = output_dir / f"{svg_path.stem}_filtered.svg"
    tree.write(out_svg, encoding="unicode", xml_declaration=True)
    print(f"Filtered SVG: {out_svg}")

    # プレビュー
    preview = output_dir / f"{svg_path.stem}_filtered_preview.png"
    _svg_to_png(out_svg, preview)
    print(f"Preview: {preview}")


def cmd_keep(svg_path: Path, ids: list[str], output_dir: Path) -> None:
    """指定IDのパスのみを保持した新SVGを生成する."""
    tree = ET.parse(svg_path)
    root = tree.getroot()

    g_elem = root.find(f".//{{{SVG_NS}}}g")
    if g_elem is None:
        print("ERROR: <g> element not found")
        sys.exit(1)

    ids_set = set(ids)
    to_remove = []
    for path_elem in g_elem.findall(f"{{{SVG_NS}}}path"):
        pid = path_elem.get("id", "")
        if pid not in ids_set:
            to_remove.append(path_elem)

    for elem in to_remove:
        g_elem.remove(elem)

    kept = len(g_elem.findall(f"{{{SVG_NS}}}path"))
    print(f"Kept {kept} paths, removed {len(to_remove)}")

    # annotations グループがあれば削除
    anno_g = root.find(f".//{{{SVG_NS}}}g[@id='annotations']")
    if anno_g is not None:
        root.remove(anno_g)

    # 保存
    output_dir.mkdir(parents=True, exist_ok=True)
    out_svg = output_dir / f"{svg_path.stem}_walls.svg"
    tree.write(out_svg, encoding="unicode", xml_declaration=True)
    print(f"SVG: {out_svg}")

    # プレビュー
    preview = output_dir / f"{svg_path.stem}_walls_preview.png"
    _svg_to_png(out_svg, preview)
    print(f"Preview: {preview}")


def _svg_to_png(svg_path: Path, png_path: Path, density: int = 150) -> None:
    """ImageMagickでSVGをPNGに変換する."""
    try:
        subprocess.run(
            ["magick", "-density", str(density), str(svg_path), str(png_path)],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"WARNING: PNG conversion failed: {e.stderr}")
    except FileNotFoundError:
        print("WARNING: ImageMagick (magick) not found, skipping PNG generation")


def main() -> None:
    parser = argparse.ArgumentParser(description="potrace SVGパス分析・フィルタリングツール")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # index
    p_index = subparsers.add_parser("index", help="パスにIDを付与しBBox情報を出力")
    p_index.add_argument("svg", type=Path, help="入力SVGファイル")
    p_index.add_argument("-o", "--output-dir", type=Path, default=None, help="出力ディレクトリ")

    # annotate
    p_anno = subparsers.add_parser("annotate", help="ID付きアノテーションプレビュー生成")
    p_anno.add_argument("svg", type=Path, help="ID付与済みSVGファイル")
    p_anno.add_argument("-o", "--output-dir", type=Path, default=None, help="出力ディレクトリ")

    # remove
    p_remove = subparsers.add_parser("remove", help="指定パスを削除")
    p_remove.add_argument("svg", type=Path, help="ID付与済みSVGファイル")
    p_remove.add_argument("--ids", required=True, help="削除するパスID（カンマ区切り）")
    p_remove.add_argument("-o", "--output-dir", type=Path, default=None, help="出力ディレクトリ")

    # keep
    p_keep = subparsers.add_parser("keep", help="指定パスのみ保持")
    p_keep.add_argument("svg", type=Path, help="ID付与済みSVGファイル")
    p_keep.add_argument("--ids", required=True, help="保持するパスID（カンマ区切り）")
    p_keep.add_argument("-o", "--output-dir", type=Path, default=None, help="出力ディレクトリ")

    # decompose
    p_decompose = subparsers.add_parser("decompose", help="複合パスをサブパスに分解・分類")
    p_decompose.add_argument("svg", type=Path, help="ID付与済みSVGファイル")
    p_decompose.add_argument("--target", default="path_001", help="分解対象パスID（デフォルト: path_001）")
    p_decompose.add_argument("-o", "--output-dir", type=Path, default=None, help="出力ディレクトリ")

    # template
    p_template = subparsers.add_parser("template", help="PNG背景付きSVGテンプレートを生成")
    p_template.add_argument("png", type=Path, help="入力PNG画像")
    p_template.add_argument("-o", "--output-dir", type=Path, default=None, help="出力ディレクトリ")

    # scan
    p_scan = subparsers.add_parser("scan", help="PNG画像から壁の特徴点を検出")
    p_scan.add_argument("png", type=Path, help="フィルタ済み壁線PNG")
    p_scan.add_argument("-o", "--output-dir", type=Path, default=None, help="出力ディレクトリ")

    args = parser.parse_args()

    # PNG入力コマンドは別処理
    if args.command in ("template", "scan"):
        png_path = args.png.resolve()
        output_dir = args.output_dir.resolve() if args.output_dir else png_path.parent
        if args.command == "template":
            cmd_template(png_path, output_dir)
        else:
            cmd_scan(png_path, output_dir)
        return

    svg_path = args.svg.resolve()
    output_dir = args.output_dir.resolve() if args.output_dir else svg_path.parent

    if args.command == "index":
        cmd_index(svg_path, output_dir)
    elif args.command == "annotate":
        cmd_annotate(svg_path, output_dir)
    elif args.command == "remove":
        ids = [s.strip() for s in args.ids.split(",")]
        cmd_remove(svg_path, ids, output_dir)
    elif args.command == "keep":
        ids = [s.strip() for s in args.ids.split(",")]
        cmd_keep(svg_path, ids, output_dir)
    elif args.command == "decompose":
        cmd_decompose(svg_path, output_dir, args.target)


if __name__ == "__main__":
    main()
