---
name: floor_plan_to_video
description: 間取りPNG画像からフォトリアルなインテリアウォークスルー動画を生成する7ステップパイプラインのマスタースキル。workdirを指定して実行する。間取り動画化、Floor Plan to Video、インテリアウォークスルー、間取りから動画、間取りを3D化して動画にするタスクで必ずこのスキルを参照すること。
argument-hint: <workdir>
allowed-tools: Bash(uv run *), Bash(mkdir *), Bash(cp *), Bash(ls *), Bash(rm *)
---

# Floor Plan to Video

間取りPNG画像 → フォトリアルなインテリアウォークスルー動画を生成する7ステップパイプライン。

## 前提条件

- ImageMagick, potrace（Step 1）
- Blender 5.0+, `scripts/run_blender.sh`（Step 2, 5, 6）
- Tripo AI APIキー: `DAILY_ROUTINE_API_KEY_TRIPO`（Step 3）
- Kling APIキー: `DAILY_ROUTINE_API_KEY_KLING_AK`, `DAILY_ROUTINE_API_KEY_KLING_SK`（Step 7）
- gcloud CLI（Step 7: GCSアップロード用）

## workdir構造

ユーザーは `workdir/input/` にファイルを配置してからパイプラインを開始する。

```
workdir/
├── input/
│   ├── floor_plan.png              ← 間取り画像（必須）
│   └── assets/                     ← 家具画像（Step 3で使用）
│       ├── chair/front.png
│       └── desk/front.png
├── output/                         ← 全ステップの成果物
├── work/                           ← 中間ファイル
└── final/                          ← 最終成果物（フォトリアル動画）
```

## パイプライン全体図

```
Step 1: PNG → SVG → 要素rect + walls.json          [自動]
    │
    ├──→ Step 2: 要素SVG → scene.blend（壁3D）      [自動] ─┐
    │                                                       ├─→ Step 5
    └──→ Step 3: 家具画像 → GLB                     [自動] ─┘
    │
Step 4: レイアウト設計（対話ループ）                 [対話]
    │   4a: drawioアノテーション
    │   4b: 家具定義
    │   4c: リファレンス調査（任意）
    │   4d: 配置refineループ
    │
Step 5: 家具配置 → scene.blend（家具込み）           [自動]
    │
Step 6: カメラカット動画レンダリング                 [対話]
    │
Step 7: V2V フォトリアル動画化                      [対話]
```

---

## Step 0: 状態確認

workdir内のファイル存在で現在のステップを判定する。途中再開時は完了済みステップをスキップする。

```
チェック対象 → 判定:
output/{stem}_elements.svg + output/walls.json       → Step 1 完了
output/scene.blend                                   → Step 2 完了
output/assets/objects/*.glb（1つ以上）                → Step 3 完了
output/layout_proposal.json                          → Step 4 完了
output/placement/scene.blend                         → Step 5 完了
work/camera/output/renders/*.mp4（1つ以上）           → Step 6 完了
final/*.mp4（1つ以上）                                → Step 7 完了
```

判定結果をユーザーに報告する:

```
=== Floor Plan to Video パイプライン状態 ===
workdir: {workdir}

✓ Step 1: 間取り抽出（{stem}_elements.svg, walls.json）
✓ Step 2: 3Dシーン生成（scene.blend）
✓ Step 3: 家具GLB生成（{N}個）
✗ Step 4: レイアウト設計
✗ Step 5: 家具配置
✗ Step 6: カメラカット動画
✗ Step 7: フォトリアル動画化

→ 次: Step 4（レイアウト設計）に進みます
```

---

## Step 1: 間取り抽出

PNG間取り画像から壁・柱の建築要素rectを持つSVGと、壁座標データ（walls.json）を生成する。

```
/floor_plan_to_video_sub_extract {workdir}
```

入力: `{workdir}/input/floor_plan.png`
出力:
- `{workdir}/output/{stem}_floor_plan.svg` — クリーンSVG
- `{workdir}/output/{stem}_elements.svg` — 建築要素rect SVG
- `{workdir}/output/walls.json` — 壁座標データ
- `{workdir}/output/floor_plan_meta.json` — SVG座標メタデータ

完了確認: `output/{stem}_elements.svg` と `output/walls.json` が存在する。

---

## Step 2 + Step 3: 3Dシーン生成 + 家具GLB生成

Step 2とStep 3は独立しているため並列実行できる。

### Step 2: SVG → Blender 3Dシーン

建築要素SVGからPBRマテリアル付きの3Dインテリアシーンを生成する。

```
/floor_plan_to_video_sub_scene {workdir}/output/{stem}_elements.svg {workdir}/output/
```

入力: `output/{stem}_elements.svg`
出力: `output/scene.blend`

### Step 3: 家具画像 → GLBモデル

家具の画像をTripo AI APIで3Dモデルに変換する。`input/assets/` にオブジェクト別ディレクトリがない場合はスキップする。

```
uv run python .claude/skills/floor_plan_to_video_sub_glb/scripts/image_to_3d.py \
  {workdir}/input/assets/ --output-dir {workdir}/output/assets/objects/
```

入力: `input/assets/{object_name}/front.png` 等
出力: `output/assets/objects/{object_name}.glb`

完了確認: `output/scene.blend` が存在し、GLBファイルが1つ以上生成されている（または`input/assets/`が空でスキップ）。

---

## Step 4: レイアウト設計（対話ループ）

4つのサブステップで家具の配置計画を作成する。対話的に進行する。

### Step 4a: 空間アノテーション

drawioテンプレートを生成し、ユーザーが部屋・設備を定義した後、実座標データに変換する。

```
/floor_plan_to_video_sub_annotate {workdir}/output/
```

1. テンプレート生成 → `output/floor_plan_rooms.drawio` をユーザーに渡す
2. ユーザーがdrawioで部屋・ドア・窓・設備・配置不可領域を描く
3. 統合実行:

```
/floor_plan_to_video_sub_annotate {workdir}/output/ integrate
```

出力: `output/room_info.json`, `output/floor_plan_complete.svg`

### Step 4b: 家具アセット定義

ユーザーと対話して家具情報と生活シナリオを定義する。

```
/floor_plan_to_video_sub_assets {workdir}/output/
```

出力: `output/assets.json`

### Step 4c: リファレンス調査（任意）

レイアウト事例を調査し、スコアリング基準を生成する。スキップ可能。

```
/floor_plan_to_video_sub_research {workdir}/output/
```

出力: `output/scoring_criteria.json`, `output/layout_design_principles.md`

### Step 4d: 配置refineループ

家具配置の座標を計算し、配置エンジンで検証するループを実行する。

```
/floor_plan_to_video_sub_refine {workdir}/output/
```

出力: `output/placement_plan.json`, `output/layout_proposal.json`, `output/layout_proposal.svg`

完了確認: `output/layout_proposal.json` が存在する。

---

## Step 5: 家具配置

layout_proposal.jsonの座標に従い、GLBアセットをBlenderシーンに配置する。

```
/floor_plan_to_video_sub_placement {workdir}/output/ {workdir}/output/placement/
```

入力:
- `output/layout_proposal.json` — 配置座標
- `output/assets.json` — 家具定義
- `output/scene.blend` — 壁3Dモデル（Step 2の出力）
- `output/assets/objects/*.glb` — 家具GLB（Step 3の出力）

出力:
- `output/placement/scene.blend` — 家具配置済みシーン
- `output/placement/placement_report.json`

完了確認: `output/placement/scene.blend` が存在する。

---

## Step 6: カメラカット動画レンダリング

家具配置済みscene.blendからカメラカット動画を生成する。カット設計はユーザーと対話的に行う。

### パス準備

```bash
mkdir -p {workdir}/work/camera/input
cp {workdir}/output/placement/scene.blend {workdir}/work/camera/input/scene.blend
```

### 実行

```
/floor_plan_to_video_sub_camera {workdir}/work/camera/
```

出力: `work/camera/output/renders/{cut_name}.mp4`

完了確認: `work/camera/output/renders/` に `.mp4` ファイルが1つ以上存在する。

---

## Step 7: V2V フォトリアル動画化

カメラカット動画をKling V3 Omni V2Vでフォトリアルなインテリア動画に変換する。

### パス準備

```bash
mkdir -p {workdir}/work/v2v/input {workdir}/final
cp {workdir}/work/camera/output/renders/cut_*.mp4 {workdir}/work/v2v/input/
```

### 実行

```
/floor_plan_to_video_sub_photoreal {workdir}/work/v2v/
```

### 最終成果物の収集

```bash
cp {workdir}/work/v2v/output/*_photorealistic.mp4 {workdir}/final/
```

完了確認: `final/` に `.mp4` ファイルが1つ以上存在する。

---

## 完了報告

全ステップ完了後、ユーザーに最終成果物を報告する:

```
=== Floor Plan to Video 完了 ===

最終成果物:
  {workdir}/final/cut_living_photorealistic.mp4
  {workdir}/final/cut_bedroom_photorealistic.mp4

中間成果物:
  間取りSVG: output/{stem}_elements.svg
  3Dシーン: output/scene.blend
  家具配置: output/placement/scene.blend
  カメラ動画: work/camera/output/renders/

open {workdir}/final/
```

---

## トラブルシューティング

### 特定ステップからやり直したい

該当ステップの出力ファイルを削除してから再実行する。例えばStep 5からやり直す場合:

```bash
rm -rf {workdir}/output/placement/
```

### Step 3をスキップしたい（GLBを自前で用意）

`output/assets/objects/` にGLBファイルを直接配置すればStep 3はスキップされる。

### Step 4cをスキップしたい

リファレンス調査は任意。Step 4dに直接進んでよい。
