# 東京23区メッシュ坪単価 3D可視化アプリケーション

事前計算されたメッシュ坪単価データをStreamlit + PyDeck 3Dマップで可視化するアプリケーションです。

## 機能

- **インタラクティブな条件選択**: サイドバーで築年数範囲と専有面積を選択
- **3D可視化**: PyDeck ColumnLayerで100mメッシュごとの坪単価を立体表示
- **統計情報**: メッシュ数、平均・最小・最大坪単価を表示
- **ツールチップ**: マウスオーバーでメッシュの詳細情報を表示

## 前提条件

以下のスクリプトを事前に実行してデータを生成しておく必要があります:

1. **メッシュマスター生成**

   ```bash
   uv run python scripts/generate_mesh_master.py --mode multi --max-walk-minutes 30
   ```

2. **モデル学習**

   ```bash
   uv run python scripts/train_price_estimator.py
   ```

3. **2025年集約統計量算出**

   ```bash
   uv run python scripts/prepare_aggregated_stats_2025.py
   ```

4. **メッシュ価格マップ生成**
   ```bash
   uv run python scripts/generate_mesh_price_variations.py
   ```

これらのスクリプトにより、`outputs/` ディレクトリに以下のファイルが生成されます:

- `mesh_price_map_2025_*.csv` - メッシュ価格マップ（10パターン）
- `mesh_price_map_2025_*_metadata.json` - メタデータ（10パターン）

## 起動方法

### 1. 依存関係のインストール

```bash
uv sync
```

### 2. 環境変数の設定

`.env` ファイルにMapboxトークンを設定します:

```bash
MAPBOX_TOKEN=your_mapbox_token_here
```

Mapboxトークンは [Mapbox](https://www.mapbox.com/) で無料アカウントを作成して取得できます。

### 3. アプリケーション起動

```bash
uv run streamlit run src/real_state_geo_core/streamlit/app.py
```

ブラウザが自動的に開き、アプリケーションが表示されます。

## 使い方

1. **サイドバーで条件を選択**
   - 築年数範囲: 1〜5年、5〜10年、10〜15年、15〜20年
   - 専有面積: 60㎡、70㎡、80㎡、90㎡、100㎡

2. **3Dマップで可視化**
   - マウスでドラッグして視点を回転
   - スクロールでズームイン/アウト
   - 右クリック + ドラッグで平行移動

3. **詳細情報の確認**
   - メッシュにマウスオーバーで詳細情報を表示
   - 「データ詳細情報」を展開してメタデータを確認

## アーキテクチャ

```
src/real_state_geo_core/streamlit/
├── __init__.py           # モジュール初期化
├── app.py                # Streamlitメインアプリケーション
├── data_loader.py        # データ読み込みとメタデータ管理
└── README.md             # このファイル
```

### 主要コンポーネント

#### `data_loader.py`

- **MeshPriceDataLoader**: メッシュ価格データの読み込みと管理
  - `get_available_conditions()`: 利用可能な築年数範囲と面積を取得
  - `load_mesh_price_data(map_key)`: 指定された条件のデータを読み込み
  - `prepare_pydeck_data(df)`: PyDeck用データに変換

#### `app.py`

- **Streamlitアプリケーション**: UI構築とデータ可視化
  - サイドバーでの条件選択UI
  - PyDeck ColumnLayerでの3D可視化
  - 統計情報の表示
  - ツールチップ表示

## データフォーマット

### 入力データ（CSV）

```csv
mesh_id,latitude,longitude,city_name,district_name,predicted_price,num_stations_used,...
35.733603_139.788061,35.73360348648242,139.78806056217425,荒川区,"",3814268.17,3,...
```

### メタデータ（JSON）

```json
{
  "target_year": 2025,
  "age_range": [1, 5],
  "area_sqm": 70.0,
  "structure": "RC",
  "total_meshes": 61552,
  "generation_timestamp": "2026-02-05T06:57:18.588437"
}
```

## カスタマイズ

### 色の変更

`app.py` の `create_pydeck_layer()` 関数で色の設定を変更できます:

```python
get_fill_color="[255, predicted_price / 10000, 100, 200]"
```

### 高さスケールの調整

```python
elevation_scale=0.001  # この値を変更
```

### マップスタイルの変更

```python
map_style="mapbox://styles/mapbox/dark-v10"  # light-v10, streets-v11 など
```

## トラブルシューティング

### データが見つからない

```
メッシュ価格マップが見つかりません。
```

→ `generate_mesh_price_variations.py` を実行してデータを生成してください。

### Mapboxトークンエラー

→ `.env` ファイルに `MAPBOX_TOKEN` を設定してください。

### 依存関係エラー

```bash
uv sync
```

を実行して依存関係を再インストールしてください。

## ライセンス

このプロジェクトに準拠します。
