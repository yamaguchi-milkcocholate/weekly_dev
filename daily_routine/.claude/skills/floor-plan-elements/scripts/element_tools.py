"""壁rect配置スキル用ツール.

使い方:
    # PNG背景付きSVGテンプレートを生成
    uv run .claude/skills/floor-plan-walls/scripts/wall_tools.py template input.png -o output_dir

    # PNG画像から壁の特徴点（端点・交差点）を検出
    uv run .claude/skills/floor-plan-walls/scripts/wall_tools.py scan input.png -o output_dir

"""

import argparse
import base64
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np
from PIL import Image, ImageDraw

SVG_NS = "http://www.w3.org/2000/svg"
ET.register_namespace("", SVG_NS)

SCAN_BINARY_THRESHOLD = 128  # 二値化閾値
SCAN_CLUSTER_RADIUS = 15  # 特徴点クラスタリング半径（px）


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
    for group_id in ("walls", "pillars", "doors", "fixtures"):
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


def main() -> None:
    parser = argparse.ArgumentParser(description="壁rect配置スキル用ツール")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # template
    p_template = subparsers.add_parser("template", help="PNG背景付きSVGテンプレートを生成")
    p_template.add_argument("png", type=Path, help="入力PNG画像")
    p_template.add_argument("-o", "--output", type=Path, required=True, help="出力ディレクトリ")

    # scan
    p_scan = subparsers.add_parser("scan", help="PNG画像から壁の特徴点を検出")
    p_scan.add_argument("png", type=Path, help="入力PNG画像")
    p_scan.add_argument("-o", "--output", type=Path, required=True, help="出力ディレクトリ")

    args = parser.parse_args()

    if args.command == "template":
        cmd_template(args.png, args.output)
    elif args.command == "scan":
        cmd_scan(args.png, args.output)


if __name__ == "__main__":
    main()
