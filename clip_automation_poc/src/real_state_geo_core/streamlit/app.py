#!/usr/bin/env python3
"""東京23区メッシュ坪単価 3D可視化アプリケーション

事前計算されたメッシュ坪単価データをPyDeck 3Dマップで可視化します。
築年数範囲、専有面積などの条件を選択して、異なる価格マップを表示できます。

使用方法:
    streamlit run src/real_state_geo_core/streamlit/app.py
"""

import os

from pathlib import Path

import pydeck as pdk
import streamlit as st

from dotenv import load_dotenv

from real_state_geo_core.streamlit.data_loader import MeshPriceDataLoader

# 環境変数読み込み
load_dotenv()

# プロジェクトルート
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
OUTPUTS_DIR = PROJECT_ROOT / "outputs"

# Mapbox トークン
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

# ページ設定
st.set_page_config(
    page_title="東京23区メッシュ坪単価マップ",
    page_icon="🏘️",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def load_data_loader() -> MeshPriceDataLoader:
    """データローダーを初期化します（キャッシュ）。"""
    return MeshPriceDataLoader(output_dir=OUTPUTS_DIR)


@st.cache_data
def load_mesh_data(map_key: str) -> tuple[list[dict], dict]:
    """メッシュデータを読み込みます（キャッシュ）。

    Args:
        map_key: マップキー

    Returns:
        tuple: (PyDeck用データ, メタデータ)
    """
    loader = load_data_loader()
    df = loader.load_mesh_price_data(map_key)
    metadata = loader.get_metadata(map_key)

    if df is None or metadata is None:
        return [], {}

    pydeck_data = loader.prepare_pydeck_data(df)
    return pydeck_data, metadata


def format_price(price: float) -> str:
    """価格を読みやすい形式にフォーマットします。"""
    if price >= 1e8:
        return f"{price / 1e8:.2f}億円"
    elif price >= 1e4:
        return f"{price / 1e4:.0f}万円"
    else:
        return f"{price:.0f}円"


def create_pydeck_layer(data: list[dict], color_range: list[list[int]]) -> pdk.Layer:
    """PyDeck ColumnLayerを作成します。

    Args:
        data: メッシュ価格データ
        color_range: カラーレンジ

    Returns:
        pdk.Layer: ColumnLayer
    """
    return pdk.Layer(
        "ColumnLayer",
        data=data,
        get_position=["longitude", "latitude"],
        get_elevation="predicted_price",
        elevation_scale=0.001,  # 価格を高さにマッピング（スケール調整）
        radius=50,  # 柱の半径（メートル）
        get_fill_color="[255, predicted_price / 10000, 100, 200]",  # 価格に応じた色
        pickable=True,
        auto_highlight=True,
    )


def main():
    """メインアプリケーション"""
    st.title("🏘️ 東京23区メッシュ坪単価マップ")
    st.markdown("**2025年想定の坪単価を100mメッシュで可視化**")

    # データローダー初期化
    loader = load_data_loader()

    if not loader.available_maps:
        st.error("メッシュ価格マップが見つかりません。先に generate_mesh_price_variations.py を実行してください。")
        st.stop()

    # 利用可能な条件を取得
    conditions = loader.get_available_conditions()

    # サイドバー: 条件選択
    st.sidebar.header("📋 物件条件選択")

    # 築年数範囲
    age_range_options = [f"{start}〜{end}年" for start, end in conditions["age_ranges"]]
    age_range_selected_idx = st.sidebar.selectbox(
        "築年数範囲",
        range(len(age_range_options)),
        format_func=lambda i: age_range_options[i],
        index=0,
    )
    age_range_selected = conditions["age_ranges"][age_range_selected_idx]

    # 専有面積
    area_options = [f"{area:.0f}㎡" for area in conditions["areas"]]
    area_selected_idx = st.sidebar.selectbox(
        "専有面積",
        range(len(area_options)),
        format_func=lambda i: area_options[i],
        index=0,
    )
    area_selected = conditions["areas"][area_selected_idx]

    # 建物構造（現状はRC固定）
    structure = "RC"

    st.sidebar.markdown("---")
    st.sidebar.info(
        f"**選択中の条件**\n\n"
        f"- 築年数: {age_range_selected[0]}〜{age_range_selected[1]}年\n"
        f"- 面積: {area_selected:.0f}㎡\n"
        f"- 構造: {structure}"
    )

    # マップキー取得
    map_key = loader.get_map_key(age_range_selected, area_selected, structure)

    if map_key is None:
        st.error("選択された条件に対応するデータが見つかりません。")
        st.stop()

    # データ読み込み
    with st.spinner("データ読み込み中..."):
        pydeck_data, metadata = load_mesh_data(map_key)

    if not pydeck_data:
        st.error("データの読み込みに失敗しました。")
        st.stop()

    # 統計情報
    prices = [d["predicted_price"] for d in pydeck_data]
    avg_price = sum(prices) / len(prices)
    min_price = min(prices)
    max_price = max(prices)

    # メトリクス表示
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("メッシュ数", f"{len(pydeck_data):,}件")
    with col2:
        st.metric("平均坪単価", format_price(avg_price))
    with col3:
        st.metric("最小坪単価", format_price(min_price))
    with col4:
        st.metric("最大坪単価", format_price(max_price))

    # カラーレンジ（価格に応じた色）
    color_range = [
        [0, 255, 0],  # 緑（低価格）
        [255, 255, 0],  # 黄色
        [255, 128, 0],  # オレンジ
        [255, 0, 0],  # 赤（高価格）
    ]

    # PyDeck ColumnLayer作成
    column_layer = create_pydeck_layer(pydeck_data, color_range)

    # 初期ビュー設定（東京23区の中心）
    view_state = pdk.ViewState(
        latitude=35.6895,
        longitude=139.6917,
        zoom=11,
        pitch=45,
        bearing=0,
    )

    # PyDeckマップレンダリング
    st.pydeck_chart(
        pdk.Deck(
            layers=[column_layer],
            initial_view_state=view_state,
            map_style="mapbox://styles/mapbox/dark-v10",
            tooltip={
                "html": "<b>メッシュID:</b> {mesh_id}<br>"
                "<b>坪単価:</b> ¥{predicted_price_str}<br>"
                "<b>区:</b> {city_name}<br>"
                "<b>地区:</b> {district_name}",
                "style": {"backgroundColor": "steelblue", "color": "white"},
            },
            map_provider="mapbox",
            api_keys={"mapbox": MAPBOX_TOKEN} if MAPBOX_TOKEN else None,
        )
    )

    # メタデータ表示
    with st.expander("📊 データ詳細情報"):
        st.json(metadata)

    # フッター
    st.markdown("---")
    st.markdown(
        "*データソース: 国土交通省 不動産情報ライブラリ | "
        "モデル: LightGBM | "
        f"生成日時: {metadata.get('generation_timestamp', 'N/A')}*"
    )


if __name__ == "__main__":
    main()
