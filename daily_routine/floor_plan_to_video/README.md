# Floor Plan to Video パイプライン

間取り画像から一気通貫でフォトリアルなインテリア動画を生成するパイプライン。

## パイプライン全体像

```
間取りPNG → SVG → Blender 3Dシーン → 家具配置 → カメラカット動画 → V2V フォトリアル動画
```

## ステップ詳細

| # | ステップ | PoC | 入力 → 出力 | 手法 |
|---|---------|-----|-------------|------|
| 1 | 間取りPNG → クリーンSVG → 建築要素rect | poc0_a | カラーPNG → ベクターSVG → 壁・柱rect SVG | potrace + ピクセル分析 |
| 2 | SVG → Blender 3Dシーン | poc0_b | 要素SVG → scene.blend（壁・柱3D化+PBRマテリアル） | Blender Python |
| 3 | 家具画像 → GLBモデル | poc2 | 家具写真PNG → GLBファイル | Tripo AI API |
| 4 | レイアウト設計（反復） | poc3 | 間取り情報+アセット → placement_plan.json | 配置エンジン検証 + Geminiデザイン評価 |
| 5 | 家具配置 → Blenderシーン | poc4 | layout_proposal.json + GLB → 家具配置済みscene.blend | Blender Python |
| 6 | カメラカット動画レンダリング | poc0_c | scene.blend → カメラパス動画（Cycles） | Blender Cycles + ffmpeg |
| 7 | V2V フォトリアル動画化 | poc9 | レンダリング動画 → フォトリアルMP4 | Kling V2V |

## 各ステップの詳細

### 1. 間取りPNG → クリーンSVG → 建築要素rect（poc0_a）

カラー間取りPNG画像をpotraceでベクタートレースしてクリーンSVGを生成し、ピクセルデータ分析（Zhang-Suen骨格化）で壁・柱を個別の`<rect>`要素としてSVG化する。

### 2. SVG → Blender 3Dシーン（poc0_b）

建築要素rectのSVGをBlender Pythonで読み込み、壁（2.4m高）・柱・ドア・窓の3Dメッシュを生成。PBRマテリアル（Principled BSDF）を適用し、エリアライトを配置してscene.blendを出力する。

### 3. 家具画像 → GLBモデル（poc2）

家具の写真画像をTripo AI REST APIにアップロードし、GLB形式の3Dモデルを生成する。タスクポーリングでモデル生成完了を待ち、GLBをダウンロードする。

### 4. レイアウト設計（poc3）

間取り情報（room_info.json）とアセット定義（assets.json）をもとに、配置エンジンで空間的な妥当性（衝突検出・動線検証）を検証し、Gemini AIでデザイン品質を評価する。複数候補を並列生成し、反復的に改善する。

### 5. 家具配置 → Blenderシーン（poc4）

layout_proposal.jsonの2D座標・回転情報に基づき、GLBモデルをBlender Pythonでscene.blendに自動配置する。アセットタイプごとのスケーリング・Z軸オフセット・前面方向マッピングを処理する。

### 6. カメラカット動画レンダリング（poc0_c）

家具配置済みscene.blendに対して、3フェーズで動画を生成する。
1. 空間分析 + カット設計（俯瞰レンダリング → draw.ioでカメラパス設計）
2. Cyclesフレームレンダリング（GPU Metal, 各カット5秒/30fps = 150フレーム）
3. ffmpegでPNG連番 → MP4動画化

### 7. V2V フォトリアル動画化（poc9）

Blenderでレンダリングしたカメラカット動画をKling V2Vに入力し、フォトリアルなインテリアウォークスルー動画に変換する。

## 補足: 関連PoC

| PoC | 内容 | 備考 |
|-----|------|------|
| poc1 | 手動Blenderモデリング | 自動化前の試行 |
| poc_inkspace, poc_blender | 初期探索 | poc0_a, poc0_bに発展 |
| poc5 | 静止画カメラレンダリング（EEVEE） | 動画フローでは不要 |
| poc6 | Geminiスタイル適用（Re-skinning） | V2Vが吸収 |
| poc8 | Gemini生活感小物追加（マルチアングル一貫性） | V2Vが吸収 |
| poc7 | World Labs 3D再構成 | 代替アプローチ検証 |
