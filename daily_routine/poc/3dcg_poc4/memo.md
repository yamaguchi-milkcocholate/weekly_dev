# PoC 4: レイアウト提案をBlender上に配置する

## 目的

PoC 3で生成した家具配置座標（layout_proposal.json）を、GLBアセットとしてBlender上に自動配置する。

## 入力ファイル

| ファイル     | パス                                        | 内容                                                         |
| ------------ | ------------------------------------------- | ------------------------------------------------------------ |
| 配置座標     | `poc/3dcg_poc3/output/layout_proposal.json` | 10アセットの2D座標(center x,y)・向き(front_dir)・サイズ      |
| アセット定義 | `poc/3dcg_poc3/output/assets.json`          | 各アセットの3Dサイズ(w/d/h)・GLBパス・配置ルール             |
| GLBファイル  | `poc/3dcg_poc2/output/*.glb`                | 6種類: bed, desk, chair, counter, closet, dining_table       |
| 壁データ     | `poc/3dcg_poc3/output/walls.json`           | 壁23本・柱4本・床2面のBBox座標（Blender .blendから抽出済み） |
| 部屋情報     | `poc/3dcg_poc3/output/room_info.json`       | 各部屋の実寸座標(real_m)                                     |
| 壁の.blend   | `poc/3dcg_poc3/input/madori.blend`          | 手動作成済みの壁3Dモデル                                     |

## 座標系の理解

layout_proposal.jsonの座標はBlenderのXY平面上のメートル単位:

- X軸: 左(-) → 右(+)
- Y軸: 下(-) → 上(+)
- Z軸: 高さ（layout_proposalでは未指定、床面=0とする）

front_dirの回転マッピング:
| front_dir | 意味 | Z軸回転(rad) |
|-----------|------|-------------|
| N | 前面が北(+Y) | 0 |
| E | 前面が東(+X) | -π/2 |
| S | 前面が南(-Y) | π |
| W | 前面が西(-X) | π/2 |

## GLBアセットのサイズ（assets.jsonより）

| id           | width(m) | depth(m) | height(m) | 個数 |
| ------------ | -------- | -------- | --------- | ---- |
| bed          | 1.40     | 2.00     | 0.95      | 1    |
| desk         | 1.40     | 0.70     | 0.75      | 2    |
| chair        | 0.65     | 0.65     | 1.20      | 2    |
| counter      | 0.80     | 0.40     | 0.70      | 3    |
| closet       | 1.80     | 0.50     | 1.80      | 1    |
| dining_table | 1.20     | 0.80     | 0.72      | 1    |

GLBファイルサイズ（10〜33MB）。Tripo AIで生成したものなので、GLB内のスケール・原点・向きは要確認。

## 実装手順

### Step 1: GLBの原点・スケール・向き確認

GLBをBlenderに個別インポートしてバウンディングボックスを確認する。assets.jsonの想定サイズ(m)とGLB内の実サイズを比較し、スケール係数を決定する。

```bash
# 各GLBのBBox確認スクリプト
scripts/run_blender.sh --background --python poc/3dcg_poc4/check_glb_bbox.py
```

確認項目:

- [ ] GLBの単位系（メートル? センチメートル?）
- [ ] 原点の位置（中心? 底面中心?）
- [ ] デフォルトの向き（front方向はどちらか?）
- [ ] assets.jsonの想定サイズとの差分

### Step 2: 配置スクリプト作成

`poc/3dcg_poc4/place_assets.py` — Blenderヘッドレスで実行するスクリプト。

```
入力:
  --layout   poc/3dcg_poc3/output/layout_proposal.json
  --assets   poc/3dcg_poc3/output/assets.json
  --glb-dir  poc/3dcg_poc2/output/
  --walls    poc/3dcg_poc3/input/madori.blend  (壁モデル)
  --output   poc/3dcg_poc4/output/scene.blend

処理:
  1. madori.blendを開く（壁モデルがある状態からスタート）
  2. layout_proposal.jsonをループ
  3. 各アセットについて:
     a. GLBインポート (bpy.ops.import_scene.gltf)
     b. スケール調整（Step 1で確認した係数）
     c. center座標をlocationに設定 (x, y, z=0)
     d. front_dirに応じてrotation_euler.zを設定
     e. オブジェクト名をlabel（bed_1, desk_1等）にリネーム
  4. scene.blendとして保存

実行:
  scripts/run_blender.sh --background poc/3dcg_poc3/input/madori.blend \
    --python poc/3dcg_poc4/place_assets.py -- \
    --layout poc/3dcg_poc3/output/layout_proposal.json \
    --assets poc/3dcg_poc3/output/assets.json \
    --glb-dir poc/3dcg_poc2/output/
```

### Step 3: 配置結果の確認

```bash
# Blender GUIで開いて目視確認
open poc/3dcg_poc4/output/scene.blend
```

確認項目:

- [ ] 全10アセットが配置されているか
- [ ] 壁を貫通していないか
- [ ] アセット同士が重なっていないか
- [ ] 向き(front_dir)が正しいか
- [ ] 床面に接地しているか（浮いていないか・めり込んでいないか）

### Step 4: 手動調整 → 確定

Blender GUIで微調整し、確定版を保存。

## 注意点

- **Blender実行**: `blender`コマンド直接禁止。必ず`scripts/run_blender.sh`経由
- **GLBスケール**: Tripo AI生成GLBはスケールが不定。Step 1で必ず確認する
- **GLBの向き**: front方向がGLBごとに異なる可能性あり。Step 1で各アセットのデフォルト向きを記録する
- **Z座標**: layout_proposal.jsonにZ座標はない。GLBの原点が底面中心であればz=0でOK。そうでなければBBoxの底面をz=0に合わせる補正が必要
- **壁モデルの高さ**: walls.jsonはXY座標のみ。壁の高さ(extrude)は madori.blend 内で設定済みのはず。要確認

## 合格基準

| 評価項目     | 合格の目安                          |
| ------------ | ----------------------------------- |
| 挿入の成立   | 全10アセットがBlender上に配置される |
| 空間的妥当性 | 壁貫通・アセット重複がない          |
| 向きの正確性 | front_dirが配置提案通り             |
| 手動調整可能 | Blender GUIで移動・回転ができる     |
| 保存・再読込 | .blendで保存し再度開ける            |

## 成果物

- `poc/3dcg_poc4/check_glb_bbox.py` — GLB確認スクリプト
- `poc/3dcg_poc4/place_assets.py` — 自動配置スクリプト
- `poc/3dcg_poc4/output/scene.blend` — 配置済みシーン

---

## 修正履歴

### Patch 3: blender-placementスキルによる再実行（2026-03-29）

スキル化された`blender-placement`で`poc/3dcg_poc4/output_test`に再配置を実行。
Patch 1-2で発覚した問題がスキル側のスクリプトで全て解消されていることを確認。

**front方向の判定結果（スケール比率による検証済み）:**

| Asset | default_front | X:Y比 | use_uniform_scale |
|-------|--------------|-------|-------------------|
| bed | +X | 1.2:1 | false |
| desk | -X | 1.13:1 | false |
| chair | +Y | 1.04:1 | false |
| counter | -X | 1.35:1 | false |
| closet | -X | 1.55:1 | false |
| dining_table | -Y | 1.08:1 | false |

**Patch 2からの差分:**
- bed: `-X`→`+X`（足元側の方向を再判定）
- chair: `-Y`→`+Y`（座面前方を再判定）
- desk/counter/closet: `+Y`→`-X`に修正（Patch 2で未修正だったscale歪み問題を解消）

### Patch 2: front方向判定とコードバグの修正（2026-03-26）

**ユーザー報告:**
- ベッドのサイズ比が変わっている
- 椅子の向きが逆
- テーブルも縦横が逆でサイズ比が変わっている

**根本原因:**
1. `place_assets.py`の`GLB_FRONT_CORRECTION`で`+X`と`-X`の回転値が入れ替わっていたバグ
2. front方向の誤判定: 全アセットを`+Y`に統一していたが、実際のGLBのfront方向が異なる
3. front方向が±Xのアセットでは`check_glb_bbox.py`のwidth→X / depth→Y マッピングが実軸と合わず、per-axis scaleでメッシュの縦横比が崩れる

**修正内容:**

| 修正箇所 | 変更内容 |
|---------|---------|
| `place_assets.py` GLB_FRONT_CORRECTION | `+X`: -π/2→**π/2**, `-X`: π/2→**-π/2** |
| bed default_front | `+Y`→**`-X`** |
| chair default_front | `+Y`→**`-Y`** |
| dining_table default_front | `+Y`→**`-Y`** |

**学んだこと:**
- `default_front`の変更は回転だけでなくscale_factorのwidth/depth→axis割り当ても連動する
- front方向が±Xのアセットでは、scale_factorをdepth→X, width→Yで再計算する必要がある
- `check_glb_bbox.py`は常にwidth→X, depth→Yで計算するため、±X frontのアセットは手動でscale修正が必要

### Patch 1: uniform_scale→per-axis scaleの変更（2026-03-26）

- bed/desk/counter/closetの`use_uniform_scale`を`false`に変更
- 全アセットの`default_front`を`+Y`で統一（→Patch 2で個別修正）

---

## 過去の問題点と解消状況

### 1. Z方向の浮き（接地不良）→ 解消済み

**原因**: `z_correction = -z_offset * scale_factor_z`でscale_zが1.0から乖離すると過剰補正
**対策**: `place_assets.py`を`expected_height / 2`方式に変更。Patch 3で全アセットの接地を確認済み

### 2. desk/counter/closetのscale歪み → 解消済み

**原因**: front方向を`+Y`に統一していたため、GLBの長軸Yがwidth/depthのマッピングと合わなかった
**対策**: Patch 3でfront方向を`-X`に修正。X:Y比が全て2:1以内に収まることを確認

| アセット | 修正前X:Y比 | 修正後X:Y比 |
|---------|-----------|-----------|
| desk | 3.5:1 | 1.13:1 |
| counter | 5.4:1 | 1.35:1 |
| closet | 8.4:1 | 1.55:1 |

### 3. パースビューの視認性 → 解消済み

**原因**: 壁が家具を遮りパースビューで家具が見えない
**対策**: `render_scene.py`でパースビュー時に壁コレクションを自動非表示化
