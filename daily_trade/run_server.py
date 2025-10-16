#!/usr/bin/env python3
"""
FastAPIサーバー起動スクリプト

使用方法:
    python run_server.py

開発環境での使用を想定しています。
"""

import uvicorn

from src.daily_trade.app import app

if __name__ == "__main__":
    print("🚀 Daily Trade API を起動しています...")
    print("📝 API Documentation: http://localhost:8000/docs")
    print("📚 ReDoc: http://localhost:8000/redoc")
    print("🏥 Health Check: http://localhost:8000/health")
    print("🌐 Root: http://localhost:8000/")
    print()
    print("サーバーを停止するには Ctrl+C を押してください")

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True,  # 開発モードでファイル変更を監視
        log_level="info",
    )
