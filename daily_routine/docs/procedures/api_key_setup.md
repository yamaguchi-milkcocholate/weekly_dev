# APIキー取得・設定手順

## 1. 概要

本プロジェクトで使用する外部APIキーの取得方法と設定方法をまとめる。

| 環境変数                                 | サービス           | 用途                                                                     |
| ---------------------------------------- | ------------------ | ------------------------------------------------------------------------ |
| `DAILY_ROUTINE_API_KEY_YOUTUBE_DATA_API` | YouTube Data API   | Intelligence Engine — YouTube 検索・メタデータ取得                       |
| `DAILY_ROUTINE_API_KEY_STABILITY`        | Stability AI       | 画像生成                                                                 |
| `DAILY_ROUTINE_API_KEY_OPENAI`           | OpenAI             | 画像生成（DALL-E 3）/ 評価（GPT-4o Vision）/ Intelligence（Whisper字幕） |
| `DAILY_ROUTINE_API_KEY_GOOGLE_AI`        | Google AI (Gemini) | 画像生成・評価 / Intelligence（トレンド分析LLM）                         |
| `DAILY_ROUTINE_API_KEY_KLING_AK`         | Kling AI           | 動画生成（T0-2 PoC）— Access Key                                         |
| `DAILY_ROUTINE_API_KEY_KLING_SK`         | Kling AI           | 動画生成（T0-2 PoC）— Secret Key                                         |
| `DAILY_ROUTINE_API_KEY_LUMA`             | Luma Dream Machine | 動画生成（T0-2 PoC）                                                     |
| `DAILY_ROUTINE_API_KEY_RUNWAY`           | Runway             | 動画生成（T0-2 PoC）                                                     |

> **Google Veo** は GCP サービスアカウント認証を使用する（`gcloud auth login` で認証）。

## 2. APIキーの作成

### 2.1 Stability AI

1. https://platform.stability.ai/ にアクセスする
2. 「Login」からGoogle アカウントまたはメールアドレスでアカウントを作成する
3. ログイン後、https://platform.stability.ai/account/keys に移動する
4. 「Create API Key」をクリックする
5. 生成されたAPIキーをコピーする

- https://platform.stability.ai/account/keys

### 2.2 OpenAI

1. https://platform.openai.com/ にアクセスする
2. メールアドレスまたは Google / Microsoft アカウントでサインアップする
3. ログイン後、https://platform.openai.com/api-keys に移動する
4. 「Create new secret key」をクリックし、キーに名前を付ける
5. 生成されたキーをコピーする（画面を閉じると二度と表示されないため、必ずこの時点でコピーする）

- https://platform.openai.com/api-keys

### 2.3 Kling AI

Kling AI は **Access Key (AK)** と **Secret Key (SK)** の2つを使用した JWT 認証方式を採用している。

1. https://klingai.com/global/dev にアクセスする
2. アカウントを作成・ログインする
3. https://app.klingai.com/global/dev/api-key に移動する
4. 「Create API Key」をクリックする
5. **Access Key** と **Secret Key** の両方をコピーする

- https://app.klingai.com/global/dev/api-key

### 2.4 Luma Dream Machine

1. https://lumalabs.ai/dream-machine にアクセスする
2. アカウントを作成・ログインする
3. https://lumalabs.ai/dream-machine/api/keys に移動する
4. APIキーを作成しコピーする

- https://lumalabs.ai/api/keys

### 2.5 Runway

1. https://dev.runwayml.com/ にアクセスする
2. アカウントを作成・ログインする
3. API Keysページに移動する
4. APIキーを作成しコピーする

- https://dev.runwayml.com/organization/b0dc8ac0-feb7-42e9-b86d-c043546e4362/api-keys

### 2.6 YouTube Data API

1. https://console.cloud.google.com/ にアクセスする
2. プロジェクトを選択（または新規作成）する
3. 左メニューの「APIとサービス」→「ライブラリ」に移動する
4. 「YouTube Data API v3」を検索し、「有効にする」をクリックする
5. 「APIとサービス」→「認証情報」に移動する
6. 「認証情報を作成」→「APIキー」をクリックする
7. 生成されたAPIキーをコピーする
8. （推奨）APIキーの制限で「YouTube Data API v3」のみに制限する

- https://console.cloud.google.com/apis/library/youtube.googleapis.com

### 2.7 Google AI (Gemini)

1. https://aistudio.google.com/ にアクセスする
2. Google アカウントでサインインする
3. 左サイドバーの「Get API key」をクリックする
4. 「Create API key」をクリックする
5. 生成されたAPIキーをコピーする

- https://aistudio.google.com/api-keys?project=gen-lang-client-0563635194

## 3. 環境変数の設定

プロジェクトルートの `.env.example` をコピーして `.env` ファイルを作成し、取得したAPIキーを記入する。

```bash
cp .env.example .env
```

```dotenv
DAILY_ROUTINE_API_KEY_YOUTUBE_DATA_API=your-youtube-data-api-key
DAILY_ROUTINE_API_KEY_STABILITY=your-stability-key
DAILY_ROUTINE_API_KEY_OPENAI=your-openai-key
DAILY_ROUTINE_API_KEY_GOOGLE_AI=your-google-ai-key
DAILY_ROUTINE_API_KEY_KLING_AK=your-kling-access-key
DAILY_ROUTINE_API_KEY_KLING_SK=your-kling-secret-key
DAILY_ROUTINE_API_KEY_LUMA=your-luma-key
DAILY_ROUTINE_API_KEY_RUNWAY=your-runway-key
```

`.env` ファイルは `.gitignore` に登録されているため、リポジトリにコミットされない。

> **注:** `export` で設定した環境変数は `.env` より優先される。CI 等で `export` を使う場合はそちらが採用される。
