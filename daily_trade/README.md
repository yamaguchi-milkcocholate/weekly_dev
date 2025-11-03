# daily_trade

株価予測モデルの実験・開発フレームワーク

## 📈 実験実行

詳細な実験手順と記録は以下のドキュメントを参照：

- [experiments/RESTART_GUIDE.md](experiments/RESTART_GUIDE.md) - **🔄 実験の中断・再開ガイド**
- [experiments/STATUS.yaml](experiments/STATUS.yaml) - **📊 現在の実験進捗状況**
- [experiments/EXPERIMENT_LOG.md](experiments/EXPERIMENT_LOG.md) - **実験記録とデータサイエンティストの分析観点**
- [EXPERIMENT_OVERVIEW.md](EXPERIMENT_OVERVIEW.md) - 実験パラメータ仕様
- [EXPERIMENT_FLOW.md](EXPERIMENT_FLOW.md) - 実行フロー
- [EXPERIMENT_SYSTEM_PROMPT.md](EXPERIMENT_SYSTEM_PROMPT.md) - システム全体ドキュメント

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
