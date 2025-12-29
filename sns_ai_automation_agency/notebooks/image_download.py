import os
import tempfile
from io import BytesIO
from pathlib import Path

import gspread
import pandas as pd
import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as SACredentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from PIL import Image

load_dotenv()
root_dir = Path(__file__).resolve().parent.parent
cache_dir = root_dir / ".cache" / "tts_test"
cache_dir.mkdir(exist_ok=True, parents=True)


API_KEY = os.getenv("ELEVENLABS_API_KEY")
VOICE_ID = "fUjY9K2nAIwlALOwSiwc"
MODEL_ID = "eleven_v3"
OUTPUT_FORMAT = "mp3_44100_128"
LANGUAGE = "ja"
SHEET_KEY = "1bzROAf4BHIdq551QpWbRL1xRnB2hFqJGQ9Mu9Vj0w-c"
FOLDER_ID = "1zt6nOAhAX_9fvSracT0yvqab_rzsWgLq"
TIMEOUT_SEC = 15


def read_sheet() -> pd.DataFrame:
    sa_filepath = root_dir / "sa-key.json"

    # 認証情報の設定
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

    # サービスアカウントキーのパスを指定
    creds = SACredentials.from_service_account_file(sa_filepath, scopes=scopes)

    # gspreadクライアントの初期化
    client = gspread.authorize(creds)

    # スプレッドシートを開く(URLまたはキーで指定)
    spreadsheet = client.open_by_key(SHEET_KEY)

    # 特定のワークシートを取得
    worksheet = spreadsheet.worksheet("selections")

    # 全データを取得してDataFrameに変換
    df = pd.DataFrame(worksheet.get_all_records())

    return df


class GoogleDriveClient:
    def __init__(self):
        sa_filepath = root_dir / "oauth.json"
        token_filepath = root_dir / "token.json"

        # 認証情報の設定
        scopes = ["https://www.googleapis.com/auth/drive"]

        creds: Credentials | None = None
        if token_filepath.exists():
            creds = Credentials.from_authorized_user_file(str(token_filepath), scopes=scopes)

        # 2. トークンがない / 無効なら更新 or 新規認証
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                # 期限切れ → 自動でリフレッシュ（ブラウザ不要）
                creds.refresh(Request())
            else:
                # 初回だけブラウザ認証（ここでリンクが出る）
                flow = InstalledAppFlow.from_client_secrets_file(str(sa_filepath), scopes=scopes)
                creds = flow.run_local_server(port=0)

            # 取得・更新したトークンを保存（次回以降はこれを使う）
            token_filepath.write_text(creds.to_json(), encoding="utf-8")

        # Google Drive APIクライアントの初期化
        self.service = build("drive", "v3", credentials=creds)

    def create_folder(self, folder_name: str, parent_folder_id: str | None = None) -> str:
        """
        Google Driveにフォルダを作成する（既に存在する場合はそのIDを返す）

        Args:
            folder_name: 作成するフォルダ名
            parent_folder_id: 親フォルダのID（Noneの場合はルートに作成）

        Returns:
            作成したフォルダのID（または既存フォルダのID）
        """
        # 同名のフォルダが既に存在するか確認
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        if parent_folder_id:
            query += f" and '{parent_folder_id}' in parents"

        results = self.service.files().list(q=query, spaces="drive", fields="files(id, name)").execute()
        items = results.get("files", [])

        if items:
            folder_id = items[0]["id"]
            print(f"既存フォルダを使用します: {folder_name} (ID: {folder_id})")
            return folder_id

        # 存在しない場合は新規作成
        file_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}

        if parent_folder_id:
            file_metadata["parents"] = [parent_folder_id]

        folder = self.service.files().create(body=file_metadata, fields="id").execute()

        print(f"フォルダを作成しました: {folder_name} (ID: {folder.get('id')})")
        return folder.get("id")

    def upload_file(self, file_path: Path | str, folder_id: str | None = None, filename: str | None = None) -> str:
        """
        Google Driveにファイルをアップロードする

        Args:
            file_path: アップロードするファイルのパス
            folder_id: アップロード先のフォルダID（Noneの場合はルートにアップロード）
            filename: Google Drive上でのファイル名（Noneの場合は元のファイル名を使用）

        Returns:
            アップロードしたファイルのID
        """
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

        file_metadata = {"name": filename or file_path.name}

        if folder_id:
            file_metadata["parents"] = [folder_id]

        media = MediaFileUpload(str(file_path), resumable=True)

        file = self.service.files().create(body=file_metadata, media_body=media, fields="id").execute()

        print(f"ファイルをアップロードしました: {file_metadata['name']} (ID: {file.get('id')})")
        return file.get("id")


def download_image_to_png(url: str, out_path: Path) -> None:
    """
    画像URLから取得して PNG 形式で保存する。
    元が jpg / webp でも PNG に統一する。
    """
    try:
        resp = requests.get(url, timeout=TIMEOUT_SEC)
        resp.raise_for_status()
    except Exception as e:
        print(f"  ❌ ダウンロード失敗: {url} | error={e}")
        return

    try:
        img = Image.open(BytesIO(resp.content))
    except Exception as e:
        print(f"  ❌ 画像として開けませんでした: {url} | error={e}")
        return

    # RGBA なども含めて PNG 保存しやすいように変換
    if img.mode in ("P", "RGBA"):
        img = img.convert("RGBA")
    else:
        img = img.convert("RGB")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    print(f"  ✅ 保存: {out_path}")


if __name__ == "__main__":
    df = read_sheet()

    drive_client = GoogleDriveClient()
    task_folder_id = drive_client.create_folder(folder_name="test", parent_folder_id=FOLDER_ID)
    images_folder_id = drive_client.create_folder(folder_name="images", parent_folder_id=task_folder_id)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        for i, row in df.iterrows():
            tmp_file_path = tmp_path / f"scene_{i + 1:02d}.png"
            image_url = row["imageUrl"]

            download_image_to_png(url=image_url, out_path=tmp_file_path)
            drive_client.upload_file(file_path=tmp_file_path, folder_id=images_folder_id, filename=tmp_file_path.name)
