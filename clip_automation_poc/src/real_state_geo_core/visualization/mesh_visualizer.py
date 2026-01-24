"""メッシュデータの3D可視化モジュール（駅別色分け対応）"""

import logging
import os

from pathlib import Path

import pandas as pd
import pydeck as pdk

from dotenv import load_dotenv

# 環境変数を読み込み
load_dotenv()

logger = logging.getLogger(__name__)


class MeshVisualizer:
    """東京23区メッシュマスターデータをpydeckで3D可視化するクラス

    駅別に色分けし、徒歩分数を高さとして表現します。
    """

    def __init__(self, csv_path: Path) -> None:
        """初期化処理

        Args:
            csv_path: tokyo_23_mesh_master.csvのパス

        Raises:
            FileNotFoundError: CSVファイルが存在しない場合
        """
        if not csv_path.exists():
            raise FileNotFoundError(f"CSVファイルが見つかりません: {csv_path}")

        logger.info(f"メッシュデータを読み込み中: {csv_path}")
        self.df = pd.read_csv(csv_path)
        logger.info(f"読み込み完了: {len(self.df)} メッシュ")

        # 駅別の色を割り当て
        self._assign_station_colors()

    def _assign_station_colors(self) -> None:
        """各駅に一意のRGB色を割り当て、DataFrameにcolorカラムを追加

        ハッシュ値ベースでRGB色を生成します。
        視認性を高めるため、明度と彩度を調整しています。
        """
        unique_stations = self.df["station_name"].unique()
        station_count = len(unique_stations)
        logger.info(f"ユニークな駅数: {station_count}")

        # カラーマップの作成
        station_color_map = {}

        # ハッシュ値ベースでRGB色を生成
        for station in unique_stations:
            hash_val = hash(station)
            # ハッシュ値から3つの異なる値を抽出
            r = ((hash_val & 0xFF0000) >> 16) % 200 + 55  # 55-255の範囲
            g = ((hash_val & 0x00FF00) >> 8) % 200 + 55
            b = (hash_val & 0x0000FF) % 200 + 55
            station_color_map[station] = [r, g, b]

        # DataFrameにcolorカラムを追加
        self.df["color"] = self.df["station_name"].map(station_color_map)
        logger.info("駅別の色割り当てが完了しました")

    def create_visualization(self, output_path: Path, elevation_scale: int = 40, radius: int = 60) -> None:
        """3D可視化を生成してHTMLファイルとして保存

        Args:
            output_path: 出力するHTMLファイルのパス
            elevation_scale: 高さ（walk_minutes）のスケール係数（デフォルト: 40）
            radius: カラムの半径（メートル、デフォルト: 60）
        """
        logger.info("pydeck ColumnLayerを作成中...")

        # DataFrameをdict形式に変換
        data = self.df.to_dict("records")

        # ColumnLayerの設定
        layer = pdk.Layer(
            "ColumnLayer",
            data=data,
            get_position=["longitude", "latitude"],
            get_elevation="walk_minutes",
            elevation_scale=elevation_scale,
            radius=radius,
            get_fill_color="color",
            pickable=True,
            auto_highlight=True,
        )

        # ビューポートの設定（東京23区中心）
        view_state = pdk.ViewState(
            latitude=35.6895,
            longitude=139.6917,
            zoom=10,
            pitch=45,
            bearing=0,
        )

        # Tooltipの設定
        tooltip = {
            "html": """
            <b>駅名:</b> {station_name}<br/>
            <b>徒歩:</b> {walk_minutes} 分<br/>
            <b>住所:</b> {city_name} {district_name}
            """,
            "style": {"backgroundColor": "steelblue", "color": "white"},
        }

        # Mapboxトークンの取得と設定
        mapbox_token = os.getenv("MAPBOX_TOKEN")
        if not mapbox_token:
            logger.warning("MAPBOX_TOKENが設定されていません。地図が表示されない可能性があります。")
        else:
            # pydeckはMAPBOX_API_KEYという環境変数名を使用
            os.environ["MAPBOX_API_KEY"] = mapbox_token

        # Deckオブジェクトの作成
        deck = pdk.Deck(
            map_provider="mapbox",
            layers=[layer],
            initial_view_state=view_state,
            tooltip=tooltip,
            map_style="mapbox://styles/mapbox/dark-v10",
        )

        # HTMLファイルとして保存
        output_path.parent.mkdir(parents=True, exist_ok=True)
        deck.to_html(str(output_path))
        logger.info(f"可視化ファイルを保存しました: {output_path}")
