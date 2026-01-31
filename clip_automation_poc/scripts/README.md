# スクリプト一覧

## generate_mesh_master.py

東京23区のメッシュマスターデータを生成するスクリプト。

### 入力

- `data/station/station20251211free.csv` - 駅データCSV
- `data/boundary/` - 行政区域GeoJSON

### 出力

- `data/tokyo_23_mesh_master_multi_30min.csv` - 徒歩圏内全駅モード（デフォルト）
- `data/tokyo_23_mesh_master_single.csv` - 最寄駅1つモード

### 実行方法

```bash
# 徒歩圏内全駅モード（デフォルト: 徒歩30分以内）
python scripts/generate_mesh_master.py

# 最寄駅1つのみモード
python scripts/generate_mesh_master.py --mode single

# 徒歩圏内全駅モード（徒歩20分以内）
python scripts/generate_mesh_master.py --mode multi --max-walk-minutes 20

# メッシュサイズを変更（例: 50m）
python scripts/generate_mesh_master.py --mesh-size 50
```

### 説明

駅データと行政区域境界から、東京23区を100mメッシュに分割したマスターデータを生成します。

**モード**:

- `single`: 各メッシュに最寄駅1つのみを紐付け（横持ち形式: 1メッシュ1行）
- `multi`: 各メッシュに徒歩圏内の駅をすべて紐付け（縦持ち形式: 1メッシュ×N駅）

**パラメータ**:

- `--mode`: 駅紐付けモード（デフォルト: `multi`）
- `--max-walk-minutes`: 最大徒歩分数（デフォルト: 30.0）
- `--mesh-size`: メッシュサイズ（メートル、デフォルト: 100.0）

---

## aggregate_mesh_price.py

メッシュ単位で不動産取引価格を集約するスクリプト。

### 入力

- `data/tokyo_23_mesh_master.csv` - メッシュマスターデータ
- 国土交通省 MLIT API（環境変数 `REINFOLIB_API_KEY` が必要）

### 出力

- `data/tokyo_23_mesh_price.csv` - メッシュ別坪単価集約データ

### 実行方法

```bash
python scripts/aggregate_mesh_price.py
```

### 説明

MLIT APIから東京23区の不動産取引データ（2023-2024年）を取得し、メッシュ単位で坪単価を集約します。

---

## visualize_mesh_colored.py

メッシュマスターデータを3D可視化するスクリプト。

### 入力

- `data/tokyo_23_mesh_master.csv` - メッシュマスターデータ

### 出力

- `output/mesh_verification_colored.html` - インタラクティブ3D可視化HTML

### 実行方法

```bash
python scripts/visualize_mesh_colored.py
```

### 説明

メッシュマスターを駅別に色分けした3D可視化をPyDeckで生成し、HTMLファイルとして出力します。
