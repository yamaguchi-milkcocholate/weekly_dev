# Seamless Keyframe PoC: Phase 3 — Runway / Gemini による比較検証

## 1. 背景

Phase 2 で FLUX Kontext の P-A（1パス: 人物差し替え + ポーズ変更）が有効であることを確認した。ただし P-A ではポーズを大きく変更するため、元画像の構図保持という Kontext の強みが活きていない。

T2I + 参照画像方式（Runway）や、I2I 対応の Gemini でも同等以上の結果が得られる可能性がある。

## 2. 使用 API

### Runway Gen-4 Image

- エンドポイント: `POST https://api.dev.runwayml.com/v1/text_to_image`
- 認証: `Authorization: Bearer {DAILY_ROUTINE_API_KEY_RUNWAY}`, `X-Runway-Version: 2024-11-06`
- 方式: T2I + 参照画像（@tag）、最大3枚
- I2I: **非対応**（参照画像ベースの新規生成のみ）
- レスポンス: 非同期（ポーリング）
- コスト: $0.02（turbo）/ $0.05（720p）

### Gemini（画像生成）

- エンドポイント: `POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent`
- 認証: `x-goog-api-key: {DAILY_ROUTINE_API_KEY_GOOGLE_AI}`
- 方式: I2I 対応（入力画像 + テキスト指示）、参照画像は parts に含める
- モデル: `gemini-2.0-flash-preview-image-generation`（無料枠あり）
- レスポンス: **同期**（直接レスポンス、base64 で画像返却）
- コスト: ~$0.04/画像

## 3. 実験設計

Phase 2 の P-A / P-B に対応する実験を Runway と Gemini で実施する。

### Runway パターン

| パターン | 方式 | 内容 | コスト |
|----------|------|------|--------|
| R-A | T2I + @char + @location | seed キャプチャを @location、彩花を @char として参照 + 自撮りポーズをプロンプト指示 | $0.05 |
| R-B | T2I + @char のみ | 彩花を @char として参照 + 環境・ポーズをプロンプトで記述 | $0.05 |

### Gemini パターン

| パターン | 方式 | 内容 | コスト |
|----------|------|------|--------|
| G-A | I2I（seed + テキスト指示） | seed キャプチャを入力 + 人物差し替え・ポーズ変更を指示（FLUX P-A と同等） | ~$0.04 |
| G-B | I2I（seed + 参照画像 + テキスト指示） | seed キャプチャ + 彩花の参照画像を入力 + ポーズ変更を指示 | ~$0.04 |

### 参照画像

- **キャラクター参照**: `poc/seamless/reference/front.png`（彩花）
- **シーン参照**: `seeds/captures/tamachan_life_/6.png`

### プロンプト設計

**R-A（Runway: @char + @location）**

```
@char takes a selfie with her smartphone in @location,
arm extended forward, front camera perspective,
slightly above eye level, gentle smile.
Lifestyle photography, natural lighting.
```

**R-B（Runway: @char のみ）**

```
@char takes a selfie with her smartphone in an underground walkway,
arm extended forward, front camera perspective,
slightly above eye level, gentle smile.
Fluorescent overhead lighting, tiled floor, wide corridor.
Lifestyle photography.
```

**G-A（Gemini: I2I テキスト指示のみ）**

```
Change the person in this image to a young Japanese woman, mid 20s, slender build,
wavy dark brown shoulder-length hair, soft round eyes, fair skin,
wearing a beige V-neck blouse, light gray pencil skirt,
a delicate gold necklace, beige flat shoes.
She holds a smartphone in her right hand, arm extended forward,
taking a selfie with the front camera, smiling gently at the phone screen.
The camera angle is slightly above eye level, as seen from the phone's perspective.
Keep the same background environment and lighting.
Single person only, solo.
```

**G-B（Gemini: 参照画像 + テキスト指示）**

```
Change the person in this image to the woman shown in the reference photo.
She holds a smartphone in her right hand, arm extended forward,
taking a selfie with the front camera, smiling gently at the phone screen.
The camera angle is slightly above eye level, as seen from the phone's perspective.
Keep the same background environment and lighting.
Maintain the same facial features, hairstyle, and outfit as the reference photo.
Single person only, solo.
```

## 4. 評価基準

Phase 2 と同一基準で比較:

1. **ポーズ反映度**: 自撮り構図が再現されているか
2. **キャラクター一致度**: 彩花の参照画像とどの程度同一人物に見えるか
3. **環境再現度**: seed キャプチャの背景が維持されているか
4. **自然さ**: ポーズ・手・スマホの描画が自然か

## 5. 実装

`poc/seamless/run_plan3.py` として独立スクリプトを作成する（config.py のパターン追加ではなく、API が異なるため）。

## 6. コスト見積もり

| パターン | API | コスト |
|----------|-----|--------|
| R-A | Runway gen4_image 720p | $0.05 |
| R-B | Runway gen4_image 720p | $0.05 |
| G-A | Gemini 2.0 Flash | ~$0.04 |
| G-B | Gemini 2.0 Flash | ~$0.04 |
| **合計** | | **~$0.18** |
