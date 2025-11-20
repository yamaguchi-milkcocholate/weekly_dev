# 必要なライブラリのインポート
import json
from typing import Optional

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

import sns_ai_automation_agency.agent.access.prompt as prompt
import sns_ai_automation_agency.agent.access.schema as schema
import sns_ai_automation_agency.utils as utils


def survey_access_information(station_name: str, num_highlight_stations: int, thread_id: Optional[str] = None) -> dict:
    load_dotenv()

    if thread_id:
        cache = utils.CachePathManager(app_name=thread_id)
        cache_file = cache.file(f"access_survey_{station_name}.json")

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
    else:
        cache, cache_file = None, None

    # プロンプト生成
    access_prompt = prompt.generate_access_survey_prompt(
        station_name=station_name,
        num_highlight_stations=num_highlight_stations,
    )

    llm = ChatOpenAI(model="gpt-5-search-api", temperature=0.0)
    llm = llm.with_structured_output(schema.ResponseSchema)
    result = llm.invoke([("user", access_prompt)])
    result_dict = utils.to_serializable(result)

    if cache:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=4)

    return result_dict
