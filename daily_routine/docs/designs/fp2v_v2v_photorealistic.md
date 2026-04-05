# V2V フォトリアル動画化 設計書

## 1. 概要

Blenderでレンダリングしたカメラカット動画をV2V（Video-to-Video）AIサービスに入力し、フォトリアルなインテリアウォークスルー動画に変換するスキル。

**対応パイプラインステップ**: Floor Plan to Video ステップ7
**入力元**: `floor_plan_to_video_sub_camera` スキル（ステップ6）の出力

### 参照PoC

- `poc/3dcg_poc9/run_v2v.py`（V2V API呼び出し）
- `poc/3dcg_poc9/render_walkthrough.py`（Blenderウォークスルーレンダリング、参考）

## 2. 入出力

### 入力

| 項目 | 形式 | 説明 |
|------|------|------|
| レンダリング動画 | `.mp4` | `floor_plan_to_video_sub_camera` が出力したカメラカット動画 |
| スタイルプロンプト | テキスト | フォトリアル変換の指示（最大2500文字） |
| スタイル参照画像 | PNG / JPG（任意） | 目指すインテリアスタイルの参照画像 |

### 出力

| 項目 | 形式 | 説明 |
|------|------|------|
| フォトリアル動画 | `.mp4` | V2V変換後の動画 |

## 3. 処理フロー

```
[1] 動画のGCSアップロード
    ├─ gcloud storage cp でGCSバケットにアップロード
    └─ → 公開URLを取得

[2] （任意）スタイル参照画像のアップロード
    └─ 同様にGCSへアップロード → URL取得

[3] V2V API呼び出し
    ├─ サービス選択: Kling V3 / Luma ray-2 / Runway gen4
    ├─ 動画URL + プロンプト + （参照画像URL）を送信
    └─ → タスクIDを取得

[4] ポーリング（完了待機）
    ├─ 5秒間隔 × 最大120回 = 最大10分
    └─ status: queued → processing → completed / failed

[5] 動画ダウンロード
    └─ 完成動画URLからMP4をダウンロード
```

## 4. 対応V2Vサービス

### Kling V3 Omni（推奨）

PoCでの評価結果、3D→フォトリアル変換の品質が最も高い。

| 項目 | 値 |
|------|-----|
| APIキー環境変数 | `DAILY_ROUTINE_API_KEY_KLING_AK`, `DAILY_ROUTINE_API_KEY_KLING_SK` |
| video_reference_type | `base`（モーション保持、推奨） |
| cfg_scale | 0〜1（0=創造的、1=忠実） |
| duration | 3〜15秒 |
| aspect_ratio | `auto`, `16:9`, `9:16`, `1:1` |

### Luma ray-2

| 項目 | 値 |
|------|-----|
| エンドポイント | `POST https://api.lumalabs.ai/dream-machine/v1/generations/video/modify` |
| APIキー環境変数 | `DAILY_ROUTINE_API_KEY_LUMA` |
| mode | `adhere_1`〜`adhere_3`（忠実）, `flex_1`〜`flex_3`（自由） |
| ステータス確認 | `GET /v1/generations/{id}` |
| state | `queued` → `processing` → `completed` / `failed` |

### Runway gen4

| 項目 | 値 |
|------|-----|
| エンドポイント | `POST https://api.dev.runwayml.com/v1/video_to_video` |
| APIキー環境変数 | `DAILY_ROUTINE_API_KEY_RUNWAY` |
| モデル | `gen4_aleph`（デフォルト）, `gen4_turbo` |
| ヘッダー | `X-Runway-Version: 2024-11-06` |
| ステータス確認 | `GET /v1/tasks/{id}` |
| status | `QUEUED` → `IN_PROGRESS` → `SUCCEEDED` / `FAILED` |

## 5. GCSアップロード

V2V APIは公開URLを要求するため、ローカル動画をGCSにアップロードする。

```python
def upload_to_gcs(local_path: Path, bucket_name: str) -> str:
    gcs_dest = f"gs://{bucket_name}/v2v/{local_path.name}"
    subprocess.run(["gcloud", "storage", "cp", str(local_path), gcs_dest])
    return f"https://storage.googleapis.com/{bucket_name}/v2v/{local_path.name}"
```

- `gcloud` CLIが認証済みであること
- バケットにパブリック読み取りアクセスが必要

## 6. 定数

```python
POLL_INTERVAL = 5         # ポーリング間隔（秒）
MAX_POLL_COUNT = 120      # 最大ポーリング回数（= 10分タイムアウト）
HTTP_TIMEOUT = 120        # HTTPリクエストタイムアウト（秒）
```

## 7. 実行方法

```bash
uv run python scripts/run_v2v.py \
  --video {input_mp4} \
  --gcs-bucket {bucket_name} \
  --service kling \
  --prompt "photorealistic interior walkthrough with natural lighting and wood textures" \
  --style-image {style_reference.png} \
  --output-dir {output_dir}
```

### パラメータ

| 引数 | 必須 | 説明 |
|------|------|------|
| `--video` | Yes | 入力MP4ファイルパス |
| `--gcs-bucket` | Yes | GCSバケット名 |
| `--service` | Yes | `kling` / `luma` / `runway` |
| `--prompt` | Yes | スタイル変換プロンプト |
| `--style-image` | No | スタイル参照画像 |
| `--output-dir` | Yes | 出力ディレクトリ |
| `--mode` | No | Luma用: `adhere_1`等 |
| `--model` | No | Runway用: `gen4_aleph`等 |

## 8. 依存関係

| コンポーネント | バージョン | 用途 |
|-------------|----------|------|
| httpx | >=0.27 | HTTP通信 |
| python-dotenv | >=1.0 | 環境変数読み込み |
| gcloud CLI | - | GCSアップロード |

### 環境変数

```bash
# .env に設定（使用するサービスに応じて）
DAILY_ROUTINE_API_KEY_KLING_AK=xxxxx
DAILY_ROUTINE_API_KEY_KLING_SK=xxxxx
DAILY_ROUTINE_API_KEY_LUMA=xxxxx
DAILY_ROUTINE_API_KEY_RUNWAY=xxxxx
```

## 9. エラーハンドリング

| 状況 | 対処 |
|------|------|
| 動画ファイル不在 | FileNotFoundError |
| APIキー未設定 | エラーメッセージ表示して終了 |
| GCSアップロード失敗 | gcloudエラー出力 |
| V2Vタスク失敗 | failure_reason を表示して RuntimeError |
| タイムアウト（10分超過） | 最大ポーリング回数到達で終了 |

## 10. 手動ステップ

- **実行前**: GCSバケットの作成・認証設定（`gcloud auth application-default login`）
- **実行前**: V2VサービスのAPIキーを取得し `.env` に設定
- **実行前**: スタイルプロンプトの作成（`/docs/guidelines/visual_prompt.md` 参照）
- **実行後**: 出力動画の品質確認（空間構造の保持度、スタイルの適用度）
- **実行後**: 品質不足の場合、プロンプト修正やサービス/パラメータ変更して再実行

## 11. サービス選定の知見（PoCから）

| 観点 | Kling V3 | Luma ray-2 | Runway gen4 |
|------|----------|------------|-------------|
| 空間構造の保持 | 最良 | 良 | 良 |
| テクスチャ品質 | 高 | 中〜高 | 中 |
| 処理時間 | 1〜3分 | 1.5〜3分 | 1.5〜5分 |
| 推奨用途 | 本番用 | 比較検証 | 比較検証 |

- `video_reference_type: "base"` （Kling）でモーション保持が最も安定
- `adhere_1`（Luma）が最も忠実だが、やや保守的
- 5〜10秒の動画が最適（長すぎると品質低下）
