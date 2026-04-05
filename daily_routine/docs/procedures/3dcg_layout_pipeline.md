# 3DCGレイアウトパイプライン実行ガイド

## 概要

Blenderの3Dモデル(.blend)から間取りを抽出し、Claude Codeと対話しながら家具配置を最適化するワークフロー。

## クイックスタート

パイプラインの状態を確認するには:

```
/layout-pipeline
```

## パイプライン全体図

```
Phase 1: .blend → SVG + walls.json
    │  スキル: /floor-plan-extract
    ▼
Phase 2: SVG → drawioテンプレート
    │  スキル: /layout-floor-plan-annotate
    │  ★ ユーザー手作業: drawioで部屋・設備・配置不可を記入
    ▼
Phase 3: drawio → room_info.json + floor_plan_complete.svg
    │  スキル: /layout-floor-plan-annotate integrate
    ▼
Phase 4: アセット情報の準備
    │  スキル: /layout-asset-prep
    │  ★ ユーザー対話: 家具仕様・生活シナリオを提供
    ▼
Phase 5: リファレンス調査 + スコア基準作成（任意）
    │  スキル: /layout-research
    │  ★ Web検索で事例を調査 → 設計原則を抽出
    │  ★ ユーザー対話: 重視したい観点を収集
    ▼
Phase 6: レイアウト提案（refineループ）
    │  スキル: /layout-refine
    │  ┌──────────────────────────────────┐
    │  │ 6a: 配置  → エンジン実行          │
    │  │ 6b: 評価  ← SVG画像 + Geminiスコア │
    │  │ 6c: 修正  → 6aに戻る              │
    │  └──────────────────────────────────┘
    │  ★ ユーザー確認: 各バージョンの評価
    ▼
Phase 7: レンダリング確認
       スキル: /layout-render
```

---

## フェーズ別ガイド

### Phase 1: 間取り抽出

**目的**: 3Dモデルから2D平面図(SVG)と壁座標データを抽出する

**実行**:

```
/floor-plan-extract poc/3dcg_poc1/madori.blend
```

**やること**:

1. Claude Codeが.blendファイルの構造を確認
2. Blenderスクリプトを作成・実行（`scripts/run_blender.sh`経由）
3. SVGと壁データを生成

**出力確認**:

- `floor_plan.svg` を開いて壁・柱・開口部が正しく描画されているか確認
- 座標スケールがメートル単位で正しいか確認

**出力ファイル**: `floor_plan.svg`, `walls.json`, `floor_plan_meta.json`

---

### Phase 2: 空間アノテーション（テンプレート生成）

**目的**: SVGにユーザーが部屋・設備・配置不可領域を定義するためのdrawioテンプレートを作成

**実行**:

```
/layout-floor-plan-annotate
```

**やること**:

1. Claude CodeがSVGをBase64エンコードしてdrawioファイルに埋め込む
2. 凡例パーツ5種を配置

**ユーザー手作業**:

1. drawio.ioまたはデスクトップアプリでファイルを開く
2. 凡例パーツをコピーし、壁にピッタリ合わせて矩形を配置:
   - ① 部屋（青）: 部屋名を記入
   - ② ドア（ピンク）: ドアの位置に配置
   - ③ 窓（シアン）: 窓の位置に配置
   - ④ 固定設備（紫）: 設備名を記入
   - ⑤ 配置不可（赤破線）: 理由を記入（「通路」「通路(50%空いていれば良い)」等）
3. 保存

**Tips**: Alt+ドラッグで1px単位の細かい配置が可能

**出力ファイル**: `floor_plan_rooms.drawio`

---

### Phase 3: drawio統合

**目的**: drawioアノテーションを実座標に変換し、壁データと統合した完成版SVGを生成

**実行**:

```
/layout-floor-plan-annotate integrate
```

**やること**:

1. drawioのXMLをパースし、色コードでタイプを判定
2. drawioピクセル座標を実座標(m)に変換
3. 壁データと統合してroom_info.jsonとfloor_plan_complete.svgを生成

**出力確認**:

- `floor_plan_complete.svg` を開いて部屋・設備が正しく表示されているか確認
- 部屋のサイズが実測値と大きくずれていないか確認

**出力ファイル**: `room_info.json`, `floor_plan_complete.svg`

---

### Phase 4: アセット情報の準備

**目的**: 配置する家具の仕様と生活シナリオを定義する

**実行**:

```
/layout-asset-prep
```

**やること**:

1. Claude Codeが間取りSVGを読み、空間を把握
2. 対話形式で家具情報を収集:
   - 家具のリスト、サイズ、個数
   - 形状特徴（front/back）、配置ルール
   - グルーピング（desk+chair等）
3. 生活シナリオを定義:
   - 居住者情報、典型的な1日の流れ
   - 各シナリオの移動経路と検証ポイント

**ユーザーが提供するもの**:

- 配置したい家具のリストとサイズ
- GLBファイル（あれば）
- 生活パターンの説明

**出力ファイル**: `assets.json`, `life_scenarios.json`

---

### Phase 5: リファレンス調査 + スコア基準作成（任意）

**目的**: Web検索でレイアウト事例を調査し、設計原則を抽出してデザインスコア基準を作成する

**実行**:

```
/layout-research
```

**やること**:

1. Claude Codeが間取り・家具情報を把握
2. ユーザーと対話して調査条件を確定（間取りタイプ、用途、重視点）
3. Web検索で事例を収集、参考画像をダウンロード
4. 事例から設計原則を抽出してレポートを作成
5. ユーザーに「特に重視したい観点」を質問
6. 標準観点 + ユーザー要望を合成して `scoring_criteria.json` を生成

**ユーザーが提供するもの**:

- 居住者情報、用途の特徴
- 特に重視したい観点（任意）

**出力ファイル**: `layout_design_principles.md`, `research_images/`, `scoring_criteria.json`

**スキップ可能**: このフェーズは任意。Phase 6でスコアリングなしでも配置は可能。

---

### Phase 6: レイアウト提案（refineループ）

**目的**: 家具を具体的な座標に配置し、評価・修正を繰り返して最適なレイアウトを導く

**実行**:

```
/layout-refine
```

**refineループの流れ**:

#### 6a: 配置

1. Claude Codeが空間を画像で把握し、各家具の座標を決定
2. `placement_plan.json`に座標を記入
3. 配置エンジンを実行: `uv run python poc/3dcg_poc3/placement_engine.py`
4. PASS → 6bへ / FAIL → 座標修正して再実行

#### 6b: 評価（ユーザー主導）

1. Claude Codeがエンジン結果を報告
2. `scoring_criteria.json`が存在する場合、`uv run python poc/3dcg_poc3/layout_scorer.py`でGemini Pro 3.0によるデザインスコアを取得・報告
3. `layout_proposal.png`を画像として読み取り、動線+デザインスコアの所見を報告
4. **ユーザーも`layout_proposal.png`を確認する**
5. 修正点をフィードバック / 「OK」で完了

#### 6c: 修正

1. ユーザーのフィードバックに基づき座標を修正
2. バージョンを更新（v1→v2→v3...）
3. 6aに戻る

**進捗の見え方**: Claude Codeは各ステップで`[6a-1]` `[6a-2]` `[6b]`のようにタグ付きで進捗を報告する。長い沈黙はない。

**ユーザーの役割**:

- 各バージョンのSVGを確認し、フィードバックを提供
- 「この配置で良い」と承認するまでループ継続

**出力ファイル**: `placement_plan.json`, `layout_proposal.svg`, `layout_proposal.json`

---

### Phase 7: レンダリング確認

**目的**: 確定した配置をBlenderで3Dレンダリングし、視覚的に確認する

**実行**:

```
/layout-render
```

**やること**:

1. Blenderで間取り3Dモデルを開く
2. GLB家具モデルを配置座標にインポート
3. 複数アングル（俯瞰、パースペクティブ）でレンダリング

**問題があれば**: `/layout-refine`に戻って配置を修正

**出力ファイル**: レンダリング画像（PNG）

---

## 入出力ファイル一覧

| ファイル                  | 生成Phase | 使用Phase | 説明                     |
| ------------------------- | --------- | --------- | ------------------------ |
| `floor_plan.svg`          | 1         | 2         | 間取りSVG（実座標）      |
| `walls.json`              | 1         | 3, 6      | 壁・柱の座標データ       |
| `floor_plan_meta.json`    | 1         | 3         | SVG座標メタデータ        |
| `floor_plan_rooms.drawio` | 2         | 3         | アノテーション済みdrawio |
| `room_info.json`          | 3         | 4, 5, 6   | 部屋・配置不可の座標     |
| `floor_plan_complete.svg` | 3         | 4, 5, 6   | 完成版間取りSVG          |
| `assets.json`             | 4         | 5, 6, 7   | 家具アセット情報         |
| `life_scenarios.json`     | 4         | 5, 6      | 生活シナリオ             |
| `scoring_criteria.json`   | 5         | 6         | デザインスコア基準（任意）|
| `layout_design_principles.md` | 5     | -         | リファレンス調査レポート  |
| `design_scores.json`      | 6         | 6         | Geminiデザインスコア結果  |
| `placement_plan.json`     | 6         | 6, 7      | 配置方針（座標指定）     |
| `layout_proposal.svg`     | 6         | 7         | 配置結果SVG              |
| `layout_proposal.png`     | 6         | 6         | 配置結果PNG（空間認識用）|
| `layout_proposal.json`    | 6         | 7         | 配置結果データ           |

---

## 途中再開

どのフェーズからでも再開可能。`/layout-pipeline`で現在の状態を確認できる。

**前提**: 各フェーズの入力ファイルが出力ディレクトリに存在すること。

---

## よくある質問

### Q: 新しい間取りで始めるには？

A: `.blend`ファイルを用意し、`/floor-plan-extract`からスタート。

### Q: 家具を追加・変更したい

A: `assets.json`を編集し、`/layout-refine`からやり直す。

### Q: 配置エンジンがFAILする

A: エラーメッセージに衝突相手が表示される。`placement_plan.json`の該当家具の座標を衝突を避ける方向に調整する。

### Q: drawioの座標がずれる

A: `layout-floor-plan-annotate`スキルの既知の問題。SVG画像のdrawio上での位置ずれが原因。基準点2点のアフィン変換で補正可能。

### Q: レイアウトのセンスが悪い

A: Phase 5で`/layout-research`を実行してデザインスコア基準を作成する。Phase 6のrefineループで`poc/3dcg_poc3/layout_scorer.py`がGemini Pro 3.0で配置を評価し、「壁面密着」「採光優先度」「中央開放」等の観点でスコアと改善提案を出す。ユーザーのフィードバックを具体的に（「この家具を壁際に」「この通路を広く」等）伝えることでも改善する。
