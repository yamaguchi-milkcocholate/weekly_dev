# PoC 7: ウォークスルー動画生成 — 技術調査

調査日: 2026-03-30

## 調査目的

スタイル適用済みインテリア画像/動画から、リアルなウォークスルー動画を生成するための手法を調査する。以下の2方式を検討。

- **方式A（画像間補間）**: スタイル適用済み静止画のStart/Endフレームを指定し、間を動画生成で補間
- **方式B（V2V）**: Blenderのウォークスルー動画を入力し、AI動画スタイル転写

---

## 1. Luma AI（Dream Machine / Ray）

### 1.1 Start-End Frame to Video（キーフレーム補間）

**機能名**: Keyframe Control

- Ray2（2025年3月）で Keyframes / Extend / Loop が追加
- Ray3.14（最新）で性能向上

**API**: `POST https://api.lumalabs.ai/dream-machine/v1/generations`

```json
{
  "prompt": "A smooth camera transition through the room",
  "model": "ray-2",
  "keyframes": {
    "frame0": {
      "type": "image",
      "url": "https://cdn.example.com/start.jpg"
    },
    "frame1": {
      "type": "image",
      "url": "https://cdn.example.com/end.jpg"
    }
  },
  "resolution": "720p",
  "aspect_ratio": "16:9"
}
```

| 項目 | 仕様 |
|------|------|
| 入力 | CDN上の公開URL（2枚の画像） |
| 出力解像度 | 540p / 720p / 1080p / 4K |
| 出力尺 | 5秒単位 |
| 出力fps | 24fps（推定） |
| 出力形式 | MP4 |
| レンダリング時間 | 4Kで2〜5分程度 |

**料金（クレジット、Ray3.14）:**

| 解像度 | 5秒 | 10秒 |
|--------|------|------|
| 540p | 50 | 100 |
| 720p | 100 | 200 |
| 1080p | 400 | 800 |

**構造維持**: 時間的一貫性を維持。深度・遮蔽を尊重し、オブジェクトや空間関係が補間中も保たれる。

**注意点**:
- 画像URLはCDN上の公開URLである必要がある（ローカルファイル不可）
- 2画像間の差異が大きいほど中間の予測可能性は低下

### 1.2 Video-to-Video（Modify Video）

**機能名**: Modify Video

- Ray2 / Ray2 Flash / Ray3 Modify / Ray3.14 Modify で利用可能

**API**: Modify Video 専用エンドポイント

```json
{
  "prompt": "Transform to photorealistic interior with warm wood textures",
  "media": {
    "url": "https://example.com/input_video.mp4"
  },
  "first_frame": {
    "url": "https://example.com/style_reference.png"
  },
  "mode": "flex_1",
  "model": "ray-2"
}
```

**Mode（構造維持レベル）** — 9段階:

| モード | 説明 | 用途 |
|--------|------|------|
| adhere_1〜3 | 元動画に非常に忠実。微細な補正、軽いリテクスチャ | 背景差し替え、リテクスチャ |
| flex_1〜3 | 中程度の変換。形状をある程度保持しつつスタイル変更 | スタイル大幅変更 |
| reimagine_1〜3 | 元動画への追従が最も緩い | 完全なスタイル変換 |

| 項目 | 仕様 |
|------|------|
| 入力動画形式 | MP4, MOV, MKV, WebM（H.264/H.265推奨、CRF 17以下推奨） |
| 最大入力尺 | 10秒（Ray2）/ 15秒（Ray2 Flash） |
| 最大ファイルサイズ | 100MB |
| 出力解像度 | Ray3.14 Modify はネイティブ1080p対応 |
| 出力形式 | MP4 |
| 処理時間 | 通常2〜4分 |

**料金（API、ピクセル単価）:**

| モデル | 単価 |
|--------|------|
| ray-2 | $0.01582 / 百万ピクセル |
| ray-flash-2 | $0.00544 / 百万ピクセル |

参考: 720p, 5秒, 16:9 → ray-2: $1.75 / ray-flash-2: $0.60

**料金（クレジット、Ray3.14 Modify）:**

| 解像度 | 5秒 | 10秒 |
|--------|------|------|
| 540p | 120 | 240 |
| 720p | 240 | 480 |
| 1080p | 960 | 1,920 |

※ V2Vは通常のText-to-Videoの約2〜4倍のクレジットコスト

**構造維持**: カメラ移動・ダイナミクスを忠実に再現。表情・振り付け等も維持。`mode`パラメータで調整可能。

**注意点**:
- 動画全体が均一に変換される（領域ごとの選択的変換は不可）
- 高速・混沌とした動きではアーティファクト発生の可能性
- プリセット外のアスペクト比はクロップされ品質劣化の可能性

---

## 2. Runway

### 2.1 Start-End Frame to Video（キーフレーム補間）

**対応状況**:
- **Gen-3 Alpha / Turbo**: First Frame + Last Frame + Middle Keyframe 対応（最も成熟）
- **Gen-4 Turbo**: First Frame のみ（Last Frame は Web UI 非対応、API では対応の可能性あり）
- **Gen-4.5**: First Frame + Last Frame + Middle Keyframe 対応

**API**: `POST https://api.dev.runwayml.com/v1/image_to_video`

```json
{
  "model": "gen4.5",
  "promptImage": [
    {"uri": "https://example.com/start.jpg", "position": "first"},
    {"uri": "https://example.com/end.jpg", "position": "last"}
  ],
  "promptText": "smooth camera movement through the room",
  "ratio": "1280:720",
  "duration": 10
}
```

| 項目 | 仕様 |
|------|------|
| 入力画像形式 | JPEG, PNG, WebP（GIF不可） |
| ファイルサイズ | URL: 16MB以下、Data URI: 5MB以下 |
| 推奨解像度 | 640x640px 以上、4K以下 |
| 出力解像度 | 1280x720, 720x1280, 1104x832, 832x1104, 960x960, 1584x672 |
| 出力fps | 24fps |
| 出力尺 | 5秒 or 10秒（デフォルト10秒） |
| 出力形式 | MP4 |

**料金:**

| モデル | コスト/秒 | 10秒 |
|--------|-----------|------|
| Gen-4.5 | 12クレジット（$0.12） | $1.20 |
| Gen-4 Turbo | 5クレジット（$0.05） | $0.50 |
| Gen-3 Turbo | 5クレジット（$0.05） | $0.50 |

**構造維持**: First/Last画像に忠実だが、中間フレームはAIが自由に生成。2画像間の差異が大きいほど中間の予測可能性は低下。一貫性のある画像ペア（同一シーン）を使うと結果が良い。

### 2.2 Video-to-Video

**2つの方式:**

#### Gen-3 Alpha / Turbo V2V
- `Structure Transformation` スライダーで構造維持レベルを制御
- 低設定ではレイアウト・動き・形状がかなり保持される
- 最大20秒の入力対応

#### Gen-4 Aleph（2025年7月リリース、次世代V2V）
- シーン構造の理解が大幅に向上。照明・影・パース・奥行きを理解した上で編集
- オブジェクトの位置・動き・環境の詳細が全フレームにわたり一貫して維持
- 追加オブジェクトの影や反射も自然に処理
- 参照画像（references）を指定可能

**API**: `POST https://api.dev.runwayml.com/v1/video_to_video`

```json
{
  "model": "gen4_aleph",
  "videoUri": "https://example.com/input.mp4",
  "promptText": "convert to photorealistic interior with warm lighting",
  "references": [{"uri": "https://example.com/style_ref.jpg", "type": "image"}]
}
```

| 項目 | Gen-3 V2V | Gen-4 Aleph |
|------|-----------|-------------|
| 入力動画形式 | MP4, MOV, MKV, WebM | 同左 |
| 入力コーデック | H.264, H.265, VP8, VP9, AV1, ProRes | 同左 |
| ファイルサイズ | URL: 32MB, Data URI: 16MB | 同左 |
| 最大入力尺 | 20秒 | 入力動画に依存 |
| 出力解像度 | 1280x768 | 1280x720等 複数対応 |
| 出力fps | 24fps | 24fps |
| **出力尺** | 入力と同じ（最大20秒） | **5秒固定** |
| 出力形式 | MP4 | MP4 |
| 参照画像 | なし | あり（オプション） |

**料金:**

| モデル | コスト/秒 |
|--------|-----------|
| Gen-4 Aleph | 15クレジット（$0.15） |
| Gen-3 Turbo | 5クレジット（$0.05） |

**構造維持**:
- Gen-3: Structure Transformationスライダーで制御。低設定で構造維持、高設定で抽象的変換
- Gen-4 Aleph: シーン構造理解が大幅向上。照明・影・パースを理解した上で編集。時間的一貫性が高い

**注意点**:
- **Gen-4 Aleph の出力は5秒固定** — 長い動画は複数回実行+連結が必要
- Gen-3 V2Vは最大20秒対応だが構造維持精度がAlephより低い
- Gen-4 Aleph の処理時間は約3.5分（5秒動画）

---

## 3. 比較まとめ

### 方式A: Start-End Frame 補間

| 項目 | Luma (Ray3.14) | Runway (Gen-4.5) |
|------|----------------|-------------------|
| First+Last対応 | ○ | ○ |
| Middle Keyframe | ○（generation補間） | ○ |
| 出力尺 | 5秒単位 | 5秒 or 10秒 |
| 出力解像度 | 540p〜4K | 1280x720等 |
| コスト（720p, 5秒） | 100クレジット | $0.60（Gen-4.5） |
| 構造維持 | 深度・遮蔽を尊重 | First/Lastに忠実、中間はAI |

### 方式B: Video-to-Video

| 項目 | Luma Modify (Ray3.14) | Runway Gen-4 Aleph | Runway Gen-3 V2V |
|------|----------------------|--------------------|--------------------|
| 構造維持制御 | 9段階mode | プロンプト+参照画像 | スライダー |
| 最大入力尺 | 10秒 | 制限なし（出力は5秒固定） | 20秒 |
| 出力尺 | 入力と同じ | **5秒固定** | 入力と同じ |
| 出力解像度 | 1080p | 1280x720等 | 1280x768 |
| コスト（720p, 5秒） | $1.75（ray-2）/ $0.60（flash） | $0.75 | $0.25 |
| 参照画像 | ○（first_frame） | ○（references） | × |
| 構造維持品質 | adhere設定で高い | シーン構造理解で高い | 中程度 |

---

## 4. PoC 7への示唆

### 方式B（V2V）の優位性

- Luma Modify の `adhere` モードは「元動画に非常に忠実なリテクスチャ」が可能 → 3DCGの構造維持+スタイル転写に最適
- Runway Gen-4 Aleph はシーン構造理解が高いが出力5秒固定 → セグメント分割方針と合致
- いずれも5秒セグメント運用なら「ちらつき問題」はモデル内で解決される見込み

### 検証優先順位

1. **Luma Modify（adhere_1〜3）**: 構造維持に特化したモード設定があり、3DCGウォークスルーのリテクスチャに最も適している可能性
2. **Runway Gen-4 Aleph**: 参照画像でスタイル指定+高い構造理解。ただし5秒固定
3. **Runway Gen-3 V2V**: 最大20秒対応で安価だが構造維持精度は低い

### コスト見積もり（ウォークスルー30秒、720p、6セグメント×5秒）

| サービス | 1セグメント | 全体（6セグメント） |
|----------|------------|-------------------|
| Luma ray-flash-2 | $0.60 | $3.60 |
| Runway Gen-4 Aleph | $0.75 | $4.50 |
| Luma ray-2 | $1.75 | $10.50 |

---

## 5. API利用可能性の確認（2026-03-30）

### Luma AI

| 項目 | 状況 |
|------|------|
| API公開状況 | **一般公開済み**（ウェイトリストなし） |
| APIキー取得 | https://lumalabs.ai/dream-machine/api/keys でアカウント作成後すぐ発行可能 |
| V2V (Modify Video) API | **利用可能** — `POST https://api.lumalabs.ai/dream-machine/v1/generations/video/modify` |
| キーフレーム補間 API | **利用可能** — `POST https://api.lumalabs.ai/dream-machine/v1/generations` の keyframes パラメータ |
| 料金体系 | 従量課金（ピクセル単価）。サブスクのクレジットとは別体系 |
| SDK | Python / JavaScript 公式SDK あり |
| ドキュメント | https://docs.lumalabs.ai/docs/api |

### Runway

| 項目 | 状況 |
|------|------|
| API公開状況 | **一般公開済み** |
| APIキー取得 | https://dev.runwayml.com/ でアカウント作成後、ダッシュボードからAPIキー生成 |
| V2V API | **利用可能** — `POST https://api.dev.runwayml.com/v1/video_to_video`（gen4_aleph対応確認済み） |
| キーフレーム補間 API | **利用可能** — `POST https://api.dev.runwayml.com/v1/image_to_video`（gen4.5でfirst+last対応） |
| 料金体系 | クレジット購入（$0.01/credit）。サブスクプランのクレジットもAPI利用可 |
| 認証 | Bearer Token（`Authorization: Bearer $RUNWAYML_API_SECRET`） |
| SDK | Python / Node.js 公式SDK あり |
| ドキュメント | https://docs.dev.runwayml.com/ |

### World Labs（Marble）

| 項目 | 状況 |
|------|------|
| API公開状況 | **一般公開済み**（2026年1月21日公開） |
| APIキー取得 | https://platform.worldlabs.ai/ でアカウント作成後、APIキー生成 |
| ワールド生成 API | **利用可能** — `POST /marble/v1/worlds:generate` |
| 認証 | APIキー方式（`WLT-Api-Key: YOUR_API_KEY`） |
| 料金体系 | クレジット購入（$1.00 = 1,250クレジット、最低$5.00） |
| サンプルコード | https://github.com/worldlabsai/worldlabs-api-examples |
| ドキュメント | https://docs.worldlabs.ai/api |

### 結論

**3サービスとも、API一般利用可能。** PoC 7の検証に進める状態。

---

## 6. 方式C: World Labs 3D空間化（2026-03-30 追加）

### 背景

OpenArt Worldsの調査から、World Labs（Marble）のGaussian Splatting技術を発見。画像から3D空間を生成し、自由なカメラ移動が可能。APIも公開済み。

### 方式の概要

```
Blender3D → レンダリング → Geminiスタイル適用（複数枚）
→ World Labs APIに複数枚+方位指定で入力
→ リアルな3D空間が生成される
→ 3D空間内でカメラを自由に動かしてウォークスルー
```

### V2V方式との根本的な違い

V2V（方式A/B）は「2D動画のフレーム間一貫性」をAIに任せている。
方式Cは「3D空間化」によって一貫性を**原理的に解消**する。3D空間になれば、どのアングルから見ても一貫しているのは当然。

### World Labs Marble 仕様

| 項目 | 仕様 |
|------|------|
| 入力 | テキスト / 画像（複数枚+方位指定） / 動画 / 360°パノラマ |
| 出力形式 | Gaussian Splat (PLY/SPZ) + **GLBメッシュ** |
| モデル | Marble 0.1-plus（高品質, 約5分）/ Marble 0.1-mini（高速, 30-45秒） |
| コスト | mini: **$0.12〜$0.20/生成** / plus: $1.20〜$1.28/生成 |
| Blender連携 | 公式ドキュメントあり（KIRI Engine等のプラグイン、GLBインポートも可） |
| 移動範囲 | 部屋サイズが基本単位。複数ワールド合成で拡張可能 |

### 強み

- **一貫性問題が原理的に解消**: 3D空間なのでどのアングルでも一貫
- **コストが安い**: 1生成 $0.12〜$1.28（V2Vの6セグメント$3.60〜$10.50より安い可能性）
- **GLBでBlenderに戻せる**: 既存パイプラインとの統合が可能
- **カメラパスが自由**: V2Vのように始点・終点に縛られない

### 懸念・検証ポイント

- Geminiで独立生成した複数画像の一貫性ズレを、World Labsがどこまで吸収できるか
- 部屋サイズの移動範囲で部屋全体のウォークスルーに十分か
- Gaussian Splatの品質（解像度の限界、元視点から離れた際のアーティファクト）
- Blenderの精密な空間構造がどこまで維持されるか

### 検証方法

PoC6の出力画像（スタイル適用済み6枚）をWorld Labs APIに方位指定付きで入力し、生成された3D空間の品質を評価する。

---

## 7. World Labs API疎通確認（2026-04-01）

### 実行手順

1. https://platform.worldlabs.ai/ でアカウント作成・APIキー取得・クレジット購入
2. `.env`に`DAILY_ROUTINE_API_KEY_WORLD_LABS`を設定
3. `poc/3dcg_poc7/generate_world.py`で以下を実行:
   - `POST /marble/v1/media-assets:prepare_upload` → 署名付きURL取得 → `PUT`で画像アップロード
   - `POST /marble/v1/worlds:generate` でワールド生成（マルチ画像+azimuth指定）
   - `GET /marble/v1/operations/{operation_id}` でポーリング → 完了後アセットダウンロード

### 疎通確認結果

| 項目 | 結果 |
|------|------|
| API認証 | OK（`WLT-Api-Key`ヘッダー） |
| 画像アップロード | OK（5枚、`kind: "image"`が必須） |
| ワールド生成（mini） | OK（約10秒で完了） |
| アセットダウンロード | OK（GLB 4.6MB、SPZ 4.9MB） |
| Webビューアー確認 | OK（platform.worldlabs.aiにログインして閲覧） |

### 生成されたアセット

- `output/world_mesh.glb` — 3Dメッシュ（Blenderインポート可能）
- `output/world_splat_500k.spz` — Gaussian Splat
- `output/thumbnail.webp` — サムネイル
- `output/final_result.json` — APIレスポンス全体

### 判明した制約

- マルチ画像5枚で400エラー → 2枚では成功。入力枚数の上限あり
- APIからのpublic設定は未サポート → ダッシュボードからログインして確認が必要
- 生成リクエストに`permission: {public: true}`を指定しても反映されない

### 品質所感

- サムネイルではカメラ1（廊下→デスク）の構図が忠実に再現されている
- 家具のディテールはGaussian Splatの特性上ぼけが出る → リアルな動画制作用途には不十分
- Web公開用の3Dビューア（インタラクティブに視点変更）としては活用の余地あり

### 方式Cの位置づけ

| 用途 | 判定 | 理由 |
|------|------|------|
| リアルな動画制作 | **×** | 3D再構成品質が不足。家具のディテールが崩壊する |
| Web公開用3Dビューア | **○** | ユーザーが任意視点でインタラクティブに確認できる価値がある |

方式Cは動画制作のメインラインからは外れるが、**Web公開用の補助的アウトプット**として活用の余地あり。

---

## 8. 方針整理（2026-04-01）

### 核心の認識

**全ての品質はGeminiの画像生成に依存する。** Blenderでの3Dオブジェクト配置によるシーン強化は高コストで現実的ではない。レイアウトをリッチにする（生活感・小物・装飾）のはGemini一択。

```
Gemini画像（リッチなレイアウト） → 動画化（V2V or 画像間補間）
Gemini画像（リッチなレイアウト） → 3D化（World Labs、Web公開用）
```

### 未解決の2つの検証テーマ → PoC 8, PoC 9 として分離

---

## PoC 8: Geminiマルチアングル一貫性の改善

### 目的

Geminiで複数アングルの画像を生成する際、小物・装飾の位置をアングル間で一貫させる手法を検証する。

### 背景

- PoC 6でGeminiのスタイル転写は高品質と確認済み（構造維持97.8、スタイル反映95.8）
- しかし各画像を独立生成するため、AIが追加する小物・装飾がアングルごとに異なる
- PoC 6では「AIに追加させない」方針で対処したが、生活感のためにはAIに小物を追加させたい
- Blenderでの小物3D配置は高コストで非現実的 → Gemini側で一貫性を担保する必要がある

### 検証アイデア

**俯瞰画像をreferenceとしてオブジェクト位置を拘束する**

1. 俯瞰（カメラ6相当）でリッチなレイアウトをGeminiにまず生成させる
2. 各アングル生成時に、その俯瞰画像をreferenceとして渡す
3. 「この俯瞰に見えるオブジェクト配置を守って、このアングルから描け」と指示
4. 一貫性が保たれるか評価

### 成功基準

- 3アングル以上で小物の位置・種類が概ね一致していること
- Blenderでの手動配置なしで生活感のあるレイアウトが実現できること

### 実装場所

`poc/3dcg_poc8/`

---

## PoC 9: V2Vスタイル転写の生活感検証

### 目的

Blenderカメラパス動画→V2Vスタイル転写で、Gemini画像ベースと同等の生活感が出せるか検証する。

### 背景

- 方式B（V2V）は構造維持では最も確実（Blenderが完全に担保）
- しかしV2Vのスタイル転写で「生活感」がどこまで表現されるかは未検証
- Gemini画像ベース（方式A）の方が生活感は豊かだが、構造維持・フレーム間一貫性にリスクがある
- 両者を比較して、動画制作のメインラインを最終決定する必要がある

### 検証内容

1. Blenderでカメラ1→カメラ2の5秒ウォークスルー動画をレンダリング
2. V2Vサービス（Luma Modify adhere / Runway Gen-4 Aleph）でスタイル転写
3. Gemini画像ベース（画像間補間）と生活感・構造維持・一貫性を比較

### 評価軸

| 軸 | V2V（方式B） | Gemini画像ベース（方式A） |
|----|-------------|----------------------|
| 生活感 | ? | Geminiの強み |
| 構造維持 | Blenderが担保 | AIに依存 |
| フレーム間一貫性 | 5秒セグメント内はモデルが保証 | AIに依存 |

### 依存関係

PoC 8（Gemini一貫性）の結果が、方式Aの実現可能性を左右する。PoC 8が成功すれば方式Aの競争力が上がる。

### 実装場所

`poc/3dcg_poc9/`

---

## 検証ロードマップ（2026-04-01）

```
PoC 8: Gemini一貫性 ──→ 成功すればGemini画像ベース（方式A）が有力候補に
    ↓
PoC 9: V2V生活感 ────→ 方式Aと方式Bを比較して動画制作のメインラインを最終決定
```

### 次のアクション

1. **PoC 8**: 俯瞰reference方式でGeminiの一貫性改善を検証
2. **PoC 9**: V2Vスタイル転写の生活感をGemini画像と比較検証
