# プロジェクト仕様書: 都内中古マンション 坪単価分析と将来予測

## 1. プロジェクト概要

本プロジェクトは、2005年から2025年までの東京都内の中古マンション取引データを用いてデータ分析を行い、将来の「坪単価」を予測することを目的とする。

従来の決定木モデルが苦手とする「将来トレンドの外挿」課題を解決するため、**Prophet（時系列トレンド）**と**LightGBM（物件構造の非線形性）**を組み合わせたハイブリッドアプローチを採用する。
最終成果物は、StreamlitやPydeck等のBIツールで可視化・分析を行うための**構造化データ（CSV/JSON）**として出力する。

## 2. 入力データセット

以下のカラムを持つCSVデータを使用する。

| カラム名               | データ型 | 役割         | 備考                                      |
| :--------------------- | :------- | :----------- | :---------------------------------------- |
| `transaction_date`     | Date     | 時系列キー   | 分析の基準日 (2005-2025)                  |
| `tsubo_price`          | Float    | **目的変数** | 坪単価 (Target)                           |
| `Year`                 | Int      | 時系列特徴量 | 補助的に使用                              |
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

**最重要項目**: 未来の情報を学習モデルに漏洩させないため（リーク防止）、厳密な時系列分割を行う。

### 3.1. データ分割方針

1.  **データのソート**: 全データを `transaction_date` の昇順でソートする。
2.  **ホールドアウト検証 (Hold-out)**:
    - **Testデータ**: 2025年の全データ（最終的な未知データ評価用）。
    - **Train/Validデータ**: 2005年〜2024年のデータ（モデル構築用）。
3.  **交差検証 (Cross Validation)**:
    - Train/Validデータに対し、`sklearn.model_selection.TimeSeriesSplit` を適用する。

### 3.2. Time Series Split の定義

- **手法**: Expanding Window (学習期間を徐々に広げていく方式)
- **分割数 (n_splits)**: 5
- **Gap**: 0 (学習データと検証データの間に期間を空けない)

---

## 4. 分析プロセスとモデリング要件

### Step 1: 構造分析 (Static Analysis)

- **目的**: 時系列要素を除いた、純粋な「立地」や「物件スペック」の影響度を定量化する。
- **手法**: LightGBM Regressor
- **特徴量**: `tsubo_price` を目的変数とし、`transaction_date` 以外の全ての物件・立地属性を使用。
- **出力**: 特徴量重要度 (Feature Importance)。

### Step 2: マクロトレンド分析 (Macro Trend Analysis)

- **目的**: 物件個別の事情を無視した、市場全体の価格推移（トレンド・季節性）を抽出する。
- **データ加工**: `transaction_date` を月単位等で集約し、坪単価の平均値/中央値を算出する。
- **手法**: Prophet
  - 日本の休日 (`add_country_holidays(country_name='JP')`) を設定すること。

### Step 3: ハイブリッド予測 (Hybrid Modeling)

- **目的**: `予測価格 = トレンド(Prophet) + 物件固有価値(LGBM)` の式に基づき予測を行う。
- **CVループ内の処理フロー (厳守)**:
  各Foldにおいて、以下の手順を実行する。
  1.  **Prophet学習**: そのFoldの `Train` データのみを使ってProphetを学習させる。
  2.  **残差算出**: 学習済みProphetを使い、そのFoldの `Train` データのトレンドを予測し、実測値との残差 (`y - y_trend`) を計算する。
  3.  **LGBM学習**: `Train` の残差を目的変数として、LGBMを学習させる。
  4.  **検証(Predict)**:
      - そのFoldの `Valid` データに対して、Prophetでトレンド予測 (`y_trend_valid`) を行う。
      - 同じく `Valid` データに対して、LGBMで残差予測 (`y_resid_valid`) を行う。
      - `Final Prediction = y_trend_valid + y_resid_valid`
  5.  **スコア算出**: RMSE, MAE, MAPEを記録する。

---

## 5. 出力成果物とデータ定義 (Output Data Schema)

分析結果は `outputs/` ディレクトリ配下に以下のCSV/JSON形式で保存すること。
**Visualization Tools (Streamlit/Pydeck) での利用を前提とする。**

### 5.1. 構造分析結果 (`outputs/feature_importance.csv`)

Step 1の結果。

| カラム名       | 型     | 説明                                     |
| :------------- | :----- | :--------------------------------------- |
| `feature_name` | String | 特徴量名 (例: Age, TimeToNearestStation) |
| `importance`   | Float  | 重要度スコア (Gain/Split)                |
| `category`     | String | 分類 ("Location", "Property", "Macro")   |

### 5.2. 市場トレンド推移 (`outputs/market_trend_prophet.csv`)

Step 2の結果。時系列チャート用。

| カラム名      | 型    | 説明                                          |
| :------------ | :---- | :-------------------------------------------- |
| `ds`          | Date  | 年月 (YYYY-MM-DD)                             |
| `trend`       | Float | トレンド成分の値                              |
| `yhat`        | Float | 予測値（トレンド＋季節性）                    |
| `yhat_lower`  | Float | 予測信頼区間（下限）                          |
| `yhat_upper`  | Float | 予測信頼区間（上限）                          |
| `is_forecast` | Bool  | `True`: 将来予測期間, `False`: 実績(学習)期間 |

### 5.3. ハイブリッド予測詳細 (`outputs/hybrid_prediction_results.csv`)

Step 3の最終モデルを用い、Testデータ(2025年)または任意のシナリオに対する予測結果。
**Pydeck (地図) や Plotly (ドリルダウン) のメインソースとなる。**

| カラム名              | 型     | 説明                                  |
| :-------------------- | :----- | :------------------------------------ |
| `transaction_date`    | Date   | 取引時点（予測対象日）                |
| `NearestStation`      | String | 最寄駅（地図マッピング用キー）        |
| `DistrictName`        | String | 行政区・町名                          |
| `Age`                 | Int    | 築年数                                |
| `actual_price`        | Float  | 実測坪単価（将来予測の場合は null）   |
| `predicted_total`     | Float  | **最終予測坪単価** (Trend + Residual) |
| `component_trend`     | Float  | トレンド成分 (Prophet由来)            |
| `component_structure` | Float  | 構造成分 (LGBM由来の残差)             |
| `error_abs`           | Float  | 絶対誤差                              |

### 5.4. モデル精度指標 (`outputs/cv_metrics.csv`)

モデルの信頼性評価用。

| カラム名      | 型    | 説明                           |
| :------------ | :---- | :----------------------------- |
| `fold_id`     | Int   | Fold番号 (0〜4)                |
| `train_start` | Date  | 学習開始日                     |
| `train_end`   | Date  | 学習終了日                     |
| `valid_start` | Date  | 検証開始日                     |
| `valid_end`   | Date  | 検証終了日                     |
| `rmse`        | Float | Root Mean Squared Error        |
| `mae`         | Float | Mean Absolute Error            |
| `mape`        | Float | Mean Absolute Percentage Error |

## 6. 技術要件 (Technical Requirements)

- **言語**: Python 3.x
- **ライブラリ**:
  - `pandas`, `numpy` (データ処理)
  - `prophet` (時系列解析)
  - `lightgbm` (機械学習)
  - `scikit-learn` (前処理・検証・評価)
- **再現性**: `random_state=42` で統一する。
- **エラーハンドリング**: データ欠損や異常値に対して適切な処置（除外または補完）を行うコードを含めること。
- **ディレクトリ**: 実行時に `outputs/` フォルダが存在しない場合は自動生成すること。
