# floor_plan_to_video マスタースキル作成計画

## Context

Floor Plan to Videoパイプラインの15サブスキルが揃い、命名も`floor_plan_to_video_sub_*`に統一済み。入出力の結合性も検証・修正済み。これらを一貫して使うマスタースキル`floor_plan_to_video`を作成する。

## スキルの役割

間取りPNG画像からフォトリアルなインテリアウォークスルー動画までの7ステップパイプラインを、workdirを起点に統括するオーケストレーションスキル。

- **ステップ制御**: 現在の進捗を自動判定し、次ステップを実行
- **パス受け渡し**: 各サブスキル間のファイルパスを仲介（コピー/リンク含む）
- **対話ポイント管理**: 自動実行と対話実行の切り替え

## 成果物

```
.claude/skills/floor_plan_to_video/
└── SKILL.md
```

## SKILL.md 設計

### frontmatter

```yaml
name: floor_plan_to_video
description: 間取りPNG画像からフォトリアルなインテリアウォークスルー動画を生成する7ステップパイプラインのマスタースキル。workdirを指定して実行する。間取り動画化、Floor Plan to Video、インテリアウォークスルー、間取りから動画、間取りを3D化して動画にするタスクで必ずこのスキルを参照すること。
argument-hint: <workdir>
```

### workdir構造

```
workdir/
├── input/
│   ├── floor_plan.png              ← ユーザー配置
│   └── assets/                     ← ユーザー配置（家具画像）
│       ├── chair/front.png
│       └── desk/front.png
├── output/                         ← 全ステップの成果物
│   ├── {stem}_floor_plan.svg
│   ├── {stem}_elements.svg
│   ├── walls.json
│   ├── floor_plan_meta.json
│   ├── scene.blend                 ← Step 2: 壁のみ
│   ├── floor_plan_rooms.drawio
│   ├── room_info.json
│   ├── floor_plan_complete.svg
│   ├── assets.json
│   ├── life_scenarios.json
│   ├── scoring_criteria.json
│   ├── placement_plan.json
│   ├── layout_proposal.json
│   ├── layout_proposal.svg
│   ├── assets/objects/*.glb        ← Step 3: 家具GLB
│   └── placement/
│       ├── scene.blend             ← Step 5: 家具配置済み
│       └── placement_report.json
├── work/                           ← 中間ファイル
│   ├── trace/
│   ├── elements/
│   ├── camera/                     ← Step 6 workdir
│   │   ├── input/scene.blend       ← placement/scene.blend のコピー
│   │   └── output/renders/*.mp4
│   └── v2v/                        ← Step 7 workdir
│       ├── input/cut_*.mp4         ← camera出力のコピー
│       └── output/*_photorealistic.mp4
└── final/                          ← 最終成果物
    └── *.mp4
```

### 7ステップ定義

| Step | サブスキル | 自動/対話 | 入力（output/内） | 出力（output/内） |
|------|-----------|----------|------------------|------------------|
| 1 | `sub_extract` | 自動 | `../input/floor_plan.png` | `{stem}_elements.svg`, `walls.json`, `floor_plan_meta.json` |
| 2 | `sub_scene` | 自動 | `{stem}_elements.svg` | `scene.blend` |
| 3 | `sub_glb` | 自動 | `../input/assets/` | `assets/objects/*.glb` |
| 4 | `sub_annotate` → `sub_assets` → `sub_research` → `sub_refine` | **対話** | 複数（前ステップ出力） | `layout_proposal.json` 等 |
| 5 | `sub_placement` | 自動 | `layout_proposal.json`, `scene.blend`, GLB | `placement/scene.blend` |
| 6 | `sub_camera` | **対話**（カット設計） | `placement/scene.blend` | `work/camera/output/renders/*.mp4` |
| 7 | `sub_photoreal` | **対話**（プロンプト確認） | `camera出力/*.mp4` | `work/v2v/output/*_photorealistic.mp4` |

### パス受け渡しロジック

Step 5→6: `cp output/placement/scene.blend work/camera/input/scene.blend`
Step 6→7: `cp work/camera/output/renders/cut_*.mp4 work/v2v/input/`
Step 7→final: `cp work/v2v/output/*_photorealistic.mp4 final/`

### 進捗判定（ファイル存在チェック）

```
Step 1完了: output/{stem}_elements.svg + output/walls.json
Step 2完了: output/scene.blend
Step 3完了: output/assets/objects/*.glb（1つ以上）
Step 4完了: output/layout_proposal.json
Step 5完了: output/placement/scene.blend
Step 6完了: work/camera/output/renders/*.mp4（1つ以上）
Step 7完了: final/*.mp4（1つ以上）
```

### 並列実行

- Step 2（scene生成）と Step 3（GLB生成）は独立 → 並列実行可能
- Step 4内の sub_research は任意 → スキップ可能

### 実行フロー（SKILL.md本文の骨格）

```
## 実行手順

### Step 0: 状態確認
workdir/output/ 内のファイル存在で現在のステップを判定。
途中再開の場合、完了済みステップをスキップ。

### Step 1: 間取り抽出
/floor_plan_to_video_sub_extract workdir

### Step 2+3: 3Dシーン生成 + 家具GLB生成（並列）
Step 2: /floor_plan_to_video_sub_scene output/{stem}_elements.svg output/
Step 3: /floor_plan_to_video_sub_glb input/assets/ --output-dir output/assets/objects/

### Step 4: レイアウト設計（対話ループ）
4a: /floor_plan_to_video_sub_annotate output/
    → ユーザーがdrawioで部屋定義
    /floor_plan_to_video_sub_annotate output/ integrate
4b: /floor_plan_to_video_sub_assets output/
4c: /floor_plan_to_video_sub_research output/ （任意）
4d: /floor_plan_to_video_sub_refine output/

### Step 5: 家具配置
/floor_plan_to_video_sub_placement output/ output/placement/

### Step 6: カメラカット動画
cp output/placement/scene.blend work/camera/input/scene.blend
/floor_plan_to_video_sub_camera work/camera/

### Step 7: フォトリアル動画化
cp work/camera/output/renders/cut_*.mp4 work/v2v/input/
/floor_plan_to_video_sub_photoreal work/v2v/
cp work/v2v/output/*_photorealistic.mp4 final/
```

## sub_status との関係

`sub_status`はレイアウトパイプライン（旧PoC3系）の進捗確認スキル。マスタースキルが全7ステップをカバーするため、`sub_status`の役割はマスタースキルに吸収される。`sub_status`は後方互換のため残すが、マスタースキルのStep 0が同等の機能を提供する。

## テストケース（eval不要 — 対話的スキルのため）

このスキルは対話的なオーケストレーターであり、出力の正しさは各サブスキルが保証する。テストケースによる自動評価は不適切。実際のworkdirで手動実行して確認する。

## 検証方法

1. スキルディレクトリ作成確認: `ls .claude/skills/floor_plan_to_video/SKILL.md`
2. スキル一覧に表示されることを確認
3. `/floor_plan_to_video <workdir>` でStep 0の状態判定が動作することを確認
