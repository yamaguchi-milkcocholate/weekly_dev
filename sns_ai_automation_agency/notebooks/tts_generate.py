import os
from pathlib import Path

import gspread
import pandas as pd
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import save
from google.oauth2.service_account import Credentials

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

elevenlabs = ElevenLabs(api_key=API_KEY)


def generate_tts(text: str, filename: str) -> None:
    audio = elevenlabs.text_to_speech.convert(
        text=text,
        voice_id=VOICE_ID,
        model_id=MODEL_ID,
        output_format=OUTPUT_FORMAT,
        language_code=LANGUAGE,
    )

    save(audio, cache_dir / filename)


def read_sheet() -> pd.DataFrame:
    sa_filepath = root_dir / "sa-key.json"

    # 認証情報の設定
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

    # サービスアカウントキーのパスを指定
    creds = Credentials.from_service_account_file(sa_filepath, scopes=scopes)

    # gspreadクライアントの初期化
    client = gspread.authorize(creds)

    # スプレッドシートを開く(URLまたはキーで指定)
    spreadsheet = client.open_by_key(SHEET_KEY)

    # 特定のワークシートを取得
    worksheet = spreadsheet.worksheet("scenes")

    # 全データを取得してDataFrameに変換
    df = pd.DataFrame(worksheet.get_all_records())

    df["target_sec"] = df["end_sec"] - df["start_sec"]

    return df


if __name__ == "__main__":
    df = read_sheet()

    records = []
    print("=" * 50)
    for i, row in df.iterrows():
        print(f"タイトル: {row['title']}")
        print(f"テキスト: {row['content']}")
        print("=" * 50)

        record = row.copy()

        filename = f"scene_{i + 1:02d}.mp3"
        record["tts_filename"] = filename

        generate_tts(text=row["content"], filename=filename)

        records.append(record)

    df_result = pd.DataFrame(records)
    df_result.to_csv(cache_dir / "scenes.tsv", sep="\t")
