---
name: floor_plan_to_video_sub_refine
description: 家具配置のrefineループを実行する。配置方針の作成→配置エンジン実行→SVG画像評価→修正を繰り返し、最適なレイアウトを導く。家具の配置提案、レイアウト改善、配置エンジンの実行、placement_plan.jsonの作成・修正、配置評価に関連するタスクで必ずこのスキルを参照すること。
argument-hint: [出力ディレクトリ]
allowed-tools: Bash(uv run *), Bash(magick *), Bash(mkdir *), Bash(ls *), Bash(cp *)
---

# floor_plan_to_video_sub_refine

家具配置のrefineループ（配置→評価→修正）を実行するスキル。

## 大原則: 座標を決めるのはClaude Code

**placement_plan.jsonにClaude Codeが具体的な座標(cx, cy)を記入する。** 配置エンジン(placement_engine.py)はその座標に家具を配置し、重なりチェックだけ行う。座標を探索するロジック（グリッドサーチ等）はエンジンに持たせない。

理由:
- グリッドサーチは空間認識ではなくブルートフォースであり、空間の理解に基づかない
- 柱や通路の位置を理解して「ここなら置ける」と判断するのはClaude Codeの能力
- エンジンが座標を探索すると、意図しない位置に配置される

## 前提条件

以下のファイルが出力ディレクトリに存在すること:
- `floor_plan_complete.svg` — 間取り完成版SVG
- `assets.json` — 家具アセット情報
- `room_info.json` — 部屋・配置不可の座標（エンジンとClaude Code両方が使用）
- `walls.json` — 壁座標データ（エンジンが使用。Claude Codeは読まない）
- `placement_engine.py` — 配置エンジン（`.claude/skills/floor_plan_to_video_sub_refine/scripts/placement_engine.py`）
- `scoring_criteria.json` — デザインスコア基準（任意。存在すればPhase 5bで使用）

### 既存イテレーションの確認

`iterations/HISTORY.md` が出力ディレクトリに存在する場合、読み取って過去の経緯を報告する:

→ 報告:
```
[resume] 過去{N}回のrefineがあります。最新は{vN}（スコア{score}）。
  直近FB: {feedback}
  直近変更: {changes}
  ここから再開します
```

存在しない場合は初回実行として進める。

## 出力

- `placement_plan.json` — 配置方針（Claude Codeが作成・更新）
- `layout_proposal.svg` — 配置結果SVG（エンジンが生成）
- `layout_proposal.json` — 配置結果データ（エンジンが生成）
- `design_scores.json` — デザインスコア（layout_scorer.pyが生成。scoring_criteria.json存在時のみ）

## データソースの使い分け（重要）

画像認識と構造化データには異なる役割がある。混同するとスタックの原因になる。

| 判断の種類 | データソース | 例 |
|-----------|-----------|-----|
| どこにどう置くか（定性） | **画像**（空間認識） | 「西壁にデスクを」「窓の横に」 |
| cx, cyの数値決定（定量） | **JSON**（boundary座標） | cx = x_min + depth/2 |
| 配置結果の良し悪し | **画像**（直感的判断） | 「通路が塞がれている」 |
| 修正方針 | **画像** + ユーザーFB | 「クローゼット前を空ける」 |

**禁止事項**: 画像から座標の数値を推論すること（thinkingが膨大になりスタックする）

| フェーズ | 読むファイル |
|---------|------------|
| 5a 配置 | floor_plan_complete.png（画像）→ 配置方針。assets.json + room_info.json → 座標計算。scoring_criteria.json → デザイン考慮事項 |
| 5b 評価 | layout_proposal.png（画像）+ エンジン出力 + design_scores.json（Geminiの評価結果） |
| 5c 修正 | layout_proposal.png（画像）+ ユーザーFB + design_scores.jsonの低スコア項目・改善提案 → placement_plan.json修正 |

walls.jsonはエンジンのみが使用。Claude Codeは読まない。
Claude Codeはroom_info.jsonの部屋境界から壁位置を取得する。

**壁厚オフセット**: room_info.jsonの境界座標は部屋内面の理論値であり、Blenderモデルの壁構造体（壁厚0.15〜0.20m）やコーナー柱とは一致しない。壁面に家具を配置する際は、壁面座標から**0.08mのオフセット**（壁厚マージン）を加算し、壁構造体との衝突を防ぐ。壁衝突が解消しない場合は0.10〜0.15mに調整する。

---

## 進捗報告の原則（重要）

各ステップの**開始時と完了時にユーザーへ短く報告する**。長い沈黙を避け、途中経過が見えるようにする。

報告の例:
- `「[5a-1] 間取りSVGを読み取り中...」`
- `「[5a-2] assets.json + room_info.json を確認しました。家具6種10個を配置します」`
- `「[5a-3] placement_plan.json を作成しました。配置エンジンを実行します...」`
- `「[5a-4] エンジン結果: PASS（全10個配置成功）」`
- `「[5b] layout_proposal.svg を確認してください。所見: ...」`

**ルール**: ファイル読み込みや処理の前後で必ず1行出力する。ユーザーが「今何をしているか」を常に把握できるようにする。

---

## Phase 5a-0: 戦略探索（初回のみ）

**目的**: 構造的に異なる配置戦略を2-3パターン並列に生成・実行し、最良の戦略をユーザーが選択する。局所最適への陥りを防ぐ。

**実行条件**: 初回実行時のみ。`iterations/HISTORY.md` が既に存在する場合（再開時）はスキップし、Phase 5a に進む。

### Step 0-1: 空間認識（画像）+ デザイン基準の把握

→ 報告: `「[5a-0-1] 間取りSVGを読み取り中...」`

`floor_plan_complete.png`を**画像として読み取る**（PNGがなければSVGから`rsvg-convert -w 1600 -o floor_plan_complete.png floor_plan_complete.svg`で生成）。以下を定性的に把握する:
- 各部屋の形状・広さの印象
- 壁沿いで家具を置けそうな場所
- ドア・窓の位置と、家具を置くと塞がれそうな場所
- 全体の動線イメージ

**`scoring_criteria.json` が存在する場合**: ファイルを読み、デザイン原則を把握する。

→ 報告: `「[5a-0-1] 空間把握完了。デザイン基準{N}観点を確認」`

### Step 0-2: 壁面インベントリの作成

Phase 5a の Step 1b と同じ手順で壁面セグメントを列挙する（後述のStep 1bを参照）。

→ 報告: 壁面インベントリを表示

### Step 0-3: 戦略立案

空間認識と壁面インベントリに基づき、**構造的に異なる**配置戦略を2-3パターン言語化する。

**「構造的に異なる」の定義**: 壁面割り当て・ゾーニング・家具のグルーピングが異なること。座標の微差（cx=1.5 vs cx=2.0）は構造的差異ではない。

**戦略差異の例**:
- A: 西壁集約型 — 全ワーク家具を西壁に集約、東側は動線確保
- B: 対面配置型 — 2台のデスクを東西壁に対面配置、中央にcloset
- C: 中央分離型 — closetをroom dividerとして使い南北に2ゾーン分割

各戦略には以下を含める:
1. **戦略名**（短い名称）
2. **説明**（どの壁面にどの家具群を割り当てるか）
3. **狙い**（この配置で何を優先するか）

`candidates/comparison.json` に戦略メタデータを書き出す:

```json
{
  "strategies": [
    {"id": "a", "name": "西壁集約型", "description": "全ワーク家具を西壁に...", "engine_result": "N/A", "overall_score": null, "selected": false},
    {"id": "b", "name": "対面配置型", "description": "...", "engine_result": "N/A", "overall_score": null, "selected": false}
  ],
  "winner": null,
  "reason": ""
}
```

→ 報告:
```
[5a-0-3] 配置戦略を立案しました:
  A: 西壁集約型 — 全ワーク家具を西壁に集約、東側は動線確保
  B: 対面配置型 — 2台のデスクを東西壁に対面配置
  C: 中央分離型 — closetをroom dividerとして使い南北に2ゾーン分割
```

### Step 0-4: 候補ディレクトリ準備

```bash
uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/prepare_candidates.py <出力ディレクトリ> --candidates a b c
```

### Step 0-5: 並列実行（Agent tool）

Claude Code が **1つのメッセージで** 2-3個の Agent を同時起動する。各 Agent に以下を渡す:

1. **空間情報**: room_info.jsonの部屋境界座標（数値）、壁面インベントリ（Step 0-2の結果）
2. **家具リスト**: assets.jsonの全アセット（ID、サイズ、placement_rules）
3. **担当戦略**: Step 0-3で決めた戦略の説明
4. **座標計算ルール**: 後述の Phase 5a Step 2 のステップA/B/C の内容
5. **配置チェックリスト**: 後述の Phase 5a のチェックリスト
6. **候補ディレクトリパス**: `<出力ディレクトリ>/candidates/{a,b,c}`

**Agent プロンプトテンプレート**:

```
あなたは配置戦略「{strategy_name}」を実行するエージェントです。

## 空間情報
{room_info_summary（部屋境界座標、壁面インベントリ）}

## 家具リスト
{assets_summary（ID, サイズ, 配置ルール）}

## あなたの戦略
{strategy_description}

## 実行手順
1. 戦略に従い、配置順序の原則に沿って1家具ずつ座標を計算する
2. placement_plan.jsonを {candidate_dir}/placement_plan.json に書き出す
   - version: "v0_{candidate_id}"
   - strategy: "{strategy_name}: {strategy_description}"
3. 配置エンジンを実行:
   uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/placement_engine.py {candidate_dir}
4. エンジン結果（PASS/FAIL + 各家具のOK/NG）を報告して終了

## 座標計算ルール
{SKILL.md Phase 5a Step 2 のステップA/B/C の全文}

## 配置チェックリスト
{SKILL.md Phase 5a のチェックリスト全文}

## 配置順序の原則
1. 大型壁付け家具（bed, closet）: 最も長い壁面を先に確保
2. ワークステーション（desk + chair）: 壁面にbackを向けて配置
3. ダイニング（dining_table）: キッチン動線の距離を最小化
4. 小型壁付け家具（counter）: 残った壁面に並べて配置

## 重要
- walls.jsonは読まない（エンジンが使用）
- 画像から座標を推論しない（JSONの数値のみ使用）
- エンジンがFAILしても再実行しない。結果をそのまま報告する
- 1家具ずつ座標を計算し報告する
```

各 Agent の実行内容:
1. 戦略に従い座標計算 → `placement_plan.json` 書き出し
2. `uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/placement_engine.py <candidate_dir>` 実行
3. エンジン結果を報告して終了（FAILでも再実行しない）

### Step 0-6: 結果比較 + ユーザー選択

全 Agent 完了後、Claude Code が:
1. 各候補の `layout_proposal.png` を**画像として読み取る**
2. エンジン結果（PASS/FAIL）を `layout_proposal.json` から確認
3. （任意）`uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/layout_scorer.py <candidate_dir>` を各候補に実行
4. `comparison.json` の各戦略に `engine_result` と `overall_score` を記入

→ 報告:
```
[5a-0-6] 候補の配置結果:

| 候補 | 戦略 | エンジン | スコア | 所見 |
|------|------|----------|--------|------|
| A | 西壁集約型 | PASS | 0.72 | 動線良好、東側空き |
| B | 対面配置型 | PASS | 0.68 | デスク間距離4m |
| C | 中央分離型 | FAIL | - | closetが動線を分断 |

各候補の layout_proposal.png を確認してください。
どの戦略をベースにrefineしますか？（A/B/C）
```

### Step 0-7: 勝者確定

ユーザーが候補を選択したら:

1. 勝者の `placement_plan.json`, `layout_proposal.svg`, `layout_proposal.png`, `layout_proposal.json` をメイン出力ディレクトリにコピー
2. `placement_plan.json` の `version` を `"v1"` に更新
3. `comparison.json` の勝者に `selected: true`、`winner` と `reason` を記入
4. 候補をアーカイブ:
   ```bash
   uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/save_iteration.py <出力ディレクトリ> v0_candidates --candidates-dir
   ```
5. 勝者を v1 として記録:
   ```bash
   uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/save_iteration.py <出力ディレクトリ> v1
   ```

→ 報告: `「[5a-0-7] 戦略{name}を選択。v1として記録しました。Phase 5b（評価）に進みます」`

6. **Phase 5b に進む**（Phase 5a の Step 1〜3 はスキップ）

---

## Phase 5a: 配置

**フロー分岐**:
- **Phase 5a-0 完了後**: Step 1, 1b, 2, 3 をスキップ → Step 4（イテレーション記録）→ Phase 5b
- **再開時（HISTORY.md 存在）**: 従来通り Step 1 から実行
- **単一戦略モード（ユーザー指定）**: 従来通り Step 1 から実行

### Step 1: 空間認識（画像）+ デザイン基準の把握

→ 報告: `「[5a-1] 間取りSVGを読み取り中...」`

`floor_plan_complete.png`を**画像として読み取る**（PNGがなければSVGから`rsvg-convert -w 1600 -o floor_plan_complete.png floor_plan_complete.svg`で生成）。以下を定性的に把握する:
- 各部屋の形状・広さの印象
- 壁沿いで家具を置けそうな場所
- ドア・窓の位置と、家具を置くと塞がれそうな場所
- 全体の動線イメージ

**`scoring_criteria.json` が存在する場合**: ファイルを読み、デザイン原則を把握する。配置方針を決める際にこれらの観点を考慮する。特にcustom観点（ユーザーが重視したい観点）には注意を払う。

→ 報告: `「[5a-1] 空間把握完了。デザイン基準{N}観点を確認。配置方針を決めます」`

**ここでは座標の数値を考えない。** 「西壁にデスク」「窓際に寄せる」「この通路は空ける」のような定性的な方針のみ。

### Step 1b: 壁面インベントリの作成

room_info.jsonの各部屋（type="room"）の境界座標から壁面セグメントを列挙する。各壁面の有効長と配置予定家具の合計幅を照合する。**有効長は壁厚マージン（片側0.05m）を差し引いた保守的な値で計算する。**

#### 壁面セグメントの算出方法

1. 各部屋のreal_mから4辺の壁を取得（x_min=西壁, x_max=東壁, y_min=南壁, y_max=北壁）
2. 各壁からドア・通路（type="no_place"）が占める区間を除外し、有効セグメントを算出
3. 隣接するfixture（キッチン、水回り等）との共有辺は壁ではないため除外
4. 各セグメントの有効長から**壁厚マージン（片側0.05m、合計0.10m）**を差し引く。ただしセグメント両端がno_place境界（通路端）の場合、その側のマージンは不要（壁構造体がないため）

#### 通路クリアランスの確保

壁面セグメントに家具を配置する際、隣接する出入口への歩行通路を確保する:

- 出入口（no_place領域）から**0.6m以上**の歩行通路幅を確保すること
- 出入口間の壁セグメント幅が **家具幅 + 1.2m 未満** の場合、そのセグメントへの配置は不可として扱う（両側に0.6mずつ必要）
- 片側のみ出入口に隣接する場合は **家具幅 + 0.6m 未満** で配置不可

これにより、配置エンジンの動線検証（連結性チェック）で失敗するケースを事前に回避できる。

例（リビング南壁 y_min=-1.308）:
- 全長: x[-2.206, 3.003] = 5.21m
- キッチン通路除外: x[-1.849, -1.178]
- 水回り通路除外: x[0.42, 1.091]
- 廊下通路除外: x[1.847, 3.003]
- 有効セグメント（壁厚マージン適用前）: x[-2.206, -1.849](0.36m), x[-1.178, 0.42](1.60m), x[1.091, 1.847](0.76m)
- 壁厚マージン適用後: x[-2.206, -1.849](0.26m※), x[-1.178, 0.42](1.50m), x[1.091, 1.847](0.66m)
  ※ 西端は部屋コーナー(0.05m減)、通路側はマージン不要だが狭すぎて実用不可

→ 報告:
```
[5a-1b] 壁面インベントリ:
■ 寝室:
  - 西壁(x=-2.206): 有効長2.93m
  - 北壁(y=4.044): 有効長2.93m
■ リビング:
  - 西壁(x=-2.206): 有効長3.77m → desk_1(1.4m) + counter_1(0.8m) ✓
  - 東壁(x=3.003): 有効長1.69m → desk_2(1.4m) ✓
  - 南壁セグメント x[-1.178, 0.42]: 1.50m（壁厚マージン後）→ counter_1(0.8m) ✓
  - 北壁: ベランダ引き戸（50%制約あり）
```

壁面長が不足する場合、壁面割り当てを再検討する。

**早期代替検討ルール**: セグメント有効長 < 配置予定家具の合計幅 の場合、エンジンFAILで発覚する前にこの段階で代替策を決める:
1. 家具数を減らす（1台を別の壁面に移動）
2. 別のセグメントや別の壁面に再割り当て
3. 家具を他の部屋に移動

### Step 2: 配置方針の決定 + 座標計算（JSON）

→ 報告: `「[5a-2] assets.json + room_info.json から座標を計算中...」`

`assets.json`と`room_info.json`を読み、Step 1の方針に従って**1家具ずつ座標を計算し報告する**。

**2段階で処理する:**
1. **方針（画像から）**: 「desk_1はwork_aゾーンの西壁にbackを付ける」
2. **座標（JSONから）**: work_a.boundary.x_min=-2.21, desk.depth=0.6 → cx=-2.21+0.3=-1.91

**報告の例:**
```
[5a-2] bed_1: 北壁にヘッドボード → cx=-0.75, cy=3.30, front=S
[5a-2] desk_1: 西壁にback → cx=-1.91, cy=1.80, front=E
[5a-2] desk_2: 東壁にback → cx=2.70, cy=1.00, front=W
...
[5a-2] 全10個の座標決定完了。placement_plan.json を書き出します
```

**重要: 1家具ごとに報告する。** 悩んだらまず妥当な位置に置いてエンジンに検証させる。完璧を目指さない。

**placement_plan.json のフォーマット:**

```json
{
  "version": "v1",
  "strategy": "配置戦略の説明",
  "placement_order": [
    {
      "id": "bed",
      "instance": 1,
      "cx": -0.75,
      "cy": 3.30,
      "front_dir": "S",
      "reason": "北壁にヘッドボード"
    }
  ]
}
```

**各フィールドの意味:**
- `id`: assets.jsonのアセットID
- `instance`: 同一IDの何番目か（1始まり）
- `cx`, `cy`: 家具中心のBlender座標（メートル）
- `front_dir`: 家具のfrontが向く方向（N/S/E/W）
- `reason`: 短い理由（1行以内）

**front_dirと家具サイズの関係:**
- N/S方向: width=幅, depth=奥行（そのまま）
- E/W方向: width↔depthが入れ替わる

**配置順序の原則（v1の品質を決定する）:**

家具を以下の順序で配置する。大型家具を先に壁際に固定し、小型家具を残りの壁面に配置する:

1. **大型壁付け家具**（bed, closet）: 最も長い壁面を先に確保
2. **ワークステーション**（desk + chair）: 壁面にbackを向けて配置。chairの引きスペース(0.5m)を含めて計画
3. **ダイニング**（dining_table）: キッチン動線の距離を最小化
4. **小型壁付け家具**（counter ×3）: 残った壁面に**並べて**配置

**禁止**: counterを3箇所に分散させない。連続した壁面に並べるか、最大2グループに分ける。

**座標決定の方法（壁面セグメント基準）:**

#### ステップA: 配置先の壁面セグメントを選択

Step 1bの壁面インベントリから、家具のwidthが収まるセグメントを選ぶ。

#### ステップB: 壁沿い家具の座標計算

backを壁につける家具（counter, closet, desk等。assets.jsonのplacement_rules.wall_relation参照）:

1. **壁に垂直な座標**: 壁面の座標 ± (depth/2 + 0.08)  ※壁厚マージン0.08m
   - 西壁 → cx = 壁のx座標 + depth/2 + 0.08
   - 東壁 → cx = 壁のx座標 - depth/2 - 0.08
   - 南壁 → cy = 壁のy座標 + depth/2 + 0.08
   - 北壁 → cy = 壁のy座標 - depth/2 - 0.08
2. **壁に平行な座標**: セグメント内で、他の家具と0.1m以上の隙間を確保して配置

#### ステップC: その他のルール

1. **他家具との距離**: 前に配置した家具から0.6m以上離す
2. **通路との距離**: no_place領域に重ならないようにする

数値計算のみで決定する。SVG画像を見て「ここが良さそう」と推論しない。

### 配置チェックリスト（placement_plan.json書き出し前に必ず確認）

全項目を確認し、違反があれば座標を修正してから書き出す:

```
□ 全counter, closetのbackが壁面セグメント上にあるか
□ 全counterが壁沿いに連続配置か（3箇所分散していないか）
□ 全deskのbackが壁面に接しているか
□ chairの後ろに0.5m以上の引きスペースがあるか
□ dining_tableからキッチン入口まで2m以内か
□ 壁から1.5m以上離れた位置にcounter/closetがないか
□ 壁沿い家具の座標に壁厚マージン(0.08m)が加算されているか
□ 壁面セグメントの有効長に壁厚マージン(片側0.05m)が反映されているか
□ 出入口隣接セグメントに通路クリアランス(0.6m)が確保されているか
```

→ 報告: `「[5a-check] チェックリスト: 7/7 PASS」`

→ 報告: `「[5a-2] placement_plan.json 作成完了（v1, 家具10個）」`

### Step 3: 配置エンジンの実行

**Phase 5a内でのエンジン実行は1回のみ。** エンジンFAILでもStep 4（記録）→ Phase 5b（評価）→ ユーザー報告 → Phase 5c（修正）の順に進む。5a内でのループ（エンジン→座標修正→エンジン再実行）は禁止。

→ 報告: `「[5a-3] 配置エンジンを実行中...」`

```bash
uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/placement_engine.py <出力ディレクトリ>
```

→ 報告: エンジンの出力（PASS/FAIL + 各家具のOK/NG）をそのまま表示

**出力の読み方:**
- `OK`: 重なりなし
- `NG: 壁:平面.004, 柱:立方体.001`: 壁や柱との衝突
- `NG: desk_1`: 他の家具との重なり
- `NG: 配置不可:通路`: 配置不可領域との重なり
- `NG: 配置不可(50%):通路(50%)(占有65%)`: 50%ルール違反

**全体判定:**
- `PASS`: 全家具の配置が成功
- `FAIL`: 1つ以上の衝突あり（問題家具は赤枠で表示）

**PASS/FAILに関わらず、Step 4（記録）→ Phase 5b（評価）に進む。** FAILでもエンジンはSVG/PNG/JSONを出力するため、画像確認・デザインスコア取得・ユーザーFB収集が可能。

---

**【強制ルール】エンジン実行直後の行動**

エンジン実行後、PASS/FAILに関わらず、Claude Codeの**次の行動は必ず`save_iteration.py`の実行**である。以下は禁止:

- FAILを理由にsave_iteration.pyをスキップすること
- 座標を修正してからエンジンを再実行すること
- 「まず問題を直してから記録」と判断すること

座標の修正はPhase 5cの責務であり、Phase 5a内では行わない。

---

### Step 4: イテレーション記録

→ 報告: `「[5a-4] イテレーション {version} を記録中...」`

```bash
uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/save_iteration.py <出力ディレクトリ> <version>
```

→ 報告: `「[5a-4] {version} を iterations/{version}/ に保存しました」`

---

## Phase 5b: 評価（画像で空間把握 + デザインスコア + ユーザー確認）

### Step 1: エンジン出力を報告

→ 報告: エンジンの衝突チェック + 動線検証結果をそのまま表示

### Step 2: デザインスコアの取得（scoring_criteria.json存在時のみ）

`scoring_criteria.json` が存在する場合、Gemini Pro 3.0によるデザインスコア評価を実行する:

```bash
uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/layout_scorer.py <出力ディレクトリ>
```

→ 報告: デザインスコアの結果をそのまま表示

**出力の読み方:**
- 各観点のスコア（0.0〜1.0）。0.7未満は ⚠ 付き
- 低スコアの原因家具と理由
- 改善提案
- `[custom]` タグはユーザーが重視した観点

### Step 2b: デザインスコアを含めてイテレーション記録を更新

```bash
uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/save_iteration.py <出力ディレクトリ> <現バージョン>
```

### Step 3: PNGを画像として読み取る

`layout_proposal.png`を**画像として読み取る**（SVGではなくPNG）。配置エンジンがSVGからPNGを自動生成する。PNGは純粋な画像データなので高速に処理できる。

→ 読み取り完了したら**即座に**報告: `「[5b-3] PNG読み取り完了」`

### Step 4: 所見を報告

画像の動線可視化（緑/オレンジ/赤）とデザインスコアを総合して、気づいた点を報告する。

→ 報告:
```
[5b-4] 所見:
- [動線に関する気づき（1行）]
- [デザインスコアで低い観点と原因家具（1行）]
layout_proposal.svg を確認してください。修正したい箇所があれば教えてください。
```

デザインスコアが0.7未満の基準がある場合、その基準と原因家具を所見に必ず含める。

### Step 5: ユーザーのフィードバックを待つ

ユーザーがSVGを確認し、修正点をフィードバック。「OK」なら完了。

---

## Phase 5c: 修正（画像 + ユーザーFB）

### Step 1: 修正方針の決定（画像 + デザインスコア）

→ 報告: `「[5c-1] layout_proposal.svg とデザインスコアを見て修正方針を検討中...」`

`layout_proposal.png`を**画像として読み取り**、ユーザーのフィードバックと`design_scores.json`の低スコア項目を照合して修正方針を決める。

- 画像を見て「ユーザーが指摘した問題」を視覚的に確認する
- デザインスコアが0.7未満の基準を優先的に改善する
- 複数基準で低スコアの家具を最優先で移動する
- Geminiの改善提案を修正方針の参考にする
- 修正方針は定性的に決める（「closetを東に移動」「counter間の隙間を広げる」）

### Step 2: 座標修正（JSONベース）

→ 報告: `「[5c-2] placement_plan.json を修正中...」`

修正方針に基づき、room_info.jsonの部屋境界座標を参照して新しいcx, cyを計算する。

- バージョンを更新（v1 → v2）
- 修正した家具のreasonに修正理由を追記

### Step 2b: イテレーション記録にFB・変更内容を確定

```bash
uv run python .claude/skills/floor_plan_to_video_sub_refine/scripts/save_iteration.py <出力ディレクトリ> <前バージョン> \
  --feedback "ユーザーのフィードバック内容" \
  --changes "今回の変更内容"
```

→ 報告: `「[5c-2b] {前バージョン}の記録にFB・変更内容を追記しました」`

### 壁面再探索（家具の配置先が見つからない場合）

ある家具の配置先が現在の壁面割り当てで見つからない場合:
1. Step 1bの壁面インベントリを**全壁面に対して**再実行する
2. 「撤去した家具の跡地」「別の部屋の壁面」も候補に含める
3. 過去の失敗は「場所」ではなく「サイズ vs 利用可能スペース」で記録する
   - ✗「南壁は使えない」→ ✓「南壁に1.4mの家具は収まらない（0.8mなら可）」
4. それでも見つからない場合のみ、家具の撤去を検討する

### Step 3: Phase 5aのStep 3に戻る

→ 報告: `「[5c-3] 修正完了。配置エンジンを再実行します」`

修正したplacement_plan.jsonで配置エンジンを再実行する。5aのStep 1（画像読み取り）はスキップし、Step 3（エンジン実行）から再開する。

---

## ループ管理

### バージョン管理

各iterationのplacement_plan.jsonのversionフィールドを更新する（v1, v2, v3...）。

### ユーザー確認のタイミング

以下のタイミングでユーザーに確認する:
1. **初回配置（v1）完成時**: 全体方針の確認
2. **評価結果が出たとき**: 問題点の共有とユーザー自身のSVG確認依頼
3. **3回以上ループしたとき**: 方針転換が必要か相談

### 終了条件

- ユーザーが「この配置で良い」と承認
- 配置エンジンがPASS

---

## 配置エンジンの仕様

`placement_engine.py`（`.claude/skills/floor_plan_to_video_sub_refine/scripts/placement_engine.py`）の動作:

1. `placement_plan.json`を読み込み
2. 障害物を登録: 壁 + 柱 + 配置不可領域
3. 各家具を指定座標に配置し、重なりチェック:
   - 本体 vs 障害物（壁・柱・配置不可）
   - 本体 vs 既配置家具
   - 50%ルール: 配置不可(50%)ラベルの領域は面積の50%まで許容
4. 問題家具は赤枠で表示
5. `layout_proposal.svg` + `layout_proposal.json` を出力

**家具の色:**
- ベッド: `#FF8A65`, クローゼット: `#9575CD`, デスク: `#FFB74D`
- チェア: `#FFD54F`, ダイニング: `#AED581`, カウンター: `#4FC3F7`

**動線検証（自動）:**

配置エンジンは家具配置後に動線検証を自動実行する。部屋全領域から壁・柱・家具を除いた空間（歩行可能領域）の連結性と幅を検証する。

SVGに歩行可能領域が色分けで表示される:
- 緑（薄）: 歩行可能（正常）
- オレンジ: 通れるが狭い（0.6m未満）
- 赤: ドアから到達不能（分断されている）

コンソール出力の読み方:
- `連結性: PASS` — 全ドア間が歩いて到達可能
- `連結性: FAIL（到達不能: 通路）` — 指定のドアが家具で孤立している → 配置修正が必要
- `最狭部: 0.45m → WARNING` — 通路幅が0.6m未満の箇所がある

Phase 5bの評価でSVGを見るとき、緑が途切れている箇所・赤い領域・オレンジの狭い箇所に注目する。

