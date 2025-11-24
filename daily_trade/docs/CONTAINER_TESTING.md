# ローカルコンテナ検証手順

## 🌐 アクセス先

コンテナ起動後、以下の URL でアクセスできます：

- **API Root**: http://localhost:8000/
- **API Documentation**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health
- **Example Endpoint**: http://localhost:8000/example

## 🧪 手動テスト例

```bash
# ヘルスチェック
curl http://localhost:8000/health

# サンプルエンドポイント
curl http://localhost:8000/example

# JSONレスポンスを整形表示
curl -s http://localhost:8000/health | jq .
```

## 🔧 コンテナの起動

```bash
# ログを確認
docker compose logs

# コンテナの状態を確認
docker compose ps

# イメージを再ビルド
docker compose build --no-cache
```
