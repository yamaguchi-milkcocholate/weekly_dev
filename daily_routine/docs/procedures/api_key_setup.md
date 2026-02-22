# APIキー取得・設定手順

## 1. 概要

本プロジェクトで使用する外部APIキーの取得方法と設定方法をまとめる。

| 環境変数                          | サービス           | 用途                 |
| --------------------------------- | ------------------ | -------------------- |
| `DAILY_ROUTINE_API_KEY_STABILITY` | Stability AI       | 画像生成             |
| `DAILY_ROUTINE_API_KEY_OPENAI`    | OpenAI             | 画像生成（DALL-E 3） |
| `DAILY_ROUTINE_API_KEY_GOOGLE_AI` | Google AI (Gemini) | 画像生成・評価       |

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

### 2.3 Google AI (Gemini)

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
DAILY_ROUTINE_API_KEY_STABILITY=your-stability-key
DAILY_ROUTINE_API_KEY_OPENAI=your-openai-key
DAILY_ROUTINE_API_KEY_GOOGLE_AI=your-google-ai-key
```

`.env` ファイルは `.gitignore` に登録されているため、リポジトリにコミットされない。

> **注:** `export` で設定した環境変数は `.env` より優先される。CI 等で `export` を使う場合はそちらが採用される。
