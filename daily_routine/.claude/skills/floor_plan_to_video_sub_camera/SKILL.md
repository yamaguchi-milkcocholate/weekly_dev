---
name: floor_plan_to_video_sub_camera
description: 任意のscene.blendからV2V入力用カメラカット動画を生成する3フェーズの対話的パイプライン。空間分析+カット設計→Cyclesレンダリング→MP4動画化を対話的にガイドする。カメラカット動画、V2V入力動画、ウォークスルー動画、カメラパス動画、Cyclesレンダリング動画、カメラアニメーション動画に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <workdir>
---

# floor_plan_to_video_sub_camera

任意のscene.blendから、V2V（Kling等）入力に最適な5秒カット動画群を生成する対話的パイプライン。各カットは始点→終点カメラのsmooth_step補間で150フレーム（5秒 × 30fps）をCyclesレンダリングし、MP4に変換する。

## ディレクトリ規約

```
<workdir>/
├── input/
│   └── scene.blend          # 入力シーン（ユーザーが配置）
└── output/                  # 全出力先（スキルが生成）
    ├── room_bounds.json
    ├── overhead.png
    ├── camera_paths.drawio
    ├── cuts.json
    ├── tmp/
    │   ├── scene_cuts.blend
    │   └── scene_animation.blend
    └── renders/
        ├── {cut_name}/      # 連番PNG
        └── {cut_name}.mp4   # MP4動画
```

## 前提条件

- `blender-python`スキルを参照済みであること（Blender CLIは必ず`scripts/run_blender.sh`経由）
- `/Applications/Blender.app` がインストールされていること
- `ffmpeg` がインストールされていること
- `<workdir>/input/scene.blend` が存在すること（Walls/Structure等のコレクション）

## 処理フロー

```
Phase 1: 空間分析 + カット設計
    1a. extract_room_bounds.py → room_bounds.json
    1b. render_overhead.py → overhead.png
    1c. generate_drawio.py → camera_paths.drawio
    1d. >>> ユーザー確認 <<< draw.ioでパス描画 or 口頭指示
    1e. Claudeがcuts.jsonを生成
    1f. place_cut_cameras.py → scene_cuts.blend
    1g. >>> ユーザー確認 <<< Blenderでカメラ調整
    1h. Blenderから座標抽出 → cuts.json更新
    1i. setup_cut_animation.py → scene_animation.blend
    1j. >>> ユーザー確認 <<< タイムラインで動き確認
    ↓
Phase 2: Cyclesレンダリング
    2a. >>> ユーザー確認 <<< レンダリング設定確認
    2b. render_cuts.py → renders/{cut_name}/*.png
    ↓
Phase 3: 動画化
    3a. ffmpeg → renders/{cut_name}.mp4
    3b. 出力パスを報告
```

---

## Phase 1: 空間分析 + カット設計

### 1a. 空間構造を抽出

```bash
scripts/run_blender.sh --background <workdir>/input/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_camera/scripts/extract_room_bounds.py -- \
  <workdir>/output/room_bounds.json
```

出力: `room_bounds.json`（壁・ドア・窓の座標、シーン境界）

### 1b. 俯瞰画像を生成

```bash
scripts/run_blender.sh --background <workdir>/input/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_camera/scripts/render_overhead.py -- \
  --output <workdir>/output/overhead.png \
  --room-bounds <workdir>/output/room_bounds.json \
  --resolution 1920
```

### 1c. draw.ioテンプレートを生成

俯瞰画像を背景に埋め込んだ `.drawio` ファイルを生成する。ユーザーがdraw.io上で矢印を描画してカメラパスを指示できるようにする。

```bash
uv run python .claude/skills/floor_plan_to_video_sub_camera/scripts/generate_drawio.py \
  --image <workdir>/output/overhead.png \
  --output <workdir>/output/camera_paths.drawio
```

### 1d. ユーザーにパス指示を依頼

ユーザーに以下を案内する:

> `<workdir>/output/camera_paths.drawio` をdraw.ioで開いて��ださい。
> 俯瞰画像の上にカメラパスを矢印で描画してください。
> - 矢印の線 = カメラの進行方向
> - 別色の矢印 = カメラの向き（進行方向と異なる場合）
> 描画が完了したら、draw.ioの画像またはスクリーンショットを共有してください。

口頭指示（「玄関から廊下をドリーイン」等）でも可。

### 1e. cuts.jsonを生成

ユーザーの指示を元にcuts.jsonを作成する。各カットの設計ガイド:

- **ドリーイン**: 始点→終点で0.5-2m直進。カメラ向きは進行方向と一致
- **トラッキング**: 始点→終点で横移動。カメラ向きは進行方向と異なる（例: 横移動しながら南を見る）
- **スイープ**: 始点→終点で斜め移動 + カメラ回転。rotation_degが始点と終点で変化
- **ズームアウト**: 始点(低高度)→終点(高高度)で上昇。レンズは同一、高さで画角変化
- **パン**: 始点→終点で位置ほぼ同じ、rotation_degのみ変化

cuts.jsonフォーマット:
```json
[
  {
    "name": "C1_entrance_dolly",
    "description": "玄関→廊下ドリーイン",
    "start": { "location": [-1.0, 6.4, 1.4], "rotation_deg": [84.0, 0.0, 180.0], "lens": 24.0 },
    "end":   { "location": [-1.4, 1.4, 1.6], "rotation_deg": [79.0, 0.0, 178.0], "lens": 24.0 },
    "frames": 150
  }
]
```

### 1f. カットカメラをBlenderに配置

```bash
scripts/run_blender.sh --background <workdir>/input/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_camera/scripts/place_cut_cameras.py -- \
  --cuts <workdir>/output/cuts.json \
  --save <workdir>/output/tmp/scene_cuts.blend
```

### 1g. ユーザー確認

> `<workdir>/output/tmp/scene_cuts.blend` をBlenderで開いてください。
> 「CutCameras」コレクションに始点(`_s`)・終点(`_e`)カメラがあります。
> 各カメラを選択して `Numpad 0` でビューを確認し、調整してください。
> 調整が完了したらお知らせください。

### 1h. 調整後の座標を抽出してcuts.json更新

```bash
scripts/run_blender.sh --background <workdir>/output/tmp/scene_cuts.blend \
  --python-expr "
import bpy, json, math
col = bpy.data.collections.get('CutCameras')
cameras = {}
for obj in sorted(col.objects, key=lambda o: o.name):
    if obj.type == 'CAMERA':
        cameras[obj.name] = {
            'location': [round(v, 3) for v in obj.location],
            'rotation_deg': [round(math.degrees(r), 1) for r in obj.rotation_euler],
            'lens': round(obj.data.lens, 1),
        }
print(json.dumps(cameras, indent=2, ensure_ascii=False))
"
```

出力されたカメラ座標でcuts.jsonを更新する。`{name}_s`が始点、`{name}_e`が終点。

### 1i. アニメーション設定

```bash
scripts/run_blender.sh --background <workdir>/input/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_camera/scripts/setup_cut_animation.py -- \
  --cuts <workdir>/output/cuts.json \
  --save <workdir>/output/tmp/scene_animation.blend
```

### 1j. ユーザー確認

> `<workdir>/output/tmp/scene_animation.blend` をBlenderで開いてください。
> タイムラインをスクラブ（またはスペースで再生）してカメラの動きを確認してください。
> タイムラインマーカーでカットごとにカメラが自動切替されます。
> 問題がなければ「OK」と伝えてください。

---

## Phase 2: Cyclesレンダリング

### 2a. レンダリング設定を確認

レンダリング前にユーザーにプリセットを確認する:

| プリセット | サンプル | 解像度 | 1フレーム | 4カット見積もり |
|---|---|---|---|---|
| **fast** | 32 | 480×270 | ~0.6秒 | ~6分 |
| quality | 64 | 960×540 | ~2.6秒 | ~26分 |
| production | 128 | 1920×1080 | 要計測 | 要計測 |

特に指定がなければ`fast`を使用する。

### 2b. レンダリング実行

```bash
scripts/run_blender.sh --background <workdir>/input/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_camera/scripts/render_cuts.py -- \
  --cuts <workdir>/output/cuts.json \
  --output-dir <workdir>/output/renders \
  --samples <samples> --width <width> --height <height>
```

特定カットのみ再レンダリングする場合:
```bash
  --cut <cut_name>
```

---

## Phase 3: 動画化

### 3a. ffmpegでMP4変換

各カットの連番PNGを30fps MP4に変換する:

```bash
for d in <workdir>/output/renders/*/; do
  name=$(basename "$d")
  ffmpeg -y -framerate 30 -i "${d}%04d.png" \
    -c:v libx264 -pix_fmt yuv420p -crf 18 \
    "<workdir>/output/renders/${name}.mp4"
done
```

### 3b. 完了報告

生成されたMP4ファイルのパスをユーザーに報告する。

---

## トラブルシューティング

- **俯瞰画像が暗い**: render_overhead.pyは天井を自動非表示にするが、検出に失敗する場合がある。`--room-bounds`を指定するか、scene.blendの天井オブジェクト名を確認
- **レンダリングが真っ黒**: Cyclesではroom内の照明が必要。render_cuts.pyはHDRI環境照明を自動設定するが、閉じた部屋では光が届かない場合がある
- **GPU初回が遅い**: Metalカーネルコンパイルで初回~80秒かかる。2フレーム目以降は高速
- **壁の中にカメラ**: room_bounds.jsonの壁座標を確認し、壁から0.3m以上離れた位置に配置
- **カメラの回転が不自然**: shortest_angle_lerp補間のため、始点と終点のrotation_degの差が180°を超えないように設計する
