# PoC 0_c: V2V入力用カメラカット + Cyclesレンダリング

## 目的

PoC 0_bで構築したPBRマテリアル付きscene.blendから、V2V（Kling）入力に最適な短尺カット動画群を生成する。各カットは独立した5秒クリップとして、始点→終点のカメラ動きをCyclesでフレームレンダリングし動画化する。

## 背景

### なぜV2V入力にCyclesが必要か

KlingなどのAIは入力映像の**影・反射・素材感**を手がかりに空間構造を理解する。EEVEEの近似的な影ではAIが奥行きや素材を誤認しやすい。Cycles + フルPBRが推奨。

### PoC 9からの拡張

PoC 9の`render_walkthrough.py`は2点間の線形補間のみ。本PoCでは複数の独立カットを生成するワークフローに拡張する。

### カット方式の採用理由

当初はキーポイント間をスプライン補間で繋ぐ連続ウォークスルーを検討したが、以下の理由で**独立カット方式**に変更:

- PR動画は5秒程度の短いカットを編集で繋ぐ構成が主流
- 連続パスでは進行方向とカメラ向きの不整合、壁衝突、速度ムラ等の問題が発生
- Kling V2Vの入力単位（5秒/セグメント）と独立カットが完全に一致
- カットごとに独立してV2V投入・再生成が可能

## Kling V2V入力仕様

| 項目 | 値 |
| --- | --- |
| 入力動画 | 3〜10秒/セグメント |
| 推奨セグメント長 | 5秒 |
| フレームレート | 30fps |
| 解像度 | 1920×1080（本番）/ 960×540（検証） |
| 延長 | Video Extend APIで5秒ずつ、最大3分 |

5秒 × 30fps = **150フレーム/カット**

## カット設計

### カット構造

各カットは**始点カメラ(s)と終点カメラ(e)のペア**で定義する。カット間に連続性は不要。

```json
{
  "name": "K1_entrance",
  "start": { "location": [...], "rotation_deg": [...], "lens": 24 },
  "end":   { "location": [...], "rotation_deg": [...], "lens": 24 },
  "frames": 150
}
```

始点→終点は線形補間（smooth_step）。各カット内の移動は小さい（0.5〜1m程度のドリーや数度のパン）。

### カット一覧（Step 2で確定）

| カット | 始点(s) | 終点(e) | 動き |
| --- | --- | --- | --- |
| C1_corridor_dolly | (-1.1, 5.6, 1.6) 南向き | (-1.5, 0.9, 1.2) 南向き | 玄関→廊下ドリーイン |
| C2_ldk_sweep | (-3.3, -5.0, 1.4) 北東向き(z=-35.6°) | (1.4, -6.1, 1.4) 北向き(z=-1.6°) | LDK南側を左→右スイープ、北東を向きながら移動 |
| C3_ldk_tracking | (1.3, -1.8, 1.4) 南向き(z=178.8°) | (-2.6, -2.7, 1.4) 南西向き(z=208.4°) | LDK右→左トラッキング、カメラ南〜南西向き |
| C4_overhead_zoomout | (0.1, -6.8, 5.2) 斜め下(x=32°) | (-0.2, -3.8, 12.2) 真下(x=0.8°) | LDK南側から斜め俯瞰→全景ズームアウト |

## ワークフロー

### Step 1: 空間分析 + カット設計（対話的） ✅

俯瞰画像とdraw.ioでカットパスを設計し、各カットの始点・終点カメラをBlenderで対話的に決定する。

1. `extract_room_bounds.py` で壁座標・部屋境界を取得 ✅
2. `render_overhead.py` で俯瞰レンダリング画像を生成（EEVEE、天井非表示、影なし） ✅
3. `generate_drawio.py` で俯瞰画像を背景に埋め込んだ `.drawio` を生成 ✅
4. ユーザーがdraw.ioでカメラパスを矢印で描画 ✅
   - 矢印の線 = カメラの進行方向
   - 矢印のラベル = カメラの向き（進行方向と異なる場合あり）
5. パスを元にカット数・各カットの動きイメージを決定（当初7→4カットに変更） ✅
6. `place_cut_cameras.py` で始点・終点カメラをscene.blendに配置 ✅
7. ユーザーがBlenderで各カメラの位置・向きを調整 ✅
8. 調整後のカメラ位置をBlenderから抽出し `cuts.json` を更新 ✅
9. `setup_cut_animation.py` でキーフレームアニメーションを設定し、Blenderで動き確認 ✅
   - 各カットの始点→終点をBezier補間でアニメーション化
   - タイムラインマーカーでカットごとにカメラ自動切替
   - C1: 1-150, C2: 151-300, C3: 301-450, C4: 451-600（計600フレーム/20秒）

**検証済み事項**:
- スプライン補間（Catmull-Rom、Hermite）を検証し、独立カット方式に方針変更
- draw.ioでパスを描くことで、カット設計を視覚的に議論できる
- Blenderのカメラ位置を正とし、cuts.jsonはBlenderから自動抽出する
- カメラの進行方向と向きは独立（PR動画では一般的）
- Cyclesレンダリング前にBlenderのタイムライン再生で動きを事前確認する（高コスト回避）

### Step 2: Cyclesフレームレンダリング ✅

`render_cuts.py` で各カットの始点→終点をsmooth_step補間し、150フレームをCyclesレンダリング。

```bash
scripts/run_blender.sh --background <scene.blend> \
  --python poc/3dcg_poc0_c/scripts/render_cuts.py -- \
  --cuts <cuts.json> --output-dir <output_dir> \
  --samples 32 --width 480 --height 270
```

- GPU (Metal) + OpenImageDenoiseで高速化
- `--cut <NAME>` で特定カットのみレンダリング可能
- 実績: GPU 32s, 480×270, 4カット × 150フレーム = **6.2分**

### Step 3: 動画化 ✅

各カットの連番PNGをffmpegで30fps mp4に変換。

```bash
ffmpeg -y -framerate 30 -i <cut_dir>/%04d.png \
  -c:v libx264 -pix_fmt yuv420p -crf 18 <output>.mp4
```

## スキル化

PoC 0_cのワークフローを `v2v-camera-cuts` スキル（`.claude/skills/v2v-camera-cuts/`）として汎用化済み。

主な変更点:
- 旧4ステップ（始点カメラ→カット設計→レンダリング→動画化）→ **3フェーズ**に統合（キーポイントカメラを削除し、空間分析+カット設計を1フェーズに）
- `render_overhead.py` を汎用化（`--room-bounds`引数でortho_scale/カメラ位置/解像度を自動計算）
- `generate_drawio.py` を新規作成（俯瞰画像をBase64埋め込みした.drawioテンプレート自動生成）
- ディレクトリ規約: `<workdir>/input/scene.blend` → `<workdir>/output/` に統一

## レンダリング設定

### GPU (Metal) レンダリング

ベンチマーク結果（Apple M4 Pro, Metal 20コア）により、GPU + 低サンプル + デノイジングが最適と判明。

| 設定 | デバイス | サンプル | 解像度 | 1フレーム | メモ |
| --- | --- | --- | --- | --- | --- |
| CPU 128s（旧設定） | CPU | 128 | 960×540 | ~20秒 | CPU全コアフル稼働、高負荷 |
| **GPU 64s（検証用）** | **GPU** | **64** | **960×540** | **~2.6秒** | **推奨。CPU負荷軽減** |
| GPU 32s（高速確認用） | GPU | 32 | 960×540 | ~1.6秒 | キーポイント確認向け |
| GPU 32s 半解像度 | GPU | 32 | 480×270 | ~0.7秒 | 最速 |

- GPU初回はMetalカーネルコンパイルで~80秒。2フレーム目以降は高速
- OpenImageDenoiseにより32sでも64sでも画質差はほぼなし
- CPU 128s → GPU 64sで**約7.5倍高速**、CPU負荷も大幅軽減

### レンダリング時間見積もり（GPU 64s基準）

| 設定 | 1フレーム | 1カット（150フレーム） | 7カット |
| --- | --- | --- | --- |
| **採用: GPU 32s, 480×270** | **~0.6秒** | **~1.5分** | **~6.2分（4カット実績）** |
| GPU 64s, 960×540 | ~2.6秒 | ~6.5分 | ~26分（4カット） |
| GPU 128s, 1920×1080 | 要計測 | 要計測 | 要計測 |

## 入力

- `poc/3dcg_poc0_c/input/scene.blend` — PBRマテリアル付き3Dシーン

## ベースコード

- `poc/3dcg_poc9/render_walkthrough.py` — 2点間補間+レンダリング（流用）
- `poc/3dcg_poc9/run_v2v.py` — V2V API呼び出し（Luma/Runway）
- `poc/3dcg_poc0_c/scripts/render_cycles.py` — Cycles設定（流用）

## スクリプト

| スクリプト | 用途 |
| --- | --- |
| `scripts/extract_room_bounds.py` | scene.blendから壁座標・部屋境界を抽出 |
| `scripts/add_keypoint_cameras.py` | キーポイントカメラをblendに配置して保存 |
| `scripts/generate_camera_path.py` | カメラパス生成（Catmull-Rom、検証用に残存） |
| `scripts/visualize_path.py` | パスをBlenderカーブで可視化 |
| `scripts/benchmark_cycles.py` | CPU/GPU・サンプル数・解像度の比較計測 |
| `scripts/render_cycles.py` | Cyclesフレームレンダリング（GPU対応済み） |
| `scripts/render_overhead.py` | 俯瞰レンダリング（EEVEE、天井非表示、影なしサンライト） |
| `scripts/place_cut_cameras.py` | cuts.jsonの始点・終点カメラをblendに配置して保存 |
| `scripts/setup_cut_animation.py` | cuts.jsonからキーフレームアニメーション設定（タイムライン確認用） |
| `scripts/render_cuts.py` | cuts.jsonの各カットをsmooth_step補間しCyclesフレームレンダリング |

## 成果物

### スキル実行（v2v-camera-cuts）による出力

- `output/room_bounds.json` — 壁座標・部屋境界データ
- `output/overhead.png` — 俯瞰レンダリング画像（1920×3969）
- `output/camera_paths.drawio` — パス描画用draw.ioファイル（俯瞰画像を背景埋め込み）
- `output/cuts.json` — 4カットの始点・終点ペア定義（Blenderで調整済み座標）
- `output/tmp/scene_cuts.blend` — 始点・終点カメラ配置済みシーン（ユーザー調整用）
- `output/tmp/scene_animation.blend` — キーフレームアニメーション付きシーン（タイムライン確認用）
- `output/renders/{cut_name}/` — 各カットのCyclesレンダリング連番PNG（150枚/カット）
- `output/renders/{cut_name}.mp4` — 各カットの動画（5秒/30fps）

### 過去の検証成果物（1/）

- `1/tmp/keypoints_v3.json` — 確定始点カメラ位置（7点）
- `1/tmp/scene_keypoints.blend` — 始点カメラ配置済みシーン
- `1/cuts.json` — 旧カット定義
- `1/renders/` — 旧レンダリング出力

## スキル実行時の知見

### draw.ioテンプレートの背景サイズ
- 初回生成時、俯瞰画像(1920×3969)をそのままページサイズに使用したため巨大すぎた
- `generate_drawio.py`を修正し、長辺800pxにリサイズする処理を追加
- 修正後は387×800pxで扱いやすいサイズに

### C2スイープの回転問題
- 初回のcuts.jsonでrot_z=290°→-0.8°を設定したところ、補間で意図しない大回転が発生
- ユーザーがBlenderで始点・終点カメラを調整し、LDK北東方向を常に向く形に修正
- 最終的にrot_z=-35.6°→-1.6°（差34°）でスムーズな補間に
