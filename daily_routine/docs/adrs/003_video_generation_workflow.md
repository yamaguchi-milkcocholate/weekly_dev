# ADR-003: 動画生成ワークフローの設計

## ステータス

採用

## コンテキスト

T1-4（Visual Core）の統合検証で、Runway Gen-4 Turbo の Image-to-Video（I2V）に**キャラクター正面画像（白背景立ちポーズ）をそのまま `promptImage` に渡す**方式では、意図したシーン内容の動画が生成されない問題が判明した。

### 判明した問題

| 問題 | 原因 |
| --- | --- |
| シーンの場所・状況が反映されない | I2V は入力画像を起点にアニメーションするため、白背景の立ちポーズからカフェやオフィスのシーンは生成できない |
| モンタージュ等のシーン切替が不可能 | I2V は1枚の画像からの連続的な動き生成であり、複数場所の切り替えは原理的に不向き |
| カメラワーク（POV、クローズアップ等）が反映されにくい | 入力が全身正面ポーズのため、I2V モデルが解釈できるカメラワークが制約される |

### 調査の実施

Runway の公式ドキュメント、プロンプティングガイド、映画制作・CM制作での事例、最新モデルラインナップを調査した。

**情報源:**

- [Available AI Models | Runway API](https://docs.dev.runwayml.com/guides/models/)
- [API Pricing & Costs | Runway API](https://docs.dev.runwayml.com/guides/pricing/)
- [Gen-4 Video Prompting Guide](https://help.runwayml.com/hc/en-us/articles/39789879462419)
- [Creating with Gen-4 Image References](https://help.runwayml.com/hc/en-us/articles/40042718905875)
- [Creating with Gen-4.5](https://help.runwayml.com/hc/en-us/articles/46974685288467)
- [Runway Research | Introducing Gen-4.5](https://runwayml.com/research/introducing-runway-gen-4.5)
- [Lionsgate + Runway パートナーシップ事例](https://runwayml.com/news/runway-partners-with-lionsgate)
- [Tool Agency のCM制作事例](https://runwayml.com/customers/how-tool-is-reimagining-the-commercial-production-process-with-runway)

## Runway 最新モデルラインナップ（2026年2月時点）

### 動画生成モデル

| モデル | モデルID | API コスト | 10秒コスト | 特徴 |
| --- | --- | --- | --- | --- |
| **Gen-4.5** | `gen4.5` | 12 credits/sec | **$1.20** | 最上位。物理シミュレーション・モーション品質最高。T2V/I2V 両対応。Artificial Analysis 1位 |
| **Gen-4 Turbo** | `gen4_turbo` | 5 credits/sec | **$0.50** | 高速・低コスト。I2V のみ。スタイライズドな表現に強い |
| Gen-4 Aleph | `gen4_aleph` | 15 credits/sec | $1.50 | V2V（動画編集）。オブジェクト追加/削除/変換 |
| Veo 3.1 | `veo3.1` | 20-40 credits/sec | $2.00-$4.00 | Google製。ネイティブ音声生成対応 |
| Veo 3.1 Fast | `veo3.1_fast` | 10-15 credits/sec | $1.00-$1.50 | Veo 3.1 の高速版 |

### 画像生成モデル

| モデル | モデルID | API コスト | 特徴 |
| --- | --- | --- | --- |
| **Gen-4 Image** | `gen4_image` | 5 credits (720p) / 8 credits (1080p) | `referenceImages` + `@tag` 構文対応。最大3枚参照 |
| **Gen-4 Image Turbo** | `gen4_image_turbo` | **2 credits** (全解像度) | 高速・低コスト版。referenceImages 対応 |

### Gen-4.5 vs Gen-4 Turbo

| 観点 | Gen-4.5 | Gen-4 Turbo |
| --- | --- | --- |
| 10秒動画コスト | $1.20 | $0.50 |
| 入力モード | T2V + I2V | I2V のみ |
| 物理シミュレーション | 大幅改善（重力、慣性、液体、布） | 標準 |
| プロンプト追従性 | 高い | 標準 |
| テクスチャ安定性 | 高い（髪・肌の連続性維持） | やや不安定な場合あり |
| ベンチマーク | Artificial Analysis 1位 (1,247 Elo) | - |
| 推奨用途 | 最高品質の本番制作 | 高速イテレーション、コスト重視 |

### Gen-4.5 の既知の限界（2026年2月時点）

- 複雑な人物の歩行でストライドスキップが発生
- 水の物理がまだ不自然
- リップシンク非対応
- 因果関係の逆転（原因より先に結果が描画される）

## 候補

### A. 現行方式（1段階: front_view → I2V）

```
front_view.png (白背景) + video_prompt → Gen-4 Turbo I2V → 動画
```

- **利点:** シンプル、API呼び出し1回/シーン
- **欠点:** シーン文脈が反映されない（検証で実証済み）。プロの手法と大きく乖離

### B. 2段階パイプライン: Gen-4 Image → Gen-4 Video（推奨）

```
front_view.png (@char参照) + keyframe_prompt → Gen-4 Image API → キーフレーム画像
キーフレーム画像 + motion_prompt → Gen-4 Turbo / Gen-4.5 I2V → 動画
```

- **利点:** プロの標準ワークフロー。キャラ一貫性とシーン文脈を両立。Image段階で低コスト（$0.02/枚）に高速イテレーション可能。Runway エコシステム内でスタイル一貫
- **欠点:** API呼び出し2回/シーン

### C. Gemini でキーフレーム画像生成 → Gen-4 Video

```
front_view.png (参照画像) + keyframe_prompt → Gemini Image API → キーフレーム画像
キーフレーム画像 + motion_prompt → Gen-4 Turbo / Gen-4.5 I2V → 動画
```

- **利点:** 既存の Gemini 画像生成クライアント（Asset Generator で実装済み）を再利用可能
- **欠点:** Gemini と Runway 間でスタイルの不一致が生じる可能性。`@tag` のような明示的参照機構がなく、キャラクター再現精度が劣る可能性

### D. 背景画像をそのまま promptImage に使用

```
backgrounds/scene_XX.png + video_prompt → Gen-4 Turbo I2V → 動画
```

- **利点:** 追加生成不要
- **欠点:** キャラクターの同一性が完全に失われる

## キーフレーム画像生成: Runway Gen-4 Image vs Gemini

| 観点 | Runway Gen-4 Image | Gemini (gemini-3-pro-image-preview) |
| --- | --- | --- |
| キャラクター参照方式 | `referenceImages` + `@tag` で明示的参照 | 暗黙的参照（最大14枚入力可能） |
| I2V 入力としての適性 | 同一エコシステム。スタイルが I2V に最適化 | 独自スタイル。Runway I2V との不一致リスク |
| コスト | gen4_image_turbo: $0.02/枚 | Google AI API: 低コスト |
| 画質 | シーン構成力が高い | タッチが最もリアル・自然 |
| スタイル一貫性 | Runway Image → Runway Video で高い一貫性 | 画風にフォトリアル〜イラスト調の混在あり |
| 実装コスト | 新規クライアント実装が必要 | Asset Generator で実装済み |

**結論:** キーフレーム画像の生成には Runway Gen-4 Image を推奨する。理由は `@tag` 構文による明示的なキャラクター参照と、I2V との同一エコシステム内でのスタイル一貫性。ただし、キャラクターの基本画像（正面・白背景）の生成は既存の Gemini のままとする。

## 調査で判明したプロの技法

### 1. プロンプティングの3要素構造

I2V の `promptText` は**モーション記述に特化**する。画像に既にある情報（外見・服装等）は記述しない:

| 要素 | 役割 | 例 |
| --- | --- | --- |
| Subject Motion | 被写体の動き | "She slowly raises her coffee cup and takes a sip" |
| Scene Motion | 環境の動き | "Steam rises from the cup, leaves rustle outside" |
| Camera Motion | カメラワーク | "Camera slowly dollies in from medium to close-up" |

**やるべきこと:**
- 自然言語の完全な文章で記述する
- 能動態の精密な動詞を使用する（"sprints", "rotates", "drifts"）
- 静的なショットでは "The camera remains still" と明示する

**やってはいけないこと:**
- 画像に既にある外見情報を再記述しない（モーション減少の原因）
- 1ショットで複数シーンを要求しない
- 否定表現（"no camera movement" 等）を使わない
- カンマ区切りのキーワードリストにしない

### 2. Gen-4 Image API の referenceImages + @tag 構文

最大3枚の参照画像をタグ付きで指定し、プロンプト内で `@tag` として参照:

```json
{
  "model": "gen4_image",
  "promptText": "@char sits at a modern office desk, typing on laptop, soft daylight from window",
  "referenceImages": [
    { "uri": "https://.../front.png", "tag": "char" }
  ]
}
```

### 3. promptImage の配列形式と position

```json
{
  "promptImage": [
    { "uri": "https://.../keyframe.png", "position": "first" }
  ]
}
```

`position: "first"` で入力画像を動画の最初のフレームとして使用する。

### 4. seed パラメータ

`seed`（0-4294967295）で再現性のある結果を取得。複数候補生成 + 最良選択がプロの一般的手法。

### 5. 3段階イテレーション戦略

| フェーズ | モデル | duration | 目的 | コスト |
| --- | --- | --- | --- | --- |
| キーフレーム制作 | gen4_image_turbo | - | シーン構成の確認 | $0.02/枚 |
| モーション検証 | gen4_turbo | 5秒 | モーション・構図の確認 | $0.25/本 |
| 本番生成 | gen4.5 | 5-10秒 | 最高品質での最終出力 | $0.60-$1.20/本 |

### 6. 推奨パイプライン構成

```
Gemini → キャラクター基本画像 (front_view, side_view 等)
              ↓ (参照画像として使用)
Gen-4 Image Turbo (@char参照) → キーフレーム画像 (シーン内に配置)
              ↓ (promptImage として使用)
Gen-4 Turbo / Gen-4.5 I2V → 動画
```

### コスト見積もり（8シーン構成）

| パイプライン | キーフレーム | 動画生成 | 合計/動画 |
| --- | --- | --- | --- |
| Gen-4 Image Turbo + Gen-4 Turbo (10秒) | $0.16 (8枚) | $4.00 (8本) | **$4.16** |
| Gen-4 Image Turbo + Gen-4.5 (10秒) | $0.16 (8枚) | $9.60 (8本) | **$9.76** |
| Gen-4 Image Turbo + Gen-4 Turbo (5秒) | $0.16 (8枚) | $2.00 (8本) | **$2.16** |

## ADR-001 への影響

Gen-4.5 の登場により、ADR-001 の「高品質代替: Veo 3」を見直す余地がある:

| 比較 | Gen-4.5 | Veo 3 (Runway API経由) |
| --- | --- | --- |
| 10秒コスト | $1.20 | $4.00 |
| 品質 | Artificial Analysis 1位 | 高品質 |
| 入力方式 | I2V + T2V | T2V |
| エコシステム | Runway 統一 | Google (Runway API経由) |

Gen-4.5 のほうが安価かつ I2V 対応のため、高品質代替として Veo 3 より Gen-4.5 が適する可能性が高い。

## 決定

**候補B: 2段階パイプライン（Gen-4 Image → Gen-4 Video）を採用する。** Runway エコシステム内で統一する方式とする。

### 採用する構成

```
Gemini → キャラクター基本画像 (front_view, side_view 等)
              ↓ (referenceImages として使用)
Gen-4 Image Turbo (@char参照) → キーフレーム画像 (シーン内に配置)
              ↓ (promptImage として使用)
Gen-4 Turbo I2V → 動画クリップ
```

### 採用理由

1. **Runway エコシステムの一貫性**: Gen-4 Image → Gen-4 Video は同一エコシステム内で完結し、スタイルの一貫性が担保される
2. **`@tag` 構文による明示的キャラクター参照**: `referenceImages` + `@tag` で意図通りのキャラクター再現が可能
3. **プロの標準ワークフローとの一致**: 映画制作・CM制作で実証された手法であり、品質面で信頼性が高い
4. **コスト効率の良いイテレーション**: Gen-4 Image Turbo（$0.02/枚）でキーフレームを低コストに試行し、動画生成前に構図・シーンを確定できる
5. **段階的な品質向上パス**: Gen-4 Turbo（$0.50/10秒）で通常運用し、高品質が必要な場合は Gen-4.5（$1.20/10秒）に切り替え可能

### 不採用の理由

- **候補A（現行方式）**: 統合検証で白背景の立ちポーズからシーン内容が反映されないことが実証済み
- **候補C（Gemini でキーフレーム生成）**: Gemini と Runway 間のスタイル不一致リスク、`@tag` のような明示的参照機構がない
- **候補D（背景画像を promptImage に使用）**: キャラクターの同一性が完全に失われる

### モデル選定

| 用途 | モデル | 理由 |
| --- | --- | --- |
| キャラクター基本画像生成 | Gemini (既存) | Asset Generator で実装済み。基本画像は白背景で十分 |
| キーフレーム画像生成 | Gen-4 Image Turbo | 低コスト（$0.02/枚）、`@tag` 対応、Runway Video と同一エコシステム |
| 動画生成（通常） | Gen-4 Turbo | コスト効率（$0.50/10秒）、I2V に特化 |
| 動画生成（高品質） | Gen-4.5 | 最高品質（$1.20/10秒）、物理シミュレーション改善。必要に応じて切り替え |

### プロンプト設計方針

- **キーフレーム画像プロンプト（`keyframe_prompt`）**: シーンの場所・状況・キャラクターの配置を記述する（例: `@char sits at a modern office desk, typing on laptop, soft daylight from window`）
- **動画プロンプト（`motion_prompt`）**: モーション記述に特化する。画像に既にある外見情報は記述しない。Subject Motion + Scene Motion + Camera Motion の3要素で構成する

### コスト見積もり

8シーン構成の場合、Gen-4 Image Turbo + Gen-4 Turbo（10秒）で **$4.16/動画** を想定する。

## 結果

### 実装への影響

1. **Visual Core の拡張**: 2段階パイプライン（キーフレーム画像生成 → 動画生成）をサポートするようエンジンを拡張する
2. **Runway Image Client の新規実装**: Gen-4 Image API（`referenceImages` + `@tag` 構文）のクライアントを実装する
3. **Scenario スキーマの拡張**: シーンごとに `keyframe_prompt`（画像生成用）と `motion_prompt`（動画生成用）を分離する
4. **設定の拡張**: Gen-4 Image モデル設定、高品質モード（Gen-4.5）切り替え設定を追加する

### ADR-001 への影響

Gen-4.5 は Veo 3 より安価（$1.20 vs $4.00/10秒）かつ I2V 対応であるため、高品質代替として Veo 3 に代わり Gen-4.5 を位置づける。ADR-001 の該当箇所を更新する。
