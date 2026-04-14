# PoC Step 5: 構成した3D空間データを任意のカメラ位置からレンダリングできる

> [ロードマップに戻る](./roadmap.md)

## 検証目標

アセット挿入済みの3D空間データを入力として、ユーザーが3D空間上でカメラを操作して指定した視点からレンダリングできる。

---

## このステップの役割

```
Step 4の出力（アセット挿入済み3D空間データ）
    ↓
ユーザーが3D空間上でカメラを操作して視点を決める
    ↓
指定視点からレンダリングする
    ↓
レンダリング画像を出力する（テクスチャなし）
```

テクスチャ・雰囲気はこのステップでは扱わない。後工程「3Dレンダリング結果 × ユーザーのイメージ画像」で適用する。

---

## 検証ステップ

### Step 1: 3D空間上でカメラを操作してレンダリングできるか

- [ ] 3D空間上でカメラをインタラクティブに操作できる
- [ ] 操作した視点からレンダリング画像を出力できる
- [ ] 複数の異なる視点でレンダリングできる
- [ ] レンダリング結果を目視で確認する
  - 操作した視点から正しく描画されているか
  - アセットの位置関係が3D空間と一致しているか

---

## 合格基準

| 評価項目           | 合格の目安                                               |
| ------------------ | -------------------------------------------------------- |
| レンダリングの成立 | 操作した視点からレンダリング画像が出力できる             |
| 視点の正確さ       | 操作した位置・向きと出力画像が一致している               |
| 複数視点の対応     | 異なるカメラ位置から繰り返しレンダリングできる           |
| 次ステップへの接続 | レンダリング画像を次ステップ（リアルな映像生成）に渡せる |

---

## 成果物

- 複数カメラ位置からのレンダリング画像
- 次のステップ（3Dレンダリング結果 × ユーザーのイメージ画像によるリアルな映像生成）への接続方針

---

## 技術調査

### カテゴリ分類

| カテゴリ | 技術 | 特徴 |
| --- | --- | --- |
| Python 3Dライブラリ | trimesh + pyrender, Open3D, PyVista/VTK, Panda3D, moderngl | Python完結、パイプライン統合が容易 |
| DCCツール | Blender (bpy) | 高品質レンダリング、Python API完備 |
| ブラウザ3Dエンジン | Three.js, Babylon.js, React Three Fiber | インタラクティブUI構築が容易 |
| ゲームエンジン | Unity, Godot | 高品質レンダリング、ヘッドレスに制約 |
| 物理ベースレンダラー | Mitsuba 3 | 科学的精度の高いレンダリング |
| ニューラルレンダリング | 3D Gaussian Splatting, NeRF | 写実的だがメッシュ入力と異なるパラダイム |

---

### 1. Blender Python API (bpy)

**概要:** オープンソースDCCツール Blender をPythonスクリプトやヘッドレスモード（`blender --background`）で操作し、カメラ位置を指定してレンダリングする。Cycles（パストレーシング）/ EEVEE（リアルタイム）の2つのレンダリングエンジンを備える。

**カメラ操作:**
- スクリプト: `bpy.context.scene.camera` でアクティブカメラを切り替え、`camera.location` / `camera.rotation_euler` で位置・向きを設定
- インタラクティブ: Blender GUIでのビューポート操作

**対応フォーマット:** GLB/glTF, OBJ, FBX, STL, PLY, DAE, ABC (Alembic) など多数

**レンダリング画像出力:**
```python
import bpy
# カメラ位置設定
cam = bpy.data.objects['Camera']
cam.location = (5, -3, 4)
cam.rotation_euler = (1.1, 0, 0.8)
# レンダリング設定
bpy.context.scene.render.filepath = '/tmp/output.png'
bpy.context.scene.render.resolution_x = 1920
bpy.context.scene.render.resolution_y = 1080
# レンダリング実行
bpy.ops.render.render(write_still=True)
```

**Python連携:** bpyモジュールとしてインポート可能。ただしBlender同梱Pythonで動作するため、通常のvenv/uvとは分離される。`blenderless` パッケージで簡略化も可能。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 最高（Cycles使用時） |
| ヘッドレス対応 | 良好（`--background` オプション） |
| GLB/glTF対応 | ネイティブ |
| FBX対応 | ネイティブ |
| Python連携 | 中（Blender Python環境に依存） |
| セットアップ容易さ | 中（Blender本体のインストールが必要） |

---

### 2. trimesh + pyrender

**概要:** trimesh は Python 向け3Dメッシュ処理ライブラリ。pyrender は glTF 2.0 準拠の OpenGL レンダラーで、trimesh と連携しオフスクリーンレンダリング（OSMesa / EGL バックエンド）をサポート。

**カメラ操作:**
- スクリプト: `pyrender.PerspectiveCamera` + 4x4ポーズ行列でカメラ位置・向きを指定
- インタラクティブ: `pyrender.Viewer` でGUIウィンドウ表示、マウス操作可能

**対応フォーマット:** STL, OBJ, PLY, OFF, DAE, GLB/glTF 2.0, 3MF など（FBXは非対応）

**レンダリング画像出力:**
```python
import trimesh, pyrender, numpy as np
mesh = pyrender.Mesh.from_trimesh(trimesh.load('model.glb'))
scene = pyrender.Scene()
scene.add(mesh)
camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
scene.add(camera, pose=camera_pose_matrix)
r = pyrender.OffscreenRenderer(1920, 1080)
color, depth = r.render(scene)  # NumPy配列として取得
```

**Python連携:** 最高。pip/uvでインストール可能。NumPy配列として直接出力。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 中（OpenGLベース） |
| ヘッドレス対応 | 優秀（OSMesa/EGL） |
| GLB/glTF対応 | 対応 |
| FBX対応 | 非対応 |
| Python連携 | 最高 |
| バッチ処理適性 | 最高 |

注意: pyrender のメンテナンスは活発でない（最終リリース 0.1.45）。フォーク `pyribbit` が代替として存在。

---

### 3. Open3D

**概要:** Intel主導のオープンソース3D処理ライブラリ。点群・メッシュの処理、可視化、オフスクリーンレンダリングを統合的にサポート。

**カメラ操作:**
- スクリプト: `OffscreenRenderer.setup_camera(fov, center, eye, up)` またはピンホールカメラ内部/外部パラメータ行列で指定
- インタラクティブ: `open3d.visualization.draw_geometries()` でGUIビューア
- 複数カメラの登録・切り替え対応（`add_camera()` / `set_active_camera()`）

**対応フォーマット:** OBJ, PLY, STL, OFF, glTF/GLB（Tensor版 `read_triangle_mesh` で対応）, FBX（Assimpバックエンド経由）

**レンダリング画像出力:**
```python
import open3d as o3d
renderer = o3d.visualization.rendering.OffscreenRenderer(1920, 1080)
renderer.scene.add_geometry("mesh", mesh, material)
renderer.setup_camera(60, center, eye, up)
img = renderer.render_to_image()    # カラー画像
depth = renderer.render_to_depth_image()  # 深度画像
o3d.io.write_image("output.png", img)
```

**Python連携:** 高い。pip でインストール可能。NumPy互換。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 中〜高（PBRマテリアル対応） |
| ヘッドレス対応 | 良好（EGLバックエンド） |
| GLB/glTF対応 | 対応（Tensor API） |
| FBX対応 | 対応（Assimp経由） |
| Python連携 | 高 |
| 点群処理との統合 | 優秀 |

---

### 4. PyVista / VTK

**概要:** VTK のPythonラッパー。科学技術可視化に強み。`off_screen=True` でヘッドレスレンダリング、`screenshot()` で画像出力。

**カメラ操作:**
- スクリプト: `plotter.camera_position = [(x,y,z), (fx,fy,fz), (ux,uy,uz)]`（視点、焦点、上方向）
- `plotter.camera.position`, `plotter.camera.focal_point` で個別設定も可能
- インタラクティブ: `plotter.show()` でGUIウィンドウ

**対応フォーマット:** STL, OBJ, PLY, VTK/VTU/VTP, STEP（CAD）など。glTF/GLBは `plotter.import_gltf()` で読み込み可能（`pv.read()` では非対応）

**レンダリング画像出力:**
```python
import pyvista as pv
plotter = pv.Plotter(off_screen=True, window_size=[1920, 1080])
mesh = pv.read("model.obj")
plotter.add_mesh(mesh)
plotter.camera_position = [(5, -3, 4), (0, 0, 0), (0, 0, 1)]
plotter.screenshot("output.png")
```

**Python連携:** 高い。pip でインストール可能。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 中（科学可視化向け） |
| ヘッドレス対応 | 良好（`off_screen=True`） |
| GLB/glTF対応 | 対応（`import_gltf`） |
| FBX対応 | 非対応 |
| Python連携 | 高 |
| 科学可視化 | 優秀 |

---

### 5. Three.js

**概要:** ブラウザベースの3Dライブラリ（JavaScript）。WebGL/WebGPU を使用した高品質レンダリング。豊富なローダーとカメラコントロール。

**カメラ操作:**
- インタラクティブ: `OrbitControls`, `TrackballControls`, `FlyControls` 等
- スクリプト: `camera.position.set(x, y, z)`, `camera.lookAt(target)`

**対応フォーマット:** GLB/glTF（GLTFLoader）, OBJ（OBJLoader）, FBX（FBXLoader）, STL, PLY 等

**レンダリング画像出力:**
```javascript
// preserveDrawingBuffer: true が必要
const renderer = new THREE.WebGLRenderer({ preserveDrawingBuffer: true });
// スクリーンショット取得
const dataUrl = renderer.domElement.toDataURL('image/png');
```

**Python連携:** 低い（JavaScript）。Puppeteer/Playwright経由でヘッドレスブラウザからの画像出力は可能。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 高（PBR対応） |
| ヘッドレス対応 | 要ヘッドレスブラウザ |
| GLB/glTF対応 | ネイティブ |
| FBX対応 | 対応（FBXLoader） |
| Python連携 | 低 |
| インタラクティブUI | 優秀 |

---

### 6. Babylon.js

**概要:** Microsoft支援のWebGL/WebGPU 3Dエンジン。PBRレンダリング、物理シミュレーション対応。Babylon.js 8.0（2025年）でglTF拡張サポート強化。

**カメラ操作:**
- インタラクティブ: `ArcRotateCamera`, `FreeCamera`, `FollowCamera` 等
- スクリプト: `camera.position`, `camera.setTarget(target)` で制御

**対応フォーマット:** GLB/glTF（ネイティブ推奨）, OBJ（プラグイン）, STL（プラグイン）。FBXは直接非対応。

**レンダリング画像出力:** `BABYLON.Tools.CreateScreenshot(engine, camera, size, callback)`。サーバーサイドは NullEngine が存在するが実際のレンダリングは不可。Puppeteer経由が現実的。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 高（WebGPU対応） |
| ヘッドレス対応 | 要Puppeteer（NullEngineはレンダリング不可） |
| GLB/glTF対応 | ネイティブ |
| FBX対応 | 非対応 |
| Python連携 | 低 |
| Sandboxビューア | 即座にプレビュー可能 |

---

### 7. Unity

**概要:** 業界標準ゲームエンジン。URP / HDRP レンダリングパイプライン。C#スクリプトでカメラ・シーンを完全制御。

**カメラ操作:** C#で `Transform.position`, `Transform.rotation` を直接設定。

**対応フォーマット:** FBX（ネイティブ最得意）, OBJ, DAE。GLB/glTFはプラグイン（UnityGLTF）。

**レンダリング画像出力:** `RenderTexture` → `ReadPixels` → `EncodeToPNG` → `File.WriteAllBytes`。ヘッドレスモード（`-batchmode -nographics`）ではGPUレンダリングが無効になるため画像出力不可。`-batchmode`のみ（GPU初期化あり）で実行する必要あり。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 最高（HDRP使用時） |
| ヘッドレス対応 | 制約あり（GPU必須、既知バグ） |
| GLB/glTF対応 | プラグイン |
| FBX対応 | ネイティブ（最得意） |
| Python連携 | 中（ML-Agents / サブプロセス） |
| セットアップ容易さ | 重い |

---

### 8. Godot Engine

**概要:** オープンソースゲームエンジン（MIT License）。GDScript / C# でスクリプティング。Vulkan / OpenGL ES 3.0 バックエンド。

**カメラ操作:** GDScript/C#で `Camera3D` ノードの `transform` を設定。

**対応フォーマット:** GLB/glTF（ネイティブ推奨）, OBJ, DAE。FBXはFBX2glTF経由の変換インポート。

**レンダリング画像出力:**
```gdscript
var image = get_viewport().get_texture().get_image()
image.flip_y()
image.save_png("output.png")
```

注意: `--headless` モードではレンダリングが無効。真のオフスクリーンレンダリングは提案段階。`get_image()` で空白画像になるバグ報告あり。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 高 |
| ヘッドレス対応 | 未成熟（GPU必須） |
| GLB/glTF対応 | ネイティブ |
| FBX対応 | 変換対応 |
| Python連携 | 低（GDScript中心） |
| ライセンス | MIT（完全OSS） |

---

### 9. Mitsuba 3

**概要:** 研究用物理ベースレンダラー。微分可能レンダリング対応。Python APIでシーン構築・レンダリングが可能。科学的に正確な光の振る舞いをシミュレート。

**カメラ操作:** XMLシーンファイルまたは Python dict でカメラ（`perspective` / `thinlens`）のパラメータ（`to_world` 変換行列、`fov` 等）を指定。

**対応フォーマット:** OBJ, PLY, Serialized（Mitsuba独自形式）。glTF/GLB/FBXは非対応。

**レンダリング画像出力:**
```python
import mitsuba as mi
mi.set_variant('scalar_rgb')
scene = mi.load_dict({
    'type': 'scene',
    'sensor': {'type': 'perspective', 'fov': 60,
               'to_world': mi.ScalarTransform4f.look_at(origin, target, up),
               'film': {'type': 'hdrfilm', 'width': 1920, 'height': 1080}},
    'shape': {'type': 'obj', 'filename': 'model.obj'}
})
img = mi.render(scene)
mi.util.write_bitmap("output.png", img)
```

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 最高（物理ベース） |
| ヘッドレス対応 | 良好 |
| GLB/glTF対応 | 非対応 |
| FBX対応 | 非対応 |
| Python連携 | 高（pip インストール可能） |
| 用途 | 科学・研究向け |

---

### 10. Panda3D

**概要:** Disney/CMU開発のPythonネイティブ3Dエンジン。ゲーム・シミュレーション用途。`windowType='offscreen'` でオフスクリーンレンダリング対応。

**カメラ操作:** `camera.setPos(x, y, z)`, `camera.setHpr(h, p, r)` でカメラ位置・向きを設定。タスクベースの更新も可能。

**対応フォーマット:** EGG/BAM（独自形式）, glTF/GLB（`panda3d-gltf` パッケージ）, OBJ（assimp有効時）

**レンダリング画像出力:**
```python
from direct.showbase.ShowBase import ShowBase
base = ShowBase(windowType='offscreen')
# モデル読み込み・カメラ設定後
base.graphicsEngine.renderFrame()
base.screenshot("output.png")
```

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 中〜高 |
| ヘッドレス対応 | 良好（`windowType='offscreen'`） |
| GLB/glTF対応 | プラグイン（panda3d-gltf） |
| FBX対応 | 非対応 |
| Python連携 | 高（ネイティブPython） |
| 学習コスト | 中（独自概念あり） |

---

### 11. moderngl / moderngl-window

**概要:** Python向けモダンOpenGLラッパー。低レベルだが軽量で高速。シェーダーを直接書いてレンダリングを制御。

**カメラ操作:** 自前で射影行列・ビュー行列を構築してシェーダーに渡す。`pyrr` や `numpy` で行列計算。

**対応フォーマット:** 直接的なモデルローダーはない。`moderngl-window` の `ObjLoader` でOBJ読み込み可能。glTFは `trimesh` 等と組み合わせ。

**レンダリング画像出力:** FBOにレンダリング → `fbo.read()` でバイト列取得 → PIL等で画像保存。

| 評価項目 | 評価 |
| --- | --- |
| レンダリング品質 | 中〜高（シェーダー次第） |
| ヘッドレス対応 | 良好（スタンドアロンコンテキスト） |
| モデル読み込み | 限定的（自前実装が必要） |
| Python連携 | 高 |
| 柔軟性 | 最高（低レベル制御） |
| 学習コスト | 高（OpenGL/シェーダー知識必須） |

---

### 12. 3D Gaussian Splatting

**概要:** 3Dシーンをガウシアン分布の集合として表現し、任意視点からリアルタイムにレンダリングするニューラルレンダリング技術。写実的な新規視点合成が可能。

**カメラ操作:** ビューアアプリ（SIBR viewer等）でインタラクティブ操作。カメラパラメータ（外部パラメータ行列）をスクリプトで指定可能。

**入力形式:** PLY形式のガウシアンデータ（通常のメッシュPLYとは異なる特殊形式）。メッシュ（OBJ/GLB）からの変換にはSfM的な処理が必要で、単純な変換ではない。

**本PoCへの適合度:** 低い。Step 4の出力がメッシュデータであるため、Gaussian Splatting形式への変換が追加で必要。テクスチャなしの幾何学的レンダリングという目的にはオーバースペック。

---

### 13. NeRF (Neural Radiance Fields)

**概要:** ニューラルネットワークで3Dシーンを暗黙的に表現し、任意視点からの画像を合成する技術。

**本PoCへの適合度:** 低い。入力が複数視点画像からの学習を前提としており、メッシュデータからの直接レンダリングとは異なるパラダイム。テクスチャなしの幾何学レンダリングには不適。

---

## 技術比較サマリー

| 技術 | Python連携 | レンダリング品質 | ヘッドレス | GLB/glTF | FBX | セットアップ | バッチ処理 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Blender (bpy)** | 中 | 最高 | 良好 | ネイティブ | ネイティブ | 中 | 良好 |
| **trimesh + pyrender** | 最高 | 中 | 優秀 | 対応 | 非対応 | 簡単 | 最高 |
| **Open3D** | 高 | 中〜高 | 良好 | 対応 | 対応(Assimp) | 簡単 | 高 |
| **PyVista/VTK** | 高 | 中 | 良好 | 対応(import_gltf) | 非対応 | 簡単 | 高 |
| **Three.js** | 低 | 高 | 要ブラウザ | ネイティブ | 対応 | 中 | 低 |
| **Babylon.js** | 低 | 高 | 要ブラウザ | ネイティブ | 非対応 | 中 | 低 |
| **Unity** | 中 | 最高 | 制約あり | プラグイン | ネイティブ | 重い | 中 |
| **Godot** | 低 | 高 | 未成熟 | ネイティブ | 変換 | 中 | 低 |
| **Mitsuba 3** | 高 | 最高 | 良好 | 非対応 | 非対応 | 中 | 高 |
| **Panda3D** | 高 | 中〜高 | 良好 | プラグイン | 非対応 | 中 | 高 |
| **moderngl** | 高 | 中〜高 | 良好 | 自前実装 | 非対応 | 中 | 高 |

## 推奨候補

### 第1候補: Blender Python API (bpy)

- レンダリング品質が最高クラス（Cycles / EEVEE）
- GLB/glTF, FBX, OBJ 全てネイティブ対応
- ヘッドレスモード（`--background`）で安定動作
- Python APIが充実しており、カメラ位置のスクリプト制御が容易
- 次ステップ（テクスチャ・雰囲気適用）での活用も見込める
- デメリット: Blender同梱Python環境への依存

### 第2候補: trimesh + pyrender（または Open3D）

- Python パイプラインとの統合が最も容易（pip/uv で完結）
- テクスチャなしの幾何学レンダリングには十分な品質
- ヘッドレスサーバーでのバッチ処理に最適
- デメリット: レンダリング品質はBlender/ゲームエンジンに劣る、FBX非対応

### 第3候補: Three.js（インタラクティブカメラ操作重視の場合）

- ブラウザ上でのインタラクティブなカメラ操作UIが最も直感的
- GLB/glTF, FBX 対応
- Puppeteer経由で画像出力も可能
- デメリット: Python連携が間接的、バッチ処理パイプラインへの組み込みが煩雑
