"""
東京23区メッシュマスターの3D可視化スクリプト（駅別色分け）

Usage:
    python scripts/visualize_mesh_colored.py
"""

import logging

from pathlib import Path

from real_state_geo_core.visualization.mesh_visualizer import MeshVisualizer

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> None:
    """メッシュ可視化のメイン処理"""
    # プロジェクトルートディレクトリ
    project_root = Path(__file__).parent.parent

    # 入力CSVのパス
    csv_path = project_root / "data" / "tokyo_23_mesh_master.csv"

    # 出力HTMLのパス
    output_path = project_root / "output" / "mesh_verification_colored.html"

    # 可視化の実行
    visualizer = MeshVisualizer(csv_path=csv_path)
    visualizer.create_visualization(
        output_path=output_path,
        elevation_scale=40,
        radius=60,
    )

    logging.info("完了しました！")
    logging.info(f"ブラウザで開く: {output_path}")


if __name__ == "__main__":
    main()
