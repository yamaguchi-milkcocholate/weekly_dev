# Kling V3 Omni V2V ベストプラクティス調査レポート

調査日: 2026-04-08

## 調査目的

3DCGレンダリング動画（Blender等）をKling V3 Omni V2Vでフォトリアルなインテリアウォークスルー動画に変換する際の、構図・空間構造を維持しつつ品質を最大化するためのベストプラクティスを体系的に整理する。

---

## 1. refer_type: "base" vs "feature" の使い分け

### 公式定義

| モード | 説明 | 用途 |
|--------|------|------|
| `base` | 元動画のモーション・構図を**完全維持**してリスタイル | 3DCG→フォトリアル変換（**本プロジェクトで使用**） |
| `feature` | 元動画からスタイル・カメラワークを**抽出**して新コンテンツに適用 | スタイル転用・モーション参照 |

出典:
- [Scenario - Kling V3 Omni Guide](https://help.scenario.com/en/articles/kling-v3-omni-video-the-all-in-one-cinematic-powerhouse/)
- [Replicate - Kling V3 Omni](https://replicate.com/kwaivgi/kling-v3-omni-video)
- [Freepik API Docs](https://docs.freepik.com/api-reference/video/kling-v3-omni/generate-std-video-reference)

### 構造維持の観点からの選択

**`base` を使用すべき理由:**

- `base` モードは「入力動画をモーションスケルトンとして使い、ビジュアルコンテンツを再レンダリングする」設計
- 元動画のモーション・タイミング・空間構成が保持される
- 「既存映像のリスタイル」に最適化されており、3DCG→フォトリアル変換はまさにこのユースケース

**`feature` を使うべきでない理由:**

- `feature` は「カメラワーク・スタイルの特徴を抽出して新しいコンテンツを生成する」設計
- 空間構造の忠実な保持は保証されない
- 元動画の家具配置・壁の位置等の空間的要素が変わる可能性がある

### 結論

**3DCG→フォトリアル変換には `refer_type: "base"` を常に使用する。** これはPoC 9の検証結果とも一致する。

---

## 2. cfg_scale パラメータチューニング

### パラメータ仕様

| 値 | モード | 説明 |
|----|--------|------|
| 0.0〜0.3 | Creative Mode | AIの創造的解釈を最大化。抽象的・アーティスティックな結果 |
| 0.4〜0.6 | Balanced（デフォルト0.5） | 創造性と忠実度のバランス。**ほとんどのV2V用途に最適** |
| 0.7〜1.0 | Precise Mode | プロンプトへの厳密な追従。構造維持を最大化 |

出典:
- [Freepik API Docs - cfg_scale](https://docs.freepik.com/api-reference/video/kling-v3-omni/generate-std-video-reference)
- [FluxPro - Kling 2.5 CFG Control](https://www.fluxpro.ai/vm/kling/kling-2-5)
- [VEED - Kling AI Prompting Guide](https://www.veed.io/learn/kling-ai-prompting-guide)
- [ArtSmart - CFG Scale Explained](https://artsmart.ai/blog/what-is-cfg-scale/)

### 3DCG→フォトリアル変換での推奨値

**推奨: `cfg_scale = 0.5`（デフォルト）を基本とし、問題に応じて調整**

| 状況 | 推奨cfg_scale | 理由 |
|------|--------------|------|
| 初回テスト | 0.5 | バランスの取れた出発点 |
| 空間が歪む・家具が消える | 0.7〜0.8 | 構造維持を強化 |
| CG感が残る・質感が硬い | 0.4〜0.5 | 創造的自由度を上げてリアルな質感を生成 |
| プロンプトの素材指定が反映されない | 0.7〜0.8 | プロンプト追従度を上げる |
| 過度に加工された見た目 | 0.4〜0.5 | 値が高すぎると不自然になる |

### 注意点

- cfg_scaleが高すぎる（0.9以上）と「過度に処理された」見た目になり、自然さが失われる
- cfg_scaleが低すぎる（0.3以下）とプロンプトが無視され、意図しないスタイルになる
- `base` モードでは入力動画自体が強い構造的制約を提供するため、cfg_scale 0.5でも十分な構造維持が得られる

---

## 3. プロンプト設計: 構造維持のためのテクニック

### 3.1 プロンプト基本構造

Kling 3.0のプロンプトは「ディレクターがシーンを指揮するように」書くのが最も効果的。

```
[撮影メタファー] + [空間の基本記述] + [素材・テクスチャ詳細] + [照明] + [リアリティ強化] + [Kling参照記法]
```

出典:
- [fal.ai - Kling 3.0 Prompting Guide](https://blog.fal.ai/kling-3-0-prompting-guide/)
- [Atlas Cloud - Kling O3 Guide](https://www.atlascloud.ai/blog/guides/kling-video-o3-api-guide)

### 3.2 構造維持に効果的なプロンプト表現

#### 必ず含めるべき表現

| 表現 | 効果 | 出典 |
|------|------|------|
| `real estate listing video` | 不動産物件動画としてのリアリティを喚起 | PoC 9検証 |
| `shot on mirrorless camera` | カメラ撮影感を強調し、CG感を抑制 | PoC 9検証 |
| `@Video1` | 入力動画を明示的に参照（空間構造の維持を指示） | Kling公式 |
| `This is an INDOOR room — there must be a white ceiling overhead, not sky` | 天井の存在を明示（3DCGで天井なしの場合に必須） | PoC 9検証 |
| `micro-imperfections — slight dust, fingerprints, fabric wrinkles` | CG感を消すリアリティディテール | PoC 9検証 |
| `preserve shape` / `maintain scale` | 構図維持の明示的指示 | [InVideo - Hidden Secrets](https://invideo.io/blog/hidden-secrets-of-kling-ai/) |
| `smooth steadicam walkthrough` | カメラ動作の安定性を指示 | 一般的ベストプラクティス |

#### 素材・テクスチャの具体的記述

抽象的な指示ではなく、素材を具体的に記述することでKlingの認識精度が向上する。

```
// 良い例
"Walls finished in smooth matte white plaster with subtle texture variations.
Natural oak hardwood flooring with visible wood grain, slight reflections,
and realistic plank joints. Solid wood doors with warm brown grain pattern."

// 悪い例
"Beautiful interior with nice walls and floor."
```

#### 照明の具体的記述

```
"Natural soft daylight entering from windows, creating gentle shadows
and light gradients across the room. Warm color temperature around 5500K
with soft ambient fill light."
```

### 3.3 避けるべき表現

| 表現 | 理由 | 出典 |
|------|------|------|
| `3D render` / `CG` / `game` / `computer generated` | 入力がCGだと示唆すると出力もCG寄りに | PoC 9検証 |
| 過度に複雑なプロンプト（要素詰め込み） | カオスな結果になる。3〜5要素が最適 | [VEED](https://www.veed.io/learn/kling-ai-prompting-guide) |
| 激しい動きの記述 | V2Vでは入力動画の動きが基本。矛盾する動きの記述は構造を崩す | 一般的ベストプラクティス |
| 抽象的な指示のみ | 素材・照明は具体的に記述する方が品質向上 | 全般 |

### 3.4 推奨プロンプトテンプレート

#### スタイル参照画像なしの場合

```
Real estate listing video of @Video1, shot on a mirrorless camera with
natural lighting. This is an INDOOR room — there must be a white ceiling
overhead, not sky. A modern Japanese apartment with clean lines and warm
atmosphere. Walls finished in smooth matte white plaster with subtle texture
variations. Natural oak hardwood flooring with visible wood grain, slight
reflections, and realistic plank joints. Solid wood doors with warm brown
grain pattern. Large windows allowing natural soft daylight to enter,
creating gentle shadows and light gradients across the room. Furniture
upholstered in soft linen and leather with natural creases.
Micro-imperfections throughout — slight dust on surfaces, subtle fingerprints
on glass, fabric wrinkles on cushions. Warm color temperature around 5500K
with soft ambient fill light. Photorealistic interior with cinematic depth
of field.
```

#### スタイル参照画像ありの場合

```
Real estate listing video of @Video1, styled after the aesthetic of @Image1,
shot on a mirrorless camera. This is an INDOOR room — there must be a white
ceiling overhead, not sky. Apply the material palette, color grading, and
atmospheric mood from @Image1 to the spatial layout of @Video1. Maintain
the exact room geometry, furniture placement, and camera movement from
@Video1. Micro-imperfections throughout — slight dust, fingerprints, fabric
wrinkles. Natural lighting with soft shadows and realistic light gradients.
Photorealistic interior walkthrough.
```

### 3.5 プロンプトの長さ

- **最適: 100〜200 words**
- 短すぎると制御不足、2500文字が上限
- 要素は3〜5に絞る（Kling 3.0の場合。旧バージョンは3〜4が最適）

出典: [VEED - Kling AI Prompting Guide](https://www.veed.io/learn/kling-ai-prompting-guide)

---

## 4. negative_prompt のベストプラクティス

### 推奨negative_prompt

```
flicker, morphing, style change, blur, distortion, 3D render, CG, game engine,
wireframe, flat shading, plastic texture, oversaturated colors, camera shake,
exaggerated motion, visual distortion, warped surfaces, temporal inconsistency,
compression artifacts, watermark, text overlay, low quality, extra limbs,
unnatural physics
```

出典:
- [Ambience AI - Kling Prompting Guide](https://www.ambienceai.com/tutorials/kling-prompting-guide)
- [InVideo - Hidden Secrets of Kling AI](https://invideo.io/blog/hidden-secrets-of-kling-ai/)
- PoC 9検証結果

### カテゴリ別negative_prompt

| カテゴリ | negative_prompt |
|---------|----------------|
| CG感の排除 | `3D render, CG, game engine, wireframe, flat shading, plastic texture` |
| 時間的安定性 | `flicker, morphing, style change, temporal inconsistency` |
| 構造の安定性 | `distortion, warped surfaces, exaggerated motion, camera shake` |
| 画質の維持 | `blur, compression artifacts, low quality, watermark, text overlay` |
| 不自然さの排除 | `oversaturated colors, unnatural physics, extra limbs` |

### 重要な知見

- negative_promptを省略するとアーティファクト・ぼかし・歪みが増える
- **全ての生成でnegative_promptを含めるべき**
- プロジェクト内で固定して使い回すことで一貫性が向上

---

## 5. reference画像の活用

### 効果

PoC 9で検証済みの知見:

| 条件 | 結果 |
|------|------|
| reference画像なし | 「ゲームっぽさ」が残る |
| reference画像あり | 実写感に転換。フローリングがヘリンボーン柄、照明がスポットライトレール+ダウンライトで自然に |

### reference画像の選定基準

- **Kling公式推奨**: 「クリーンで、照明が良く、被写体が明確で、シンプルなエッジで、背景のクラッターが少ない」画像
- **1枚の強いアンカー画像**: 複数の矛盾する参照画像より、1枚の優れた参照画像の方が安定する
- **プロンプト内での明示的参照**: `@Image1` で参照画像をプロンプト内で言及し、どのように適用するかを記述する

出典:
- [VibeEffect - Kling 3.0 Omni Guide](https://vibeeffect.ai/blog/kling-3-0-omni-guide)
- [InVideo - Hidden Secrets of Kling AI](https://invideo.io/blog/hidden-secrets-of-kling-ai/)

### reference画像のプロンプトでの参照方法

```
// reference画像のスタイルを適用する場合
"styled after the aesthetic of @Image1"
"Apply the material palette, color grading, and atmospheric mood from @Image1"

// reference画像のタグ付け（Kling 3.0 Omni推奨）
"character design @Image1, moody lighting @Image2"
```

### Omniモードでのreference活用ベストプラクティス

1. **固定要素と可変要素を分離**: reference画像で「ロックされるもの」（素材感・色調）と「変わるもの」（カメラ動き・ムード）を明示する
2. **ショットの意図とアイデンティティを分離**: カメラワークやムードの記述に、参照画像の視覚的事実を繰り返さない
3. **段階的にテスト**: シンプルな動きから始めて、複雑なマルチビートショットへ

出典: [VibeEffect - Kling 3.0 Omni Guide](https://vibeeffect.ai/blog/kling-3-0-omni-guide)

---

## 6. 3DCG→フォトリアル変換の入力動画最適化

### Blenderレンダリング側の最適化

**「中間戦略」が最適**: フラットなソリッドカラーではなく、かつフルリアリスティックテクスチャでもなく、素材の種類が判別できる程度の軽いテクスチャヒントを加える。

| 要素 | 推奨設定 | 理由 |
|------|----------|------|
| 壁 | Roughness 0.9-1.0、Normal微細凹凸(Strength 0.02-0.05) | 「塗装された壁」として認識 |
| ドア | Roughness 0.4-0.6、木目方向テクスチャ(Mix 0.1-0.2) | 「木のドア」として認識 |
| 柱 | Roughness 0.85-0.95、微妙な色ムラ | 「コンクリート柱」として認識 |
| 床 | Roughness 0.55±7%、横方向ストライプ(Mix 0.1-0.15) | フローリング板目方向の安定 |
| 天井 | 白フラットカラー | テクスチャ不要。存在することが重要 |
| 窓 | Alpha 0.1-0.3 半透明 | Klingが「窓」と認識するため |

出典: `docs/memo/kling_v2v_3dcg_optimization.md`（プロジェクト内既存調査）

### 入力動画の推奨仕様

| 項目 | 推奨値 | 根拠 |
|------|--------|------|
| 解像度 | 1920x1080 (1080p) | Kling Pro出力と同等以上 |
| フレームレート | 30fps | Klingネイティブfps |
| コーデック | H.264 (MP4) | API受付フォーマット |
| アスペクト比 | 16:9 | 出力は入力に依存 |
| 長さ | 5秒/セグメント | 最適な品質バランス（3〜10秒の制限内） |
| ファイルサイズ | < 200MB | API制限 |
| カメラ動き | 緩やかで予測可能な動き | 急な動きはV2V変換の精度を下げる |

### 入力動画の品質向上ポイント

- **HDRI環境照明の使用**: 陰影がつくことでKlingの3D構造理解を助ける
- **アンビエントオクルージョン有効化**: 角・隅の影で構造認識が向上
- **ソフトシャドウ**: ハードシャドウはAIが誤解釈する場合がある
- **ブルーム/レンズ効果は不要**: Klingが独自に追加する

出典:
- [Atlas Cloud - Kling O3 Guide](https://www.atlascloud.ai/blog/guides/kling-video-o3-api-guide) — "Higher quality source video produces better transformations"
- `docs/memo/kling_v2v_3dcg_optimization.md`

---

## 7. よくある失敗と対策

### 7.1 構図が崩れる（空間構造が維持されない）

**原因:**
- `refer_type: "feature"` を使用している（→ `"base"` に変更）
- cfg_scaleが低すぎる（→ 0.5〜0.7に上げる）
- プロンプトに入力動画と矛盾する動きの記述がある
- 入力動画の品質が低い（解像度不足、急な動き）

**対策:**
- `refer_type: "base"` を常に使用
- プロンプトで `@Video1` を参照し、空間構造の維持を明示
- `"Maintain the exact room geometry, furniture placement, and camera movement from @Video1"` を含める
- 入力動画は1080p、30fps、緩やかなカメラ動きで

### 7.2 天井が空になる

**原因:**
- 3DCGで天井がない、または半透明
- プロンプトで天井の存在を明示していない

**対策:**
- Blender側で天井オブジェクトを配置
- プロンプトに `"This is an INDOOR room — there must be a white ceiling overhead, not sky"` を必ず含める

### 7.3 CG感が残る（壁がフラット、テクスチャが硬い）

**原因:**
- Blender側でフラットなソリッドカラーを使用
- プロンプトの素材記述が抽象的
- reference画像を使用していない

**対策:**
- Blender壁にRoughness変動+Normal微細凹凸を追加
- プロンプトで素材を具体的に記述（「smooth matte white plaster with subtle texture variations」等）
- reference画像（スタイル適用済み静止画）を追加
- `micro-imperfections` の記述を含める

### 7.4 ちらつき・モーフィング

**原因:**
- negative_promptにflicker/morphing対策がない
- 入力動画の動きが急すぎる
- セグメント間のスタイルが不一致

**対策:**
- negative_promptに `"flicker, morphing, style change, temporal inconsistency"` を含める
- 入力動画のカメラ動きを緩やかにする
- 全セグメントで同じreference画像・prompt・negative_promptを使用

### 7.5 スタイルが意図と異なる

**原因:**
- reference画像が弱い（不明瞭、クラッターが多い）
- プロンプトのスタイル記述が曖昧
- 複数の矛盾する参照素材を使用

**対策:**
- 「1枚の強いアンカー画像」を使用（複数より安定）
- スタイル記述を具体的に（「Studio Ghibli watercolor anime style」ではなく素材・照明・色温度を具体的に）
- プロジェクト全体で同じスタイル文を統一使用

### 7.6 プロンプトが無視される

**原因:**
- cfg_scaleが低すぎる（0.0〜0.3）
- プロンプトが長すぎて要素が散漫
- プロンプトの構造が不明確

**対策:**
- cfg_scaleを0.5〜0.7に
- 要素を3〜5に絞る
- 「ディレクターがシーンを指揮するように」書く（オブジェクトのリストではなく）

出典:
- [VEED - Kling AI Prompting Guide](https://www.veed.io/learn/kling-ai-prompting-guide)
- [InVideo - Hidden Secrets of Kling AI](https://invideo.io/blog/hidden-secrets-of-kling-ai/)
- [Ambience AI - Kling Prompting Guide](https://www.ambienceai.com/tutorials/kling-prompting-guide)

---

## 8. 長尺動画の一貫性維持

### 方法A: セグメント分割 + スティッチ（推奨）

```
Blender 30秒動画
  ↓ 5秒×6セグメントに分割（部屋の切り替わりで区切る）
  ↓
各セグメントを Kling V3 Omni V2V (base mode)
  + reference_images: [スタイル適用済み画像2-4枚]
  + seed: 固定値
  + negative_prompt: 固定
  + cfg_scale: 0.5（固定）
  ↓
ffmpegで結合 → 完成
```

### 方法B: Video Extend API

```
V2Vで5秒生成 → Extend APIで5秒追加 → さらに追加 → ...
```

- 最大3分までチェーン可能
- 0〜30秒: 安定
- 30〜60秒: 微妙なドリフト開始
- 60秒以降: 顕著な劣化

### 一貫性維持の鍵

- **seed固定**: 全セグメントで同じseed
- **reference画像固定**: スタイルアンカーとして全セグメントに同じ画像
- **negative_prompt固定**: 全セグメントで同じnegative_prompt
- **同一プロンプトスタイル文**: プロジェクト全体で末尾に同じスタイル文を追加

出典: `poc/3dcg_poc9/kling_v3_manual.md`

---

## 9. API パラメータ一覧（V2V用）

### Kling V3 Omni公式API

| パラメータ | 型 | デフォルト | 説明 |
|-----------|-----|----------|------|
| `model_name` | string | — | `"kling-v3-omni"` |
| `prompt` | string | — | 最大2500文字。`@Video1` `@Image1` で参照 |
| `video_list` | array | — | 入力動画のリスト（`video_url`, `refer_type`, `keep_original_sound`） |
| `video_list[].video_url` | string (URI) | — | 入力動画URL（3-10秒、720-2160px、max 200MB） |
| `video_list[].refer_type` | enum | — | `"base"`（モーション維持） / `"feature"`（スタイル抽出） |
| `video_list[].keep_original_sound` | string | `"no"` | 元動画の音声を保持するか |
| `image_list` | array | — | スタイル参照画像（`image_url`） |
| `cfg_scale` | float | 0.5 | 0=創造的自由、1=プロンプト厳密追従 |
| `negative_prompt` | string | — | 除外要素。最大2500文字 |
| `duration` | string | `"5"` | 出力秒数 `"3"` 〜 `"15"` |
| `aspect_ratio` | string | `"16:9"` | `"auto"`, `"16:9"`, `"9:16"`, `"1:1"` |
| `mode` | string | — | `"pro"` (1080p) / `"standard"` (720p) |

### 料金（2026-04-01時点）

| モード | 価格/秒 |
|--------|---------|
| Standard (720p) | $0.084 |
| Professional (1080p) | $0.168 |

---

## 10. 建築・インテリア向けAI動画の業界動向

### Klingの競合ポジション

2026年4月時点で、建築・インテリアビジュアライゼーション向けのAI動画ツール比較:

| ツール | 品質 | V2V | 構造維持 | 解像度 | 備考 |
|--------|------|-----|---------|--------|------|
| **Kling 3.0** | 4.9/5 | base/feature | 高 | 4K | 最高品質。マルチショット対応 |
| Veo 3.1 | 4.8/5 | 限定的 | 中〜高 | 4K | 映画語彙への反応が最良 |
| Runway Gen-4.5 | 4.7/5 | あり | 中 | 1080p | Motion Brush 3.0でカメラ制御 |
| Luma Ray3 | 4.6/5 | あり | 高 | 4K HDR | 3D空間認識に強い |

出典: [RenderAI - Top 15 AI Video Models 2026](https://renderai.app/blog/video-ai-models-for-architects-designers-marketers/)

### 建築V2Vで注意すべき点

- 「結果は常に予測可能ではない」「物理エラーが発生する」「複雑なシーンでは重要な建築ディテールが失われる」（Runway for Architects の評価）
- ControlNet方式（ComfyUI + SD）が最も制御可能だが、フレーム間一貫性の課題がある
- 商用V2V（Kling等）は一貫性が高いが、構造制御は間接的

出典: [ArchiObjects - Runway ML for Architects](https://www.archiobjects.org/runway-ml-for-architects-ai-video-generator-and-much-more/)

---

## 11. 推奨ワークフロー（まとめ）

### 本プロジェクトの最適ワークフロー

```
Step 1: Blender 3DCGレンダリング
  - Cycles/EEVEE + HDRI + AO + ソフトシャドウ
  - 中間テクスチャ戦略（素材判別できる程度の軽いヒント）
  - 1080p、30fps、5秒セグメント

Step 2: reference画像の準備
  - PoC 8で生成したスタイル適用済み画像（1-2枚）
  - クリーン・明瞭・背景シンプルなもの

Step 3: プロンプト設計
  - テンプレートベースで生成
  - @Video1 + @Image1 で参照
  - 素材・照明を具体的に記述
  - micro-imperfections を含める
  - 天井の存在を明示

Step 4: Kling V3 Omni V2V実行
  - refer_type: "base"
  - cfg_scale: 0.5（初回）
  - negative_prompt: 固定テンプレート
  - mode: "pro" (1080p)

Step 5: 品質確認 → 調整ループ
  - 空間構造の保持度チェック
  - CG感チェック
  - ちらつきチェック
  - 問題に応じてcfg_scale/プロンプト調整
```

### パラメータのチートシート

| パラメータ | 値 | 備考 |
|-----------|-----|------|
| `refer_type` | `"base"` | 常にbase。featureは使わない |
| `cfg_scale` | `0.5` | 基本値。空間歪みなら0.7へ |
| `duration` | `"5"` | 入力動画に合わせる |
| `aspect_ratio` | `"auto"` | 入力動画に合わせる |
| `mode` | `"pro"` | 1080p出力 |
| `negative_prompt` | 固定テンプレート | 全セグメントで統一 |

---

## 情報源一覧

### Kling公式・API

- [Kling V3 Omni - Scenario Guide](https://help.scenario.com/en/articles/kling-v3-omni-video-the-all-in-one-cinematic-powerhouse/)
- [Kling Video Models Essentials - Scenario](https://help.scenario.com/en/articles/kling-video-models-the-essentials/)
- [Kling 3.0 Prompting Guide - fal.ai](https://blog.fal.ai/kling-3-0-prompting-guide/)
- [Kling V3 Omni - Freepik API Docs](https://docs.freepik.com/api-reference/video/kling-v3-omni/generate-std-video-reference)
- [Kling V3 Omni - Replicate](https://replicate.com/kwaivgi/kling-v3-omni-video)
- [Kling Video O3 API Guide - Atlas Cloud](https://www.atlascloud.ai/blog/guides/kling-video-o3-api-guide)
- [Kling O1 V2V - fal.ai](https://fal.ai/models/fal-ai/kling-video/o1/video-to-video/edit/api)

### プロンプト・ベストプラクティス

- [Kling AI Prompting Guide - VEED](https://www.veed.io/learn/kling-ai-prompting-guide)
- [Hidden Secrets of Kling AI - InVideo](https://invideo.io/blog/hidden-secrets-of-kling-ai/)
- [Kling Prompting Guide - Ambience AI](https://www.ambienceai.com/tutorials/kling-prompting-guide)
- [Kling 3.0 Omni Guide - VibeEffect](https://vibeeffect.ai/blog/kling-3-0-omni-guide)
- [Kling 2.6 Pro Prompt Guide - fal.ai](https://fal.ai/learn/devs/kling-2-6-pro-prompt-guide)
- [CFG Scale Explained - ArtSmart](https://artsmart.ai/blog/what-is-cfg-scale/)

### 建築・インテリアAI動画

- [Top 15 AI Video Models for Architects - RenderAI](https://renderai.app/blog/video-ai-models-for-architects-designers-marketers/)
- [Runway ML for Architects - ArchiObjects](https://www.archiobjects.org/runway-ml-for-architects-ai-video-generator-and-much-more/)
- [3D Model to Cinematic Video - Rendair AI](https://rendair.ai/blog/3d-model-to-cinematic-video)

### 3DCG→AI変換ワークフロー

- [Blender + ComfyUI Workflow - RunComfy](https://www.runcomfy.com/comfyui-workflows/ai-rendering-3d-animations-with-blender-and-comfyui)
- [AI as Render Engine - Daz 3D Forums](https://www.daz3d.com/forums/discussion/725176/ai-as-render-engine)
- [Reallusion AI Render - iClone](https://magazine.reallusion.com/2025/08/08/iclone-delivers-production-level-control-for-ai-generation/)

### 日本語情報

- [Kling 3.0完全ガイド - AQUA](https://www.aquallc.jp/kling-3-complete-guide/)
- [Kling 3.0新機能ガイド - ReeX Japan](https://moodime.com/vgai/kling/kling-3-new-features-guide/)
- [Kling 3.0 Omni使い方 - note](https://note.com/humble_eel6890/n/n639b15bc41c3)
- [Kling AI完全ガイド 5W1H - okihiro](https://okihiro-school.com/kling-ai-complete-user-guide/)

### プロジェクト内既存知見

- `docs/memo/kling_v2v_3dcg_optimization.md` — Blenderマテリアル最適化調査
- `docs/memo/3dcg_ai_video_research.md` — 3DCG→AI動画生成全般調査
- `poc/3dcg_poc9/kling_v3_manual.md` — Kling V3 Omni活用マニュアル
- `.claude/skills/floor_plan_to_video_sub_photoreal/SKILL.md` — V2Vスキル定義
