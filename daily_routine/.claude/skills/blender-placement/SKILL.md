---
name: blender-placement
description: layout_proposal.jsonの家具配置をGLBアセットとしてBlenderシーンに自動配置する統合スキル。GLB測定→front方向の自律判定→配置実行→配置結果の視覚的評価までを一気通貫で実行する。GLBアセットのBlender配置、家具レイアウトの3D化、scene.blendの生成に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <input_dir> <output_dir>
---

# blender-placement

layout_proposal.jsonの家具配置座標をGLBアセットとしてBlenderシーンに自動配置するスキル。全4フェーズを自律的に実行する。

## 前提条件

- `blender-python`スキルを参照済みであること（Blender CLIは必ず`scripts/run_blender.sh`経由）
- `/Applications/Blender.app` がインストールされていること

## 入力ファイル

全てinput_dir内に配置:

| ファイル | 内容 |
|---------|------|
| `layout_proposal.json` | アセットの座標(center x,y)・向き(front_dir)・サイズ |
| `assets.json` | 家具定義（サイズ・GLBパス・shape説明） |
| `madori.blend` | 壁3Dモデル |
| `asserts/objects/*.glb` | 家具GLBファイル |
| `asserts/images/*` | 家具参考写真 |

## 処理フロー

```
Phase 1: GLB測定 → glb_check_result.json
    ↓
Phase 2: front方向判定（画像を見て自律判定）→ glb_check_result.json更新
    ↓
Phase 3: 家具配置 → scene.blend
    ↓
Phase 4: 配置確認（レンダリング画像で自律評価）
    ↓ 問題あり → Phase 2-3に戻る
完了
```

---

## Phase 1: GLB測定

```bash
scripts/run_blender.sh --background --python \
  .claude/skills/blender-placement/scripts/check_glb_bbox.py -- \
  <input_dir> <output_dir>
```

出力: `<output_dir>/glb_check_result.json`

確認すること:
- 全アセットのサイズ・スケール係数が記録されている
- `origin_relative`の値を確認（`center`=幾何中心、`bottom-center`=底面中心）
- Z補正は`place_assets.py`が`expected_height/2`で自動計算するため、手動設定不要

## Phase 2: front方向判定

### 2a. GLBレンダリング実行

```bash
scripts/run_blender.sh --background --python \
  .claude/skills/blender-placement/scripts/render_glb_views.py -- \
  <input_dir>/assets.json <output_dir>
```

出力: `<output_dir>/glb_views/{asset_id}_top.png`, `{asset_id}_persp.png`

レンダリング画像には軸ラベルが含まれる:
- **赤矢印** = +X方向
- **緑矢印** = +Y方向

### 2b. front方向を判定する

各アセットについて以下の3つの情報を照合してfront方向を判定する:

1. **レンダリング画像を読む**: `<output_dir>/glb_views/{id}_top.png` と `{id}_persp.png`
2. **参考写真を読む**: `<input_dir>/asserts/images/{id}.*`
3. **shape説明を読む**: `assets.json`の各アセットの`shape.front`と`shape.back`

判定手順:
1. パースペクティブ画像で家具の立体形状を把握する
2. shape.frontの説明（「足元側」「椅子を置く側」「引き戸がある側」等）を確認する
3. トップダウン画像で、その「front面」がどの軸方向を向いているかを特定する
4. 赤矢印(+X)・緑矢印(+Y)を基準に、front方向を`+X`, `-X`, `+Y`, `-Y`のいずれかで記録する

### 2c. glb_check_result.jsonを更新

`manual_overrides`セクションの各アセットの`default_front`を判定結果で更新する:

```json
"manual_overrides": {
  "bed": {"default_front": "-X", "use_uniform_scale": false},
  "desk": {"default_front": "-X", "use_uniform_scale": false},
  ...
}
```

`default_front`の値: `+X`, `-X`, `+Y`, `-Y`

### 2d. scale歪みチェック

front方向の判定後、per-axis scaleの妥当性を確認する:

- `place_assets.py`はfront方向に応じてwidth/depthの軸マッピングを自動スワップする
  - front=±Y: width→X, depth→Y（デフォルト）
  - front=±X: width→Y, depth→X（自動スワップ）
- `use_uniform_scale`の選択基準:
  - per-axis scaleのX:Y比率が **2:1を超える**場合、front方向が間違っている可能性が高い → 再判定
  - 家具の形状が元々歪んでいない限り、X:Y比は概ね1:1〜2:1に収まるべき

## Phase 3: 家具配置

```bash
scripts/run_blender.sh --background <input_dir>/madori.blend \
  --python .claude/skills/blender-placement/scripts/place_assets.py -- \
  <input_dir> <output_dir>
```

出力:
- `<output_dir>/scene.blend` — 配置済みBlenderシーン
- `<output_dir>/placement_report.json` — 配置結果サマリ

## Phase 4: 配置確認

### 4a. シーンレンダリング実行

```bash
scripts/run_blender.sh --background <output_dir>/scene.blend \
  --python .claude/skills/blender-placement/scripts/render_scene.py -- \
  <output_dir>
```

出力: `<output_dir>/scene_views/top.png`, `persp.png`

### 4b. 配置品質を評価する

レンダリング画像を読み、以下を確認する:

- [ ] 全アセットが配置されているか（placement_report.jsonのtotal_placedを確認）
- [ ] 壁を貫通している家具がないか（俯瞰ビューで確認）
- [ ] 家具同士が重なっていないか
- [ ] 家具が部屋の外にはみ出していないか
- [ ] 家具が床面に接地しているか（パースビューで確認。壁は自動的に非表示になる）
- [ ] 家具の形状が歪んでいないか（異常に細長い/太い場合はfront方向の誤判定の可能性）
- [ ] placement_report.jsonのscale値でX:Y比率が2:1を超えるアセットがないか

### 4c. 問題がある場合

- **front方向が間違っている**: Phase 2cに戻り、該当アセットの`default_front`を修正 → Phase 3を再実行。`place_assets.py`がfront方向に応じてwidth/depthの軸マッピングを自動スワップするため、scale_factorの手動修正は不要
- **形状が歪んでいる**: front方向の誤判定でscale軸がずれている可能性。placement_report.jsonのscale X:Y比率を確認し、2:1を超えていればfront方向を再判定
- **位置がおかしい**: `layout_proposal.json`の座標自体の問題なのでユーザーに報告
- **浮いている/めり込んでいる**: `origin_relative`の値が正しいか確認。`place_assets.py`は`expected_height/2`で自動補正する（center origin前提）

## 完了条件

- `scene.blend`が生成されている
- 全アセットが配置されている
- Phase 4bの確認項目に重大な問題がない
- ユーザーに最終結果のレンダリング画像と`scene.blend`のパスを報告する

最終的な微調整はユーザーがBlender GUIで行う: `open <output_dir>/scene.blend`
