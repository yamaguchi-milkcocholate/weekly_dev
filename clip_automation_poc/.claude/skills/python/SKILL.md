---
name: python-pro
description: 高品質なPythonコードの記述と型ヒントの適用
---

# 指針

- すべての関数とメソッドに型ヒント（Type Hints）を付与する。
- DocstringはGoogleスタイルで記述し、Args/Returns/Raisesを明記する。
- `pathlib` を優先的に使用し、OSに依存しないパス操作を行う。
- 複雑なロジックには、処理の意図を示すコメントを日本語で記述する。
- 可能な限り `TypedDict` や `pydantic` を検討し、データの構造を明示する。
- データ処理は`polars`, `numpy`を使用する。
