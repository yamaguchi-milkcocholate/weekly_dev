# PNG間取り図 → SVG変換 PoC

## 目的

現在のワークフロー（PNG間取り図をBlenderに配置 → 手動でオブジェクトをなぞる）の効率化。
PNG → SVG変換により、BlenderへのSVGインポートでカーブ/メッシュとして自動オブジェクト化できるか検証する。

## ワークフロー比較

```
【現在】 PNG → Blenderに背景配置 → 手動でオブジェクトをなぞる（時間かかる）
【提案】 PNG → SVGトレース → BlenderにSVGインポート → カーブ/メッシュとして自動オブジェクト化
```

## 環境構築

```bash
brew install --cask inkscape   # Inkscape 1.4.3
brew install potrace           # トレースエンジン（Inkscape内部でも使用されている）
brew install imagemagick       # 画像前処理（2値化）
```

## 変換手順

### 1. PNG → PBM（白黒2値化）

```bash
magick input/madori_1ldk.png -colorspace Gray -threshold 70% temp.pbm
```

- `-colorspace Gray`: グレースケール化
- `-threshold 70%`: 70%以上の明度を白、それ以下を黒に2値化

### 2. PBM → SVG（ベクタートレース）

```bash
potrace temp.pbm -s -o output/madori_trace_70.svg
```

- `-s`: SVG出力
- potraceがラスター画像の輪郭を検出し、ベジェ曲線のパスに変換

### ワンライナー

```bash
magick input/madori_1ldk.png -colorspace Gray -threshold 70% pbm:- | potrace -s -o output/madori_trace.svg
```

## 検証結果

入力画像: `input/madori_1ldk.png`（1LDK間取り図）

### 閾値による比較

| 項目 | 閾値50%（デフォルト） | 閾値70% |
|---|---|---|
| 壁線 | 薄くて欠落が多い | しっかり再現 |
| 文字 | ほぼ消えている | 読める程度に残る |
| 家具・設備 | ほぼ消えている | 形状が残っている |
| 出力ファイル | `output/madori_trace_default.svg` (30KB) | `output/madori_trace_70.svg` (40KB) |

**閾値70%が最適**。壁線・ドア・設備の形状がかなり忠実に再現された。

### 課題

- 文字（部屋名・帖数）が不要なパスとして含まれる
- 家具アイコン（ソファ等）も同様に不要パスになる
- 壁の「中心線」ではなく「外形輪郭」が取れるため、壁厚の扱いに注意が必要
- ドア・窓の開口部が閉じたパスになる場合がある

## Claude Code スキルによる自動化

### 背景

上記の手動変換手順（閾値の決定 → ImageMagick 2値化 → potrace変換 → プレビュー生成 → 比較評価）は、毎回同じ判断フローを辿る定型作業である。
これをClaude Codeのスキル（`.claude/skills/floor_plan_to_video_sub_trace/SKILL.md`）として定義し、自然言語の指示だけで一連のパイプラインを実行できるようにした。

### スキルの仕組み

```
ユーザー: "/floor_plan_to_video_sub_trace @input/madori_1ldk_2.png"
    ↓
Claude Code が SKILL.md の手順に従い自動実行:
    1. 入力画像を読み取り、特性を分析（壁線の太さ、背景色、ノイズ等）
    2. 画像特性に応じた閾値を判断（色付き背景 → 70%、ノイズ多 → 50% 等）
    3. 複数閾値で変換を実行（ImageMagick → potrace パイプライン）
    4. プレビューPNGを生成・読み取り、品質を評価
    5. 比較表を提示し、最適な閾値を推奨
```

**ポイント**: 閾値の判断をスキル内の判断基準テーブルとして定義しているため、画像の特性に応じた適応的な変換が可能。単純なシェルスクリプトでは実現できない「画像を見て判断する」工程をClaude Codeが担う。

### 実行例

#### 例1: madori_1ldk_2（白背景・高コントラスト）

```
入力: input/madori_1ldk_2.png（1LDK、洋室7.0帖+LDK13.0帖）
特性: 壁線が太く明瞭、白背景、家具アイコンあり
```

閾値70%と50%で比較 → **70%を推奨**

| 評価項目 | 70%（推奨） | 50% |
|---|---|---|
| 壁線の再現 | 太く明瞭、欠落なし | やや細いが構造は維持 |
| 文字の残留 | しっかり残る（後編集で判別しやすい） | 一部欠落 |
| 家具・設備 | ドア弧・キッチン等が明瞭 | ドア弧が点線化 |
| ノイズ | ほぼなし | バルコニー部分に点線ノイズ |

出力: `output/madori_1ldk_2/madori_trace_70.svg`

#### 例2: madori_1ldk_3（色付き背景）

```
入力: input/madori_1ldk_3.png（1LDK、キッチン3.4帖+LD10.5帖+洋室7.0帖）
特性: 部屋ごとに色分け（紫・オレンジ）、壁線はやや細め
```

色付き背景への対応が必要なため、70%と80%で比較 → **70%を推奨**

| 評価項目 | 70%（推奨） | 80% |
|---|---|---|
| 壁線の再現 | 明瞭、構造が忠実 | 一部太く潰れ気味 |
| 色付き背景 | 完全に白に飛ばせている | MB/PS部分が黒く塗りつぶし |
| 家具・設備 | ドア弧・設備が明瞭 | 一部設備が潰れ |
| ノイズ | ほぼなし | 暗い領域が黒ベタ化 |

出力: `output/madori_1ldk_3/madori_trace_70.svg`

### 成果

| 項目 | 手動実行 | スキル自動化 |
|---|---|---|
| 実行方法 | コマンドを手打ち、閾値を試行錯誤 | `/floor_plan_to_video_sub_trace @画像パス` の一言 |
| 閾値判断 | 経験に基づく手動選択 | 画像特性を分析し適応的に決定 |
| 比較評価 | 目視で個別確認 | 自動で比較表を生成・推奨 |
| 所要時間 | 15-20分/画像 | 1-2分/画像 |
| 再現性 | 作業者依存 | スキル定義により一定品質 |

3種類の間取り図（白背景・高コントラスト・色付き背景）で検証し、いずれも壁線を忠実に再現するSVGを生成できた。

### 出力ファイル一覧

```
output/
├── madori_1ldk_1/          # 初回PoC（手動実行）
│   ├── madori_trace_50.svg
│   ├── madori_trace_70.svg
│   ├── preview_50.png
│   └── preview_70.png
├── madori_1ldk_2/          # スキル実行例1
│   ├── madori_trace_50.svg
│   ├── madori_trace_70.svg  ← 推奨
│   ├── preview_50.png
│   └── preview_70.png
└── madori_1ldk_3/          # スキル実行例2（色付き背景）
    ├── madori_trace_70.svg  ← 推奨
    ├── madori_trace_80.svg
    ├── preview_70.png
    └── preview_80.png
```

## 次のステップ

1. Inkscapeで不要パス（文字・家具）を削除し、壁線だけ残したSVGを作成
2. BlenderにSVGインポート → カーブオブジェクトとして取り込み
3. 押し出し等で3D化し、手動なぞりとの工数比較
