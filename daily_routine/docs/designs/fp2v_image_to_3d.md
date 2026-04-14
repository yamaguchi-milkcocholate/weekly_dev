# 画像→3Dモデル変換 設計書

## 1. 概要

オブジェクトの画像をTripo AI APIに送信し、GLB形式の3Dモデルを生成するスキル。単一画像・マルチビュー（最大4画角）に対応し、複数オブジェクトを並列変換する。

**対応パイプラインステップ**: Floor Plan to Video ステップ3
**出力先**: `floor_plan_to_video_sub_placement` スキル（ステップ5）でscene.blendに配置

### 参照PoC

- `poc/3dcg_poc2/tripo_image_to_3d.py`

## 2. 入出力

### 入力

| 項目 | 形式 | 説明 |
|------|------|------|
| 入力ディレクトリ | ディレクトリ | オブジェクトごとのサブディレクトリを含む |
| オブジェクト画像 | PNG / JPG / JPEG / WEBP | 1〜4枚の画角別画像 |

#### 入力ディレクトリ構造

```
input_dir/
├── chair/              # オブジェクト名 = ディレクトリ名
│   ├── front.png       # 正面（必須 or 唯一の画像）
│   ├── left.jpg        # 左側面（任意）
│   ├── back.png        # 背面（任意）
│   └── right.webp      # 右側面（任意）
├── desk/
│   └── photo.png       # 1枚のみ → 単一画像モード
└── lamp/
    ├── front.jpg
    └── back.jpg         # 2枚でもOK
```

#### 画角の判定ルール

ファイル名のプレフィックスで画角を判定（大文字小文字不問）:

| プレフィックス | 画角 | API配列インデックス |
|-------------|------|---------------------|
| `front` | 正面 (0°) | 0 |
| `left` | 左側面 (90°) | 1 |
| `back` | 背面 (180°) | 2 |
| `right` | 右側面 (270°) | 3 |

- `front`プレフィックスがない場合、唯一の画像をfront扱い
- 画像1枚 → `image_to_model`（単一画像API）
- 画像2枚以上 → `multiview_to_model`（マルチビューAPI）

### 出力

| 項目 | 形式 | 説明 |
|------|------|------|
| 3Dモデル | `.glb` | glTF binary 2.0 形式（10〜32MB程度） |
| プレビュー画像 | `.webp` | 生成モデルのプレビュー（任意） |

## 3. 処理フロー

```
[1] オブジェクトディレクトリ走査
    ├─ 各サブディレクトリをオブジェクトとして認識
    ├─ 画像ファイルをビュー名に分類（front/left/back/right）
    └─ セマフォで並列数を制御

[2] 画像アップロード（オブジェクトごと）
    ├─ POST /v2/openapi/upload（multipart form）
    ├─ MIME type: 拡張子から自動判定
    └─ → image_token を取得

[3] タスク作成
    ├─ 単一画像: POST /v2/openapi/task { "type": "image_to_model", "file": {...} }
    ├─ マルチビュー: POST /v2/openapi/task { "type": "multiview_to_model", "files": [...] }
    └─ → task_id を取得

[4] ポーリング（完了待機）
    ├─ GET /v2/openapi/task/{task_id}
    ├─ 5秒間隔 × 最大60回 = 最大5分
    ├─ status: success / failed / cancelled / unknown
    └─ progress: 0〜100%

[5] モデルダウンロード
    ├─ output.model → GLBファイル
    └─ output.rendered_image → プレビューWebP（任意）
```

### 並列実行

- asyncio + httpx.AsyncClient による非同期並列処理
- `asyncio.Semaphore` で同時実行数を制御（デフォルト: 3）
- オブジェクト単位で並列化（1オブジェクト内のアップロードは直列）
- 1オブジェクトの失敗は他に影響しない

## 4. API仕様

### エンドポイント

| フェーズ | エンドポイント | メソッド | 認証 |
|---------|-------------|---------|------|
| アップロード | `https://api.tripo3d.ai/v2/openapi/upload` | POST | Bearer |
| タスク作成 | `https://api.tripo3d.ai/v2/openapi/task` | POST | Bearer |
| ステータス確認 | `https://api.tripo3d.ai/v2/openapi/task/{task_id}` | GET | Bearer |
| ダウンロード | レスポンス内URL | GET | Bearer |

### 認証

- ヘッダー: `Authorization: Bearer {api_key}`
- APIキー形式: `tsk_` プレフィックス
- 環境変数: `DAILY_ROUTINE_API_KEY_TRIPO`

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

`files`配列のインデックスが画角に対応（0=front, 1=left, 2=back, 3=right）。frontは必須。

### MIMEタイプマッピング

| 拡張子 | MIME type |
|--------|----------|
| .jpg / .jpeg | image/jpeg |
| .png | image/png |
| .webp | image/webp |

## 5. 定数

```python
BASE_URL = "https://api.tripo3d.ai"
POLL_INTERVAL = 5              # ポーリング間隔（秒）
MAX_POLL_COUNT = 60            # 最大ポーリング回数（= 5分タイムアウト）
HTTP_TIMEOUT = 120             # HTTPリクエストタイムアウト（秒）
DEFAULT_MAX_CONCURRENT = 3     # デフォルト並列数
```

## 6. 実行方法

```bash
# 基本実行（出力: input_dir/output/）
uv run python floor_plan_to_video_sub_glb/image_to_3d.py input/objects/

# 出力先を指定
uv run python floor_plan_to_video_sub_glb/image_to_3d.py input/objects/ --output-dir output/models/

# 並列数を指定
uv run python floor_plan_to_video_sub_glb/image_to_3d.py input/objects/ --max-concurrent 5
```

## 7. 依存関係

| コンポーネント | バージョン | 用途 |
|-------------|----------|------|
| httpx | >=0.27 | HTTP非同期通信 |
| python-dotenv | >=1.0 | 環境変数読み込み |

### 環境変数

```bash
# .env に設定
DAILY_ROUTINE_API_KEY_TRIPO=tsk_xxxxxxxxxxxxx
```

## 8. エラーハンドリング

| 状況 | 対処 |
|------|------|
| ディレクトリ内に画像がない | スキップしてログ出力 |
| マルチビューでfrontがない | 最初の画像をfront扱い（警告ログ） |
| APIキー未設定 | 即時終了 |
| アップロード失敗 | そのオブジェクトをスキップし他は続行 |
| タスク失敗（failed/cancelled） | そのオブジェクトをスキップし他は続行 |
| タイムアウト（5分超過） | そのオブジェクトをスキップし他は続行 |
| 全オブジェクト失敗 | 終了コード1 |

## 9. 手動ステップ

- **実行前**: Tripo AI APIキーを取得し `.env` に設定
- **実行前**: オブジェクト画像を用意（背景透過推奨、画角別にファイル名設定）
- **実行後**: GLBファイルを3Dビューアで確認（スケール・向きの検証）
- **実行後**: `floor_plan_to_video_sub_placement` で使用する `assets.json` にGLBパスを登録

## 10. 品質に関する知見（PoCから）

- 背景透過画像の方が品質が高い傾向
- マルチビューは単一画像より形状精度が高い（特に背面の再現）
- 1オブジェクトあたり約2〜5分の処理時間
- 生成モデルのサイズは10〜32MB（オブジェクトの複雑さによる）
- スケールはモデルごとに異なるため、Blender配置時に `assets.json` でスケール指定が必要
