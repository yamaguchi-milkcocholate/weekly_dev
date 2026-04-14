# Seamless Keyframe PoC: Phase 4 — 環境変更検証（Kontext vs Gemini）

## 1. 背景

Phase 1-2 では人物差し替え・ポーズ変更を検証した。Phase 3 では Kontext と Gemini がポーズ変更で同等品質であることを確認した。

Phase 4 では、**人物はそのままに、背景環境だけを変更**する検証を行う。これは Kontext の I2I 編集能力が最も活きるケースであり、Gemini との品質差が最も出やすい用途。

### 検証シナリオ

seed キャプチャ（地下通路）の人物をそのまま残し、背景を桜の川沿い遊歩道（`reference/sakura.jpg`）に変更する。

## 2. 参照画像

- **入力画像**: `seeds/captures/tamachan_life_/6.png`（地下通路で自撮り中の女性）
- **環境参照**: `poc/seamless/reference/sakura.jpg`（桜並木の川沿い遊歩道、晴天）

## 3. 実験設計

### Kontext パターン

| パターン | 方式 | 内容 | コスト |
|----------|------|------|--------|
| E-A | Kontext Pro 1枚入力（テキストのみ） | seed キャプチャを入力し、プロンプトで背景変更を指示 | $0.04 |
| E-B | Kontext Max 2枚入力（環境参照あり） | seed キャプチャ + sakura.jpg を入力し、環境の転写を指示 | $0.08 |

### Gemini パターン

| パターン | 方式 | 内容 | コスト |
|----------|------|------|--------|
| E-C | Gemini テキストのみ | seed キャプチャを入力し、プロンプトで背景変更を指示 | $0.04 |
| E-D | Gemini 環境参照あり | seed キャプチャ + sakura.jpg を入力し、環境の転写を指示 | $0.04 |

**生成数**: 4画像

**コスト**: $0.20

### プロンプト設計

**E-A: Kontext Pro テキストのみで背景変更**

```
Change the background of this image to a riverside walkway lined with
blooming pink cherry blossom trees under a clear blue sky.
Keep the person, pose, outfit, and camera angle completely unchanged.
Bright natural daylight, vivid spring atmosphere.
Single person only, solo.
```

**E-B: Kontext Max 2枚入力で環境転写**

```
Place the person from image_1 into the scene from image_2.
Keep the same person, pose, outfit, and camera angle from image_1.
Use the cherry blossom riverside environment, lighting, and atmosphere from image_2.
Single person only, solo.
```

**E-C: Gemini テキストのみで背景変更**

```
Change the background of this image to a riverside walkway lined with
blooming pink cherry blossom trees under a clear blue sky.
Keep the person, pose, outfit, and camera angle completely unchanged.
Bright natural daylight, vivid spring atmosphere.
Single person only, solo.
```

**E-D: Gemini 環境参照画像付きで背景変更**

```
Change the background of this image to match the environment shown in the reference photo.
Keep the person, pose, outfit, and camera angle completely unchanged.
Use the cherry blossom riverside environment, lighting, and atmosphere from the reference photo.
Single person only, solo.
```

## 4. 評価基準

1. **環境反映度**: 桜の川沿い遊歩道の雰囲気がどの程度再現されているか
2. **人物保持度**: 元の人物のポーズ・服装・表情が維持されているか
3. **合成の自然さ**: 人物と背景の整合性（照明・影・パースペクティブ）
4. **参照画像の忠実度**: E-B/E-D で sakura.jpg の雰囲気がどの程度転写されているか

## 5. 期待する結論

- **E-A vs E-C**: テキストのみでの背景変更で Kontext と Gemini の I2I 編集力を比較
- **E-B vs E-D**: 環境参照画像ありでの転写品質を比較
- Kontext の構図保持力が Gemini を上回るか、または Gemini 3 Pro が同等品質を出せるかを確認

## 6. コスト見積もり

| パターン | API | コスト |
|----------|-----|--------|
| E-A | Kontext Pro（1枚入力） | $0.04 |
| E-B | Kontext Max（2枚入力） | $0.08 |
| E-C | Gemini 3 Pro | $0.04 |
| E-D | Gemini 3 Pro | $0.04 |
| **合計** | | **$0.20** |
