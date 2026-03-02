---
paths:
  - poc/**/*.py
  - src/**/*.py
  - docs/**/*.md
---

# Gemini モデル指定ルール

画像生成とテキスト生成でモデル系列が異なる。

- **画像生成（I2I編集・画像出力）**: `gemini-3-pro-image-preview`（Nano Banana Pro、高品質）
- **画像生成（高速・大量処理）**: `gemini-3.1-flash-image-preview`（Nano Banana 2）
- **テキスト生成（分析・推論）**: `gemini-3-flash-preview`
