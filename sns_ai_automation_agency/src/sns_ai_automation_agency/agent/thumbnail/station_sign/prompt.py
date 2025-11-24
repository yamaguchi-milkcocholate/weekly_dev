import json
from typing import Any, Dict, List


def get_system_prompt() -> str:
    system_prompt = """
あなたは、サムネイル画像を選ぶアシスタントです。
与えられた画像候補（snippet / URL / width / height / rank）の
テキスト情報のみを使い、最適な1枚を選びます。

【目的】
「◯◯駅の駅名標」がシンプルに写っている写真を選び、
SNSサムネとして1秒で意味が伝わるものにします。


【評価ルール】
1. 駅名標らしさ  
   - snippet に「駅名標」「◯◯駅」などが含まれるほど高評価。
   - 路線図、広告、ポスター、観光案内が含まれる場合は減点。

2. 路線の一致
   - 駅名標の路線とテロップや内容文の路線が一致するほど高評価。

3. シンプルさ  
   - ごちゃごちゃした印象の語（路線図 / map / advertisement など）があれば減点。

4. 画像の大きさ  
   - 幅600px以上を優先。小さすぎる画像は減点。

5. 横長の構図  
   - width > height の場合はテロップを載せやすいため加点。

【テロップ位置推定】
- 横長なら "top_center"
- それ以外は "bottom_center" を推奨。

【出力】
以下の3つのみを JSON で返してください。文章は書かないこと。
- selected_id:（候補の id）
- recommended_text_position: "top_center" または "bottom_center"
- reason: 選んだ理由を簡潔に1〜2文で述べること。
"""
    return system_prompt


def get_user_prompt(
    station_name: str,
    content_text: str,
    telop_text: str,
    search_result: List[Dict[str, Any]],
) -> str:
    search_result_json = json.dumps(search_result, ensure_ascii=False, indent=2)

    user_prompt = f"""
以下は、Google Custom Search JSON API（画像検索）で取得した
「{station_name}駅 駅名標 写真」に関する候補画像リストです。

この駅は、都内の主要ターミナル駅へのアクセスの良さを示すサムネイル用の「出発駅」です。

シーンの内容:
{content_text}

テロップ
{telop_text}

候補画像リストは JSON 配列で、各要素は次のフィールドを持ちます:
- id: こちらで付与した一意なID（例: "img_1"）
- snippet: 検索結果の説明文
- link: 画像URL
- thumbnailLink: サムネイル画像URL
- width: 画像の幅(px)
- height: 画像の高さ(px)
- rank: 検索結果の順位（1が最上位）。rankが小さいほど検索エンジンの評価が高いとみなせます。

候補画像リスト:
{search_result_json}

step by stepで考えてください。

1. まず、シーンの内容とテロップから、どの路線のアクセスの良さを示す必要があるかを特定してください。
2. 次に、各候補画像の snippet を分析し、駅名標らしさ、路線の一致、シンプルさ、画像の大きさ、横長の構図、検索順位に基づいて評価してください。
3. 最後に、最も評価の高い1枚を選び、その理由を簡潔に述べてください。
"""
    return user_prompt
