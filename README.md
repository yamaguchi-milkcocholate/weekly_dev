# weekly_dev

weekly dev の資材をまとめたリポジトリ

## 開発

### ruff の設定について

公式を参考にする

- [Configuring Ruff](https://docs.astral.sh/ruff/configuration/)

### 準備

```shell
# パッケージを開発モードでインストール
uv pip install -e .
```

```shell
uv run python -m uvicorn src.daily_trade.app:app --host 0.0.0.0 --port 8000 --reload
```
