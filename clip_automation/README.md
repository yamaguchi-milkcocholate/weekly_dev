# CLIP AUTOMATION

短編動画の制作自動化

## 開発

### dify の更新

```bash
git submodule update --remote --merge
```

### 別 PC でクローンする時

単なる git clone では dify/ の中身が空になるため、以下のオプションが必要です。

```bash
git clone --recursive https://github.com/yamaguchi-milkcocholate/weekly_dev.git
```

### Python API を起動

```bash
cd engine && uv run uvicorn main:app --reload
```
