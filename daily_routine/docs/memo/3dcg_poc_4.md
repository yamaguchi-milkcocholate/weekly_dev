# PoC Step 4: 提案されたレイアウトで3D空間にアセットを挿入できる

> [ロードマップに戻る](./roadmap.md)

## 検証目標

Step 3で出力された配置座標を使いアセットを3D空間に挿入できる。また挿入後にユーザーが手動で座標を調整できる。

---

## このステップの役割

```
Step 3の出力（配置座標）
    ↓
座標通りにアセットを3D空間に配置する
    ↓
ユーザーが細部を手動調整する
    ↓
調整済み3D空間をレンダリング可能な状態で出力する
```

テクスチャ・雰囲気はこのステップでは扱わない。後工程「3Dレンダリング結果 × ユーザーのイメージ画像」で適用する。

---

## 検証ステップ

### Step 1: 提案座標でアセットを挿入できるか

- [ ] Step 3の配置座標をそのまま入力として与える
- [ ] 各アセットが指定座標・向きで3D空間に挿入できる
- [ ] 挿入結果を目視で確認する
  - アセットが空間内に収まっているか
  - アセット同士が重なっていないか
  - 床・壁・天井を貫通していないか

### Step 2: 挿入後にユーザーが手動で座標を調整できるか

- [ ] 任意のアセットの位置・向きを手動で変更できる
- [ ] 変更後の状態が3D空間に正しく反映される
- [ ] 調整後も空間的妥当性が維持されているか確認できる
  - 調整後にアセット同士の重なりや貫通が発生していないか

---

## 合格基準

| 評価項目           | 合格の目安                                         |
| ------------------ | -------------------------------------------------- |
| 挿入の成立         | 全アセットが3D空間に挿入できる                     |
| 空間的妥当性       | アセットが空間内に収まり、重なりや貫通がない       |
| 手動調整の成立     | 任意のアセットの位置・向きを変更できる             |
| 次ステップへの接続 | 調整済み3D空間をレンダリング可能な状態で出力できる |

---

## 成果物

- アセット挿入済みの3D空間データ（AI提案のまま）
- 手動調整後の3D空間データ
- 空間的妥当性の確認結果（問題があったケースの記録）
- 次のステップ（任意のカメラ位置からのレンダリング）への接続方針

---

## 技術調査

### 要件の整理

| 要件 | 説明 |
| --- | --- |
| Pythonスクリプトからの座標配置 | Step 3の出力（JSON座標）を入力として、アセットを自動配置 |
| GUI手動調整 | ユーザーがマウス操作で位置・回転を微調整 |
| レンダリング可能な出力 | 調整済みシーンをファイルとして保存し、次ステップで読み込める |
| glTF/OBJ対応 | 一般的な3Dアセットフォーマットを読み込める |

---

### A. 3Dソフトウェア + Pythonスクリプティング

#### A-1. Blender + bpy（Python API）

- **概要**: オープンソースの3D統合環境。Python API（bpy）で全機能をスクリプト制御可能
- **Python操作性**: ◎ — `bpy.ops.import_scene.gltf()` でインポート、`obj.location = (x, y, z)` で座標配置。ヘッドレス実行（`blender --background --python script.py`）対応
- **GUI手動調整**: ◎ — Blender GUI上でドラッグ移動・回転・スケール。ギズモ操作、プロパティパネルで数値入力も可能
- **レンダリング出力**: ◎ — Cycles（パストレーシング）/ EEVEE（リアルタイム）。glTF / USD / FBX / .blend エクスポート
- **自動化適性**: ◎ — ヘッドレス実行、Docker化実績あり。[blenderless](https://github.com/oqton/blenderless) 等のヘッドレスラッパーも存在
- **pip install bpy**: `pip install bpy` で5.0.1（Python 3.12対応）が利用可能。ただしPythonバージョンとの厳密な互換性制約あり。**本番パイプラインでは `blender --background` の方が安定的**（NumPy互換性・GPU機能等の制約あり）
- **Docker化**: [nytimes/rd-blender-docker](https://github.com/nytimes/rd-blender-docker)、[blenderkit/headless-blender](https://hub.docker.com/r/blenderkit/headless-blender) 等の実績あり
- **バージョン**: Blender 4.2 LTS（2026年7月までサポート）、Blender 5.0（2025年11月〜、破壊的変更あり）。PoCでは **4.2 LTS 推奨**
- **ライセンス**: GPL-2.0+
- **適合度**: ★★★★★ — 本PoCの全要件を単体で満たす最有力候補

**コード例（ヘッドレス自動配置）:**
```python
# place_assets.py — blender --background --python place_assets.py -- config.json
import bpy, json, sys, math
from pathlib import Path

argv = sys.argv[sys.argv.index("--") + 1:]
config = json.loads(Path(argv[0]).read_text())

bpy.ops.wm.read_factory_settings(use_empty=True)

for item in config["assets"]:
    bpy.ops.import_scene.gltf(filepath=item["path"])
    obj = bpy.context.selected_objects[0]
    obj.location = tuple(item["location"])
    obj.rotation_euler = (0, 0, math.radians(item.get("rotation_z", 0)))

bpy.ops.wm.save_as_mainfile(filepath=config["output_blend"])
```

**想定ワークフロー:**
```
Step 3 JSON → blender --background でヘッドレス自動配置 → .blend保存
→ ユーザーが Blender GUI で手動調整 → 調整済み .blend 保存
→ 次ステップでレンダリング（glTF / USD エクスポートも可能）
```

#### A-2. Maya + mayapy

- **概要**: Autodesk製プロフェッショナル3Dソフト。mayapyでPythonスクリプティング可能
- **Python操作性**: ○ — `cmds.file()` でインポート、`cmds.setAttr()` で座標設定
- **GUI手動調整**: ◎ — 業界標準のGUI操作
- **レンダリング出力**: ◎ — Arnold / Maya Software
- **自動化適性**: ○ — mayapyでヘッドレス実行可能だが、ライセンス管理が課題
- **ライセンス**: 商用（サブスクリプション、高額）
- **適合度**: ★★☆☆☆ — 高機能だがコストとセットアップ負荷が大きい

---

### B. Python 3Dライブラリ

#### B-1. trimesh

- **概要**: Pythonメッシュ操作ライブラリ（v4.11.3）。ロード・変換・解析・簡易ビューワー。唯一のハード依存はnumpy
- **Python操作性**: ◎ — `trimesh.load()` → `Scene.graph.update(node, matrix=T)` で座標配置。`scene.export("output.glb")` で**配置情報を保持したままglTFエクスポート可能**
- **GUI手動調整**: × — ビューワー（pyglet/pyrender）は表示のみでインタラクティブ編集不可。Jupyter/Marimo向けWebGLビューワーも閲覧専用
- **レンダリング出力**: △ — pyrender経由で簡易レンダリング。glTF/GLB/OBJ/COLLADAエクスポート対応（Draco圧縮、WebPテクスチャも対応）
- **自動化適性**: ◎ — 純Python、軽量、ヘッドレス実行容易
- **ライセンス**: MIT
- **適合度**: ★★★☆☆ — 自動配置・glTFエクスポートには最適だがGUI調整機能がない

#### B-2. Open3D

- **概要**: Intel発の3Dデータ処理ライブラリ。点群・メッシュ・再構成
- **Python操作性**: ◎ — `o3d.io.read_triangle_mesh()` → `mesh.translate()` / `mesh.rotate()`
- **GUI手動調整**: △ — `o3d.visualization.VisualizerWithEditing` でポイント選択は可能だが、オブジェクト移動GUIは限定的
- **レンダリング出力**: ○ — オフスクリーンレンダリング対応。PLY/OBJ出力
- **自動化適性**: ◎ — ヘッドレス対応
- **ライセンス**: MIT
- **適合度**: ★★☆☆☆ — 点群処理には強いがシーン構築向けではない

#### B-3. PyVista / pyvistaqt

- **概要**: VTKのPythonラッパー（v0.47.x）。3D可視化のMatplotlib的存在。2000+プロジェクトで使用
- **Python操作性**: ◎ — `pv.read()` → `plotter.add_mesh()` でシーン構築。`plotter.import_gltf()` でglTFインポート可能
- **GUI手動調整**: ○ — `enable_mesh_picking(callback)` でメッシュピック対応。pyvistaqt（Qt統合）でインタラクティブウィジェット利用可能。ただしドラッグ移動は自前コールバック実装が必要
- **レンダリング出力**: ○ — VTKベースPBR対応。**`plotter.export_gltf("scene.gltf")` でシーン全体のglTFエクスポート可能**
- **自動化適性**: ◎ — ヘッドレスレンダリング対応（`pyvista.start_xvfb()` でLinuxサーバー対応）
- **ライセンス**: MIT
- **適合度**: ★★★☆☆ — ピック + glTFエクスポートの組み合わせでPython 3Dライブラリ中最もバランスが良い

#### B-4. vedo

- **概要**: VTKベースの3D可視化・操作ライブラリ（v2025.5.x）。PyVistaよりインタラクティブ寄り
- **Python操作性**: ◎ — `vedo.load()` → `mesh.pos(x, y, z)` で直感的に配置
- **GUI手動調整**: ○ — `add_callback("MouseMove", func)` でマウスイベント取得、`evt.picked3d` で3D座標、`evt.object` でピック対象を取得可能。**ドラッグ移動の自前実装が比較的容易**
- **レンダリング出力**: ○ — スクリーンショット / VTK/OBJ形式。HTML（x3d/k3d）でWebページ埋め込み可能
- **注意点**: **glTF/GLB直接サポートなし**（trimesh経由で変換が必要）
- **ライセンス**: MIT
- **適合度**: ★★☆☆☆ — インタラクティブAPIは直感的だがglTF非対応が大きな欠点

#### B-5. pygltflib

- **概要**: PythonでglTF 2.0フォーマットを直接読み書きするライブラリ（v1.16.5）。glTF仕様のフルサポート
- **Python操作性**: ◎ — ノードの `translation`, `rotation`, `scale` を直接編集して配置変更可能
- **GUI手動調整**: × — ファイルフォーマット操作ライブラリ。可視化機能なし
- **レンダリング出力**: × — レンダラーなし。glTF出力のみ
- **自動化適性**: ◎ — 純Python、軽量
- **ライセンス**: MIT
- **適合度**: ★★☆☆☆ — glTFの精密な座標編集に有用。他ツールと組み合わせて使う

#### B-6. Panda3D

- **概要**: Disney/CMU開発のオープンソース3Dエンジン（SDK 1.10.16）。Pythonがメイン言語
- **Python操作性**: ◎ — `pip install panda3d`。シーングラフAPIでノード配置が直感的。`panda3d-gltf` プラグインでglTF対応
- **GUI手動調整**: △ — Panda3D Studio（コミュニティ製）でシーン編集可能だが、Blender程の洗練さはない
- **レンダリング出力**: ○ — PBR、ノーマルマッピング、HDR対応。フォトリアル品質は限定的
- **自動化適性**: ○ — オフスクリーンレンダリング対応
- **ライセンス**: BSD
- **適合度**: ★★☆☆☆ — Pythonネイティブで導入しやすいが、映像制作パイプラインへの適合性はBlenderに劣る

---

### C. Webベース3Dエディタ

#### C-1. Three.js Editor

- **概要**: Three.js公式のWebブラウザ3Dエディタ。[editor](https://threejs.org/editor/) でそのまま利用可能
- **Python操作性**: △ — JavaScript API。PythonからはJSON形式でシーンを生成→エディタで読み込む運用
- **GUI手動調整**: ◎ — ブラウザ上でドラッグ移動・回転・スケール。プロパティパネルで数値入力
- **レンダリング出力**: ○ — Three.js JSONシーン / glTFエクスポート。レンダリング品質はWebGL依存
- **自動化適性**: △ — Node.js経由で自動化可能だがPythonパイプラインとの連携にブリッジが必要
- **ライセンス**: MIT
- **適合度**: ★★★☆☆ — GUI調整に特化。Pythonとの連携はJSON受け渡しで実現可能

**想定ワークフロー:**
```
Step 3 JSON → Python で Three.js JSON形式に変換 → Three.js Editorで手動調整
→ エクスポート（glTF） → 次ステップ
```

#### C-2. Babylon.js + Inspector

- **概要**: Microsoft製のWebGL/WebGPUエンジン。Inspector（デバッグUI）でシーン操作可能
- **Python操作性**: △ — JavaScript API。Pythonとの連携は同上
- **GUI手動調整**: ◎ — Inspectorでリアルタイムにシーングラフ操作・プロパティ編集
- **レンダリング出力**: ○ — PBRレンダリング。glTF対応
- **自動化適性**: △ — Three.jsと同様
- **ライセンス**: Apache-2.0
- **適合度**: ★★☆☆☆ — Three.jsの方がエコシステムが成熟

#### C-3. カスタムWebエディタ（React Three Fiber）

- **概要**: React + Three.jsの宣言的3Dレンダラー。カスタムエディタUI構築に最適
- **Python操作性**: △ — FastAPI等でバックエンドAPIを構築し、フロントエンドのR3Fエディタと連携
- **GUI手動調整**: ◎ — drei（ヘルパーライブラリ）の `TransformControls` でドラッグ移動・回転
- **レンダリング出力**: ○ — glTFエクスポート（three.js GLTFExporter）
- **自動化適性**: ○ — APIベースで自動化可能だが開発コスト大
- **ライセンス**: MIT
- **適合度**: ★★★☆☆ — 長期的にカスタムUIが必要な場合に有力だが、PoCには過剰

---

### D. ゲームエンジン

#### D-1. Godot Engine

- **概要**: オープンソースゲームエンジン。GDScriptまたはC#でシーン構築
- **Python操作性**: △ — GDScript（Python風だが別言語）。Python bindingsは実験的。ヘッドレスモード（`--headless`）対応
- **GUI手動調整**: ○ — Godot Editorでノード操作可能だが、3Dシーンエディタとしてはツール不足
- **レンダリング出力**: ○ — Vulkan / OpenGL。glTFインポート対応
- **自動化適性**: △ — ヘッドレス実行可能だがPythonパイプライン統合は追加開発が必要
- **ライセンス**: MIT
- **適合度**: ★★☆☆☆ — ゲーム開発向け。シーン配置PoCには過剰

#### D-2. Unity（参考）

- **概要**: C#ベースのゲームエンジン。Python連携は限定的（Python for Unity は非推奨）
- **適合度**: ★☆☆☆☆ — Pythonパイプラインとの相性が悪い

---

### E. シーン記述フォーマット / 専用ライブラリ

#### E-1. OpenUSD（Universal Scene Description）

- **概要**: Pixar開発のシーン記述フレームワーク（v26.03）。AOUSD（Apple, NVIDIA, Pixar, Adobe等）が共同推進する業界標準
- **Python操作性**: ◎ — `pip install usd-core`（Python 3.8〜3.13対応）。`Usd`, `UsdGeom`, `Gf` 等の豊富なモジュール。NVIDIAの [usd_scene_construction_utils](https://github.com/NVIDIA-Omniverse/usd_scene_construction_utils) でシーン構築を簡略化可能
- **GUI手動調整**: ○ — `usdview`（Pythonインタプリタ内蔵、プラグイン拡張可能）で表示・基本操作。NVIDIA Omniverse でフル編集。**Blender 4.x のUSDインポート/エクスポートでBlender GUIも活用可能**
- **レンダリング出力**: ◎ — Hydraレンダリングフレームワーク経由で各種レンダラー接続（Storm, RenderMan, RTX等）。`.usd` / `.usda` / `.usdc` 出力。Blender USDHook APIでエクスポートカスタマイズも可能
- **自動化適性**: ◎ — シーン記述はファイル操作のためGUI不要。Reference/Payloadで外部アセット参照、レイヤリングで非破壊編集
- **ライセンス**: Modified Apache-2.0 (TOST License)
- **適合度**: ★★★★☆ — Blenderとの連携で威力を発揮。学習コストはやや高い

**コード例:**
```python
from pxr import Usd, UsdGeom

stage = Usd.Stage.CreateNew("scene.usda")
xform = UsdGeom.Xform.Define(stage, "/World")
# 外部アセットを参照して配置
chair = UsdGeom.Xform.Define(stage, "/World/Chair")
chair.GetPrim().GetReferences().AddReference("./assets/chair.usd")
chair.AddTranslateOp().Set((1.5, 0.0, 0.0))
stage.GetRootLayer().Save()
```

**想定ワークフロー:**
```
Step 3 JSON → Python（pxr）でUSDステージ構築 → .usda保存
→ usdview / Blender / Omniverse でGUI調整 → 調整済みUSD保存
→ 次ステップでレンダリング
```

#### E-2. scene_synthesizer（NVIDIA）

- **概要**: ロボット操作シーンのプロシージャル生成ライブラリ。部屋にオブジェクトを配置するAPIが充実
- **Python操作性**: ◎ — `pip install scene-synthesizer`。trimeshベースでシーン構築
- **GUI手動調整**: × — プログラマティック生成専用。GUI調整機能なし
- **レンダリング出力**: ○ — trimesh/pyrender経由。USD出力対応
- **自動化適性**: ◎ — 座標配置の自動化に特化
- **ライセンス**: Apache-2.0
- **適合度**: ★★★☆☆ — 自動配置ロジックの参考になるが、GUI調整は別途必要

#### E-3. glTF-Transform

- **概要**: Node.jsベースのglTF操作ライブラリ。シーンのプログラム構築・最適化（Draco圧縮、テクスチャ圧縮等）
- **Python操作性**: × — JavaScript/TypeScript専用。`subprocess.run(["npx", "@gltf-transform/cli", ...])` で連携
- **GUI手動調整**: × — CLI/API専用
- **レンダリング出力**: ○ — glTF出力に特化
- **自動化適性**: ○ — CLI実行可能
- **ライセンス**: MIT
- **適合度**: ★★☆☆☆ — glTF最適化用途。シーン構築の主軸にはならない

#### E-4. Habitat-sim / AI2-THOR（参考: AI向け3D環境）

これらはEmbodied AI研究向けの3Dシミュレータであり、動画制作パイプラインとは方向性が異なるが、手続き的シーン生成の知見は参考になる。

- **Habitat-sim**（Meta Research）: MIT、高性能3Dシミュレータ。Python APIでリジッドオブジェクト配置・物理シミュレーション。単一GPU上で数千FPS
- **AI2-THOR**（Allen Institute）: Apache-2.0、Unityベースの対話型3D環境。ProcTHORによる手続き的室内シーン生成。`pip install ai2thor`
- **適合度**: ★☆☆☆☆ — 本PoCの直接的な候補ではないが、シーン配置アルゴリズムの参考資料として有用

---

### 技術比較サマリー

| 技術 | Python操作 | GUI調整 | レンダリング | 自動化 | glTF対応 | 導入コスト | 総合適合度 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Blender + bpy** | ◎ | ◎ | ◎ | ◎ | ◎ | 中 | ★★★★★ |
| **OpenUSD (pxr)** | ◎ | ○ | ◎ | ◎ | △ | 中〜高 | ★★★★☆ |
| **trimesh** | ◎ | × | △ | ◎ | ◎ | 低 | ★★★☆☆ |
| **PyVista** | ◎ | ○ | ○ | ◎ | ◎ | 低 | ★★★☆☆ |
| **Three.js Editor** | △ | ◎ | ○ | △ | ◎ | 中 | ★★★☆☆ |
| **scene_synthesizer** | ◎ | × | ○ | ◎ | ○ | 低 | ★★★☆☆ |
| **R3F カスタム** | △ | ◎ | ○ | ○ | ◎ | 高 | ★★★☆☆ |
| **pygltflib** | ◎ | × | × | ◎ | ◎ | 低 | ★★☆☆☆ |
| **vedo** | ◎ | ○ | ○ | ◎ | × | 低 | ★★☆☆☆ |
| **Open3D** | ◎ | △ | ○ | ◎ | ○ | 低 | ★★☆☆☆ |
| **Panda3D** | ◎ | △ | ○ | ○ | ○ | 低 | ★★☆☆☆ |
| **Godot** | △ | ○ | ○ | △ | ◎ | 中 | ★★☆☆☆ |
| **Babylon.js** | △ | ◎ | ○ | △ | ◎ | 中 | ★★☆☆☆ |
| **Maya** | ○ | ◎ | ◎ | ○ | ○ | 高 | ★★☆☆☆ |

---

### 推奨アプローチ

#### 第1候補: Blender + bpy（単体完結）

全要件を単体で満たす。学習コストは中程度だが、エコシステムが成熟しており情報が豊富。パイプライン実績も多い。

```
Python（bpy）で自動配置 → Blender GUIで手動調整 → .blend / glTF / USD保存
```

#### 第2候補: trimesh（自動配置）+ Blender（GUI調整）

自動配置をtrimeshの軽量APIで行い、GUI調整のみBlenderを使う分離構成。

```
Python（trimesh）で自動配置 → glTFエクスポート → Blenderで手動調整 → 保存
```

#### 第3候補: OpenUSD + Blender

大規模シーン・アセット再利用を見据えた構成。USD形式で中間データを管理。

```
Python（pxr）でUSDステージ構築 → Blenderでインポート・手動調整 → USD保存
```

---

### 参考資料

- [Blender Python API](https://docs.blender.org/api/current/index.html)
- [Blender Scripting for Animation Pipelines: 2026](https://blog.cg-wire.com/blender-scripting-animation/)
- [bpy on PyPI](https://pypi.org/project/bpy) / [blenderless](https://github.com/oqton/blenderless)
- [nytimes/rd-blender-docker](https://github.com/nytimes/rd-blender-docker)
- [OpenUSD GitHub](https://github.com/PixarAnimationStudios/OpenUSD) / [usd-core on PyPI](https://pypi.org/project/usd-core/)
- [NVIDIA: Using Python to Automate 3D Workflows with OpenUSD](https://developer.nvidia.com/blog/using-python-to-automate-3d-workflows-with-openusd/)
- [usd_scene_construction_utils](https://github.com/NVIDIA-Omniverse/usd_scene_construction_utils)
- [trimesh documentation](https://trimesh.org/)
- [PyVista documentation](https://docs.pyvista.org/) / [PyVista glTF support](https://docs.pyvista.org/examples/00-load/load_gltf.html)
- [pygltflib on PyPI](https://pypi.org/project/pygltflib/)
- [vedo GitHub](https://github.com/marcomusy/vedo)
- [scene_synthesizer (NVlabs)](https://github.com/NVlabs/scene_synthesizer)
- [Three.js Editor](https://threejs.org/editor/)
- [Panda3D](https://www.panda3d.org/)
- [Habitat-sim GitHub](https://github.com/facebookresearch/habitat-sim)
- [AI2-THOR](https://ai2thor.allenai.org/) / [ProcTHOR](https://procthor.allenai.org/)
