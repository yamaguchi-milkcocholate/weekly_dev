# 音声素材の手動配置手順

**対応する設計書:** `docs/designs/audio_engine_design.md`

## 1. 概要

Audio Engine は「調達リスト出力 + 人手配置 + ローカルスキャン」方式で動作する。パイプラインの Audio ステップを実行すると、必要な BGM の条件と SE の名称が `procurement.json` に出力される。ユーザーはこのファイルを参照して音声素材をダウンロードし、所定のディレクトリに配置する。

**全体の流れ:**

1. パイプラインが Audio ステップを実行し、`procurement.json` を出力する
2. ユーザーが `procurement.json` を参照して BGM・SE をダウンロードする
3. ユーザーがファイルを所定のディレクトリに配置する
4. パイプラインを再実行（retry）すると、配置済みファイルをスキャンして `AudioAsset` を生成する

> **Note:** BGM が未配置の場合、Suno API キーが設定されていれば AI 生成でフォールバックする。SE が未配置の場合は当該 SE がスキップされる（エラーにはならない）。

## 2. 事前準備

### 2.1 パイプラインの実行

Audio ステップまでパイプラインを進める。Intelligence → Scenario → Asset → Visual のステップを順に完了させた後、Audio ステップが実行される。

```bash
# パイプラインの状態を確認
uv run daily-routine status {project_id}

# 次のステップ（Audio）を実行
uv run daily-routine resume {project_id}
```

Audio ステップの初回実行時、BGM が未配置の場合は ERROR 状態で停止する。この時点で `procurement.json` と SE 推定結果が出力されている。

### 2.2 調達リストの確認

プロジェクトディレクトリ内の `audio/procurement.json` を確認する。

```bash
cat outputs/projects/{project_id}/audio/procurement.json
```

調達リストには以下が含まれる。

```json
{
  "bgm": {
    "genres": ["lo-fi", "chill hop"],
    "bpm_range": [110, 130],
    "min_duration_sec": 45.0,
    "direction": "朝の準備シーンに合う爽やかで軽快な曲、lo-fi系で統一",
    "placement_dir": "audio/bgm/candidates/"
  },
  "sound_effects": [
    {
      "se_name": "alarm clock",
      "scene_number": 1,
      "trigger_description": "目覚まし時計のアラームが鳴る",
      "expected_filename": "scene_01_alarm_clock.*"
    },
    {
      "se_name": "door open close",
      "scene_number": 2,
      "trigger_description": "玄関のドアを開けて出発する",
      "expected_filename": "scene_02_door_open_close.*"
    }
  ]
}
```

## 3. ダウンロード方法

### 3.1 BGM のダウンロード

`procurement.json` の `bgm` セクションに記載されたジャンル・BPM・方向性を参考に、以下のサイトから BGM をダウンロードする。

| サイト             | URL                           | ライセンス                              | 備考                           |
| ------------------ | ----------------------------- | --------------------------------------- | ------------------------------ |
| Pixabay Music      | https://pixabay.com/music/    | Pixabay License（商用利用可・帰属不要） | ジャンル・ムードで絞り込み可能 |
| Free Music Archive | https://freemusicarchive.org/ | CC ライセンス（曲ごとに異なる）         | ジャンル検索が充実             |

**検索のコツ:**

- `genres` の値をそのまま検索キーワードとして使用する（例: `lo-fi chill hop`）
- `direction` の内容を英訳して補足キーワードにする（例: `fresh morning routine`）
- `min_duration_sec` 以上の楽曲長のものを選ぶ
- インストゥルメンタル（ボーカルなし）を選ぶと動画のテロップと干渉しない

### 3.2 SE のダウンロード

`procurement.json` の `sound_effects` セクションに記載された `se_name` をそのまま検索キーワードとして使用する。

| サイト                | URL                                   | ライセンス                              | 備考                           |
| --------------------- | ------------------------------------- | --------------------------------------- | ------------------------------ |
| Pixabay Sound Effects | https://pixabay.com/sound-effects/    | Pixabay License（商用利用可・帰属不要） | カテゴリ検索可能               |
| Freesound             | https://freesound.org/                | CC ライセンス（素材ごとに異なる）       | 素材数が豊富。要アカウント登録 |
| Mixkit                | https://mixkit.co/free-sound-effects/ | Mixkit License（商用利用可）            | ダウンロード無料・登録不要     |

**検索のコツ:**

- `se_name` の値をそのまま検索ボックスに入力する（例: `alarm clock`, `door open close`）
- `trigger_description` を参照して、シーンに合ったバリエーションを選ぶ
- SE は短い素材（1〜5秒程度）が適切

## 4. 配置先

### 4.1 ディレクトリ構成

```
outputs/projects/{project_id}/audio/
├── procurement.json               # ← 調達リスト（自動生成済み）
├── bgm/
│   └── candidates/                # ← BGM をここに配置
│       ├── lofi_morning.mp3
│       └── chill_track.mp3
└── se/                            # ← SE をここに配置
    ├── scene_01_alarm_clock.mp3
    └── scene_02_door_open_close.mp3
```

### 4.2 BGM の配置ルール

| 項目             | 内容                                                                            |
| ---------------- | ------------------------------------------------------------------------------- |
| 配置先           | `audio/bgm/candidates/`                                                         |
| ファイル名       | 任意（自由に命名可能）                                                          |
| 対応フォーマット | `.mp3`, `.wav`, `.ogg`, `.m4a`, `.flac`                                         |
| 配置数           | 1件以上（複数配置した場合、duration とスコアリングで最適な1曲が自動選定される） |
| 必須条件         | 楽曲長が `min_duration_sec` 以上であること                                      |

```bash
# 例: ダウンロードした BGM を配置
cp ~/Downloads/lofi_morning.mp3 outputs/projects/{project_id}/audio/bgm/candidates/
```

### 4.3 SE の配置ルール

| 項目             | 内容                                                                     |
| ---------------- | ------------------------------------------------------------------------ |
| 配置先           | `audio/se/`                                                              |
| ファイル名       | `procurement.json` の `expected_filename` に従う（**必須**）             |
| 対応フォーマット | `.mp3`, `.wav`, `.ogg`, `.m4a`, `.flac`                                  |
| 命名規則         | `scene_{シーン番号:02d}_{SE名のスペースをアンダースコアに置換}.{拡張子}` |
| 必須条件         | ファイル名が一致しないとスキャン時に検出されない                         |

**ファイル名の例:**

| `expected_filename`          | 配置するファイル名             |
| ---------------------------- | ------------------------------ |
| `scene_01_alarm_clock.*`     | `scene_01_alarm_clock.mp3`     |
| `scene_02_door_open_close.*` | `scene_02_door_open_close.wav` |
| `scene_03_keyboard_typing.*` | `scene_03_keyboard_typing.mp3` |

```bash
# 例: ダウンロードした SE をリネームして配置
cp ~/Downloads/alarm-sound.mp3 outputs/projects/{project_id}/audio/se/scene_01_alarm_clock.mp3
cp ~/Downloads/door.wav outputs/projects/{project_id}/audio/se/scene_02_door_open_close.wav
```

> **Note:** SE は全て配置する必要はない。未配置の SE はスキップされ、配置済みの SE のみが `AudioAsset` に含まれる。

## 5. 配置後の再実行

ファイルを配置したら、パイプラインを再実行する。

```bash
# ERROR 状態のステップを再試行
uv run daily-routine retry {project_id}
```

正常に完了すると、以下が生成される。

- `audio/bgm/selected.mp3` — 選定された BGM のコピー
- `audio/audio_asset.json` — BGM + SE の最終アセット情報

ステップが AWAITING_REVIEW 状態になったら、生成された `audio_asset.json` の内容を確認する。

```bash
cat outputs/projects/{project_id}/audio/audio_asset.json
```

問題なければ次のステップへ進む。

```bash
uv run daily-routine resume {project_id}
```
