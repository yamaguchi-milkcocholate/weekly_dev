# Claude Code によるパイプライン実行ガイド

本パイプラインは、Claude Code と対話しながら動画を生成するワークフローを想定している。
このドキュメントでは、利用可能なスキル、典型的なワークフロー、各ステップでの準備作業を説明する。

## 利用可能なスキル

Claude Code に `/スキル名` と入力するとスキルが起動する。

| スキル                                | 用途                 | いつ使うか                                                                                   |
| ------------------------------------- | -------------------- | -------------------------------------------------------------------------------------------- |
| `/project-setup`                      | 初回セットアップ     | 初めて環境を構築するとき。依存関係・APIキー・グローバル設定を対話的にガイドする              |
| `/pipeline-run [テーマ]`              | パイプライン新規実行 | 新しい動画プロジェクトを開始するとき。テーマの決定→モード選択→初期化→実行まで                |
| `/checkpoint-resume [プロジェクトID]` | チェックポイント再開 | `AWAITING_REVIEW` で停止中のパイプラインを再開するとき。レビュー・準備作業・承認をガイドする |

## 典型的なワークフロー

### 初回のみ

```
/project-setup
```

環境構築・APIキー設定を完了させる。一度実行すれば以降は不要。

### プロジェクト実行（毎回）

```
/pipeline-run OLの一日          ← プロジェクト作成 & 最初のステップ実行
/checkpoint-resume <project-id>  ← 以降、ステップごとに繰り返し
/checkpoint-resume <project-id>  ← ...
/checkpoint-resume <project-id>  ← パイプライン完了まで
```

## パイプラインモード

| モード         | コマンド  | ステップ構成                                                             | 用途                                             |
| -------------- | --------- | ------------------------------------------------------------------------ | ------------------------------------------------ |
| **Full**       | `run`     | Intelligence → Scenario → Storyboard → Asset → Keyframe → Visual → Audio | フル自動生成                                     |
| **Planning**   | `plan`    | Intelligence → Scenario → Storyboard                                     | プランニングのみ。手動編集後に Production へ移行 |
| **Production** | `produce` | Asset → Keyframe → Visual → Audio                                        | シナリオ・絵コンテが確定済みの場合               |

Planning → Production の流れ:

```
/pipeline-run OLの一日       ← Planning モードを選択
/checkpoint-resume <id>      ← Storyboard 完了まで進める
（scenario.json / storyboard.json を手動編集）
/pipeline-run               ← Production モードを選択し、同じプロジェクトIDを指定
```

## チェックポイント方式

パイプラインは各ステップを1つずつ実行し、`AWAITING_REVIEW` で停止する。`/checkpoint-resume` で確認・承認すると次のステップへ進む。

**Asset / Keyframe / Visual** ステップはアイテム単位（キャラクター、シーン、クリップ等）で実行される。1回の `/checkpoint-resume` で1アイテムが処理される。

```
例: Asset ステップでキャラクター2体 + 環境画像の場合

/checkpoint-resume → アイテム「Ai」を承認 → アイテム「Yuki」を実行
/checkpoint-resume → アイテム「Yuki」を承認 → 環境画像を実行
/checkpoint-resume → 環境画像を承認 → Asset 完了 → Keyframe ステップ開始
```

## ステップ別の準備作業

`/checkpoint-resume` が各ステップで必要な準備作業をガイドするが、事前に把握しておくと効率的。

### Storyboard → Asset の間（最も準備が多い）

Asset ステップの実行前に、以下の2ファイルを準備する必要がある。

#### 1. mapping.yaml（任意）

キャラクターの参照画像を手動指定する場合に作成する。作成しない場合、全キャラクターがテキストから自動生成される。

```
assets/reference/
├── person/           ← 人物の参照画像を配置
├── clothing/         ← 服装の参照画像を配置
└── mapping.yaml      ← 上記画像のマッピングを定義
```

Claude Code に「この人物画像を使いたい」と伝えれば、mapping.yaml を自動生成する。

#### 2. environment_seeds.yaml（必須）

各シーンの環境画像の生成方法を定義する。**このファイルがないと Asset ステップはエラーになる。**

```yaml
environments:
  - scene_number: 1
    source: reference # 参照写真から環境を再現
    reference_image: "photo.png" # assets/reference/environments/ に配置
    modification: "" # 修正がある場合は英語で記述
  - scene_number: 2
    source: generate # テキストから自動生成（参照写真不要）
    description: "シーンの説明"
```

**Claude Code への伝え方:**

- `source: reference` を使う場合: 参照画像を `assets/reference/environments/` に配置した上で、Claude Code にファイル名を伝える
- `modification` が必要な場合: **日本語で指示すれば Claude Code が英語プロンプトに変換する**（例: 「朝の光が差し込む感じにして」→ 英語の modification が生成される）

> /checkpoint-resumeスキルを使えば、Claude Code は modification の記入時に自動的にベストプラクティス（`docs/image_gen_best_practices/environment_generation.md`）を参照する。

#### 参照画像の配置先

```
assets/reference/
├── person/           ← 人物画像（mapping.yaml で参照）
├── clothing/         ← 服装画像（mapping.yaml で参照）
└── environments/     ← 環境参照写真（environment_seeds.yaml で参照）
```

画像は人物が写り込んでいてもOK（パイプラインが自動で人物を除去する）。

### Asset → Keyframe の間

`storyboard/keyframe_mapping.yaml` が自動生成される。必要に応じて編集可能:

- 各シーンのキャラクター割り当て
- 衣装バリアントの指定（複数衣装がある場合）
- 追加の参照画像やテキストの指定

### その他のステップ間

Intelligence, Scenario, Keyframe, Visual, Audio の各ステップ間では、特別な準備作業は不要。`/checkpoint-resume` で結果を確認し、承認するだけで次へ進める。

## エラー時の対応

```bash
# ステップ全体を再試行
uv run daily-routine retry <project-id>

# 特定のアイテムのみ再試行（Asset / Keyframe / Visual）
uv run daily-routine retry <project-id> --item <item-id>
```

`/checkpoint-resume` でエラー状態を検知した場合、Claude Code が原因の特定と対処方法を案内する。

## 状態の確認

```bash
uv run daily-routine status <project-id>
```

現在のステップ、状態（PENDING / RUNNING / AWAITING_REVIEW / APPROVED / ERROR）、アイテムの進捗を確認できる。

## よくある質問

### Q: 生成結果が気に入らない場合は？

`/checkpoint-resume` でレビュー中に、Claude Code に「このキャラクターをやり直したい」等と伝えると、`retry --item` で個別に再生成できる。

### Q: 途中でシナリオを変更したい場合は？

Planning モードで生成したシナリオ・絵コンテは手動編集可能。`scenario/scenario.json` と `storyboard/storyboard.json` を直接編集してから Production モードで実行する。

### Q: 環境画像のアングルや雰囲気を変えたい場合は？

environment_seeds.yaml の `modification` フィールドで指示する。日本語で Claude Code に伝えれば英語プロンプトに変換される。具体的な書き方のコツは `docs/image_gen_best_practices/environment_generation.md` の「modification プロンプトの書き方ガイド」を参照。

### Q: 参照画像なしでも動画を作れる？

可能。mapping.yaml を作成せず（全キャラクター自動生成）、environment_seeds.yaml で全シーンを `source: generate` にすれば、テキストのみで動画生成できる。
