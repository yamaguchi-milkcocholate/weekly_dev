import os
from pathlib import Path

from google.cloud import firestore

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(Path(__file__).resolve().parent.parent / "sa-key.json")


def read_data():
    # Firestore クライアント生成
    db = firestore.Client(project="weekly-dev-20251013", database="daily-trade-db")

    doc = db.collection("users").document("user_001").get()

    if doc.exists:
        print("📄 ドキュメント内容:")
        print(doc.to_dict())
    else:
        print("⚠️ ドキュメントが存在しません。")


def write_data():
    # Firestore クライアント生成
    db = firestore.Client(project="weekly-dev-20251013", database="daily-trade-db")

    # users コレクションに新しいドキュメントを作成
    doc_ref = db.collection("users").document("user_001")

    # データを書き込み（存在しない場合は新規作成、ある場合は上書き）
    doc_ref.set(
        {
            "name": "Teppei Yamaguchi",
            "email": "teppei@example.com",
            "active": True,
            "created_at": firestore.SERVER_TIMESTAMP,
        }
    )

    print("✅ データを書き込みました。")


def main():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["read", "write"], help="Mode: read or write")
    args = parser.parse_args()

    if args.mode == "read":
        read_data()
    elif args.mode == "write":
        write_data()


if __name__ == "__main__":
    main()
