# Python 3.12 slim ベースイメージを使用
FROM python:3.12-slim

# 非rootユーザーを作成
RUN useradd --create-home --shell /bin/bash app

# 作業ディレクトリを設定
WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# uvをインストール（高速なPythonパッケージマネージャー）
RUN pip install uv

# pyproject.tomlとuv.lockをコピー
COPY pyproject.toml uv.lock ./

# 依存関係をインストール（本番環境用）
RUN uv sync --frozen --no-dev

# アプリケーションコードをコピー
COPY src/ ./src/

RUN uv pip install .

# アプリケーションファイルの所有者を変更
RUN chown -R app:app /app

# 非rootユーザーに切り替え
USER app

# ポートを公開（Cloud Runが動的に設定する）
EXPOSE 8000

# 環境変数を設定
ENV PYTHONPATH=/app
ENV PYTHONUNBUFFERED=1
ENV UVICORN_HOST=0.0.0.0
ENV UVICORN_PORT=8000

# アプリケーションを起動（uvの仮想環境を使用）
CMD ["uv", "run", "python", "-m", "uvicorn", "src.daily_trade.app:app", "--host", "0.0.0.0", "--port", "8000"]
