# daily_trade

# 開発

## 準備

```shell
# GCPの認証情報をローカルに保存
PROJECT_ID=weekly-dev-20251013
gcloud projects get-iam-policy ${PROJECT_ID}

gcloud secrets versions access latest --secret="terraform-key" --project "${PROJECT_ID}" > sa-key.json
```
