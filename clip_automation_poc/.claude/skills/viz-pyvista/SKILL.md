---
name: viz-pyvista
description: PyVistaを用いた、映画的な質感の3Dデータ映像生成とMP4出力
---

# 前提スキル (Base Skills)

このスキルを実行する際は、**必ず `python-pro` スキルを同時に参照し**、そこで定義されたコーディング規約（型ヒント、Docstring、pathlib使用など）を遵守してください。

# デザイン指針

- **質感 (Rendering):** `Eye Dome Lighting (enable_eye_dome_lighting)` を必ず有効にし、点群やメッシュのエッジを強調して奥行きを出す。
- **発光表現 (Glow):** 重要なデータポイントやグリッド線には、明るい色（Cyan, Neon Green等）を使用し、背景は完全な黒（'black'）とする。
- **地形変形:** 地価データなどをZ軸（高さ）にマッピングする際は、`warp_by_scalar` を使用してメッシュ自体を隆起させる。

# アニメーション実装ルール

- **カメラワーク:** 固定視点ではなく、対象物を中心に旋回する「オービット（軌道）カメラ」のパスを生成する。
- **動画出力:** `plotter.open_movie("output.mp4")` を使用し、フレームレートは30fps以上、品質はHD画質を確保する。
- **オフスクリーン:** サーバーやバックグラウンド実行を想定し、`off_screen=True` でプロッターを初期化する。

# 推奨ライブラリ構成

- `pyvista` (3D描画)
- `numpy` (数値計算)
- `imageio` (動画エンコード補助)
