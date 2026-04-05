# SVG→Blender 3Dシーン変換 設計書

## 1. 概要

建築要素SVG（壁・柱・ドア・窓のrect要素）をBlender Pythonで読み込み、PBRマテリアル付きの3Dインテリアシーン（scene.blend）を生成するスキル。

**対応パイプラインステップ**: Floor Plan to Video ステップ2
**入力元**: `floor_plan_to_video_sub_extract` スキル（ステップ1）の出力
**出力先**: `floor_plan_to_video_sub_placement` スキル（ステップ5）、`floor_plan_to_video_sub_camera`（ステップ6）の入力

### 参照PoC

- `poc/3dcg_poc0_b/scripts/svg_to_blender.py`

## 2. 入出力

### 入力

| 項目 | 形式 | 説明 |
|------|------|------|
| 建築要素SVG | `.svg` | `floor_plan_to_video_sub_elements` が出力した壁・柱等のrect要素を含むSVG |

#### SVG構造の前提

```xml
<svg viewBox="0 0 {width} {height}">
  <g id="walls">    <rect id="wall_001" x="..." y="..." width="..." height="..." data-label="北側外壁"/> ... </g>
  <g id="pillars">  <rect .../> ... </g>
  <g id="doors">    <rect .../> ... </g>
  <g id="windows">  <rect .../> ... </g>
  <g id="glass_doors"> <rect .../> ... </g>
  <g id="fixtures"> <rect .../> ... </g>  <!-- 現状未使用 -->
</svg>
```

- 座標系: SVG標準（左上原点、Y軸下向き、単位=ピクセル）
- 各`<rect>`に `id`, `x`, `y`, `width`, `height`, `data-label` 属性が必要

### 出力

| 項目 | 形式 | 説明 |
|------|------|------|
| scene.blend | `.blend` | Blender 5.0+ シーンファイル |

#### scene.blend の構成

| Collection | 内容 | 備考 |
|-----------|------|------|
| Walls | 壁メッシュ + ドア/窓上部のtransom壁 | 高さ2.4m |
| Pillars | 柱メッシュ | 高さ2.4m |
| Doors | ドアパネル（2.0m高） | 上部にtransom壁（0.4m） |
| Windows | ガラスパネル + 腰壁 + transom壁 | 腰壁0.8m、ガラス1.2m |
| Lights | エリアライト（3mグリッド配置） | 80W、暖白色 |
| Structure | 床スラブ + 天井スラブ | 天井は非表示 |

## 3. 処理フロー

```
[1] SVG解析
    ├─ viewBox からキャンバスサイズ取得
    └─ 各グループ（walls, pillars, doors, windows, glass_doors）のrect要素を抽出

[2] Blenderシーン初期化
    ├─ Factory defaults で空シーン作成
    ├─ 単位系: METRIC（メートル）
    └─ 6つのCollection作成（Walls, Pillars, Doors, Windows, Lights, Structure）

[3] 座標系変換
    ├─ 全壁・柱のバウンディングボックスから建物中心を計算
    ├─ SVG→Blender座標変換:
    │   blender_x = (svg_x × SCALE) - CENTER_OFFSET_X
    │   blender_y = ((svg_height - svg_y) × SCALE) - CENTER_OFFSET_Y
    └─ SCALE = 0.01（1ピクセル = 1cm = 0.01m）

[4] 3Dメッシュ生成
    ├─ 壁: rect → 0〜2.4m の直方体
    ├─ 柱: rect → 0〜2.4m の直方体
    ├─ ドア: rect → パネル(0〜2.0m) + transom壁(2.0〜2.4m)
    ├─ 窓: rect → 腰壁(0〜0.8m) + ガラス(0.8〜2.0m) + transom壁(2.0〜2.4m)
    └─ ガラスドア: rect → ガラス(0〜2.0m) + transom壁(2.0〜2.4m)

[5] マテリアル適用（PBR）
    └─ Principled BSDF + NoiseTexture による微細な表面変化

[6] 床・天井・照明の生成
    ├─ 床: 建物外周 × 0.05m厚
    ├─ 天井: 建物外周 × 0.02m厚（非表示）
    └─ エリアライト: 3mグリッド、z=2.3m

[7] ファイル保存
    └─ bpy.ops.wm.save_as_mainfile()
```

## 4. マテリアル仕様

| マテリアル | Base Color (RGB) | Roughness | Noise Scale | 用途 |
|-----------|-----------------|-----------|-------------|------|
| mat_wall | (0.92, 0.92, 0.90) | 0.7 | 15.0 | 壁 |
| mat_pillar | (0.75, 0.75, 0.73) | 0.8 | 20.0 | 柱 |
| mat_door | (0.40, 0.28, 0.15) | 0.45 | 30.0 | ドア |
| mat_transom | (0.92, 0.92, 0.90) | 0.7 | 15.0 | ドア/窓上部壁 |
| mat_floor | (0.55, 0.45, 0.32) | 0.55 | 25.0 | 床 |
| mat_ceiling | (0.95, 0.95, 0.93) | 0.8 | 10.0 | 天井 |
| mat_window_frame | (0.85, 0.85, 0.83) | 0.3 | 10.0 | 窓枠 |
| mat_glass | (0.85, 0.92, 0.97) | 0.05 | - | ガラス（Transmission=0.85, IOR=1.45） |

## 5. 定数

```python
SCALE = 0.01              # 1 SVG px = 0.01m = 1cm
WALL_HEIGHT = 2.4         # 床〜天井（m）
DOOR_HEIGHT = 2.0         # ドアパネル高（m）
WINDOW_SILL_HEIGHT = 0.8  # 窓の腰壁高（m）
WINDOW_TOP_HEIGHT = 2.0   # 窓の上端（m）
FLOOR_THICKNESS = 0.05    # 床スラブ厚（m）
LIGHT_GRID_STEP = 3.0     # ライト配置間隔（m）
LIGHT_ENERGY = 80         # ライト出力（W）
```

## 6. 実行方法

```bash
scripts/run_blender.sh \
  --background \
  --python scripts/svg_to_blender.py \
  -- \
  --svg {input_elements_svg} \
  --output {output_scene_blend}
```

- `scripts/run_blender.sh` 経由で実行する（Blender bundled Python解決のため）
- `--background` でヘッドレスモード

## 7. 依存関係

| コンポーネント | バージョン | 用途 |
|-------------|----------|------|
| Blender | 5.0+ | 3Dシーン生成 |
| Python (Blender bundled) | 3.11+ | bpy API |
| xml.etree.ElementTree | stdlib | SVG解析 |

## 8. エラーハンドリング

| 状況 | 対処 |
|------|------|
| SVGファイル不在 | FileNotFoundError |
| グループID欠損（例: windowsなし） | スキップ（警告出力） |
| rect属性不正 | ValueError |
| viewBox属性なし | フォールバックデフォルト使用 |
| 出力ディレクトリなし | 自動作成 |

## 9. 手動ステップ

- **実行前**: 入力SVGが `floor_plan_to_video_sub_elements` の出力であることを確認
- **実行後**: Blender UIで開いて視覚的に検証（壁の隙間、ドア位置等）
- マテリアル色の微調整が必要な場合はBlender UI上で行う
