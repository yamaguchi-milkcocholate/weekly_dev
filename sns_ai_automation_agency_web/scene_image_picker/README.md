# SNS 投稿画像選択システム

Google スプレッドシート連携による画像選択アプリケーション。各シーンの候補画像から、SNS 投稿に最適な画像を選択できます。

Original Figma design: https://www.figma.com/design/Zf6j2DPtk0S8PAcmUtIkLM/%E7%94%BB%E5%83%8F%E9%81%B8%E6%8A%9E%E6%A5%AD%E5%8B%99%E3%82%A2%E3%83%97%E3%83%AA

## 機能

- ✅ Google スプレッドシートとの連携（Google Apps Script 経由)
- ✅ シーンごとの画像選択
- ✅ 選択進捗の可視化
- ✅ リアルタイムプレビュー
- ✅ レスポンシブデザイン

## セットアップ

### 1. 依存関係のインストール

```bash
npm i
```

### 2. 開発サーバーの起動（モックデータで開発）

```bash
npm run dev
```

環境変数が未設定の場合、自動的にモックデータが使用されます。すぐに開発を始められます。

### 3. Google Apps Script との連携（本番環境用・オプション）

詳細は [gas/README.md](./gas/README.md) を参照してください。

1. Google スプレッドシートを作成
2. シート「scenes」と「images」を作成
3. サンプルデータ（gas/sample*data*\*.csv）をインポート
4. Apps Script をデプロイ（gas/Code.gs）
5. デプロイ URL を取得

### 4. 環境変数の設定（GAS 連携時のみ）

```bash
cp .env.example .env
```

`.env` ファイルを編集して GAS の URL を設定:

```
VITE_GAS_API_URL=https://script.google.com/macros/s/YOUR_SCRIPT_ID/exec
```

サーバーを再起動すると、GAS からデータを取得します。

## ディレクトリ構成

```
scene_image_picker/
├── src/
│   ├── components/     # UIコンポーネント
│   ├── lib/           # API通信など
│   ├── types/         # TypeScript型定義
│   └── App.tsx        # メインアプリケーション
├── gas/               # Google Apps Script関連
│   ├── Code.gs        # GASスクリプト
│   ├── README.md      # GASセットアップガイド
│   └── sample_data_*.csv  # サンプルデータ
└── .env.example       # 環境変数テンプレート
```

## データ構造

### シーン情報 (scenes シート)

| カラム      | 説明                  |
| ----------- | --------------------- |
| id          | シーン ID（ユニーク） |
| name        | シーン名              |
| telop       | テロップ文言          |
| description | 説明文                |

### 画像データ (images シート)

| カラム    | 説明              |
| --------- | ----------------- |
| scene_id  | 対応するシーン ID |
| image_url | 画像 URL          |

## API 仕様

### GET /exec?action=getScenes

シーン一覧と画像データを取得

**レスポンス:**

```json
{
  "scenes": [
    {
      "id": 1,
      "name": "ビジネスミーティング",
      "telop": "重要な戦略会議",
      "description": "..."
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
