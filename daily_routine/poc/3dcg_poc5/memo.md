# PoC5 メモ

## 目的

カメラ位置データ → CLI経由でレンダリング画像出力を自動化する。

## PoC6との関係

レンダリング画像はPoC6（動画生成AI）への入力。オブジェクトの位置関係が分かればよく、リアルな照明・影は不要。

## 最終的なアプローチ

### 方式: EEVEE + HDRI環境照明（Material Preview相当）

GUIの「マテリアルプレビュー」と同等の見た目をCLIバックグラウンドレンダリングで再現する方式を採用。

**なぜこの方式か:**

- Workbench（Solid表示）→ オブジェクトがグレー単色で、家具の区別が困難
- Cycles/EEVEE + ライト設置 → 壁の法線が外向きで室内に光が届かず真っ暗。ライティング調整が大変でPoC5の目的外
- **EEVEE + HDRI** → 照明設定不要、マテリアル色が表示される、GUIのMaterial Previewと同等の結果

### 技術的なポイント

#### 1. HDRI環境照明の設定

Blender内蔵のStudio HDRIファイルを使用。パスは `bpy.utils.resource_path("LOCAL") / "datafiles/studiolights/world/"` にある `.exr` ファイル。World のノードツリーに `ShaderNodeTexEnvironment` を追加し、HDRIをロードして `ShaderNodeBackground` に接続する。Strength=1.5。

#### 2. マテリアルのないオブジェクトへの一時マテリアル付与

壁・柱・床・その他のコレクションに属するオブジェクトはマテリアルがない場合がある（間取りの3Dモデルは色情報を持たない）。レンダリング時に一時的に `Principled BSDF` マテリアルを付与する。

| コレクション | Base Color         |
| ------------ | ------------------ |
| 壁           | (0.85, 0.85, 0.82) |
| 柱           | (0.75, 0.75, 0.73) |
| 床           | (0.4, 0.38, 0.35)  |
| その他       | (0.7, 0.7, 0.7)    |

条件: `len(obj.data.materials) == 0` のオブジェクトのみ（家具のマテリアルは上書きしない）。

#### 3. 俯瞰カメラ時の天井自動非表示

「床」コレクション内に天井相当のオブジェクト（壁の最大高さ以上のz位置にある平面）が含まれる場合がある。俯瞰カメラ（カメラ位置z > 壁最大高さ）のレンダリング時に `hide_render = True` で自動非表示にし、他カメラのレンダリング後に復元する。

#### 4. カメラの向きとBlender座標系

- Blenderのカメラはローカル **-Z方向** を見る
- `rotation_euler = (0, 0, 0)` → **真下**（-Z = ワールド下方向）
- `rotation_euler = (π/2, 0, 0)` → **水平前方**（-Zが+Y方向に回転）
- 俯瞰カメラは `rotation_euler = (0, 0, 0)` で真下を向く

### パイプライン

```text
camera_positions.json  → カメラ位置データ（location, rotation_euler, lens）
        ↓
render_cameras.py      → EEVEE + HDRI で一括レンダリング
        ↓
output/renders/        → 各カメラ位置からの PNG 画像
```

### 実行コマンド

```bash
# カメラ位置を scene.blend から抽出
scripts/run_blender.sh --background poc/3dcg_poc4/output/scene.blend \
  --python poc/3dcg_poc5/extract_cameras.py

# 一括レンダリング
scripts/run_blender.sh --background poc/3dcg_poc4/output/scene.blend \
  --python poc/3dcg_poc5/render_cameras.py
```

## 試行錯誤の記録

### 失敗: ライティングによるレンダリング（不採用）

壁・床にマテリアルを設定し、Sun Light / Area Light を追加してCycles/EEVEEでレンダリングを試みた。

- 壁の法線が外向きで、室内側に光が当たらず真っ暗
- 法線反転、Solidifyモディファイア追加を試みたが改善せず
- **結論**: 間取りモデルの壁は片面ポリゴンで建築用途を想定していないため、従来のライティング手法は非効率。PoC5の目的（オブジェクト位置関係の確認）にはHDRI環境照明で十分。

### 失敗: Workbench（Solid表示）（不採用）

`BLENDER_WORKBENCH` エンジンでレンダリング。オブジェクトがすべてグレー単色になり、家具の種類が視覚的に判別困難。PoC6への入力として情報量が不十分。

### 成功: EEVEE + HDRI（採用）

上記「最終的なアプローチ」の通り。家具のマテリアル色が表示され、壁・床は一時マテリアルで色分けされ、俯瞰では天井を自動非表示にすることで間取り全体が見える。

## スキル化計画

### 目的

PoC5の手順を `floor_plan_to_video_sub_multiview` スキルとして汎用化し、任意の `scene.blend` + `camera_positions.json` から再現可能にする。

### スキル構成

```text
.claude/skills/floor_plan_to_video_sub_multiview/
├── SKILL.md                    ← スキル定義
└── scripts/
    ├── extract_cameras.py      ← カメラ位置抽出
    └── render_cameras.py       ← 一括レンダリング
```

### 入出力設計（汎用化）

PoC5固有のパスに依存せず、**任意の作業ディレクトリ**で動作する設計にする。

**引数**: `<work_dir>`（作業ディレクトリ）

**入力（work_dir内に存在する前提）**:

- `scene.blend` — カメラ配置済みの3Dシーン

**出力（work_dirに書き出す）**:

- `camera_positions.json` — 抽出したカメラ位置データ
- `renders/*.png` — 各カメラからのレンダリング画像

**スクリプト引数**:

```bash
# カメラ位置抽出
scripts/run_blender.sh --background <work_dir>/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_multiview/scripts/extract_cameras.py -- <work_dir>

# 一括レンダリング
scripts/run_blender.sh --background <work_dir>/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_multiview/scripts/render_cameras.py -- <work_dir>
```

スクリプト内では `sys.argv` から `work_dir` を受け取り、入出力パスを組み立てる。`bpy.data.filepath` からの相対パス計算は行わない。

### SKILL.md に記載すべき内容

1. **前提条件**: `blender-python` スキル参照済み、`scripts/run_blender.sh` 存在
2. **入力確認**: `<work_dir>/scene.blend` の存在チェック
3. **Phase 1: カメラ位置抽出** → `<work_dir>/camera_positions.json` 出力
4. **Phase 2: 一括レンダリング** → `<work_dir>/renders/*.png` 出力
   - EEVEE + HDRI環境照明（Material Preview相当）
   - マテリアルなしオブジェクトへの一時マテリアル付与
   - 俯瞰カメラ時の天井自動非表示
5. **Phase 3: 結果確認** → 画像を読んで品質チェック
6. **完了条件**: 全カメラの画像出力、オブジェクト位置関係が視覚的に判別可能

### 既存スキルとの関係

- `floor_plan_to_video_sub_placement` スキルの **後工程** として位置づけ
- `floor_plan_to_video_sub_placement` が `scene.blend` を生成 → `floor_plan_to_video_sub_multiview` がレンダリング
- `floor_plan_to_video_sub_placement` の Phase 4（配置確認レンダリング）は簡易版（top/persp 2枚）。本スキルはユーザー定義の任意カメラ位置から詳細レンダリングを行う

### skill-creator への入力

skill-creator に以下を渡してスキルを生成する:

- **参考実装**: `poc/3dcg_poc5/render_cameras.py`, `poc/3dcg_poc5/extract_cameras.py`
- **参考スキル**: `.claude/skills/floor_plan_to_video_sub_placement/SKILL.md`（構成・フォーマットの参考）
- **技術的知見**: 本メモの「最終的なアプローチ」セクション
- **汎用化方針**: スクリプトは `sys.argv` で `work_dir` を受け取り、`bpy.data.filepath` 依存を排除
