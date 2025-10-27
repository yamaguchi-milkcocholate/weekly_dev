# Daily Trade API - FastAPI サンプル実装

このプロジェクトは、FastAPI を使用したシンプルな RESTful API のサンプル実装です。基本的な API エンドポイントとヘルスチェック機能を提供します。

## 🚀 機能

- **基本的な API エンドポイント**: ルートページとサンプルエンドポイント
- **ヘルスチェック**: システムの稼働状況を確認
- **自動ドキュメント生成**: Swagger UI と ReDoc による自動 API 文書化
- **型安全性**: Pydantic によるレスポンスの型検証
- **エラーハンドリング**: 適切な HTTP ステータスコードとエラーメッセージ

## 📋 前提条件

- Python 3.12+

## 🛠️ セットアップ

### 1. 依存関係のインストール

```bash
cd daily_trade
pip install -e .
```

### 2. サーバー起動

```bash
# 開発サーバー起動
python run_server.py

# または直接uvicornを使用
uvicorn src.daily_trade.app:app --host 0.0.0.0 --port 8000 --reload
```

## 📖 API ドキュメント

サーバー起動後、以下の URL で API ドキュメントにアクセスできます：

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **ヘルスチェック**: http://localhost:8000/health

## 🔌 エンドポイント

### 基本エンドポイント

| メソッド | エンドポイント | 説明                   | レスポンス形式 |
| -------- | -------------- | ---------------------- | -------------- |
| GET      | `/`            | ルートページ（HTML）   | HTML           |
| GET      | `/health`      | ヘルスチェック         | JSON           |
| GET      | `/example`     | サンプルエンドポイント | JSON           |

### エンドポイント詳細

#### GET `/`

ルートページを表示します。HTML 形式で API の概要と各ドキュメントへのリンクを提供します。

#### GET `/health`

システムの稼働状況を返します。

**レスポンス例:**

```json
{
  "status": "healthy",
  "timestamp": "2025-10-16T12:00:00.000000",
  "database": "connected",
  "version": "1.0.0"
}
```

#### GET `/example`

サンプルのエンドポイントです。基本的なレスポンス形式のテストに使用できます。

**レスポンス例:**

```json
{
  "message": "ok"
}
```

## 📝 使用例

### ヘルスチェック

```bash
curl -X GET "http://localhost:8000/health"
```

**レスポンス:**

```json
{
  "status": "healthy",
  "timestamp": "2025-10-16T12:00:00.000000",
  "database": "connected",
  "version": "1.0.0"
}
```

### サンプルエンドポイント

```bash
curl -X GET "http://localhost:8000/example"
```

**レスポンス:**

```json
{
  "message": "ok"
}
```

## 🏗️ プロジェクト構造

```
daily_trade/
├── src/
│   └── daily_trade/
│       ├── __init__.py
│       ├── app.py           # メインアプリケーション
│       └── schema.py        # Pydanticスキーマ定義
├── example/
│   └── firestore.py         # Firestore使用例（参考）
├── run_server.py            # サーバー起動スクリプト
├── pyproject.toml           # プロジェクト設定
├── Dockerfile               # Dockerコンテナ設定
├── .dockerignore            # Docker除外ファイル設定
└── API_README.md            # このファイル
```

## 🔧 技術スタック

- **FastAPI**: 高性能な Python Web フレームワーク
- **Pydantic**: データ検証とシリアライゼーション
- **Uvicorn**: ASGI サーバー

## 📊 データモデル

### ExampleResponse

```python
class ExampleResponse(BaseModel):
    message: str
```

サンプルエンドポイントのレスポンス形式を定義する Pydantic モデルです。

## 🧪 開発

### リンティング

```bash
ruff check src/
ruff format src/
```

### テスト（今後実装予定）

```bash
pytest
```

## 🚀 デプロイメント

### Cloud Run へのデプロイ

このアプリケーションは Google Cloud Run にデプロイ可能です。

#### デプロイされるファイル

- `Dockerfile` - マルチステージビルドによる最適化されたコンテナイメージ
- `.dockerignore` - ビルドサイズ最適化のための除外ファイル設定
- `cloud-run-service.yaml` - Cloud Run サービス設定
- `deploy.sh` - 自動デプロイスクリプト

#### Cloud Run の特徴

- **自動スケーリング**: リクエスト数に応じて自動でインスタンス数を調整
- **従量課金**: 使用した分だけ課金
- **ヘルスチェック**: `/health` エンドポイントでの自動監視
- **HTTPS 対応**: 自動で SSL 証明書を設定

## 📚 参考資料

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [Uvicorn Documentation](https://www.uvicorn.org/)

## 🚀 次のステップ

このサンプルを基に、以下のような機能を追加することができます：

1. **データベース統合**: SQLite、PostgreSQL、Firestore 等の接続
2. **認証・認可**: JWT トークンベースの認証
3. **ユーザー管理**: CRUD 操作の実装
4. **バリデーション**: より複雑なデータ検証ルール
5. **テスト**: pytest を使用した単体テスト・統合テスト
6. **ログ**: 構造化ログとモニタリング
7. **CI/CD**: GitHub Actions による自動デプロイ

## 🤝 コントリビューション

1. このリポジトリをフォーク
2. 機能ブランチを作成 (`git checkout -b feature/AmazingFeature`)
3. 変更をコミット (`git commit -m 'Add some AmazingFeature'`)
4. ブランチにプッシュ (`git push origin feature/AmazingFeature`)
5. Pull Request を開く

## 📄 ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。
