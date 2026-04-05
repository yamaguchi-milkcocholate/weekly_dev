---
name: floor_plan_to_video_sub_scene
description: 建築要素SVG（壁・柱・ドア・窓のrect要素）をBlender Pythonで読み込み、PBRマテリアル付きの3Dインテリアシーン（scene.blend）を生成する。SVGからBlender 3Dシーンへの変換、建築要素の3D化、間取りSVGから3Dモデル生成、壁・ドア・窓の3Dメッシュ化に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <input_elements_svg> <output_dir>
---

# floor_plan_to_video_sub_scene

建築要素SVG（`floor_plan_to_video_sub_extract`スキルの出力）をBlender 3Dシーンに変換するスキル。壁・柱・ドア・窓・ガラスドアのrect要素を読み取り、PBRマテリアル付きの3Dメッシュとして生成する。

**対応パイプラインステップ**: Floor Plan to Video ステップ2
**入力元**: `floor_plan_to_video_sub_extract` スキル（ステップ1）の出力
**出力先**: `floor_plan_to_video_sub_placement` スキル（ステップ5）、`floor_plan_to_video_sub_camera`（ステップ6）の入力

## 前提条件

- `blender-python`スキルを参照済みであること（Blender CLIは必ず`scripts/run_blender.sh`経由）
- `/Applications/Blender.app` がインストールされていること（Blender 5.0+）

## 入力ファイル

| ファイル | 形式 | 説明 |
|---------|------|------|
| 建築要素SVG | `.svg` | `floor_plan_to_video_sub_extract`が出力した壁・柱等のrect要素を含むSVG |

### SVG構造の前提

```xml
<svg viewBox="0 0 {width} {height}">
  <g id="walls">       <rect id="wall_001" x="..." y="..." width="..." height="..." data-label="北側外壁"/> ... </g>
  <g id="pillars">     <rect .../> ... </g>
  <g id="doors">       <rect .../> ... </g>
  <g id="windows">     <rect .../> ... </g>
  <g id="glass_doors"> <rect .../> ... </g>
</svg>
```

- 座標系: SVG標準（左上原点、Y軸下向き、単位=ピクセル）
- 各`<rect>`に `id`, `x`, `y`, `width`, `height`, `data-label` 属性が必要
- グループが存在しない場合はスキップされる（エラーにならない）

## 出力ファイル

| ファイル | 形式 | 説明 |
|---------|------|------|
| `<output_dir>/scene.blend` | `.blend` | Blender 5.0+ シーンファイル |

### scene.blend の構成

| Collection | 内容 | 備考 |
|-----------|------|------|
| Walls | 壁メッシュ + ドア/窓上部のtransom壁 | 高さ2.4m |
| Pillars | 柱メッシュ | 高さ2.4m |
| Doors | ドアパネル（2.0m高） | 上部にtransom壁（0.4m） |
| Windows | ガラスパネル（窓・ガラスドア） | 腰壁0.8m、ガラス1.2m |
| Lights | エリアライト（3mグリッド配置） | 80W、暖白色 |
| Structure | 床スラブ + 天井スラブ | 天井は非表示 |

## 実行方法

```bash
scripts/run_blender.sh \
  --background \
  --python .claude/skills/floor_plan_to_video_sub_scene/scripts/svg_to_blender.py \
  -- \
  --svg {input_elements_svg} \
  --output {output_dir}/scene.blend
```

- `scripts/run_blender.sh` 経由で実行する（`blender`コマンドの直接呼び出し禁止）
- `--background` でヘッドレスモード
- `--` の後にスクリプト固有引数を渡す

## 処理フロー

1. **SVG解析**: viewBoxからキャンバスサイズ取得 → 各グループのrect要素を抽出
2. **シーン初期化**: Factory defaultsで空シーン → 単位系METRIC → 6つのCollection作成
3. **座標系変換**: 壁・柱のバウンディングボックスから建物中心を計算 → SVG→Blender座標変換（SCALE=0.01、1px=1cm）
4. **3Dメッシュ生成**:
   - 壁: rect → 0〜2.4mの直方体
   - 柱: rect → 0〜2.4mの直方体
   - ドア: rect → パネル(0〜2.0m) + transom壁(2.0〜2.4m)
   - 窓: rect → 腰壁(0〜0.8m) + ガラス(0.8〜2.0m) + transom壁(2.0〜2.4m)
   - ガラスドア: rect → ガラス(0〜2.0m) + transom壁(2.0〜2.4m)
5. **マテリアル適用**: Principled BSDF + NoiseTextureによるPBRマテリアル
6. **床・天井・照明**: 床（建物外周 × 0.05m厚）、天井（非表示）、エリアライト（3mグリッド、z=2.3m）
7. **保存**: `.blend`ファイル出力

## マテリアル仕様

| マテリアル | Base Color (RGB) | Roughness | 用途 |
|-----------|-----------------|-----------|------|
| mat_wall | (0.92, 0.92, 0.90) | 0.7 | 壁 |
| mat_pillar | (0.75, 0.75, 0.73) | 0.8 | 柱 |
| mat_door | (0.40, 0.28, 0.15) | 0.45 | ドア |
| mat_transom | (0.92, 0.92, 0.90) | 0.7 | ドア/窓上部壁 |
| mat_floor | (0.55, 0.45, 0.32) | 0.55 | 床 |
| mat_ceiling | (0.95, 0.95, 0.93) | 0.8 | 天井 |
| mat_window_frame | (0.85, 0.85, 0.83) | 0.3 | 窓枠 |
| mat_glass | (0.85, 0.92, 0.97) | 0.05 | ガラス（Transmission=0.85, IOR=1.45） |

## 実行後の確認

実行完了後、Blender UIでscene.blendを開いて以下を確認する:
- 壁の隙間がないか
- ドア・窓の位置が正しいか
- マテリアルの割り当てが正しいか
- ライトの配置が均等か
