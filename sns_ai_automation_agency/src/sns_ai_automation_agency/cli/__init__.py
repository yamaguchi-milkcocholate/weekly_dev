import argparse
import json
from datetime import datetime
from pathlib import Path

from sns_ai_automation_agency.agent.master.engine import run_master_agent


def main():
    """SNS AI Automation Agency のCLIエントリーポイント"""
    parser = argparse.ArgumentParser(
        description="駅周辺の情報を調査し、SNS動画用のデータを生成します",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 基本的な使用方法
  sns-agent survey --station 渋谷

  # パラメータを指定
  sns-agent survey --station 新宿 --highlight-stations 3 --iterations 2 --total_seconds 15

  # 結果をファイルに保存
  sns-agent survey --station 池袋 --output result.json

  # スレッドIDを指定（同じIDで実行すると前回の続きから処理）
  sns-agent survey --station 横浜 --thread-id my-survey-001
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="実行するコマンド")

    # survey コマンド
    survey_parser = subparsers.add_parser(
        "survey",
        help="駅周辺の情報を調査",
        description="指定された駅のアクセス情報と飲食店情報を調査します",
    )
    survey_parser.add_argument(
        "--station",
        "-s",
        required=True,
        type=str,
        help="調査対象の駅名（例: 渋谷、新宿）",
    )
    survey_parser.add_argument(
        "--highlight-stations",
        "-hs",
        type=int,
        default=3,
        help="強調表示する主要駅の数（デフォルト: 3）",
    )
    survey_parser.add_argument(
        "--iterations",
        "-i",
        type=int,
        default=2,
        help="飲食店調査の最大反復回数（デフォルト: 2）",
    )
    survey_parser.add_argument(
        "--total-seconds",
        "-ts",
        type=int,
        default=15,
        help="動画全体の秒数（デフォルト: 15）",
    )
    survey_parser.add_argument(
        "--image-count",
        "-ic",
        type=int,
        default=10,
        help="画像検索で取得する画像数（デフォルト: 10）",
    )
    survey_parser.add_argument(
        "--thread-id",
        "-t",
        type=str,
        default=None,
        help="スレッドID（指定すると前回の続きから処理可能）",
    )
    survey_parser.add_argument(
        "--max-concurrent",
        "-mc",
        type=int,
        default=5,
        help="最大同時実行数（デフォルト: 5）",
    )
    survey_parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="結果を保存するJSONファイルのパス（指定しない場合は標準出力）",
    )
    survey_parser.add_argument(
        "--pretty",
        "-p",
        action="store_true",
        help="JSONを整形して出力",
    )

    args = parser.parse_args()

    if args.command == "survey":
        run_survey(args)
    else:
        parser.print_help()


def run_survey(args):
    """survey コマンドの実行"""
    print("🚀 駅周辺情報調査を開始します")
    print(f"📍 対象駅: {args.station}")
    print(f"🔢 強調駅数: {args.highlight_stations}")
    print(f"🔄 調査反復数: {args.iterations}")
    print(f"⏱️ 動画全体秒数: {args.total_seconds}")
    print(f"🖼️ 画像取得数: {args.image_count}")
    if args.max_concurrent:
        print(f"⚙️ 最大同時実行数: {args.max_concurrent}")
    if args.thread_id:
        print(f"🆔 スレッドID: {args.thread_id}")
    print("=" * 60)

    try:
        # マスターエージェント実行
        result = run_master_agent(
            station_name=args.station,
            num_highlight_stations=args.highlight_stations,
            num_iterations=args.iterations,
            total_seconds=args.total_seconds,
            image_count=args.image_count,
            thread_id=args.thread_id,
            max_concurrent=args.max_concurrent,
        )

        # メタデータを追加
        output_data = {
            "metadata": {
                "station_name": args.station,
                "timestamp": datetime.now().isoformat(),
                "parameters": {
                    "highlight_stations": args.highlight_stations,
                    "iterations": args.iterations,
                    "thread_id": args.thread_id,
                },
            },
            "data": result,
        }

        # 結果の出力
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2 if args.pretty else None)

            print("\n" + "=" * 60)
            print(f"✅ 調査完了！結果を保存しました: {output_path}")
        else:
            # 標準出力
            print("\n" + "=" * 60)
            print("✅ 調査完了！")
            print("\n📊 調査結果:")
            print(json.dumps(output_data, ensure_ascii=False, indent=2 if args.pretty else None))

    except Exception as e:
        print(f"\n❌ エラーが発生しました: {e}")
        import traceback

        traceback.print_exc()
        exit(1)


if __name__ == "__main__":
    main()
