import polars as pl


def convert_for_pydeck(df: pl.DataFrame) -> list[dict]:
    """
    pydeck可視化用データ（list[dict]）に変換します。

    Args:
        df (pl.DataFrame): 可視化対象のPolars DataFrame。

    Returns:
        list[dict]: pydeckで利用可能なデータリスト。
    """
    # 必要なカラムのみ抽出
    columns_needed = [
        "longitude",
        "latitude",
        "elevation",
        "color",
        "DistrictName",
        "TradePrice",
        "Area",
        "BuildingYear",
    ]
    available_cols = [col for col in columns_needed if col in df.columns]
    # 可視化用DataFrameを作成
    df_vis = df.select(available_cols)
    # 数値カラムをfloat型に変換
    cast_cols = []
    for col in ["longitude", "latitude", "elevation", "TradePrice", "Area"]:
        if col in df_vis.columns:
            cast_cols.append(pl.col(col).cast(pl.Float64))
    if cast_cols:
        df_vis = df_vis.with_columns(cast_cols)
    # 文字列カラムをUtf8型に変換
    if "BuildingYear" in df_vis.columns:
        df_vis = df_vis.with_columns(pl.col("BuildingYear").cast(pl.Utf8))
    if "DistrictName" in df_vis.columns:
        df_vis = df_vis.with_columns(pl.col("DistrictName").cast(pl.Utf8))
    # DataFrameをlist[dict]に変換して返却
    return df_vis.to_dicts()
