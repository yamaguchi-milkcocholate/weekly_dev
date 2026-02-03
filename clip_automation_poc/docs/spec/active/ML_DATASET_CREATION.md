# 機械学習用データセット作成スクリプト 仕様書

## 1. 概要

### 目的

国土交通省 不動産情報ライブラリAPIから取得した不動産取引データを、機械学習による**坪単価予測**に適したデータセットとして整形・保存するスクリプトを実装します。

### 解決する課題

- MLIT APIから取得した生データは、機械学習に直接使用できない形式（カテゴリ変数が未加工、欠損値が多い、時系列順序が未整理など）
- 小規模データ（数百〜数千件）での過学習防止が必要
- カテゴリ変数が多く、適切な前処理が必要
- 時系列データとして扱うための年情報の抽出が必要

---

## 2. 主要機能

### 2.1 データ取得

- **`RealEstateDataFetcher.fetch_real_estate_multi_year()`** を使用して複数年のデータを取得
- デフォルト取得範囲: 2023年〜2024年（2年間）
- 対象地域: 東京23区（市区町村コード指定）

### 2.2 データフィルタリング

- **不動産種類**: `Type == "中古マンション等"` のみに絞る
- **用途**: `Use == "住宅"` のみに絞る

### 2.3 データクリーニング

- **必須カラムの欠損値除去**: `TradePrice`（取引価格）、`Area`（面積）が`null`の行を削除
- **坪単価の算出**: `TradePrice` / (`Area` \* 0.3025) で坪単価を計算（`UnitPrice`がnullの場合）
- **時系列情報の抽出**: `Period`カラム（例: "2024年第1四半期"）から`Year`を抽出
- **築年数の算出**: `Age = Year - BuildingYear`（建築年が不明な場合はnull）

### 2.4 特徴量エンジニアリング

#### 目的変数

- **`tsubo_price`** (float): 坪単価（円/坪）← **主要ターゲット**

#### 説明変数

**数値変数:**

- `Area` (float): 面積（㎡）
- `TotalFloorArea` (float): 延床面積（㎡）
- `Age` (int): 築年数（年）
- `CoverageRatio` (float): 建ぺい率（%）
- `FloorAreaRatio` (float): 容積率（%）
- `Year` (int): 取引年

**カテゴリ変数:**

- `Municipality` (str): 市区町村名
- `Structure` (str): 建物構造（RC、SRC、木造など）
- `CityPlanning` (str): 用途地域

**時系列インデックス:**

- `transaction_date` (datetime): 取引時期（Year から生成、1月1日固定）

### 2.5 データ検証

- **レコード数の確認**: 最低100件以上を確保（少ない場合は警告）
- **カラム型の検証**: 数値カラムが正しくfloat/int型に変換されているか確認
- **欠損率の計算**: 各カラムの欠損率をログ出力
- **時系列順序の確認**: `transaction_date`でソートされているか確認

### 2.6 CSV出力

- **出力パス**: `data/ml_dataset/tokyo_23_ml_dataset.csv`
- **文字エンコード**: UTF-8
- **形式**: ヘッダー行あり、カンマ区切り

---

## 3. 技術スタック

### 3.1 主要ライブラリ

| ライブラリ                | 用途               | 選定理由                               |
| ------------------------- | ------------------ | -------------------------------------- |
| **Polars**                | データ操作         | 高速なDataFrame処理、メモリ効率が良い  |
| **RealEstateDataFetcher** | API取得            | プロジェクト独自の統合クラス（既実装） |
| **Pathlib**               | ファイルパス管理   | 可読性が高く、OSに依存しない           |
| **logging**               | ログ出力           | デバッグと進捗確認                     |
| **argparse**              | コマンドライン引数 | 実行時パラメータの柔軟な指定           |

### 3.2 機械学習ライブラリ（このスクリプトでは不使用、後続処理で使用）

- **CatBoost**: カテゴリ変数の自動処理、小規模データでの過学習抑制
- **Scikit-learn**: `TimeSeriesSplit`による時系列交差検証
- **Optuna**: ハイパーパラメータ自動探索

---

## 4. データ構造/フロー

### 4.1 入力

**MLIT API（`RealEstateDataFetcher.fetch_real_estate_multi_year()`経由）:**

- 取得年範囲: 2023〜2024年（デフォルト）
- 市区町村コード: 東京23区の各コード（例: 千代田区 = "13101"）
- APIキー: 環境変数 `REINFOLIB_API_KEY` から取得

**生データのスキーマ（MLIT APIレスポンス）:**

| カラム名（API）        | 型                     | 説明                              |
| ---------------------- | ---------------------- | --------------------------------- |
| `Type`                 | String                 | 不動産種類                        |
| `TradePrice`           | String（カンマ区切り） | 取引総額                          |
| `Period`               | String                 | 取引時期（例: "2024年第1四半期"） |
| `Municipality`         | String                 | 市区町村名                        |
| `DistrictName`         | String                 | 地区名                            |
| `NearestStation`       | String                 | 最寄駅                            |
| `TimeToNearestStation` | String                 | 駅までの徒歩分数                  |
| `Area`                 | String（カンマ区切り） | 面積（㎡）                        |
| `UnitPrice`            | String（カンマ区切り） | 坪単価（APIが提供する場合）       |
| `TotalFloorArea`       | String                 | 延床面積                          |
| `BuildingYear`         | String                 | 建築年（和暦・西暦混在）          |
| `Structure`            | String                 | 建物構造                          |
| `Use`                  | String                 | 用途                              |
| `CityPlanning`         | String                 | 用途地域                          |
| `CoverageRatio`        | String                 | 建ぺい率                          |
| `FloorAreaRatio`       | String                 | 容積率                            |
| `Remarks`              | String                 | 取引事情                          |

### 4.2 処理フロー

```
1. 環境変数からAPIキー取得
   ↓
2. RealEstateDataFetcherインスタンス化
   ↓
3. fetch_real_estate_multi_year() で複数年のデータ取得
   ↓
4. clean_real_estate_data() でPolars DataFrameに変換
   ↓
5. データフィルタリング
   - Type == "中古マンション等" のみ
   - Use == "住宅" のみ
   ↓
6. データクリーニング
   - 必須カラム（TradePrice, Area）のnull除去
   - 数値カラムの型変換（カンマ除去 → float）
   - 坪単価算出（TradePrice / (Area * 0.3025)）
   ↓
7. 特徴量エンジニアリング
   - Period文字列から Year を抽出
   - transaction_date (datetime) 生成（Year-01-01）
   - BuildingYear の和暦→西暦変換
   - Age（築年数） = Year - BuildingYear
   ↓
8. データ検証
   - レコード数チェック（< 100件なら警告）
   - 欠損率計算・ログ出力
   - 時系列ソート確認
   ↓
9. CSV出力
   - data/ml_dataset/tokyo_23_ml_dataset.csv に保存
   ↓
10. 統計情報表示
   - レコード数、カラム数、欠損率サマリー
```

### 4.3 出力

**CSVファイルパス:**
`data/ml_dataset/tokyo_23_ml_dataset.csv`

**出力スキーマ:**

| カラム名           | 型       | 説明                   | 役割                 |
| ------------------ | -------- | ---------------------- | -------------------- |
| `transaction_date` | datetime | 取引時期（YYYY-01-01） | 時系列インデックス   |
| `Year`             | int      | 取引年                 | 説明変数（時系列）   |
| `tsubo_price`      | float    | **坪単価（円/坪）**    | **目的変数**         |
| `Area`             | float    | 面積（㎡）             | 説明変数             |
| `TotalFloorArea`   | float    | 延床面積（㎡）         | 説明変数             |
| `Age`              | int      | 築年数（年）           | 説明変数             |
| `CoverageRatio`    | float    | 建ぺい率（%）          | 説明変数             |
| `FloorAreaRatio`   | float    | 容積率（%）            | 説明変数             |
| `Municipality`     | str      | 市区町村名             | 説明変数（カテゴリ） |
| `Structure`        | str      | 建物構造               | 説明変数（カテゴリ） |
| `CityPlanning`     | str      | 用途地域               | 説明変数（カテゴリ） |

**サンプル行（CSV出力イメージ）:**

```csv
transaction_date,Year,tsubo_price,Area,TotalFloorArea,Age,CoverageRatio,FloorAreaRatio,Municipality,Structure,CityPlanning
2023-01-01,2023,1500000.0,50.0,80.0,13,60.0,200.0,千代田区,RC,商業地域
2024-01-01,2024,1800000.0,45.0,75.0,9,60.0,300.0,港区,SRC,商業地域
```

---

## 5. コマンドライン引数

### 5.1 引数一覧

| 引数名          | 型  | デフォルト値                              | 説明                                                       |
| --------------- | --- | ----------------------------------------- | ---------------------------------------------------------- |
| `--start-year`  | int | 2023                                      | データ取得開始年                                           |
| `--end-year`    | int | 2024                                      | データ取得終了年                                           |
| `--city-codes`  | str | "13101,13102,..."                         | 市区町村コード（カンマ区切り）<br>デフォルト: 東京23区全て |
| `--output-path` | str | `data/ml_dataset/tokyo_23_ml_dataset.csv` | 出力CSVパス                                                |

### 5.2 実行例

```bash
# デフォルト設定で実行（2023-2024年、東京23区全体）
python scripts/create_ml_dataset.py

# 期間と出力先をカスタマイズ
python scripts/create_ml_dataset.py --start-year 2020 --end-year 2024 --output-path data/ml_dataset/tokyo_2020-2024.csv

# 特定区のみ取得（例: 千代田区 + 港区）
python scripts/create_ml_dataset.py --city-codes "13101,13103"
```

---

## 6. データクリーニング詳細

### 6.1 データフィルタリング

```python
# Type == "中古マンション等" AND Use == "住宅" のみ抽出
df = df.filter(
    (pl.col("Type") == "中古マンション等") &
    (pl.col("Use") == "住宅")
)
```

### 6.2 必須カラムのnull除去

```python
# TradePrice, Area が null の行を削除
df = df.filter(
    (pl.col("TradePrice").is_not_null()) &
    (pl.col("Area").is_not_null())
)
```

### 6.3 数値変換

```python
# カンマ区切り文字列 → float
for col in ["TradePrice", "Area", "UnitPrice", "TotalFloorArea", "CoverageRatio", "FloorAreaRatio"]:
    if col in df.columns:
        df = df.with_columns(
            pl.col(col)
            .cast(pl.Utf8)
            .str.replace(",", "")
            .cast(pl.Float64, strict=False)
        )
```

### 6.4 坪単価の算出

```python
# UnitPrice が null の場合、TradePrice / (Area * 0.3025) で算出
df = df.with_columns(
    pl.when(pl.col("UnitPrice").is_null())
    .then(pl.col("TradePrice") / (pl.col("Area") * 0.3025))
    .otherwise(pl.col("UnitPrice"))
    .alias("tsubo_price")
)
```

### 6.5 時系列情報の抽出

```python
# Period: "2024年第1四半期" → Year=2024
def parse_period_year(period_str: str) -> int | None:
    """
    例: "2024年第1四半期" → 2024
    """
    import re
    match = re.search(r"(\d{4})年", period_str)
    if match:
        return int(match.group(1))
    return None

df = df.with_columns(
    pl.col("Period").map_elements(parse_period_year, return_dtype=pl.Int64).alias("Year")
)

# transaction_date を生成（1月1日固定）
df = df.with_columns(
    pl.datetime(pl.col("Year"), 1, 1).alias("transaction_date")
)
```

### 6.6 建築年の和暦→西暦変換と築年数の算出

```python
# "昭和50年" → 1975, "平成10年" → 1998, "令和3年" → 2021
def convert_building_year(year_str: str) -> int | None:
    import re
    if pd.isna(year_str) or year_str == "":
        return None
    # 西暦の場合はそのまま返却
    if re.match(r"^\d{4}$", str(year_str)):
        return int(year_str)
    # 和暦の変換
    match = re.search(r"(昭和|平成|令和)(\d+)年", str(year_str))
    if match:
        era, year = match.groups()
        year = int(year)
        if era == "昭和":
            return 1925 + year
        elif era == "平成":
            return 1988 + year
        elif era == "令和":
            return 2018 + year
    return None

df = df.with_columns(
    pl.col("BuildingYear").map_elements(convert_building_year, return_dtype=pl.Int64).alias("BuildingYear_clean")
)

# 築年数 = 取引年 - 建築年
df = df.with_columns(
    (pl.col("Year") - pl.col("BuildingYear_clean")).alias("Age")
)

# BuildingYear_clean は削除（不要）
df = df.drop("BuildingYear_clean")
```

---

## 7. データ検証

### 7.1 レコード数チェック

```python
if df.height < 100:
    logging.warning(f"レコード数が少ないです: {df.height}件（機械学習には最低100件以上推奨）")
else:
    logging.info(f"レコード数: {df.height}件")
```

### 7.2 欠損率計算

```python
# 各カラムの欠損率をログ出力
missing_rates = df.null_count() / df.height * 100
logging.info("カラム別欠損率:")
for col in df.columns:
    rate = missing_rates[col][0]
    logging.info(f"  {col}: {rate:.2f}%")
```

### 7.3 時系列順序確認

```python
# transaction_date で昇順ソート
df = df.sort("transaction_date")
logging.info(f"時系列範囲: {df['transaction_date'].min()} 〜 {df['transaction_date'].max()}")
```

---

## 8. 未実装/今後の課題

### 8.1 現在の制限事項

1. **建築年の和暦変換が不完全**:
   - 一部の和暦表記（例: "戦前"、"不詳"）に対応していない
   - 対処: `null` として扱い、後続の機械学習で欠損値補完

2. **地理情報（緯度経度）が未統合**:
   - 現在のスクリプトでは、駅名のみでメッシュマスターとの結合を行わない
   - 今後の拡張: `fetch_station_master()` を使って駅名→緯度経度を付与し、空間特徴量を追加

3. **カテゴリ変数のカーディナリティが高い**:
   - `NearestStation`（駅名）は数百種類あり、小規模データでは過学習のリスク
   - 対処: CatBoostのTarget Encodingで自動処理（学習スクリプト側で実装）

4. **時系列順序のみで交差検証は未実装**:
   - データセット作成時点では、訓練/検証/テストの分割を行わない
   - 今後の拡張: `sklearn.model_selection.TimeSeriesSplit` を使った学習スクリプトで実装

### 8.2 今後の拡張案

1. **メッシュマスターとの結合**:
   - メッシュIDを付与して、地理空間的な集約データ（周辺坪単価の中央値など）を特徴量に追加

2. **外部データの統合**:
   - 国勢調査データ（人口密度、世帯年収など）
   - 公示地価データ

3. **特徴量エンジニアリングの自動化**:
   - `駅距離カテゴリ` = "徒歩5分以内", "5-10分", "10-15分", "15分以上"

4. **時系列特徴量**:
   - `前年比` = `今年坪単価中央値` / `前年坪単価中央値`
   - `移動平均` = 過去N年の坪単価平均

---

## 9. パフォーマンス要件

### 9.1 実行時間

- **データ取得**: 1年あたり5秒程度（MLIT API）
- **データクリーニング**: 10,000件あたり1秒以下（Polars使用）
- **CSV出力**: 10,000件あたり0.5秒以下

**合計実行時間（2年分、10,000件想定）**: 約15秒

### 9.2 メモリ使用量

- **Polars DataFrame**: 10,000件で約10MB（メモリ効率が高い）
- **推奨メモリ**: 最低1GB以上

---

## 10. エラーハンドリング

### 10.1 APIエラー

```python
# fetch_real_estate_multi_year() が None を返した場合
if combined_df is None or combined_df.height == 0:
    logging.error("データ取得に失敗しました。APIキーと市区町村コードを確認してください。")
    sys.exit(1)
```

### 10.2 環境変数エラー

```python
api_key = os.getenv("REINFOLIB_API_KEY")
if not api_key:
    logging.error("環境変数 REINFOLIB_API_KEY が設定されていません。")
    sys.exit(1)
```

### 10.3 データ品質エラー

```python
# 必須カラムが存在しない場合
required_cols = ["TradePrice", "Area", "Period", "Municipality", "Type", "Use"]
missing_cols = [col for col in required_cols if col not in df.columns]
if missing_cols:
    logging.error(f"必須カラムが不足しています: {missing_cols}")
    sys.exit(1)
```

### 10.4 フィルタリング後のデータ不足エラー

```python
# Type == "中古マンション等" AND Use == "住宅" でフィルタリング後
if df.height == 0:
    logging.error("フィルタリング後のデータが0件です。Type='中古マンション等', Use='住宅' のデータが存在しません。")
    sys.exit(1)
```

---

## 11. 機械学習パイプライン連携（後続処理）

このスクリプトで生成されたCSVデータセットは、以下の機械学習パイプラインで使用されます：

### 11.1 学習スクリプト（`scripts/train_catboost_model.py`）

- **入力**: `data/ml_dataset/tokyo_23_ml_dataset.csv`
- **モデル**: CatBoost Regressor
- **検証**: TimeSeriesSplit（3-fold）
- **評価指標**: RMSE（平方根平均二乗誤差）、MAE（平均絶対誤差）
- **出力**: `models/catboost_tsubo_price.cbm`（訓練済みモデル）

### 11.2 ハイパーパラメータ探索（`scripts/optimize_hyperparameters.py`）

- **ツール**: Optuna
- **探索空間**:
  - `depth`: 4〜8（木の深さ）
  - `learning_rate`: 0.01〜0.1
  - `l2_leaf_reg`: 1〜10（L2正則化）
  - `iterations`: 100〜500（Early Stopping使用）

### 11.3 予測スクリプト（`scripts/predict_tsubo_price.py`）

- **入力**: 新規物件データ（CSV or JSON）
- **モデル**: `models/catboost_tsubo_price.cbm`
- **出力**: 予測坪単価（円/坪）

---

## 12. 参考資料

### 12.1 関連ドキュメント

- `docs/SYSTEM_DESIGN.md`: プロジェクト全体の技術仕様書
- `src/real_state_geo_core/data/fetcher.py`: データ取得クラスのソースコード
- `scripts/aggregate_mesh_price.py`: メッシュ単位の坪単価集約スクリプト（参考実装）

### 12.2 外部API仕様

- [不動産情報ライブラリ API仕様書](https://www.reinfolib.mlit.go.jp/help/api/index.html)

### 12.3 機械学習ライブラリ

- [CatBoost Documentation](https://catboost.ai/docs/)
- [Scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [Optuna Tutorial](https://optuna.readthedocs.io/)

---

## 付録A: 東京23区 市区町村コード一覧

| 区名     | コード |
| -------- | ------ |
| 千代田区 | 13101  |
| 中央区   | 13102  |
| 港区     | 13103  |
| 新宿区   | 13104  |
| 文京区   | 13105  |
| 台東区   | 13106  |
| 墨田区   | 13107  |
| 江東区   | 13108  |
| 品川区   | 13109  |
| 目黒区   | 13110  |
| 大田区   | 13111  |
| 世田谷区 | 13112  |
| 渋谷区   | 13113  |
| 中野区   | 13114  |
| 杉並区   | 13115  |
| 豊島区   | 13116  |
| 北区     | 13117  |
| 荒川区   | 13118  |
| 板橋区   | 13119  |
| 練馬区   | 13120  |
| 足立区   | 13121  |
| 葛飾区   | 13122  |
| 江戸川区 | 13123  |

---

## 付録B: データセット統計情報サンプル

```
========================================
データセット統計情報
========================================
レコード数: 8,542件
取引期間: 2023-01-01 〜 2024-01-01
カラム数: 13

目的変数（tsubo_price）:
  平均: 1,850,000円/坪
  中央値: 1,600,000円/坪
  標準偏差: 850,000円/坪
  最小値: 120,000円/坪
  最大値: 9,800,000円/坪

説明変数の欠損率:
  Area: 0.0%
  TotalFloorArea: 12.3%
  Age: 8.5%
  TimeToNearestStation: 2.1%
  CoverageRatio: 15.7%
  FloorAreaRatio: 15.7%
  Structure: 5.2%
  CityPlanning: 18.9%

カテゴリ変数のカーディナリティ:
  Municipality: 23種類（東京23区）
  NearestStation: 387種類
  Structure: 8種類
  CityPlanning: 18種類
========================================
```

---

**仕様書作成日**: 2026-01-31
**バージョン**: 1.1
**作成者**: Claude (claude-sonnet-4-5)
