import asyncio
import json
from typing import Optional

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

import sns_ai_automation_agency.agent.thumbnail.general.prompt as prompt
import sns_ai_automation_agency.agent.thumbnail.general.schema as schema
import sns_ai_automation_agency.agent.thumbnail.search as search
import sns_ai_automation_agency.utils as utils


async def run_thumbnail_agent_async(scene_data: dict, station_name: str, count: int, max_concurrent: int = 5) -> dict:
    """
    サムネイル画像検索クエリを非同期生成

    Args:
        scene_data: シーンデータ
        station_name: 駅名
        count: 画像検索で取得する画像数
        max_concurrent: 最大同時実行数（デフォルト: 5）

    Returns:
        検索クエリ結果のリスト
    """
    load_dotenv()

    scenes = scene_data["scenes"]
    for i in range(len(scenes)):
        scenes[i]["process_index"] = i

    system_prompt = prompt.get_system_prompt()
    semaphore = asyncio.Semaphore(max_concurrent)

    async def process_scene(scene) -> dict:
        async with semaphore:
            title = scene["title"]
            content = scene["content"]
            telop = scene["telop"]
            user_prompt = prompt.get_user_prompt(station_name=station_name, title=title, content=content, telop=telop)

            llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
            llm = llm.with_structured_output(schema.SearchQueryResponse)
            thumbnail_prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", user_prompt)])

            # 構造化LLMチェーンを非同期実行
            chain = thumbnail_prompt | llm
            result: schema.SearchQueryResponse = await chain.ainvoke({})

            images = await search.search_google_images_async(query=result.query, count=count)

            return {"process_index": scene["process_index"], "query": result.query, "images": images}

    # 全シーンを並列処理（最大同時実行数制限付き）
    tasks = [process_scene(scene) for scene in scene_data["scenes"]]
    results = await asyncio.gather(*tasks)

    sorted_results = sorted(results, key=lambda x: x["process_index"])

    return sorted_results


def run_thumbnail_agent(
    scene_data: dict, count: int, station_name: str, max_concurrent: int = 5, thread_id: Optional[str] = None
) -> dict:
    """
    同期インターフェース（後方互換性のため）

    Args:
        scene_data: シーンデータ
        count: 画像検索で取得する画像数
        station_name: 駅名
        max_concurrent: 最大同時実行数（デフォルト: 5）
        thread_id: スレッドID（キャッシュ用、デフォルト: None）

    Returns:
        検索クエリ結果のリスト
    """
    if thread_id:
        cache = utils.CachePathManager(app_name=thread_id)
        cache_file = cache.file(f"thumbnail_{station_name}.json")

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
    else:
        cache, cache_file = None, None

    result = asyncio.run(
        run_thumbnail_agent_async(
            scene_data=scene_data, station_name=station_name, count=count, max_concurrent=max_concurrent
        )
    )

    result_dict = utils.to_serializable(result)

    if cache:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=4)

    return result_dict
