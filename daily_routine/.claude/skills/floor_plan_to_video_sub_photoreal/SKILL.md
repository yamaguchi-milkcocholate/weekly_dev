---
name: floor_plan_to_video_sub_photoreal
description: floor_plan_to_video_sub_cameraの出力動画をKling V3 Omni V2Vでフォトリアルなインテリア動画に変換する対話的スキル。Claudeがプロンプトを生成し、ユーザー確認後にAPI実行する。V2V動画変換、フォトリアル動画生成、Kling V2V、3Dレンダリング動画のリアル化、インテリアウォークスルー動画のフォトリアル変換に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <workdir>
allowed-tools: Bash(uv run *), Bash(ffmpeg *), Bash(mkdir *), Bash(ls *), Bash(cp *)
---

# floor_plan_to_video_sub_photoreal

floor_plan_to_video_sub_cameraが出力したカメラカット動画（3Dレンダリング、テクスチャなし）をKling V3 Omni V2V（base mode）でフォトリアルなインテリアウォークスルー動画に変換する。

## ディレクトリ規約

```
<workdir>/
├── input/
│   ├── cut_*.mp4                # floor_plan_to_video_sub_cameraの出力動画（1本以上）
│   └── style_ref.png            # ユーザー提供のスタイル参照画像（必須）
└── output/
    ├── ref_images/              # Gemini合成ref画像（カットごと）
    │   ├── {cut_name}_ref.png
    │   └── ...
    ├── prompt.txt               # 生成したプロンプト
    ├── negative_prompt.txt      # negative prompt
    ├── cut_*_photorealistic.mp4 # 変換後の動画
    └── execution_log.json       # 実行ログ（パラメータ・コスト・所要時間）
```

## 前提条件

- 環境変数 `DAILY_ROUTINE_API_KEY_KLING_AK` と `DAILY_ROUTINE_API_KEY_KLING_SK` が設定済み
- `gcloud` CLIが認証済み（`gcloud auth application-default login`）
- GCSバケットがパブリック読み取りアクセスで作成済み
- 入力動画は5〜10秒、720p以上、MP4形式

## 処理フロー

```
Phase 0: ref画像合成（Gemini）
    0a. 各カット動画の先頭フレームを抽出（ffmpeg）
    0b. 先頭フレーム + style_ref.png をGeminiに入力し、構図維持のref画像を合成
    0c. >>> ユーザー確認 <<< 合成ref画像の品質確認
    ※ ref画像が元動画と同じ構図を持つことが重要。構図が一致しないとV2Vで構造が崩壊する

Phase 1: プロンプト生成（Claude + ユーザー確認）
    1a. 合成ref画像を確認し、空間の特徴を把握
    1b. V2Vプロンプトを生成
    1c. >>> ユーザー確認 <<< プロンプト・パラメータの確認・調整

Phase 2: V2V実行
    2a. GCSアップロード（動画 + 合成ref画像）
    2b. Kling V3 Omni V2V API実行（--style-image に合成ref画像を指定）
    2c. ポーリング（完了待機）
    2d. 動画ダウンロード

Phase 3: 品質確認
    3a. >>> ユーザー確認 <<< 出力動画の品質確認
    3b. 問題があればPhase 0またはPhase 1に戻って調整・再実行
```

### なぜGemini合成ref画像が必要か

スタイル参照画像をそのままKling V2Vの`image_list`に渡すと、**ref画像の構図に引っ張られて元動画のカメラパス・空間構造が崩壊する**。
各カットの先頭フレーム（3Dレンダリング）とスタイル参照画像をGeminiで合成することで、「構図が元動画と一致し、かつスタイルが適用された」ref画像を生成する。
これにより、V2Vで構造維持 + スタイル適用の両立が可能になる。

---

## Phase 0: ref画像合成（Gemini）

### 0a. 先頭フレーム抽出

各カット動画から先頭フレームを抽出する。

```bash
# 各カットの先頭フレーム抽出
ffmpeg -y -i <workdir>/input/cut_C1.mp4 -frames:v 1 <workdir>/output/ref_images/C1_first_frame.png
ffmpeg -y -i <workdir>/input/cut_C2.mp4 -frames:v 1 <workdir>/output/ref_images/C2_first_frame.png
# ...
```

### 0b. Gemini合成ref画像の生成

先頭フレーム + スタイル参照画像をGeminiに入力し、構図維持のref画像を生成する。
Claudeが先頭フレームとスタイル参照画像を確認し、カットごとに適切なプロンプトを生成して `--prompt` 引数で渡す。

```bash
uv run python <skill_dir>/scripts/generate_ref_image.py \
  --frame <workdir>/output/ref_images/C1_first_frame.png \
  --style-ref <workdir>/input/style_ref.png \
  --prompt "<Claudeが生成したプロンプト>" \
  --output <workdir>/output/ref_images/C1_ref.png
```

プロンプト生成時の観点:
- 1枚目（3Dレンダリング）の構図・家具配置・カメラアングルを維持する指示
- 2枚目（スタイル参照）の素材感・照明・雰囲気を適用する指示
- カット固有の要素（窓外の景色、天井の有無、部屋タイプ等）への言及
- 出力形式の指示（フォトリアルなインテリア写真）

### 0c. ユーザー確認

合成ref画像を提示し、以下を確認してもらう:
- 元の3Dレンダリングと構図が一致しているか
- スタイル参照画像の雰囲気が反映されているか
- 不自然な箇所がないか

品質が不十分な場合はプロンプトを調整して再生成する。

---

## Phase 1: プロンプト生成

### 1a. 合成ref画像の確認

Phase 0で生成した合成ref画像を確認し、空間の特徴を把握する。

確認する観点:
- 部屋のタイプ（リビング、寝室、キッチン等）
- 家具の配置・種類
- 窓の位置・サイズ
- 天井の有無（3Dレンダリングでは天井がない場合が多い）

### 1c. V2Vプロンプトの生成

以下のルールに従ってプロンプトを英語で生成する。

#### プロンプト構造

```
[撮影メタファー] + [空間の基本記述] + [素材・テクスチャの詳細] + [照明の詳細] + [リアリティ強化要素] + [Kling参照記法]
```

#### Kling V3固有のプロンプトテクニック

**効果的な表現（必ず含める）:**

- `real estate listing video` または `shot on mirrorless camera` — カメラ撮影感を強調し、CG感を抑える
- `This is an INDOOR room — there must be a white ceiling overhead, not sky` — 3Dレンダリングで天井がない場合に必須。天井の存在を明示しないとKlingが空として解釈する
- `micro-imperfections — slight dust, fingerprints, fabric wrinkles` — 完璧すぎるCG感を消す
- 光の具体的描写: `Natural soft daylight entering from windows, creating gentle shadows and light gradients`
- 素材の質感詳細: `natural oak hardwood with visible wood grain, slight reflections, and realistic plank joints`

**避けるべき表現:**

- `3D render`, `CG`, `game`, `computer generated` — 入力がCGであることを示唆すると、出力もCG寄りになる
- 抽象的な指示のみ — 素材・照明は具体的に記述する

**Kling参照記法:**

- `@Video1` — 入力動画を参照。「この動画の空間構造を維持して」という意味で使う
- `@Image1` — スタイル参照画像を参照。スタイル・雰囲気の方向性を示す

**プロンプトの長さ:** 100〜200 words が目安。短すぎると制御不足、2500文字が上限。

#### プロンプト生成例

スタイル参照画像なしの場合:

```
Real estate listing video of @Video1, shot on a mirrorless camera with natural lighting. This is an INDOOR room — there must be a white ceiling overhead, not sky. A modern living room with clean lines and warm atmosphere. Walls finished in smooth matte white plaster with subtle texture variations. Natural oak hardwood flooring with visible wood grain, slight reflections, and realistic plank joints. Large windows allowing natural soft daylight to enter, creating gentle shadows and light gradients across the room. Furniture upholstered in soft linen and leather with natural creases. Micro-imperfections throughout — slight dust on surfaces, subtle fingerprints on glass, fabric wrinkles on cushions. Warm color temperature around 5500K with soft ambient fill light. Photorealistic interior with cinematic depth of field.
```

スタイル参照画像ありの場合:

```
Real estate listing video of @Video1, styled after the aesthetic of @Image1, shot on a mirrorless camera. This is an INDOOR room — there must be a white ceiling overhead, not sky. Apply the material palette, color grading, and atmospheric mood from @Image1 to the spatial layout of @Video1. Maintain the exact room geometry, furniture placement, and camera movement from @Video1. Micro-imperfections throughout — slight dust, fingerprints, fabric wrinkles. Natural lighting with soft shadows and realistic light gradients. Photorealistic interior walkthrough.
```

#### negative_prompt

デフォルト値（ユーザーが編集可能）:

```
flicker, morphing, style change, blur, distortion, 3D render, CG, game engine, wireframe, flat shading, plastic texture, oversaturated colors
```

### 1d. ユーザー確認

生成したプロンプトとパラメータをユーザーに提示する。

提示内容:
- **prompt**: 生成したプロンプト全文
- **negative_prompt**: negative prompt
- **video_reference_type**: `base`（固定、モーション維持）
- **cfg_scale**: `0.5`（デフォルト。0=創造的、1=忠実）
- **duration**: 入力動画の長さに合わせる（3〜15秒）
- **aspect_ratio**: `auto`（入力動画に合わせる）
- **推定コスト**: Professional 1080pの場合、$0.168/秒 × duration

ユーザーが承認するまでPhase 2に進まない。

---

## Phase 2: V2V実行

### 実行コマンド

```bash
uv run python <skill_dir>/scripts/run_kling_v2v.py \
  --video <workdir>/input/cut_*.mp4 \
  --gcs-bucket <bucket_name> \
  --prompt "<Phase 1で確定したプロンプト>" \
  --negative-prompt "<negative prompt>" \
  --cfg-scale 0.5 \
  --duration 5 \
  --output-dir <workdir>/output
```

スタイル参照画像がある場合:

```bash
uv run python <skill_dir>/scripts/run_kling_v2v.py \
  --video <workdir>/input/cut_*.mp4 \
  --gcs-bucket <bucket_name> \
  --prompt "<プロンプト>" \
  --negative-prompt "<negative prompt>" \
  --style-image <workdir>/input/style_ref.png \
  --cfg-scale 0.5 \
  --duration 5 \
  --output-dir <workdir>/output
```

### スクリプトの動作

`scripts/run_kling_v2v.py` は以下を実行する:

1. 動画（と参照画像）をGCSにアップロード
2. Kling V3 Omni V2V APIを呼び出し（JWT認証）
3. 5秒間隔でポーリング（最大10分）
4. 完成動画をダウンロード
5. `execution_log.json` に実行パラメータ・所要時間・コストを記録

---

## Phase 3: 品質確認

出力動画をユーザーに提示し、以下の観点で品質を確認してもらう。

### 確認ポイント

1. **空間構造の保持**: 壁の位置・家具配置・カメラの動きが入力動画と一致しているか
2. **テクスチャ品質**: 素材の質感がリアルか（プラスチック感、フラットシェーディングがないか）
3. **照明**: 自然な光と影が表現されているか
4. **一貫性**: フレーム間でちらつき・モーフィングがないか
5. **天井**: 空ではなく天井として描写されているか

### 品質不足の場合の調整方針

| 問題 | 調整方法 |
|------|----------|
| CG感が残る | micro-imperfections の記述を強化、素材記述をより具体的に |
| 天井が空になる | `INDOOR room` `white ceiling overhead` の記述を強調 |
| スタイルが合わない | スタイル参照画像の追加、または素材・色調の記述を変更 |
| 空間が歪む | `cfg_scale` を上げる（0.7〜0.8）、構造維持の記述を強化 |
| ちらつきがある | `negative_prompt` に `flicker, temporal inconsistency` を追加 |
| 色が不自然 | 色温度・カラーパレットの記述を具体的に修正 |

問題があればPhase 1に戻り、プロンプトを調整して再実行する。

---

## Kling V3 Omni APIリファレンス

### 認証

Access Key + Secret KeyからJWT（HS256）を生成し、Authorizationヘッダーに付与する。

```
Authorization: Bearer <JWT>
```

JWT payload:
- `iss`: Access Key
- `exp`: 現在時刻 + 1800秒
- `nbf`: 現在時刻 - 5秒（クロックスキュー対策）

### V2V生成エンドポイント

`POST https://api-singapore.klingai.com/v1/videos/omni-video`

| パラメータ | 型 | 必須 | 説明 |
|-----------|-----|------|------|
| `model_name` | string | Yes | `"kling-v3-omni"` |
| `prompt` | string | Yes | 最大2500文字。`@Video1` `@Image1` で参照可能 |
| `video_list` | array | Yes | 入力動画リスト |
| `video_list[].video_url` | string (URI) | Yes | 入力動画URL（3-10秒、720-2160px、max 200MB） |
| `video_list[].refer_type` | enum | Yes | `"base"`（モーション維持、常にこれを使用） |
| `video_list[].keep_original_sound` | string | No | `"no"`（デフォルト） |
| `image_list` | array | No | スタイル参照画像リスト（`[{"image_url": "..."}]`） |
| `cfg_scale` | float | No | 0〜1（デフォルト0.5） |
| `negative_prompt` | string | No | 除外要素。最大2500文字 |
| `duration` | string | No | `"3"`〜`"15"`（デフォルト`"5"`） |
| `aspect_ratio` | string | No | `"16:9"`, `"9:16"`, `"1:1"`（`"auto"` は400エラー） |
| `mode` | string | No | `"pro"`（1080p） / `"standard"`（720p） |

### ステータス確認

`GET https://api-singapore.klingai.com/v1/videos/omni-video/{task_id}`

| status | 説明 |
|--------|------|
| `submitted` | 送信済み |
| `processing` | 処理中 |
| `succeed` | 完了 → `task_result.videos[0].url` から動画取得 |
| `failed` | 失敗 → `task_status_msg` にエラー内容 |

### 料金（2026-04-01時点）

| モード | 価格/秒 |
|--------|---------|
| Standard (720p) | $0.084 |
| Professional (1080p) | $0.168 |
