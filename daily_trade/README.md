# daily_trade

# 開発

## 準備

```shell
# GCPの認証情報をローカルに保存
PROJECT_ID=weekly-dev-20251013
gcloud projects get-iam-policy ${PROJECT_ID}

gcloud secrets versions access latest --secret="terraform-key" --project "${PROJECT_ID}" > sa-key.json
```

### 準備

```shell
# パッケージを開発モードでインストール
uv pip install -e .
```

```shell
uv run python -m uvicorn src.daily_trade.app:app --host 0.0.0.0 --port 8000 --reload
```
