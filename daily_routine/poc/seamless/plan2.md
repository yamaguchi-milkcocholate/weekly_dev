# Seamless Keyframe PoC: Phase 2 — ポーズ変更検証

## 1. 背景

### Phase 1 の結論

- **1パスで人物差し替え + 環境調整を同時指示**する方式（D-B / I-A）が品質・コスト両面で最良
- 連鎖編集（I-B 3パス / anchor 2パス）は、意図した環境調整効果が薄く、パスを重ねるほど画質が劣化するだけ
- Max 2枚入力（D-A）はプロンプト設計に課題あり（参照画像を再現する方向に倒れた）

### Phase 2 の問い

Phase 1 では人物差し替え + 環境調整を検証した。次の疑問:

> **ポーズの変更は 1 パスで同時に指示できるか？**

具体的には、seed キャプチャの直立ポーズ（正面カメラに向かって立っている）を、**スマホの内カメラで自撮りしている構図**に変更する。

### 自撮り構図の特徴

- 片手（通常は右手）を前方に伸ばしてスマホを持つ
- カメラアングルはやや上から（ハイアングル）
- 顔がフレームの中央〜上部
- 背景は元のシーンが残るが、カメラ位置の変化で見え方が変わる
- 自然な表情（軽い笑顔）

## 2. 実験設計

代表シーンは Phase 1 と同じ **scene 6**（6.png）を使用。

### 実験 4: ポーズ変更（自撮り化）

| パターン | 方式 | 内容 | 検証ポイント |
|----------|------|------|-------------|
| P-A | 1パス（人物差し替え + ポーズ変更） | seed キャプチャから人物差し替えとポーズ変更を同時指示 | 1パスでポーズ変更が反映されるか |
| P-B | 2パス（人物差し替え → ポーズ変更） | Pass1: 人物差し替えのみ / Pass2: ポーズを自撮りに変更 | 段階的にポーズ変更する場合の品質 |
| P-C | 1パス（ポーズ変更のみ、人物差し替えなし） | seed キャプチャの人物をそのまま、ポーズだけ自撮りに変更 | ポーズ変更の純粋な効果を確認 |

**生成数**: P-A: 1画像 / P-B: 2画像 / P-C: 1画像 → 合計 4 画像

**コスト**: $0.04 × 4 = $0.16

### プロンプト設計

Phase 1 の知見に基づく:
- 否定表現を使わない
- "transform" を避ける
- 保持すべき要素を明示する
- 1パスで複数変更を指示する場合でも、変更内容と保持内容を明確に分離する

**P-A: 1パスで人物差し替え + ポーズ変更**

```
Change the person in this image to a young Japanese woman, mid 20s, slender build,
wavy dark brown shoulder-length hair, soft round eyes, fair skin,
wearing a beige V-neck blouse, light gray pencil skirt,
a delicate gold necklace, beige flat shoes.
She holds a smartphone in her right hand, arm extended forward,
taking a selfie with the front camera, smiling gently at the phone screen.
The camera angle is slightly above eye level, as seen from the phone's perspective.
Keep the same background environment and lighting.
Maintain the same facial features, hairstyle, and outfit throughout. Single person only, solo.
```

**P-B Pass 1: 人物差し替えのみ**（Phase 1 の D-B と同一）

```
Change the person in this image to a young Japanese woman, mid 20s, slender build,
wavy dark brown shoulder-length hair, soft round eyes, fair skin,
wearing a beige V-neck blouse, light gray pencil skirt,
a delicate gold necklace, beige flat shoes.
Keep the exact same composition, background, camera angle, and lighting.
Maintain the same facial features, hairstyle, and outfit throughout. Single person only, solo.
```

**P-B Pass 2: ポーズを自撮りに変更**

```
The woman in this image holds a smartphone in her right hand, arm extended forward,
taking a selfie with the front camera, smiling gently at the phone screen.
The camera angle shifts to slightly above eye level, as seen from the phone's perspective.
Keep the same facial features, hairstyle, outfit, background environment, and lighting.
Maintain the same facial features, hairstyle, and outfit throughout. Single person only, solo.
```

**P-C: ポーズ変更のみ（人物差し替えなし）**

```
The person in this image holds a smartphone in their right hand, arm extended forward,
taking a selfie with the front camera, smiling gently at the phone screen.
The camera angle is slightly above eye level, as seen from the phone's perspective.
Keep the same background environment and lighting.
Single person only, solo.
```

## 3. 評価基準

1. **ポーズ反映度**: 自撮り構図（腕伸ばし・スマホ持ち・ハイアングル）が再現されているか
2. **キャラクター一致度**: Phase 1 の出力（D-B）と同一人物に見えるか
3. **環境再現度**: seed キャプチャの背景（地下通路）が維持されているか
4. **自然さ**: ポーズ・手・スマホの描画が自然か（AI画像で手の描画は課題になりやすい）

## 4. 期待する結論

- P-A（1パス）で十分な品質が得られれば、本番パイプラインでは **1パスで人物差し替え + ポーズ変更 + 環境調整を同時指示** する方式を採用できる
- P-B（2パス）の方が良い場合、ポーズ変更のみ2パス目で行う構成を検討する（ただし Phase 1 の劣化リスクを踏まえると非推奨）
- P-C は、ポーズ変更の純粋な効果を測るベースライン

## 5. 実行手順

```bash
# ドライラン
uv run python poc/seamless/run_experiment.py --patterns P-A,P-B,P-C --dry-run

# 実行
uv run python poc/seamless/run_experiment.py --patterns P-A,P-B,P-C
```

## 6. コスト見積もり

| パターン | 画像数 | コスト |
|----------|--------|--------|
| P-A（1パス） | 1 | $0.04 |
| P-B（2パス） | 2 | $0.08 |
| P-C（ポーズのみ） | 1 | $0.04 |
| **合計** | **4** | **$0.16** |
