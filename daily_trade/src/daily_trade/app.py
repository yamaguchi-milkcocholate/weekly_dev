from datetime import datetime

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import HTMLResponse

from daily_trade.schema import ExampleResponse

# FastAPIアプリケーション初期化
app = FastAPI(
    title="Daily Trade API",
    description="ユーザー管理のためのRESTful API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


# ルートエンドポイント
@app.get("/", response_class=HTMLResponse)
async def root():
    """ルートページ - APIの概要を表示"""
    return """
    <html>
        <head>
            <title>Daily Trade API</title>
        </head>
        <body>
            <h1>Daily Trade API</h1>
            <ul>
                <li><a href="/docs">API Documentation (Swagger UI)</a></li>
                <li><a href="/redoc">API Documentation (ReDoc)</a></li>
                <li><a href="/health">Health Check</a></li>
            </ul>
        </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """ヘルスチェックエンドポイント"""
    try:
        return {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "database": "connected",
            "version": "1.0.0",
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"connection failed: {str(e)}",
        )


@app.get("/example", response_model=ExampleResponse)
async def example() -> ExampleResponse:
    try:
        return ExampleResponse(message="ok")

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to example: {str(e)}",
        )


# アプリケーションの起動設定
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
