---
name: floor_plan_to_video_sub_multiview
description: scene.blendに配置されたカメラ位置を抽出し、各カメラからEEVEE+HDRI環境照明（Material Preview相当）で一括レンダリング画像を出力する。カメラレンダリング、カメラ位置抽出、マテリアルプレビューレンダリング、HDRI照明、シーンの多視点レンダリング、カメラアングルからの画像出力に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <input_dir> <output_dir>
allowed-tools: Bash(scripts/run_blender.sh *), Bash(mkdir *), Bash(ls *)
---

# floor_plan_to_video_sub_multiview

scene.blendに配置されたカメラから、EEVEE + HDRI環境照明（BlenderのMaterial Preview相当）で一括レンダリング画像を出力するスキル。全4フェーズを自律的に実行する。

## 前提条件

- `blender-python`スキルを参照済みであること（Blender CLIは必ず`scripts/run_blender.sh`経由）
- `/Applications/Blender.app` がインストールされていること

## 入力ファイル

| ファイル                  | 内容                       |
| ------------------------- | -------------------------- |
| `<input_dir>/scene.blend` | カメラが配置された3Dシーン |

## 出力ファイル

| ファイル                            | 内容                                                     |
| ----------------------------------- | -------------------------------------------------------- |
| `<output_dir>/camera_positions.json` | カメラ位置データ（name, location, rotation_euler, lens） |
| `<output_dir>/renders/*.png`         | 各カメラからのレンダリング画像（960x540）                |

## 処理フロー

```
Phase 1: 入力確認 → scene.blend存在チェック
    ↓
Phase 2: カメラ位置抽出 → camera_positions.json
    ↓
Phase 3: 一括レンダリング → renders/*.png
    ↓
Phase 4: 結果確認（画像を読んで品質チェック）
    ↓
完了
```

---

## Phase 1: 入力確認

`<input_dir>/scene.blend` の存在を確認する。

```bash
test -f <input_dir>/scene.blend || echo "ERROR: scene.blend not found in <input_dir>"
```

## Phase 2: カメラ位置抽出

```bash
scripts/run_blender.sh --background <input_dir>/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_multiview/scripts/extract_cameras.py -- <output_dir>
```

出力: `<output_dir>/camera_positions.json`

確認すること:

- JSONにカメラが1台以上含まれていること
- 各カメラのlocation, rotation_euler, lensが妥当な値であること

## Phase 3: 一括レンダリング

```bash
scripts/run_blender.sh --background <input_dir>/scene.blend \
  --python .claude/skills/floor_plan_to_video_sub_multiview/scripts/render_cameras.py -- <output_dir>
```

出力: `<output_dir>/renders/{カメラ名}.png`

### レンダリング方式: EEVEE + HDRI環境照明

GUIの「マテリアルプレビュー」と同等の見た目をCLIバックグラウンドレンダリングで再現する。Blender内蔵のStudio HDRIファイルを環境照明として使用するため、ライト設置は不要。

このスクリプトは以下を自動処理する:

- **HDRI環境照明**: Blender内蔵Studio HDRI（`.exr`）をWorld設定にロード
- **背景合成**: `film_transparent`で背景を透過レンダリングし、単色ライトグレー背景に合成（HDRIが背景に映り込まない）
- **一時マテリアル付与**: 壁・柱・床・その他コレクションのマテリアルなしオブジェクトに`Principled BSDF`を適用（家具の既存マテリアルは上書きしない）
- **天井自動非表示**: 俯瞰カメラ（z > 壁最大高さ）のレンダリング時、天井相当オブジェクトを自動で非表示

## Phase 4: 結果確認

レンダリング画像を読み、以下を確認する:

- [ ] camera_positions.jsonの全カメラに対応するPNGが出力されているか
- [ ] オブジェクトの位置関係が視覚的に判別可能か（真っ黒・真っ白でないか）
- [ ] 家具のマテリアル色が表示されているか
- [ ] 俯瞰カメラで間取り全体が見えているか（天井が非表示になっているか）

### 問題がある場合

- **画像が真っ暗**: HDRIのロードに失敗している可能性。Blenderのコンソール出力を確認
- **画像が真っ白（俯瞰カメラ）**: 天井の自動非表示が機能していない可能性。天井オブジェクトの検出ロジックを確認
- **オブジェクトが見えない**: マテリアルが正しく適用されていない可能性

## 完了条件

- `camera_positions.json`が生成されている
- `renders/`に全カメラのPNGが出力されている
- オブジェクトの位置関係が視覚的に判別可能
- ユーザーに結果のレンダリング画像のパスを報告する
