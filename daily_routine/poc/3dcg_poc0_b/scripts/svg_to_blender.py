"""elements SVG → Blender 3D空間構築スクリプト

壁・柱・ドア・窓・ガラスドアのrect要素を読み取り、Blenderの3Dメッシュとして生成する。
- 壁・柱: 箱型メッシュ（extrude済み）
- ドア: 独立パネルオブジェクト + 欄間壁
- 窓: ガラスパネル + 窓下壁 + 欄間壁
- ガラスドア（掃き出し窓）: ガラスパネル + 欄間壁
- 室内ライト: 各部屋エリアにエリアライト自動配置
- 窓外背景プレーン: 窓・ガラスドアの外側に空色プレーン配置

座標変換:
  SVG: 原点=左上、y軸=下向き、単位=px
  Blender: 原点=左下、z軸=上向き、単位=m
  変換: blender_x = svg_x * scale
         blender_y = -svg_y * scale (反転)
         blender_z = 0〜wall_height (上方向に立ち上げ)
  scale: 1px = 0.01m (1cm)

Usage:
  scripts/run_blender.sh --background --python poc/3dcg_poc0_b/scripts/svg_to_blender.py -- \
    --svg poc/3dcg_poc0_b/1/input/madori_1ldk_1_elements.svg \
    --output poc/3dcg_poc0_b/1/output/scene.blend
"""

import argparse
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import bpy

# ---------- 定数 ----------
SCALE = 0.01  # 1px = 0.01m
WALL_HEIGHT = 2.4  # m
DOOR_HEIGHT = 2.0  # m
WINDOW_SILL_HEIGHT = 0.8  # m（腰高窓の下端）
WINDOW_TOP_HEIGHT = 2.0  # m（窓の上端）
FLOOR_THICKNESS = 0.05  # m

# PBRマテリアル設定（課題3対応: ニュートラルな色味に調整）
PBR_SETTINGS = {
    "wall": {
        "base_color": (0.92, 0.92, 0.90, 1.0),  # ニュートラル白（暖色偏り修正）
        "roughness": 0.7,
        "noise_scale": 15.0,
        "noise_mix": 0.08,
    },
    "pillar": {
        "base_color": (0.75, 0.75, 0.73, 1.0),  # ニュートラルコンクリート
        "roughness": 0.8,
        "noise_scale": 20.0,
        "noise_mix": 0.10,
    },
    "door": {
        "base_color": (0.40, 0.28, 0.15, 1.0),  # 明るめ木目
        "roughness": 0.45,
        "noise_scale": 30.0,
        "noise_mix": 0.06,
    },
    "transom": {
        "base_color": (0.92, 0.92, 0.90, 1.0),  # 壁と同色
        "roughness": 0.7,
        "noise_scale": 15.0,
        "noise_mix": 0.08,
    },
    "floor": {
        "base_color": (0.55, 0.45, 0.32, 1.0),  # 明るいフローリング（暗すぎ修正）
        "roughness": 0.55,
        "noise_scale": 25.0,
        "noise_mix": 0.07,
    },
    "ceiling": {
        "base_color": (0.95, 0.95, 0.93, 1.0),  # ニュートラル白天井
        "roughness": 0.8,
        "noise_scale": 10.0,
        "noise_mix": 0.05,
    },
    "window_frame": {
        "base_color": (0.85, 0.85, 0.83, 1.0),  # 窓枠（白に近いグレー）
        "roughness": 0.3,
        "noise_scale": 10.0,
        "noise_mix": 0.03,
    },
}

NS = {"svg": "http://www.w3.org/2000/svg"}


# ---------- ユーティリティ ----------
# シーン中心オフセット（main()で計算後に設定）
CENTER_OFFSET_X = 0.0
CENTER_OFFSET_Y = 0.0


def svg_to_blender(x: float, y: float, svg_height: float) -> tuple[float, float]:
    """SVG座標 → Blender XY座標（Y反転 + 中心オフセット）"""
    bx = x * SCALE - CENTER_OFFSET_X
    by = (svg_height - y) * SCALE - CENTER_OFFSET_Y
    return bx, by


def assign_material(obj, category: str) -> None:
    """カテゴリに応じたPBRマテリアルを付与（Roughnessノイズ付き）"""
    settings = PBR_SETTINGS.get(
        category,
        {
            "base_color": (0.7, 0.7, 0.7, 1.0),
            "roughness": 0.5,
            "noise_scale": 15.0,
            "noise_mix": 0.08,
        },
    )
    mat_name = f"mat_{category}"

    # 同カテゴリのマテリアルを共有
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        # Principled BSDF（自動生成済み）を取得
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            bsdf.inputs["Base Color"].default_value = settings["base_color"]

            # Roughnessノイズ: TexCoord → NoiseTexture → MapRange → Roughness
            tex_coord = nodes.new("ShaderNodeTexCoord")
            noise = nodes.new("ShaderNodeTexNoise")
            noise.inputs["Scale"].default_value = settings["noise_scale"]
            noise.inputs["Detail"].default_value = 5.0
            noise.inputs["Roughness"].default_value = 0.5

            map_range = nodes.new("ShaderNodeMapRange")
            base_r = settings["roughness"]
            mix = settings["noise_mix"]
            map_range.inputs["From Min"].default_value = 0.0
            map_range.inputs["From Max"].default_value = 1.0
            map_range.inputs["To Min"].default_value = base_r - mix
            map_range.inputs["To Max"].default_value = base_r + mix

            links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
            links.new(noise.outputs["Fac"], map_range.inputs["Value"])
            links.new(map_range.outputs["Result"], bsdf.inputs["Roughness"])

    obj.data.materials.append(mat)


def assign_glass_material(obj) -> None:
    """ガラスマテリアルを付与（半透明、Cycles/EEVEE両対応）"""
    mat_name = "mat_glass"
    mat = bpy.data.materials.get(mat_name)
    if mat is None:
        mat = bpy.data.materials.new(name=mat_name)
        mat.use_nodes = True
        mat.blend_method = "BLEND"  # EEVEE用アルファブレンド
        mat.use_backface_culling = False

        nodes = mat.node_tree.nodes
        links = mat.node_tree.links

        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf:
            # 薄いブルーティントのガラス
            bsdf.inputs["Base Color"].default_value = (0.85, 0.92, 0.97, 1.0)
            bsdf.inputs["Roughness"].default_value = 0.05
            bsdf.inputs["Transmission Weight"].default_value = 0.85
            bsdf.inputs["IOR"].default_value = 1.45
            bsdf.inputs["Alpha"].default_value = 0.3  # EEVEE用

    obj.data.materials.append(mat)


def create_box(
    name: str,
    x: float,
    y: float,
    width: float,
    height: float,
    z_bottom: float,
    z_top: float,
    svg_height: float,
    collection,
):
    """箱型メッシュを作成"""
    # SVG rect の4隅をBlender座標に変換
    x1, y1 = svg_to_blender(x, y + height, svg_height)  # 左下(SVG) → Blender
    x2, y2 = svg_to_blender(x + width, y, svg_height)  # 右上(SVG) → Blender

    cx = (x1 + x2) / 2
    cy = (y1 + y2) / 2
    cz = (z_bottom + z_top) / 2
    sx = abs(x2 - x1)
    sy = abs(y2 - y1)
    sz = z_top - z_bottom

    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, cz))
    obj = bpy.context.active_object
    obj.name = name
    obj.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)

    # コレクションに移動
    for col in obj.users_collection:
        col.objects.unlink(obj)
    collection.objects.link(obj)

    return obj


def get_rect_center_blender(x: float, y: float, w: float, h: float, svg_height: float) -> tuple[float, float]:
    """SVG rectの中心をBlender XY座標で返す"""
    cx_svg = x + w / 2
    cy_svg = y + h / 2
    return svg_to_blender(cx_svg, cy_svg, svg_height)


# ---------- メイン処理 ----------
def main():
    # Blender の -- 以降の引数をパース
    argv = sys.argv
    if "--" in argv:
        argv = argv[argv.index("--") + 1 :]
    else:
        argv = []

    parser = argparse.ArgumentParser(description="SVG elements → Blender 3D")
    parser.add_argument("--svg", required=True, help="入力SVGパス")
    parser.add_argument("--output", required=True, help="出力.blendパス")
    args = parser.parse_args(argv)

    svg_path = Path(args.svg)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # SVG解析
    tree = ET.parse(svg_path)
    root = tree.getroot()

    vb = root.get("viewBox", "0 0 856 1740").split()
    svg_width = float(vb[2])
    svg_height = float(vb[3])
    print(f"SVG viewBox: {svg_width} x {svg_height}")

    # 全rectからシーン中心を計算
    global CENTER_OFFSET_X, CENTER_OFFSET_Y
    all_rects_for_center = []
    for group_id in ("walls", "pillars"):
        g = root.find(f'.//svg:g[@id="{group_id}"]', NS)
        if g is not None:
            for rect in g.findall("svg:rect", NS):
                rx = float(rect.get("x"))
                ry = float(rect.get("y"))
                rw = float(rect.get("width"))
                rh = float(rect.get("height"))
                all_rects_for_center.append((rx, ry, rw, rh))

    if all_rects_for_center:
        svg_min_x = min(r[0] for r in all_rects_for_center)
        svg_min_y = min(r[1] for r in all_rects_for_center)
        svg_max_x = max(r[0] + r[2] for r in all_rects_for_center)
        svg_max_y = max(r[1] + r[3] for r in all_rects_for_center)
        svg_cx = (svg_min_x + svg_max_x) / 2
        svg_cy = (svg_min_y + svg_max_y) / 2
        # Blender座標系での中心
        CENTER_OFFSET_X = svg_cx * SCALE
        CENTER_OFFSET_Y = (svg_height - svg_cy) * SCALE
        print(f"Scene center offset: ({CENTER_OFFSET_X:.2f}, {CENTER_OFFSET_Y:.2f})m")

    # シーン初期化
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0

    # コレクション作成
    collections = {}
    for col_name in ("Walls", "Pillars", "Doors", "Windows", "Lights", "Structure"):
        col = bpy.data.collections.new(col_name)
        scene.collection.children.link(col)
        collections[col_name] = col

    # ---------- 壁の生成 ----------
    walls_g = root.find('.//svg:g[@id="walls"]', NS)
    wall_objects = []
    if walls_g is not None:
        for rect in walls_g.findall("svg:rect", NS):
            rid = rect.get("id", "wall")
            x = float(rect.get("x"))
            y = float(rect.get("y"))
            w = float(rect.get("width"))
            h = float(rect.get("height"))
            label = rect.get("data-label", "")

            obj = create_box(
                name=rid,
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=0,
                z_top=WALL_HEIGHT,
                svg_height=svg_height,
                collection=collections["Walls"],
            )
            obj["data-label"] = label
            assign_material(obj, "wall")
            wall_objects.append(obj)
            print(f"  Wall: {rid} ({label})")

    print(f"Walls created: {len(wall_objects)}")

    # ---------- 柱の生成 ----------
    pillars_g = root.find('.//svg:g[@id="pillars"]', NS)
    pillar_objects = []
    if pillars_g is not None:
        for rect in pillars_g.findall("svg:rect", NS):
            rid = rect.get("id", "pillar")
            x = float(rect.get("x"))
            y = float(rect.get("y"))
            w = float(rect.get("width"))
            h = float(rect.get("height"))
            label = rect.get("data-label", "")

            obj = create_box(
                name=rid,
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=0,
                z_top=WALL_HEIGHT,
                svg_height=svg_height,
                collection=collections["Pillars"],
            )
            obj["data-label"] = label
            assign_material(obj, "pillar")
            pillar_objects.append(obj)
            print(f"  Pillar: {rid} ({label})")

    print(f"Pillars created: {len(pillar_objects)}")

    # ---------- ドアの生成（薄いパネル） ----------
    doors_g = root.find('.//svg:g[@id="doors"]', NS)
    door_objects = []
    if doors_g is not None:
        for rect in doors_g.findall("svg:rect", NS):
            rid = rect.get("id", "door")
            x = float(rect.get("x"))
            y = float(rect.get("y"))
            w = float(rect.get("width"))
            h = float(rect.get("height"))
            label = rect.get("data-label", "")

            obj = create_box(
                name=rid,
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=0,
                z_top=DOOR_HEIGHT,
                svg_height=svg_height,
                collection=collections["Doors"],
            )
            obj["data-label"] = label
            assign_material(obj, "door")
            door_objects.append(obj)
            print(f"  Door: {rid} ({label})")

    print(f"Doors created: {len(door_objects)}")

    # ---------- ドア上部の欄間壁（ドア上端〜天井の隙間を埋める） ----------
    transom_objects = []
    if doors_g is not None:
        for rect in doors_g.findall("svg:rect", NS):
            rid = rect.get("id", "door")
            x = float(rect.get("x"))
            y = float(rect.get("y"))
            w = float(rect.get("width"))
            h = float(rect.get("height"))

            obj = create_box(
                name=f"{rid}_transom",
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=DOOR_HEIGHT,
                z_top=WALL_HEIGHT,
                svg_height=svg_height,
                collection=collections["Walls"],
            )
            obj["data-label"] = f"{rid} 欄間壁"
            assign_material(obj, "transom")
            transom_objects.append(obj)

    print(f"Transoms (door): {len(transom_objects)}")

    # ---------- 窓の生成（課題1対応） ----------
    # 窓 = 窓下壁(0〜sill) + ガラスパネル(sill〜window_top) + 欄間壁(window_top〜ceiling)
    windows_g = root.find('.//svg:g[@id="windows"]', NS)
    window_objects = []
    if windows_g is not None:
        for rect in windows_g.findall("svg:rect", NS):
            rid = rect.get("id", "window")
            x = float(rect.get("x"))
            y = float(rect.get("y"))
            w = float(rect.get("width"))
            h = float(rect.get("height"))
            label = rect.get("data-label", "")

            # 窓下壁（0 〜 WINDOW_SILL_HEIGHT）
            sill_wall = create_box(
                name=f"{rid}_sill",
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=0,
                z_top=WINDOW_SILL_HEIGHT,
                svg_height=svg_height,
                collection=collections["Walls"],
            )
            sill_wall["data-label"] = f"{label} 窓下壁"
            assign_material(sill_wall, "wall")

            # ガラスパネル（WINDOW_SILL_HEIGHT 〜 WINDOW_TOP_HEIGHT）
            glass = create_box(
                name=f"{rid}_glass",
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=WINDOW_SILL_HEIGHT,
                z_top=WINDOW_TOP_HEIGHT,
                svg_height=svg_height,
                collection=collections["Windows"],
            )
            glass["data-label"] = f"{label} ガラス"
            assign_glass_material(glass)

            # 欄間壁（WINDOW_TOP_HEIGHT 〜 WALL_HEIGHT）
            transom = create_box(
                name=f"{rid}_transom",
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=WINDOW_TOP_HEIGHT,
                z_top=WALL_HEIGHT,
                svg_height=svg_height,
                collection=collections["Walls"],
            )
            transom["data-label"] = f"{label} 欄間壁"
            assign_material(transom, "transom")

            window_objects.append(glass)
            print(f"  Window: {rid} ({label}) - sill + glass + transom")

    print(f"Windows created: {len(window_objects)}")

    # ---------- ガラスドア（掃き出し窓）の生成（課題1対応） ----------
    # ガラスドア = ガラスパネル(0〜DOOR_HEIGHT) + 欄間壁(DOOR_HEIGHT〜WALL_HEIGHT)
    glass_doors_g = root.find('.//svg:g[@id="glass_doors"]', NS)
    glass_door_objects = []
    if glass_doors_g is not None:
        for rect in glass_doors_g.findall("svg:rect", NS):
            rid = rect.get("id", "glass_door")
            x = float(rect.get("x"))
            y = float(rect.get("y"))
            w = float(rect.get("width"))
            h = float(rect.get("height"))
            label = rect.get("data-label", "")

            # ガラスパネル（0 〜 DOOR_HEIGHT）
            glass = create_box(
                name=f"{rid}_glass",
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=0,
                z_top=DOOR_HEIGHT,
                svg_height=svg_height,
                collection=collections["Windows"],
            )
            glass["data-label"] = f"{label} ガラス"
            assign_glass_material(glass)

            # 欄間壁（DOOR_HEIGHT 〜 WALL_HEIGHT）
            transom = create_box(
                name=f"{rid}_transom",
                x=x,
                y=y,
                width=w,
                height=h,
                z_bottom=DOOR_HEIGHT,
                z_top=WALL_HEIGHT,
                svg_height=svg_height,
                collection=collections["Walls"],
            )
            transom["data-label"] = f"{label} 欄間壁"
            assign_material(transom, "transom")

            glass_door_objects.append(glass)
            print(f"  Glass door: {rid} ({label}) - glass + transom")

    print(f"Glass doors created: {len(glass_door_objects)}")

    # ---------- 床の生成 ----------
    all_wall_rects = []
    if walls_g is not None:
        for rect in walls_g.findall("svg:rect", NS):
            x = float(rect.get("x"))
            y = float(rect.get("y"))
            w = float(rect.get("width"))
            h = float(rect.get("height"))
            all_wall_rects.append((x, y, w, h))

    if all_wall_rects:
        min_x = min(r[0] for r in all_wall_rects)
        min_y = min(r[1] for r in all_wall_rects)
        max_x = max(r[0] + r[2] for r in all_wall_rects)
        max_y = max(r[1] + r[3] for r in all_wall_rects)

        floor = create_box(
            name="Floor",
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y,
            z_bottom=-FLOOR_THICKNESS,
            z_top=0,
            svg_height=svg_height,
            collection=collections["Structure"],
        )
        assign_material(floor, "floor")
        print(f"\nFloor created: {(max_x - min_x) * SCALE:.2f}m x {(max_y - min_y) * SCALE:.2f}m")

    # ---------- 天井の生成 ----------
    if all_wall_rects:
        ceiling = create_box(
            name="Ceiling",
            x=min_x,
            y=min_y,
            width=max_x - min_x,
            height=max_y - min_y,
            z_bottom=WALL_HEIGHT,
            z_top=WALL_HEIGHT + FLOOR_THICKNESS,
            svg_height=svg_height,
            collection=collections["Structure"],
        )
        assign_material(ceiling, "ceiling")
        ceiling.hide_viewport = True
        ceiling.hide_render = True
        print(f"Ceiling created at z={WALL_HEIGHT}m (hidden by default)")

    # ---------- 室内エリアライト配置（課題1対応） ----------
    # 建物全体を均等にカバーするグリッド配置
    if all_wall_rects:
        # 建物範囲をBlender座標で取得
        bld_x1, bld_y1 = svg_to_blender(min_x, max_y, svg_height)
        bld_x2, bld_y2 = svg_to_blender(max_x, min_y, svg_height)
        bld_min_x = min(bld_x1, bld_x2)
        bld_max_x = max(bld_x1, bld_x2)
        bld_min_y = min(bld_y1, bld_y2)
        bld_max_y = max(bld_y1, bld_y2)

        # 3m間隔でグリッド配置
        grid_step = 3.0
        light_z = WALL_HEIGHT - 0.1  # 天井直下
        light_count = 0

        x_pos = bld_min_x + grid_step / 2
        while x_pos < bld_max_x:
            y_pos = bld_min_y + grid_step / 2
            while y_pos < bld_max_y:
                light_data = bpy.data.lights.new(name=f"AreaLight_{light_count:03d}", type="AREA")
                light_data.energy = 80  # ワット
                light_data.size = 1.5  # 1.5m角
                light_data.color = (1.0, 0.95, 0.90)  # 暖白色

                light_obj = bpy.data.objects.new(name=f"AreaLight_{light_count:03d}", object_data=light_data)
                light_obj.location = (x_pos, y_pos, light_z)
                # 下向きに照射（デフォルトで-Z方向）
                collections["Lights"].objects.link(light_obj)
                light_count += 1
                y_pos += grid_step
            x_pos += grid_step

        print(f"\nArea lights created: {light_count} (grid {grid_step}m, {light_data.energy}W each)")

    # ---------- 保存 ----------
    bpy.ops.wm.save_as_mainfile(filepath=str(output_path.resolve()))
    print(f"\nSaved: {output_path}")
    print(f"Total objects: {len(bpy.data.objects)}")


if __name__ == "__main__":
    main()
