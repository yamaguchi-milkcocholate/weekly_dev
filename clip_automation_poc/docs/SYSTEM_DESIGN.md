# システム設計書：Urban Dynamics PoC

## 1. 概要

### 1.1 目的

国土交通省の公示地価データを用いて、地価変動を3D可視化した60秒のYouTube Shorts動画を生成するPoCを構築する。

### 1.2 スコープ（PoC範囲）

| 項目         | PoC範囲                     | 将来対応         |
| ------------ | --------------------------- | ---------------- |
| データソース | 公示地価CSV（手動DL / API） | API連携          |
| 対象エリア   | 東京都1エリア               | 全国展開         |
| 可視化       | pydeck / PyVista 検証       | 最適なものを選択 |
| AI強化       | Runway API                  | 自動パイプライン |
| 自動化       | セミ自動（手動介入あり）    | フル自動         |

### 1.3 出力仕様（YouTube Shorts）

| 項目           | 値                      |
| -------------- | ----------------------- |
| 解像度         | 1080 x 1920 (9:16 縦型) |
| フレームレート | 30fps                   |
| 動画長         | 60秒                    |
| 形式           | MP4 (H.264)             |

---

## 2. システム構成図

```
┌─────────────────────────────────────────────────────────────────────┐
│                          PoC Pipeline                               │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   1. Data    │     │  2. Analyze  │     │ 3. Visualize │
  │   Extract    │────▶│   & Clean    │────▶│   (3D Map)   │
  └──────────────┘     └──────────────┘     └──────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    公示地価CSV          polars処理           pydeck/PyVista
    (手動DL / API)       欠損値補完            フレーム連番出力
                       座標変換

                                               │
                                               ▼
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   6. Export  │     │  5. Compose  │     │  4. Enhance  │
  │   (Final)    │◀────│   (FFmpeg)   │◀────│  (Runway)    │
  └──────────────┘     └──────────────┘     └──────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    YouTube Shorts       動画結合              Video-to-Video
    用MP4出力           テキスト合成            質感向上
```

---

## 3. 処理フロー詳細

各 Phase の「処理」は必ず現状の実装状況（`現状の実装`）と、設計上必要な残タスク（`未実装 / 今後`）を分けて記載します。

### Phase 1: データ取得 (Extract)

処理:

1. `fetch_real_estate` — 不動産情報ライブラリAPIから取引データを取得（src/real_state_geo_core/data/fetcher.py）
   - APIレスポンスはJSONまたはgzip圧縮のJSONを想定し、両方に対応する実装済み。
2. `fetch_station_master` — 駅データCSVを読み込み、`station_name` の正規化と駅座標マスタ（駅名→(lat, lon)）を作成（実装済み）。
3. `fetch_boundary_geojson` — JapanCityGeoJson（GitHub）から自治体のGeoJSONを取得・保存する処理（実装済み）。

未実装 / 今後:

- 手動ダウンロードの自動化（CSVの自動取得・UTF-8正規化）
- ローカルCSVからの一括取り込みワークフロー

**入力例:** 国土交通省 不動産取引価格情報API / 駅データCSV

**出力例:** API JSON, 駅座標辞書, 保存した GeoJSON

---

### Phase 2: データ加工 (Analyze & Clean)

処理:

1. `clean_real_estate_data` — APIレスポンスの `data` 部分を `polars.DataFrame` に変換し、数値カラム（`TradePrice`, `Area`, `UnitPrice` 等）の文字列→float の変換と、必須カラムの欠損値除去を実行（実装済み）。
2. `geocode_random` — 区の中心座標に対してランダムオフセットで緯度経度を生成（面積に応じた散らばりを調整する実装済み）。
3. 駅座標マスタ参照 — `fetch_station_master` の出力を使って、駅ベースのジオコーディングを補助（実装済み、参照のみ）。

未実装 / 今後:

- 地区名+最寄駅を用いた厳密なジオコーディング（外部Geocoding API連携やルールベースのマッチング）
- 取引時期のパース（例: "2024年第3四半期" → "2024Q3"）
- 単価計算（円/㎡）や外れ値除去、時系列集約処理
- 出力形式（Parquet 等）への永続化ワークフロー

**出力スキーマ（想定）:**

```python
{
    "latitude": float,
    "longitude": float,
    "price_total": int,
    "price_per_sqm": float,
    "area_sqm": float,
    "district": str,
    "station": str,
    "year_quarter": str,
    "building_year": int,
}
```

---

### Phase 3: 可視化 (Visualize)

処理:

1. `convert_for_pydeck` — `polars.DataFrame` を pydeck 用の `list[dict]` に変換（型キャストや必要カラムの抽出を実装済み、`src/real_state_geo_core/visualization/pydeck.py`）。
2. pydeck による ColumnLayer の組立て・HTML 出力・Playwright によるスクリーンショット取得は現時点では未実装（設計に残す）。
3. 境界 GeoJSON の重ね合わせは `fetch_boundary_geojson` で取得したデータを利用可能（実装済み）。

未実装 / 今後:

- pydeck レイヤー構築（色・高さ・ツールチップのマッピング）、HTML出力、Playwright を用いたフレーム出力
- 可視化パラメータ（カラーマップ、高さスケール、半径等）の設定管理

**出力例:** `output/frames_pydeck/{year}_{frame:04d}.png`（未実装）

---

#### 3B. PyVista 版

処理:

1. PyVista による 3D メッシュ化・レンダリング（未実装）
2. 地図タイル取得（contextily 等を想定・未実装）

**出力例:** `output/frames_pyvista/{year}_{frame:04d}.png`（未実装）

---

### Phase 4: AI強化 (Enhance)

処理:

1. FFmpeg でフレームを一時動画化
2. Runway Gen-3（Video-to-Video） API に送信して画質や質感を強化
3. 強化済み動画を取得

現状の実装: Runway API 連携・FFmpeg 呼び出しは未実装（設計として残す）

**出力例:** `output/enhanced/enhanced_{segment}.mp4`（未実装）

---

### Phase 5: 動画合成 (Compose)

処理:

1. FFmpeg による動画結合
2. テキストオーバーレイ（西暦カウンター、エリア名、データソース表記）
3. BGM 合成（オプション）

現状の実装: 上記は未実装（設計として残す）

**出力例:** `output/composed/composed.mp4`（未実装）

---

### Phase 6: 最終出力 (Export)

処理:

1. YouTube Shorts 仕様（1080x1920, 30fps, 60s）に最終エンコード
2. メタデータ付与

現状の実装: 最終エンコード・メタデータ付与は未実装（設計として残す）

**出力例:** `output/final/urban_dynamics_{area}_{date}.mp4`（未実装）

---

## 4. ディレクトリ構成（想定）

```
clip_automation_poc/
├── docs/
│   ├── PLANNING.md
│   └── SYSTEM_DESIGN.md
├── data/
│   ├── raw/
│   └── processed/
├── src/
│   ├── real_state_geo_core/
│   │   ├── __init__.py
│   │   ├── utils.py
│   │   ├── data/
│   │   │   ├── __init__.py
│   │   │   └── fetcher.py
│   │   └── visualization/
│   │       ├── __init__.py
│   │       └── pydeck.py
│   ├── extract.py
│   ├── analyze.py
│   ├── visualize_pydeck.py
│   ├── visualize_pyvista.py
│   ├── enhance.py
│   ├── compose.py
│   └── export.py
├── output/
│   ├── frames_pydeck/
│   ├── frames_pyvista/
│   ├── enhanced/
│   ├── composed/
│   └── final/
├── notebooks/
└── config/
```

---

## 5. 技術スタック

（省略せずそのまま維持。現在の実装は `polars`, `pydeck` 用の前処理を含みます。）

## 6. 設定ファイル仕様

（既存の `config/settings.yaml` 仕様をそのまま参照）

---

## 7. PoC検証項目 / 次のステップ

- 現在の優先作業:
  1. `pydeck` を用いた最小可視化パスを実装（`convert_for_pydeck` → Deck 作成 → HTML 保存 → Playwright スクリーンショット）。
  2. 地区名／駅ベースのジオコーディング強化（ルールベースのマッチング、外部 API 検討）。
  3. Parquet 出力と FFmpeg 連携のためのフレーム出力パイプライン整備。

---

## 付録A: 参考リンク

- 国土交通省 公示地価: https://www.land.mlit.go.jp/webland/
- pydeck ドキュメント: https://pydeck.gl/
- PyVista ドキュメント: https://docs.pyvista.org/
- Runway API: https://docs.runwayml.com/
- FFmpeg フィルタガイド: https://ffmpeg.org/ffmpeg-filters.html
