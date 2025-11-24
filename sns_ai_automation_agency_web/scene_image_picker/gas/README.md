# Google Apps Script との連携

## 1. スプレッドシートの準備

### シート 1: scenes

シーン情報を管理するシート

| id  | name                   | telop          | description                               |
| --- | ---------------------- | -------------- | ----------------------------------------- |
| 1   | ビジネスミーティング   | 重要な戦略会議 | チームメンバーと共に新しいプロジェクト... |
| 2   | オフィスワークスペース | 快適な作業環境 | 生産性を高める理想的なオフィス環境で...   |
| ... | ...                    | ...            | ...                                       |

### シート 2: images

各シーンの画像 URL を管理するシート

| scene_id | image_url                             |
| -------- | ------------------------------------- |
| 1        | https://images.unsplash.com/photo-... |
| 1        | https://images.unsplash.com/photo-... |
| 2        | https://images.unsplash.com/photo-... |
| ...      | ...                                   |

## 2. GAS のセットアップ

1. Google スプレッドシートを開く
2. `拡張機能` > `Apps Script` を選択
3. `gas/Code.gs` の内容をコピー&ペースト
4. スクリプト内の `SPREADSHEET_ID` を実際のスプレッドシート ID に変更
5. 保存

## 3. デプロイ

1. `デプロイ` > `新しいデプロイ` をクリック
2. 種類: `ウェブアプリ`
3. 次のユーザーとして実行: `自分`
4. アクセスできるユーザー: `全員`
5. `デプロイ` をクリック
6. 表示されるウェブアプリの URL をコピー

## 4. フロントエンドの設定

1. `.env.example` をコピーして `.env` を作成:

   ```bash
   cp .env.example .env
   ```

2. `.env` ファイルを編集:

   ```
   VITE_GAS_API_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec
   ```

3. アプリケーションを起動:
   ```bash
   npm run dev
   ```

## 5. API エンドポイント

### GET /exec?action=getScenes

シーン一覧と画像データを取得

**レスポンス例:**

```json
{
  "scenes": [
    {
      "id": 1,
      "name": "ビジネスミーティング",
      "telop": "重要な戦略会議",
      "description": "チームメンバーと共に..."
    }
  ],
  "images": {
    "1": [
      "https://images.unsplash.com/photo-...",
      "https://images.unsplash.com/photo-..."
    ]
  }
}
```

## トラブルシューティング

### CORS エラーが発生する場合

GAS のデプロイ設定で「アクセスできるユーザー」が「全員」になっているか確認してください。

### データが取得できない場合

1. GAS エディタで `testGetScenes()` 関数を実行してログを確認
2. スプレッドシート ID が正しいか確認
3. シート名が `scenes` と `images` になっているか確認

### 画像が表示されない場合

1. 画像 URL が正しいか確認
2. URL が https://で始まっているか確認
3. Unsplash など外部サービスの URL にアクセス制限がないか確認
