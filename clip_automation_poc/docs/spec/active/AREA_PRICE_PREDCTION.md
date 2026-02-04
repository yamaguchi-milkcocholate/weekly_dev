# プロジェクト仕様書: 都内中古マンション 坪単価相場推定モデル

## 1. プロジェクト概要

本プロジェクトは、2005年から2025年までの東京都内の中古マンション取引データを用いて、**任意の立地・物件条件における現在の坪単価相場を推定する**機械学習モデルを構築することを目的とする。

**LightGBM Regressor**を用いて、立地情報（最寄駅、徒歩時間、区、用途地域等）と物件スペック（築年数、面積、構造等）および取引時点から、「滑らかで安定した相場」を学習する。
最終成果物は、StreamlitやPydeck等のBIツールで可視化・分析を行うための**構造化データ（CSV/JSON）**として出力する。

## 2. 入力データセット

以下のカラムを持つCSVデータを使用する。

| カラム名               | データ型 | 役割         | 備考                                      |
| :--------------------- | :------- | :----------- | :---------------------------------------- |
| `transaction_date`     | Date     | 時点特徴量   | 取引時点 (2005-2025)、相場の時系列変化を捉える |
| `tsubo_price`          | Float    | **目的変数** | 坪単価 (Target)                           |
| `Year`                 | Int      | 時点特徴量   | 取引年（transaction_dateから導出可能）    |
| `Area`                 | Float    | 物件特徴量   | 専有面積                                  |
| `Age`                  | Int      | 物件特徴量   | 築年数                                    |
| `TimeToNearestStation` | Int      | 立地特徴量   | 最寄駅までの徒歩時間                      |
| `NearestStation`       | String   | 立地特徴量   | 最寄駅名 (要カテゴリカルエンコーディング) |
| `DistrictName`         | String   | 立地特徴量   | 地区名                                    |
| `Municipality`         | String   | 立地特徴量   | 市区町村                                  |
| `BuildingYear`         | Int      | 物件特徴量   | 建築年                                    |
| `Structure`            | String   | 物件特徴量   | 建物構造 (RC等)                           |
| `CityPlanning`         | String   | 立地特徴量   | 用途地域                                  |
| `Renovation`           | String   | 物件特徴量   | 改装の有無                                |

## 3. 検証戦略 (Validation Strategy)

**目的**: モデルの汎化性能を正しく評価するため、エリアの偏りを防いだ交差検証を行う。

### 3.1. データ分割方針

1.  **ホールドアウト検証 (Hold-out)**:
    - **Testデータ**: 全データの20%をランダムに抽出（最終評価用）。
    - **Trainデータ**: 残り80%のデータ（モデル学習・交差検証用）。
2.  **交差検証 (Cross Validation)**:
    - Trainデータに対し、`sklearn.model_selection.GroupKFold` を適用する。
    - **グループキー**: `Municipality`（区）を使用し、同一区のデータが Train/Valid に分かれないようにする。
    - **分割数 (n_splits)**: 5
    - **理由**: 特定の区に過剰適合することを防ぎ、未知の区やエリア特性の変化に対する汎化性能を評価する。

---

## 4. 前処理 (Preprocessing)

### 4.1. 外れ値除去

**目的**: 極端な価格データ（入力ミス、特殊な取引等）を除外し、モデルの安定性を向上させる。

**手順**:
1. 全データの `tsubo_price` の分布を確認する。
2. 上位1%と下位1%のパーセンタイル値を計算する。
3. その範囲外のデータを除外する。

**実装例**:

```python
# パーセンタイル計算
lower_bound = df['tsubo_price'].quantile(0.01)
upper_bound = df['tsubo_price'].quantile(0.99)

# 外れ値除去
df_cleaned = df.filter(
    (pl.col('tsubo_price') >= lower_bound) &
    (pl.col('tsubo_price') <= upper_bound)
)
```

**注意**: この前処理は、データ分割（Train/Test split）の**前**に実行すること。

---

## 5. 特徴量エンジニアリング (Feature Engineering)

### 5.1. 基本方針

LightGBMは非線形性やカテゴリカル変数を直接扱えるため、過度な加工は不要。ただし、**時系列による価格変動**を捉えるため、**年ごと**の集約統計量を特徴量として追加する。

### 5.2. 時点関連の特徴量

`transaction_date` から以下を導出する:

- **Year**: 取引年（既存カラム）
- **Month**: 取引月 (1-12)
- **Quarter**: 四半期 (1-4)

### 5.3. 物件関連の特徴量

- **Age**: 築年数（既存カラム、そのまま使用）
- **Area**: 専有面積（既存カラム、そのまま使用）

### 5.4. 立地関連の特徴量

- **TimeToNearestStation**: 最寄駅までの徒歩時間（既存カラム、そのまま使用）
- **NearestStation**: カテゴリカル変数として LightGBM に渡す
- **Municipality**: 区名、カテゴリカル変数として LightGBM に渡す
- **DistrictName**: 地区名、カテゴリカル変数として LightGBM に渡す

### 5.5. 集約統計量（年ごとの価格傾向を捉える特徴量）

**重要**: 単価は時系列によって大きく変わるため、**集約KEY × 年**で集約統計量を算出する。
リークを防ぐため、**交差検証内で適切に計算**する必要がある（Train データのみから算出し、Valid/Test には Train の統計量を使用）。

以下の特徴量を作成する:

- **Municipality_Year_mean_price**: 区 × 年ごとの平均坪単価
- **Municipality_Year_median_price**: 区 × 年ごとの中央値坪単価
- **NearestStation_Year_mean_price**: 最寄駅 × 年ごとの平均坪単価
- **NearestStation_Year_median_price**: 最寄駅 × 年ごとの中央値坪単価

**算出方法の例**:
```python
# Train データのみから集約統計量を算出
train_stats = train_df.groupby(['Municipality', 'Year'])['tsubo_price'].agg(['mean', 'median']).reset_index()
train_stats.columns = ['Municipality', 'Year', 'Municipality_Year_mean_price', 'Municipality_Year_median_price']

# Train/Valid/Test データに結合（left join）
train_df = train_df.merge(train_stats, on=['Municipality', 'Year'], how='left')
valid_df = valid_df.merge(train_stats, on=['Municipality', 'Year'], how='left')
```

### 5.6. カテゴリカル変数のエンコーディング方針

LightGBM は `categorical_feature` パラメータでカテゴリカル変数を直接扱えるため、Label Encoding や One-Hot Encoding は不要。以下のカラムをカテゴリカル変数として指定する:

- `NearestStation`
- `DistrictName`
- `Municipality`
- `Structure`
- `CityPlanning`
- `Renovation`

---

## 6. モデリング要件

### 6.1. LightGBM による坪単価推定モデルの構築

- **目的**: 立地情報・物件スペック・取引時点から坪単価を推定するモデルを構築し、汎化性能を評価する。
- **手法**: LightGBM Regressor
- **目的変数**: `tsubo_price`
- **特徴量**:
  - 元のカラム: `Year`, `Month`, `Quarter`, `Area`, `Age`, `TimeToNearestStation`, `NearestStation`, `Municipality`, `DistrictName`, `BuildingYear`, `Structure`, `CityPlanning`, `Renovation`
  - 集約統計量: `Municipality_Year_mean_price`, `Municipality_Year_median_price`, `NearestStation_Year_mean_price`, `NearestStation_Year_median_price`
- **カテゴリカル変数**: `NearestStation`, `DistrictName`, `Municipality`, `Structure`, `CityPlanning`, `Renovation` を LightGBM のカテゴリカル変数として扱う。

### 6.2. 交差検証と評価

**CVループ内の処理フロー**:
各Fold（GroupKFold, n_splits=5, groups=Municipality）において、以下の手順を実行する。

1. **特徴量エンジニアリング**: Train データから年ごとの集約統計量を計算し、Train/Valid 両方に特徴量を追加する（リーク防止のため、Valid には Train の統計量のみを使用）。
2. **モデル学習**: そのFoldの `Train` データで LightGBM を学習させる。
3. **検証 (Predict)**: そのFoldの `Valid` データで予測を行う。
4. **スコア算出**: RMSE, MAE, MAPE を記録する。

**最終モデル**:
- 全 Train データで学習した最終モデルを作成する。
- Test データで最終評価を行う。
- 特徴量重要度 (Feature Importance) を出力する。

---

## 7. 出力成果物とデータ定義 (Output Data Schema)

分析結果は `outputs/` ディレクトリ配下に以下のCSV/JSON形式で保存すること。
**Visualization Tools (Streamlit/Pydeck) での利用を前提とする。**

### 7.1. 特徴量重要度 (`outputs/feature_importance.csv`)

LightGBMモデルの特徴量重要度を記録。

| カラム名           | 型     | 説明                                     |
| :----------------- | :----- | :--------------------------------------- |
| `feature_name`     | String | 特徴量名 (例: Age, TimeToNearestStation) |
| `importance_gain`  | Float  | Gain による重要度スコア                  |
| `importance_split` | Float  | Split による重要度スコア                 |

### 7.2. 予測結果 (`outputs/prediction_results.csv`)

Test データに対する予測結果。**Pydeck (地図) や Plotly (ドリルダウン) のメインソースとなる。**

| カラム名           | 型     | 説明                           |
| :----------------- | :----- | :----------------------------- |
| `transaction_date` | Date   | 取引時点                       |
| `NearestStation`   | String | 最寄駅（地図マッピング用キー） |
| `DistrictName`     | String | 地区名                         |
| `Municipality`     | String | 区名                           |
| `Age`              | Int    | 築年数                         |
| `Area`             | Float  | 専有面積                       |
| `actual_price`     | Float  | 実測坪単価                     |
| `predicted_price`  | Float  | **予測坪単価**                 |
| `error_abs`        | Float  | 絶対誤差                       |
| `error_pct`        | Float  | 相対誤差（%）                  |

### 7.3. 交差検証メトリクス (`outputs/cv_metrics.csv`)

モデルの信頼性評価用。GroupKFold (n_splits=5) の各Foldにおける評価指標を記録。

| カラム名  | 型    | 説明                           |
| :-------- | :---- | :----------------------------- |
| `fold_id` | Int   | Fold番号 (0〜4)                |
| `rmse`    | Float | Root Mean Squared Error        |
| `mae`     | Float | Mean Absolute Error            |
| `mape`    | Float | Mean Absolute Percentage Error |

## 8. 技術要件 (Technical Requirements)

- **言語**: Python 3.x
- **ライブラリ**:
  - `polars` (高速データ処理)
  - `pandas`, `numpy` (補助的なデータ処理)
  - `lightgbm` (機械学習)
  - `scikit-learn` (交差検証・評価指標)
- **再現性**: `random_state=42` で統一する。
- **前処理**: 坪単価の上位・下位1%を外れ値として除外すること。
- **エラーハンドリング**: データ欠損や異常値に対して適切な処置（除外または補完）を行うコードを含めること。
- **ディレクトリ**: 実行時に `outputs/` フォルダが存在しない場合は自動生成すること。
