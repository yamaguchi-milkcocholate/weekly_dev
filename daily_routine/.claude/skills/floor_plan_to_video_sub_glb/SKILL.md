---
name: floor_plan_to_video_sub_glb
description: 画像からTripo AI APIで3Dモデル（GLB）を生成するスキル。各オブジェクトのfront画像を使用して単一画像モードで3D変換し、複数オブジェクトを並列変換する。画像から3Dモデル生成、GLBファイル作成、Tripo APIでの3D変換、オブジェクトの3Dモデル化、写真から3Dに関連するタスクで必ずこのスキルを参照すること。
argument-hint: <input_dir> [--output-dir <output_dir>] [--max-concurrent <N>]
allowed-tools: Bash(uv run *), Bash(mkdir *), Bash(ls *)
---

# floor_plan_to_video_sub_glb

画像からTripo AI APIでGLB形式の3Dモデルを生成する。各オブジェクトのfront画像（正面）を使用して単一画像モード（`image_to_model`）で3D変換する。複数オブジェクトを並列に変換できる。

## 前提条件

- 環境変数 `DAILY_ROUTINE_API_KEY_TRIPO` にTripo AI APIキー（`tsk_`プレフィックス）を設定済み
- `uv sync` で依存関係インストール済み

## 入力ディレクトリ構造

```
input_dir/
├── chair/              # オブジェクト名 = ディレクトリ名
│   └── front.png       # front: 正面画像（必須）
├── desk/
│   └── photo.png       # 画像が1枚のみ → front扱い
└── sofa/
    ├── front.png       # frontが使用される（他の画像は無視）
    ├── left.png
    └── back.png
```

### 画像の選択ルール

- `front`プレフィックスの画像を使用する（`image_to_model` API）
- `front`がない場合、ディレクトリ内の最初の画像をfront扱いにする
- 複数画像があっても**常にfront 1枚のみ**で変換する
- 対応フォーマット: PNG, JPG, JPEG, WEBP

## 実行方法

```bash
# 基本実行（出力: input_dir/output/）
uv run python .claude/skills/floor_plan_to_video_sub_glb/scripts/image_to_3d.py input/objects/

# 出力先を指定
uv run python .claude/skills/floor_plan_to_video_sub_glb/scripts/image_to_3d.py input/objects/ --output-dir output/models/

# 並列数を指定（デフォルト: 3）
uv run python .claude/skills/floor_plan_to_video_sub_glb/scripts/image_to_3d.py input/objects/ --max-concurrent 5
```

## 出力

```
output_dir/
├── chair.glb              # 3Dモデル
├── chair_preview.webp     # プレビュー画像（取得可能な場合）
├── desk.glb
├── desk_preview.webp
├── lamp.glb
└── lamp_preview.webp
```

- GLBファイル名はオブジェクトのディレクトリ名に一致
- プレビュー画像はTripo APIが返す場合のみ生成

## API仕様（Tripo AI v2）

### 単一画像モード（`image_to_model`）

```json
{
  "type": "image_to_model",
  "file": { "type": "png", "file_token": "<token>" }
}
```

### マルチビューモード（`multiview_to_model`）

```json
{
  "type": "multiview_to_model",
  "files": [
    { "type": "png", "file_token": "<front_token>" },
    { "type": "jpg", "file_token": "<left_token>" },
    { "type": "png", "file_token": "<back_token>" },
    { "type": "jpg", "file_token": "<right_token>" }
  ]
}
```

`files`配列のインデックスが画角に対応（0=front, 1=left, 2=back, 3=right）。frontは必須、他は任意。

### 定数

| 定数 | 値 | 説明 |
|------|-----|------|
| BASE_URL | `https://api.tripo3d.ai` | APIベースURL |
| POLL_INTERVAL | 5秒 | ポーリング間隔 |
| MAX_POLL_COUNT | 60回 | 最大ポーリング（=5分） |
| HTTP_TIMEOUT | 120秒 | HTTPタイムアウト |
| MAX_CONCURRENT | 3 | デフォルト並列数 |

## エラーハンドリング

| 状況 | 挙動 |
|------|------|
| ディレクトリ内に画像がない | スキップしてログ出力 |
| マルチビューでfrontがない | 最初の画像をfront扱い（警告ログ） |
| APIキー未設定 | 即時終了 |
| タスク失敗/タイムアウト | そのオブジェクトをスキップし他は続行 |
| 全オブジェクト失敗 | 終了コード1 |

## 品質に関する知見

- 背景透過画像の方が品質が高い傾向
- マルチビューは単一画像より形状精度が高い（特に背面の再現）
- 1オブジェクトあたり約2〜5分の処理時間
- 生成モデルのサイズは10〜32MB（複雑さによる）
- スケールはモデルごとに異なるため、Blender配置時に別途スケール指定が必要
