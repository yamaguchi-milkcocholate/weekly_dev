import os

import pandas as pd


def convert_to_utf8(file_path):
    try:
        # 'shift_jis' ではなく 'cp932' を使うことで特殊文字に対応
        df = pd.read_csv(file_path, encoding="cp932")

        # 保存先ファイル名の設定
        base, ext = os.path.splitext(file_path)
        new_file = f"{base}_utf8{ext}"

        # Excelでも文字化けしないように 'utf-8-sig' で保存
        df.to_csv(new_file, encoding="utf-8-sig", index=False)
        print(f"✅ 変換成功: {new_file}")

    except UnicodeDecodeError as e:
        print(f"❌ 文字コードエラー: cp932でも読み込めませんでした。 {e}")
    except FileNotFoundError:
        print("❌ エラー: ファイルが見つかりません。")
    except Exception as e:
        print(f"❌ 予期せぬエラーが発生しました: {e}")


# 実行
convert_to_utf8("data/Tokyo_20053_20253.csv")
