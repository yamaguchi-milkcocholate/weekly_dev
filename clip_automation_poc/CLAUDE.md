# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## プロジェクト概要

ショート動画の自動化のPoC検証

国土交通省の不動産取引データ30年分を可視化し、YouTube Shorts動画を自動生成するPoCプロジェクト。MLIT APIからデータ取得→Polarsで加工→PyDeckで可視化→1080x1920の縦型動画を生成する構成。

## コマンド

```bash
# 依存関係インストール（uvパッケージマネージャー使用）
uv sync

# コードフォーマット
ruff format src/

# リント
ruff check src/

# リント自動修正
ruff check --fix src/

# Jupyter Lab起動
jupyter lab
```

## アーキテクチャ

### 6フェーズパイプライン（一部実装済み）

```
Phase 1: データ取得 (RealEstateDataFetcher) ✓
    ↓
Phase 2: 分析・クリーニング (Polars) ✓
    ↓
Phase 3: 可視化 (PyDeck) - 一部実装
    ↓
Phase 4: AI拡張 (Runway AI) - 未実装
    ↓
Phase 5: 動画編集 (FFmpeg) - 未実装
    ↓
Phase 6: エクスポート (YouTube Shorts形式) - 未実装
```

### 主要コンポーネント

**RealEstateDataFetcher** (`src/real_state_geo_core/data/fetcher.py`)

- `fetch_real_estate(year, city_code)`: MLIT APIから取引データ取得（gzip対応）
- `clean_real_estate_data(api_response)`: Polars DataFrameに変換、数値フィールドをクリーニング
- `fetch_station_master(csv_path)`: ekidata.jp CSVから駅名→(緯度, 経度)の辞書を作成
- `fetch_boundary_geojson(ward_code, save_path)`: JapanCityGeoJsonから区境界を取得
- `geocode_random(area_sqm, center_lat, center_lon, max_radius_km)`: 可視化用の散布座標を生成

**可視化** (`src/real_state_geo_core/visualization/pydeck.py`)

- `convert_for_pydeck(df)`: Polars DataFrameをpydeck形式に変換

### データソース

- **不動産データ**: 国土交通省 不動産情報ライブラリAPI（.envにREINFOLIB_API_KEY必要）
- **駅データ**: ekidata.jp CSV（`data/station/station20251211free.csv`）
- **行政境界**: JapanCityGeoJson GitHubリポジトリ
- **地図タイル**: Mapbox（.envにMAPBOX_TOKEN必要）

## コードスタイル

pyproject.tomlのRuff設定:

- 行の長さ: 120文字
- Pythonターゲット: 3.13
- ダブルクォート、スペースインデント
- 有効ルール: E, W, F, I (isort), B, C4, UP

## 主要ディレクトリ

- `src/real_state_geo_core/`: メインPythonパッケージ
- `notebooks/`: Jupyter実験（01_pydeck_experiment.ipynb）
- `output/`: 生成されたHTML可視化ファイル（gitignore対象）
- `data/`: 生データ、加工済みデータ、駅データ
- `docs/`: PLANNING.md（企画書）、SYSTEM_DESIGN.md（技術仕様書）

# Commands

- 仕様書更新: `claude /spec-update "SKILLに基づき、現在のコードを解析して、実装済みの機能を docs/SYSTEM_DESING.md に反映して"`
