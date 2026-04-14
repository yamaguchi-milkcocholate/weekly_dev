---
name: floor_plan_to_video_sub_render
description: 確定した配置座標でBlenderレンダリングを実行し、3D視点で配置を確認する。layout_proposal.jsonの配置結果をBlenderで3Dレンダリングしたい、家具配置の3D確認、GLBモデルの配置可視化に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <出力ディレクトリ>
allowed-tools: Bash(scripts/run_blender.sh *), Bash(uv run *), Bash(mkdir *), Bash(ls *)
---

# floor_plan_to_video_sub_render

確定した家具配置座標をBlenderで3Dレンダリングし、視覚的に配置を確認するスキル。

## 前提条件

- `blender-python`スキルを参照済みであること
- `scripts/run_blender.sh` が存在すること
- `/Applications/Blender.app` がインストールされていること

## 入力

以下のファイルは出力ディレクトリ（引数で指定）内に配置:

- `scene.blend` — 壁3Dモデル（sub_sceneの出力）
- `layout_proposal.json` — 確定した配置座標（floor_plan_to_video_sub_refineスキルの出力）
- `assets/objects/*.glb` — 家具の3Dモデル（sub_glbの出力）
- `assets.json` — 家具サイズ情報（スケーリング計算に使用）

## 出力

- レンダリング画像（PNG）— 複数アングル

---

## 実行手順

### Step 1: レンダリングスクリプトの作成

以下の処理を行うPythonスクリプトを作成する:

1. **ベースシーン読み込み**: .blendファイルを開く
2. **天井の非表示**: 天井オブジェクト（例: `平面.033`）の`hide_render = True`
3. **GLBインポート**: 各家具のGLBファイルをインポート
4. **配置**: layout_proposal.jsonの座標に配置
5. **カメラ設定**: 複数アングルを設定
6. **レンダリング**: 各アングルでレンダリング実行

### Step 2: GLBの配置

layout_proposal.jsonの各家具について:

```python
import bpy
import json

# GLBインポート
bpy.ops.import_scene.gltf(filepath=glb_path)
imported = bpy.context.selected_objects[0]

# 座標設定（Blender座標系のまま）
imported.location.x = center_x
imported.location.y = center_y
imported.location.z = 0  # 床面

# 回転（front_dirに応じて）
import math
rotation_map = {"N": 0, "E": math.pi/2, "S": math.pi, "W": -math.pi/2}
imported.rotation_euler.z = rotation_map[front_dir]
```

### Step 3: GLBスケーリング

**既知の問題**: GLBモデルのサイズがassets.jsonの実寸と異なる場合がある。

スケーリングの手順:
1. インポート後のGLBのバウンディングボックスサイズを取得
2. assets.jsonの実寸と比較
3. 均一スケールを適用: `scale = max(実寸) / max(GLB寸法)`

**注意**: `max(実寸) / max(GLB寸法)` の均一スケールは、GLBの軸方向と実寸の対応が不明なため不正確な場合がある。各軸ごとにスケールを合わせるか、GLBの軸方向を事前に確認すること。

### Step 4: カメラ設定

推奨アングル:
1. **俯瞰（トップダウン）**: 全体レイアウトの確認
2. **パースペクティブ**: 部屋の入口からの視点
3. **生活視点**: ベッドから見た寝室、デスクからの視点等

### Step 5: レンダリング実行

```bash
scripts/run_blender.sh --background <.blendファイル> --python render_script.py
```

**Blender 5.0.1の注意点:**
- レンダリングエンジンのenum名: `BLENDER_EEVEE`
- `Material.use_nodes`は非推奨。`diffuse_color`を直接設定

### Step 6: 結果確認

レンダリング画像を確認し、問題があればfloor_plan_to_video_sub_refineスキルに戻ってplacement_plan.jsonを修正する。

確認ポイント:
- 家具が正しい位置にあるか
- 家具の向きが正しいか（front/backの方向）
- 家具同士の間隔が適切か
- 動線が確保されているか
- 全体的な見た目のバランス
